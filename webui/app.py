#!/usr/bin/python3
"""Brushograph WebUI — machine config in, brush G-code out."""
from __future__ import annotations

import io
import json
import re
import secrets
from datetime import datetime
import socket
import urllib.error
import urllib.parse
import urllib.request
import shutil
import tempfile
import threading
import traceback
from pathlib import Path

from flask import (Flask, abort, jsonify, render_template, request, send_file,
                   session, url_for)
import numpy as np
from PIL import Image

import facefilter
import gcode_pipeline
import subject
import woodcut
from configspec import apply_form, build_schema, tray_entries
from sketch import PALETTES, render as render_sketch

WEBUI_DIR = Path(__file__).resolve().parent
REPO_ROOT = WEBUI_DIR.parent
SESSIONS_DIR = REPO_ROOT / "webui_sessions"
MAX_UPLOAD_MB = 64

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
SESSIONS_DIR.mkdir(exist_ok=True)


def _secret_key() -> bytes:
    """A key that survives a restart, so sessions do too.

    A fresh key per process invalidates every cookie the moment the service is
    restarted, which hands every open page a new session id. Uploaded configs
    live under the old one, so the page then asks for a file the server can no
    longer find — the config is still on disk, just addressed by a session that
    no longer exists. Keeping the key on disk keeps the session, and with it
    everything already uploaded.
    """
    path = SESSIONS_DIR / ".secret_key"
    if path.exists():
        return path.read_bytes()
    key = secrets.token_bytes(32)
    path.write_bytes(key)
    path.chmod(0o600)
    return key


app.secret_key = _secret_key()

# copicograf keeps state on the instance and the pipeline shells out through a
# shared working directory, so one generation at a time.
GENERATE_LOCK = threading.Lock()

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

# Never let a browser run yesterday's JavaScript. Editing a script and reloading
# is not enough on its own: the page keeps the copy it already parsed, and a
# stale copy is indistinguishable from a bug in the new one.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.context_processor
def _asset_helper():
    def asset(filename: str) -> str:
        """A static URL stamped with the file's modification time."""
        path = Path(app.static_folder) / filename
        stamp = int(path.stat().st_mtime) if path.exists() else 0
        return url_for("static", filename=filename, v=stamp)
    return {"asset": asset}


@app.after_request
def _no_store(response):
    # Everything this app serves is either generated per request or a small
    # local file; none of it is worth caching, and all of it is worth being
    # current.
    response.headers.setdefault("Cache-Control", "no-store, must-revalidate")
    return response


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
        if mode == "uploaded":
            raise ValueError(
                f"{name} is no longer on the server. Uploaded configs are kept with your "
                "session and this one has expired — upload the file again, or pick a preset.")
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


def _num(form, name, default):
    try:
        return float(form.get(name, default))
    except (TypeError, ValueError):
        return default


def _flag(form, name, default="true"):
    """Read a checkbox, taking the last value posted under the name.

    A checkbox that is not ticked posts nothing, so each one is paired with a
    hidden field carrying "false" and the box itself carries "true". Both arrive
    when it is ticked, in that order — so the *first* value is always "false"
    and `form.get()`, which returns the first, reports every box as off however
    it was set. `apply_form` already reads these correctly; this did not.
    """
    values = form.getlist(name) if hasattr(form, "getlist") else []
    raw = values[-1] if values else default
    return str(raw).lower() in {"1", "true", "on", "yes"}


def _woodcut_params(form) -> dict:
    return {
        "detail": _num(form, "woodcut_detail", 78.0),
        "threshold": _num(form, "woodcut_threshold", 8.0),
        "roughness": _num(form, "woodcut_roughness", 40.0),
        "hatching": _num(form, "woodcut_hatching", 70.0),
        "outlines": _flag(form, "woodcut_outlines"),
    }


def _gcode_name(images: dict, entries: list, conf: dict, infill: bool) -> str:
    """Name the file after the picture and the colours that painted it.

    `vali_letten_c1_infill.gcode`: the source image, then the tray numbers the
    form showed for each colour used, then whether the shapes were filled. The
    numbers are the ones on screen, so a file can be matched to the run that
    made it without opening it.
    """
    used = [e for e in entries if e["tray"] in images]
    first = images[used[0]["tray"]].filename if used else ""
    stem = "".join(c for c in Path(first).stem if c.isalnum() or c in "-_") or "brushograph"
    colours = "".join(f"_c{e['index']}" for e in used)
    return f"{stem}{colours}{'_infill' if infill else ''}.gcode"


def _scale_params(form) -> dict:
    """How wide the picture will be painted, and how wide a stroke.

    Passed as millimetres rather than pixels: the conversion picks its own
    working resolution from the Detail control, so only it can turn these into
    a pixel size that is still correct afterwards.
    """
    # A line distance of 0 means "no infill", not "an infinitely fine brush".
    # The woodcut's finest mark is measured in brush widths too, so it takes the
    # same nominal width the outline does.
    spacing = _num(form, "slicer-infill_line_distance", 1.0)
    brush = spacing if spacing > 0 else gcode_pipeline.NOMINAL_BRUSH_MM
    return {
        "width_mm": _num(form, "brushograph-width", 150.0),
        "brush_mm": max(brush, 0.05),
    }


def _subject_mask(form, image: Image.Image, log=None):
    """The isolation mask, or None when isolation was not asked for or found."""
    if not _flag(form, "woodcut_isolate", "false"):
        return None
    found = subject.detect(image, log)
    if not found.get("found"):
        if log:
            log(f"isolation skipped: {found.get('reason', 'nothing detected')}")
        return None
    return subject.isolate(image, found["box"], faces=found.get("faces"), log=log)


def _prettify_faces(form, image: Image.Image, log=None) -> Image.Image:
    """The face filter, when it was asked for; otherwise the picture as it came."""
    if not _flag(form, "woodcut_face_filter", "false"):
        return image
    return facefilter.enhance(image, log=log)


@app.post("/detect_subject")
def detect_subject():
    """Report whether a person or prominent object is worth isolating."""
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return jsonify(error="No image supplied"), 400
    try:
        with Image.open(upload.stream) as im:
            im.load()
            return jsonify(subject.detect(im, app.logger.info))
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=f"Could not inspect that image: {exc}"), 400


def _on_theme_paper(cut: Image.Image, theme: str) -> Image.Image:
    """The cut printed on the theme's paper, in the theme's ink.

    The preview is two tones and both of them are surfaces of the interface: the
    paper it will be painted on and the mark the brush leaves. Neither stands
    for a particular pigment — which tray paints it is chosen elsewhere — so
    both follow the theme, and a dark theme gets a dark sheet with light marks
    rather than a white rectangle cut out of the page.
    """
    pal = PALETTES.get(theme, PALETTES["default"])
    grey = np.asarray(cut.convert("L"))
    out = np.empty(grey.shape + (3,), np.uint8)
    ink = grey < 128
    out[ink] = pal["canvas"]
    out[~ink] = pal["bg"]
    return Image.fromarray(out, "RGB")


@app.post("/woodcut_preview")
def woodcut_preview():
    """Render the woodcut for one uploaded photo, so it can be judged before a run."""
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return jsonify(error="No image supplied"), 400
    try:
        with Image.open(upload.stream) as im:
            im.load()
            # The mask is read off the photograph as it came: isolation works
            # on the real picture, not on a retouched one.
            mask = _subject_mask(request.form, im)
            converted = woodcut.convert(
                _prettify_faces(request.form, im),
                mask=mask,
                **_scale_params(request.form),
                **_woodcut_params(request.form),
            )
    except Exception as exc:  # noqa: BLE001 - shown to the user as-is
        return jsonify(error=f"Could not convert that image: {exc}"), 400
    buf = io.BytesIO()
    _on_theme_paper(converted, request.form.get("theme", "default")).save(buf, "PNG")
    return app.response_class(buf.getvalue(), mimetype="image/png")


# ------------------------------------------------------------------ the machine

# FluidNC's web UI is ESP3D's: a file goes to /upload as multipart, and a job is
# started by handing the controller the command $SD/Run=/<name>. Both are plain
# HTTP. The websocket it also exposes is the console — status and terminal
# output — and carries no file transfer, so it is not the road a G-code file
# travels down.
#
# The request is made from here rather than from the browser because the machine
# answers a cross-origin preflight without an Access-Control-Allow-Origin
# header, so a browser refuses the reply. That means this only works where the
# server itself can reach the machine.
MACHINE_TIMEOUT = 60
_HOSTNAME_OK = re.compile(r"^[A-Za-z0-9._-]+(:\d{1,5})?$")


def _machine_url(host: str, path: str, query: dict | None = None) -> str:
    url = f"http://{host}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    return url


def _multipart(name: str, data: bytes, path: str = "/") -> tuple[bytes, str]:
    """The upload body ESP3D expects, field for field.

    Taken from the machine's own web UI rather than guessed: the destination in
    `path`, the size in a field named after the full path with an S on the end,
    the modification time likewise with a T, and the file itself under
    `myfiles` with the full path as its filename. Getting any of those names
    wrong is accepted and then silently ignored.
    """
    full = (path.rstrip("/") + "/" + name) if path != "/" else "/" + name
    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    boundary = "----brushograph" + secrets.token_hex(8)
    out = []
    for field, value in (("path", path), (full + "S", str(len(data))), (full + "T", stamp)):
        out.append((f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{field}"\r\n\r\n'
                    f"{value}\r\n").encode())
    out.append((f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="myfiles"; filename="{full}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n").encode())
    out.append(data)
    out.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def _ask_machine(req: urllib.request.Request) -> str:
    with urllib.request.urlopen(req, timeout=MACHINE_TIMEOUT) as r:
        return r.read(20000).decode("utf-8", "replace")


@app.post("/machine/send")
def machine_send():
    """Put a G-code file on the machine, and optionally set it running."""
    host = (request.form.get("hostname") or "").strip().rstrip("/")
    host = host.split("://", 1)[-1]
    if not host or not _HOSTNAME_OK.match(host):
        return jsonify(error="Set a machine hostname in Connection first."), 400
    upload = request.files.get("gcode")
    if not upload or not upload.filename:
        return jsonify(error="No G-code to send"), 400
    name = Path(upload.filename).name
    if not SAFE_NAME.match(name):
        return jsonify(error="That filename cannot go on the machine"), 400
    data = upload.read()
    start = _flag(request.form, "start", "false")

    body, content_type = _multipart(name, data)
    try:
        _ask_machine(urllib.request.Request(
            _machine_url(host, "/upload"), data=body,
            headers={"Content-Type": content_type}, method="POST"))
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        # A machine mid-job refuses the web UI outright, which is worth saying.
        if getattr(exc, "code", None) == 503:
            return jsonify(error=f"{host} is busy running a job — stop it first."), 502
        return jsonify(error=f"Could not reach {host}: {reason}"), 502

    started = False
    if start:
        try:
            _ask_machine(urllib.request.Request(
                _machine_url(host, "/command", {"cmd": f"$SD/Run=/{name}"})))
            started = True
        except (urllib.error.URLError, socket.timeout, OSError) as exc:
            return jsonify(
                error=f"{name} is on {host}, but it would not start: "
                      f"{getattr(exc, 'reason', exc)}"), 502

    app.logger.info("sent %s (%d KB) to %s%s", name, len(data) // 1024, host,
                    " and started it" if started else "")
    return jsonify(name=name, host=host, started=started, bytes=len(data))


@app.get("/about")
def about():
    return render_template("about.html")


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
        # The plan is drawn on the same paper the page is using.
        theme = request.form.get("theme", "default")
        return app.response_class(render_sketch(conf, theme), mimetype="image/png")

    stem = Path(name).stem
    if request.form.get("config_only") == "true":
        buf = json.dumps(conf, indent=4).encode()
        return app.response_class(
            buf, mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{stem}.conf"'},
        )

    entries = tray_entries(conf)
    images = {e["tray"]: request.files.get(f"trays-{e['tray']}-image")
              for e in entries if e["image"]}
    images = {k: v for k, v in images.items() if v and v.filename}
    if not images:
        return jsonify(error="No images selected"), 400

    try:
        infill = float(conf.get("slicer", {}).get("infill_line_distance", 1)) > 0
    except (TypeError, ValueError):
        infill = True
    download_name = _gcode_name(images, entries, conf, infill)

    with GENERATE_LOCK:
        work = Path(tempfile.mkdtemp(prefix="brushograph_", dir=session_dir(sid)))
        try:
            wc = _woodcut_params(request.form)
            saved = {}
            for tray, storage in images.items():
                p = work / f"upload_{tray}{Path(storage.filename).suffix or '.png'}"
                storage.save(p)
                # A photo has to become bold black and white before the tracer
                # sees it; an already-thresholded image is passed through.
                if request.form.get(f"trays-{tray}-image_kind") == "photo":
                    with Image.open(p) as im:
                        im.load()
                        mask = _subject_mask(request.form, im, app.logger.info)
                        converted = woodcut.convert(
                            _prettify_faces(request.form, im, app.logger.info),
                            mask=mask,
                            **_scale_params(request.form),
                            **wc,
                        )
                    p = work / f"woodcut_{tray}.png"
                    converted.convert("L").save(p)
                    app.logger.info("[%s] woodcut: %.1f%% ink", tray,
                                    woodcut.ink_fraction(converted) * 100)
                saved[tray] = p
            log_lines: list[str] = []
            out = work / download_name
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
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Brushograph WebUI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default=8080, type=int)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    print(f"Brushograph WebUI on http://{args.host}:{args.port}")
    # Warm the segmentation model here rather than inside the first upload, so
    # the download happens once, visibly, and not in the middle of a request.
    print(f"  {'subject':9} "
          + ("segmentation model ready" if subject.warm(print) else "GrabCut fallback"))
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
