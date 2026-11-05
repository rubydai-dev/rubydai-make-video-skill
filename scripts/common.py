#!/usr/bin/env python3
"""Small helpers the kit's tools share (Python 3 standard library only). Copied into every film's tools/ with them.

  show(path)              put a board, sheet or film in front of the user (only with RUBYDAI_VIDEO_OPEN=1)
  read_json(path, default) the file's JSON, the default when it is missing or broken; the file is always closed
  write_json(path, data)   written whole or not at all (a .tmp file moved into place), parent folders made
  read_text(path)          UTF-8 text, the file closed (read_bytes, write_text, write_bytes alike)
  debug(where, error)      one line on stderr with RUBYDAI_VIDEO_DEBUG=1: an error a tool chose to step over
  user_agent(tool, why)    the User-Agent every request of the kit sends
"""
import json
import os
import shutil
import subprocess
import sys


def show(path):
    """Put a board, a sheet or a film in front of the user: Preview on macOS, the default viewer elsewhere.
    RUBYDAI_VIDEO_NO_OPEN=1 turns it off (tests, servers); nothing opens unless RUBYDAI_VIDEO_OPEN=1."""
    if os.environ.get("RUBYDAI_VIDEO_NO_OPEN") or not os.path.exists(str(path)):
        return False
    if not os.environ.get("RUBYDAI_VIDEO_OPEN"):
        return False                              # nothing opens a window: paths go into the message
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("win"):
            os.startfile(str(path))
        elif shutil.which("xdg-open") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            return False
    except OSError as e:
        debug("show", e)
        return False
    return True


_MISSING = object()


def read_json(path, default=_MISSING):
    """The JSON in path. Without a default a missing or broken file raises as json.load would; with one, the default
    comes back instead (and RUBYDAI_VIDEO_DEBUG names a broken file)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        if default is _MISSING:
            raise
        if not isinstance(e, FileNotFoundError):
            debug(f"read_json {path}", e)
        return default


def write_json(path, data, **kwargs):
    """Write data as JSON, whole or not at all: a crash midway leaves the old file, never half of one."""
    kwargs.setdefault("ensure_ascii", False)
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, **kwargs)
    os.replace(tmp, path)


def read_text(path, errors="strict"):
    with open(path, encoding="utf-8", errors=errors) as f:
        return f.read()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def debug(where, error):
    """A tool that steps over an error on purpose says so here; silent unless RUBYDAI_VIDEO_DEBUG is set."""
    if os.environ.get("RUBYDAI_VIDEO_DEBUG"):
        print(f"[debug] {where}: {type(error).__name__}: {str(error)[:300]}", file=sys.stderr)


def user_agent(tool, why="low volume"):
    return f"rubydai-video-{tool}/1.0 ({why})"
