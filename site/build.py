#!/usr/bin/env python3
"""Build the kit's GitHub Pages site into _site/.

  python3 site/build.py [out_dir]        # writes _site/index.html (style data inlined) and the logo
  python3 -m http.server -d _site 8000   # preview at http://localhost:8000

The style list comes from styles/index.json and styles/aliases.json, so the page always matches the kit.
Posters and demo films stay on LemoLab's servers (lemo-opuscar, CC BY 4.0); nothing is copied here.
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
REPO = "https://github.com/rubydai-dev/rubydai-make-video-skill"
GALLERY = "https://lemomo-ai.github.io/lemo-opuscar/"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main(out=OUT):
    index =json.loads((ROOT / "styles" / "index.json").read_text(encoding="utf-8"))
    aliases = json.loads((ROOT / "styles" / "aliases.json").read_text(encoding="utf-8"))["aliases"]
    names = {}
    for al in aliases:
        for sid in al["styles"][:1]:                 # a known name belongs to its closest recipe only
            names.setdefault(sid, []).extend(al["names"])
    styles = []
    for s in index["styles"]:
        own = bool(s.get("source"))
        styles.append({
            "id": s["id"], "name": s["name"], "category": s["category"], "base": s["base"],
            "essence": s["essence"], "uses": s["uses"], "aliases": names.get(s["id"], []),
            "own": own,
            "poster": s.get("poster"),
            "film": None if own else f"{GALLERY}films/{s['id']}.mp4",
            "gallery": None if own else f"{GALLERY}#{slug(s['category'])}",
            "recipe": f"{REPO}/blob/main/styles/{s['id']}.md",
        })
    data = {"repo": REPO, "gallery": GALLERY, "upstream": index["source"], "commit": index["commit"], "styles": styles}
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    marker = "/*STYLE_DATA*/null"
    if marker not in page:
        sys.exit("site/index.html: the data marker is missing")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page.replace(marker, blob), encoding="utf-8")
    shutil.copyfile(ROOT / "docs" / "media" / "logo.png", out / "logo.png")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{out / 'index.html'} · {len(styles)} styles ({sum(s['own'] for s in styles)} the kit's own)")
    return data


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else OUT)
