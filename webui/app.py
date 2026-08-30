#!/usr/bin/python3
"""Brushograph WebUI — machine config in, brush G-code out."""
from __future__ import annotations

import json
import re
import secrets
import shutil
import tempfile
import threading
import traceback
from pathlib import Path

from flask import (Flask, abort, jsonify, render_template, request, send_file,
                   session)

import gcode_pipeline
from configspec import apply_form, build_schema, tray_entries
from sketch import render as render_sketch

WEBUI_DIR = Path(__file__).resolve().parent
REPO_ROOT = WEBUI_DIR.parent
SESSIONS_DIR = REPO_ROOT / "webui_sessions"
MAX_UPLOAD_MB = 64

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.secret_key = secrets.token_hex(16)
SESSIONS_DIR.mkdir(exist_ok=True)

# copicograf keeps state on the instance and the pipeline shells out through a
# shared working directory, so one generation at a time.
GENERATE_LOCK = threading.Lock()

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


# ------------------------------------------------------------------- sessions

def session_id() -> str:
    sid = session.get("sid")
    if not sid:
        sid = secrets.token_hex(4)
        session["sid"] = sid
    return sid


def session_dir(sid: str) -> Path:
    if not SAFE_NAME.match(sid):
        abort(400)
    d = SESSIONS_DIR / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def preset_paths() -> list[Path]:
    return sorted(REPO_ROOT.glob("*.conf"))


def load_config(name: str, mode: str, sid: str) -> dict:
    """Presets live in the repo root; uploads live in the caller's session."""
    if not name or not SAFE_NAME.match(name) or not name.endswith(".conf"):
        raise ValueError("bad config name")
    path = session_dir(sid) / name if mode == "uploaded" else REPO_ROOT / name
    if not path.is_file():
        raise ValueError(f"config not found: {name}")
    with path.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------- pages

@app.get("/")
def index():
    return render_template(
        "index.html", session_id=session_id(),
        presets=[p.name for p in preset_paths()],
    )


@app.get("/about")
def about():
    return render_template("about.html", preflight=gcode_pipeline.preflight())


# ------------------------------------------------------------- machine config

@app.get("/machine_config/get")
def machine_config_get():
    name = request.args.get("name", "")
    mode = request.args.get("mode", "preset")
    try:
        if not SAFE_NAME.match(name) or not name.endswith(".conf"):
            raise ValueError("bad config name")
        path = session_dir(session_id()) / name if mode == "uploaded" else REPO_ROOT / name
        if not path.is_file():
            raise ValueError("config not found")
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return send_file(path, as_attachment=True, download_name=name, mimetype="application/json")


@app.post("/machine_config/upload")
def machine_config_upload():
    f = request.files.get("config_file")
    if not f or not f.filename:
        return jsonify(error="No file supplied"), 400
    name = Path(f.filename).name
    if not name.endswith(".conf"):
        return jsonify(error="Machine configs must be named *.conf"), 400
    if not SAFE_NAME.match(name):
        return jsonify(error="Config name may only contain letters, digits, dot, dash, underscore"), 400
    raw = f.read()
    try:
        conf = json.loads(raw)
    except json.JSONDecodeError as exc:
        return jsonify(error=f"Not valid JSON: {exc}"), 400
    if not isinstance(conf, dict) or "brushograph" not in conf:
        return jsonify(error="That JSON has no 'brushograph' section — not a machine config"), 400
    (session_dir(session_id()) / name).write_bytes(raw)
    return jsonify(name=name)


# ----------------------------------------------------------------- the form

@app.get("/options_form")
def options_form():
    name = request.args.get("machine_config_name", "")
    mode = request.args.get("machine_config_mode", "preset")
    try:
        conf = load_config(name, mode, session_id())
    except (ValueError, json.JSONDecodeError) as exc:
        return f'<p class="error">Could not load that config: {exc}</p>', 400
    return render_template(
        "options_form.html",
        schema=build_schema(conf),
        session_id=session_id(),
        machine_config_name=name,
        machine_config_mode=mode,
        generator=conf.get("brushograph", {}).get("generator", "copicograf"),
    )


@app.post("/options_form")
def options_form_post():
    """One endpoint, three jobs — the sketch, the edited config, the G-code."""
    sid = session_id()
    name = request.form.get("machine_config_name", "")
    mode = request.form.get("machine_config_mode", "preset")
    try:
        base = load_config(name, mode, sid)
    except (ValueError, json.JSONDecodeError) as exc:
        return jsonify(error=str(exc)), 400

    conf, problems = apply_form(base, request.form)
    if problems:
        return jsonify(error="; ".join(problems[:4])), 400

    if request.form.get("sketch_only") == "true":
        return app.response_class(render_sketch(conf), mimetype="image/png")

    stem = Path(name).stem
    if request.form.get("config_only") == "true":
        buf = json.dumps(conf, indent=4).encode()
        return app.response_class(
            buf, mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{stem}.conf"'},
        )

    images = {e["tray"]: request.files.get(f"trays-{e['tray']}-image")
              for e in tray_entries(conf) if e["image"]}
    images = {k: v for k, v in images.items() if v and v.filename}
    if not images:
        return jsonify(error="No images selected"), 400

    with GENERATE_LOCK:
        work = Path(tempfile.mkdtemp(prefix="brushograph_", dir=session_dir(sid)))
        try:
            saved = {}
            for tray, storage in images.items():
                p = work / f"upload_{tray}{Path(storage.filename).suffix or '.png'}"
                storage.save(p)
                saved[tray] = p
            log_lines: list[str] = []
            out = work / f"{stem}.gcode"
            gcode_pipeline.generate(conf, saved, work, out, log_lines.append)
            data = out.read_bytes()
        except gcode_pipeline.PipelineError as exc:
            app.logger.warning("pipeline failed: %s", exc)
            return jsonify(error=str(exc)), 400
        except Exception as exc:  # noqa: BLE001 - report, do not 500 silently
            app.logger.error("pipeline crashed:\n%s", traceback.format_exc())
            return jsonify(error=f"{type(exc).__name__}: {exc}"), 500
        finally:
            shutil.rmtree(work, ignore_errors=True)

    return app.response_class(
        data, mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{stem}.gcode"'},
    )


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Brushograph WebUI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default=8080, type=int)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    pre = gcode_pipeline.preflight()
    print(f"Brushograph WebUI on http://{args.host}:{args.port}")
    for tool, path in pre["tools"].items():
        print(f"  {tool:9} {path or 'NOT FOUND'}")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
