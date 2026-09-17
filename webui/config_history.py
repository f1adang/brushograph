#!/usr/bin/python3
"""Version history for the configs kept on the server.

webui_configs/ is a git repository of its own — the code's repository ignores
the directory, so the two never meet — and every write to a kept config is a
commit there, naming the file, what was done to it and the address the request
came from. A kept config is shared by everyone using the server, so when one
changes under somebody it is worth being able to see when, from where, and
what it was before.

History is a record, not a gate: if git is missing or a commit fails, the
config is still saved and the failure is logged. Nobody's Update should be
refused because the server could not write its diary.
"""
from __future__ import annotations

import ipaddress
import subprocess
from pathlib import Path

# The same identity on every server, whatever git is configured with there: the
# author of a commit is the WebUI, and who asked for it is in the message.
_IDENTITY = [
    "-c", "user.name=Brushograph WebUI",
    "-c", "user.email=webui@brushograph.invalid",
    "-c", "commit.gpgsign=false",
]

# Files a write passes through on its way into place, never worth recording.
_IGNORE = ".upload-*.part\n"


def client_ip(request) -> str:
    """The address a request came from.

    Deployed, gunicorn listens on loopback behind nginx, so the peer is always
    127.0.0.1 and the client is in X-Real-IP, which nginx sets to its own
    $remote_addr, overwriting anything the client sent. The header is only
    believed from a loopback peer: straight to the app, a client could claim
    any address it liked in it. Run without nginx, the peer is the client.
    """
    peer = request.remote_addr or "unknown"
    real = request.headers.get("X-Real-IP", "").strip()
    try:
        if real and ipaddress.ip_address(peer).is_loopback:
            return str(ipaddress.ip_address(real))
    except ValueError:
        pass
    return peer


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *_IDENTITY, "-C", str(repo), *args],
                          capture_output=True, text=True, timeout=30)


def init(repo: Path, log) -> None:
    """Make the directory a repository, recording whatever it already holds.

    Run once at start. A directory already under version control is left as it
    is; one that is not gets a repository and a first commit of the configs
    kept before there was any history, so the first real change has something
    to be compared with.
    """
    try:
        if (repo / ".git").exists():
            return
        _check(_git(repo, "init", "-q"))
        (repo / ".gitignore").write_text(_IGNORE)
        _check(_git(repo, "add", "-A"))
        _check(_git(repo, "commit", "-q", "-m", "Configs kept before version history"))
        log("config history: started a repository in %s", repo)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        log("config history: could not start a repository in %s: %s", repo, exc)


def commit(repo: Path, name: str, action: str, ip: str, log) -> None:
    """Commit one config as it now stands: "<action> <name> from <ip>".

    Nothing is committed when the file is as it was — an Update that changed
    nothing, say — since an empty commit records an event, not a change.
    """
    if not (repo / ".git").exists():
        return      # init failed and said so; git -C would find the code's repository
    try:
        _check(_git(repo, "add", "--", name))
        if not _git(repo, "diff", "--cached", "--quiet", "--", name).returncode:
            return
        _check(_git(repo, "commit", "-q", "-m", f"{action} {name} from {ip}", "--", name))
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        log("config history: could not commit %s (%s from %s): %s", name, action, ip, exc)


def _check(result: subprocess.CompletedProcess) -> None:
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or f"git exited {result.returncode}")
