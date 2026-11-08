#!/usr/bin/env python3
"""Draw the posters of the kit's own style recipes (Python 3 stdlib, headless Chrome, ffmpeg).

  python3 site/posters/render.py              # every kit-own style that has a drawing in posters.html
  python3 site/posters/render.py stickman     # only these ids

Each poster is a still drawn entirely in code by site/posters/posters.html (?id=<style id>), with the stick-figure rig
of templates/quick/film.html injected, so the stickman poster shows the rig the films use. Writes
styles/posters/<id>.jpg (1280x720) and sets "poster": "posters/<id>.jpg" (relative to styles/) in styles/index.json.
LemoLab's styles keep their own posters, shown from their servers.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from styles import chrome  # noqa: E402  (the same browser lookup the board uses)

RIG_START, RIG_END = "const EMOTIONS = {", "// The model sheet:"


def rig():
    """The characters block of the Quick template: EMOTIONS, the bean rig, SKETCH and the stick figure."""
    page = (ROOT / "templates" / "quick" / "film.html").read_text(encoding="utf-8")
    a, b = page.find(RIG_START), page.find(RIG_END)
    if a < 0 or b < a:
        sys.exit("templates/quick/film.html: the characters block (EMOTIONS … model sheet) was not found")
    return page[a:b]


def main(ids):
    exe = chrome()
    if not exe or not shutil.which("ffmpeg"):
        sys.exit("render.py needs Chrome (or Chromium / Edge) and ffmpeg")
    index_path = ROOT / "styles" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    page = (HERE / "posters.html").read_text(encoding="utf-8")
    drawn = set(re.findall(r"^'([a-z0-9-]+)'\(\) \{", page, re.M))
    own = [s["id"] for s in index["styles"] if s.get("source")]
    ids = ids or [i for i in own if i in drawn]
    for i in ids:
        if i not in own:
            sys.exit(f"{i}: not one of the kit's own styles (LemoLab's styles keep their own posters)")
        if i not in drawn:
            sys.exit(f"{i}: posters.html has no drawing for it yet")
    out = ROOT / "styles" / "posters"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "posters.html"
        html.write_text(page.replace("/*RIG*/", rig()), encoding="utf-8")
        for i in ids:
            png = Path(tmp) / f"{i}.png"
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                            "--window-size=1280,720", "--virtual-time-budget=8000", f"--screenshot={png}",
                            f"{html.as_uri()}?id={i}"], capture_output=True, text=True, timeout=180)
            if not png.exists():
                sys.exit(f"{i}: Chrome wrote no screenshot")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-q:v", "3", str(out / f"{i}.jpg")], check=True)
            print(f"{out / f'{i}.jpg'}")
    for s in index["styles"]:
        if s["id"] in ids:
            s["poster"] = f"posters/{s['id']}.jpg"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(ids)} poster(s); styles/index.json points at them")


if __name__ == "__main__":
    main(sys.argv[1:])
