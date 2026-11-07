#!/usr/bin/env python3
"""Sync the style recipes from lemo-opuscar (LemoLab, MIT) into KIT/styles/. A kit maintainer's tool, never copied
into a film.

  python3 scripts/sync_styles.py --dry                     # what the latest upstream commit would change
  python3 scripts/sync_styles.py                           # sync to the latest commit on main
  python3 scripts/sync_styles.py --commit <sha>            # sync to one commit
  python3 scripts/sync_styles.py --base news-package=glossy-commercial   # a new style's base family
  python3 scripts/sync_styles.py --src <local clone> --commit <sha>     # offline, from a clone at that commit

Each upstream styles/<id>/STYLE.md becomes styles/<id>.md, its links to DEMO.md pinned to the commit. styles/index.json
takes the name, category, uses and essence from upstream; the base family is the kit's own (kept for known styles, given
with --base for new ones). The kit's own recipes ("source" set) stay as they are. A style removed upstream is reported
and kept. Nothing is written until every style has been read and checked.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import user_agent  # noqa: E402

REPO = "lemomo-ai/lemo-opuscar"
FAMILIES = ("cinematic-realistic", "anime-cel", "pastel-storybook", "claymation", "papercut-collage",
            "retro-synthwave-vhs", "glossy-commercial", "handmade-ink")
KIT = Path(__file__).resolve().parent.parent


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent("sync-styles", "kit maintenance")})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


class Remote:
    """The upstream repo at one commit, over HTTPS: one API call for the file list, raw files for the rest."""

    def __init__(self, commit):
        self.commit = commit or json.loads(get(f"https://api.github.com/repos/{REPO}/commits/main"))["sha"]
        tree = json.loads(get(f"https://api.github.com/repos/{REPO}/git/trees/{self.commit}?recursive=1"))
        if tree.get("truncated"):
            sys.exit("the upstream file list came back truncated; sync from a clone with --src")
        self.paths = {t["path"] for t in tree["tree"]}
        self.cache = {}

    def exists(self, path):
        return path in self.paths

    def prefetch(self, paths):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as pool:
            self.cache.update(zip(paths, pool.map(self.read, paths)))

    def read(self, path):
        if path in self.cache:
            return self.cache[path]
        return get(f"https://raw.githubusercontent.com/{REPO}/{self.commit}/{path}")


class Local:
    def __init__(self, src, commit):
        if not commit:
            sys.exit("--src needs --commit (the commit the clone is at)")
        self.root, self.commit = Path(src), commit

    def exists(self, path):
        return (self.root / path).exists()

    def read(self, path):
        return (self.root / path).read_text(encoding="utf-8")


def styles_of(up):
    if isinstance(up, Remote):
        found = {p.split("/")[1] for p in up.paths if re.fullmatch(r"styles/[^/]+/STYLE\.md", p)}
    else:
        found = {p.name for p in (up.root / "styles").iterdir() if (p / "STYLE.md").is_file()}
    return sorted(s for s in found if not s.startswith("_"))


def pin(md, slug, commit):
    """Relative links to the demo notes become links to upstream at the commit; any other relative link is an error."""
    md = re.sub(r"\]\((DEMO\.md[^)]*)\)", lambda m: f"](https://github.com/{REPO}/blob/{commit}/styles/{slug}/{m.group(1)})", md)
    if re.search(r"\]\((?!https?://|#)[^)]+\)", re.sub(r"`[^`]*`", "", md)):
        raise ValueError("a relative link the kit cannot follow is left in STYLE.md")
    return md


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", help="upstream commit (default: the latest on main)")
    ap.add_argument("--src", help="a local clone of lemo-opuscar instead of the network")
    ap.add_argument("--base", action="append", default=[], metavar="ID=FAMILY", help="base family for a new style")
    ap.add_argument("--dry", action="store_true", help="report only, write nothing")
    ap.add_argument("--kit", default=str(KIT), help=argparse.SUPPRESS)
    a = ap.parse_args()

    kit = Path(a.kit)
    idx_path = kit / "styles" / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    old = {s["id"]: s for s in idx["styles"]}
    own = [s for s in idx["styles"] if s.get("source")]
    given = {}
    for b in a.base:
        sid, _, fam = b.partition("=")
        if fam not in FAMILIES:
            sys.exit(f"--base {b}: the family must be one of {', '.join(FAMILIES)}")
        given[sid] = fam

    up = Local(a.src, a.commit) if a.src else Remote(a.commit)
    commit = up.commit
    entries, texts, added, changed, unbased = [], [], [], [], []
    slugs = styles_of(up)
    if isinstance(up, Remote):
        up.prefetch([f"styles/{s}/{f}" for s in slugs for f in ("style.json", "STYLE.md")])
    for slug in slugs:
        if slug in old and old[slug].get("source"):
            sys.exit(f"{slug}: upstream now has a style with the id of one of the kit's own; rename the kit's first")
        sj = json.loads(up.read(f"styles/{slug}/style.json"))
        try:
            md = pin(up.read(f"styles/{slug}/STYLE.md"), slug, commit)
        except ValueError as e:
            sys.exit(f"{slug}: {e}")
        m = re.search(r"^> (.+)$", md, re.M)
        if not m:
            sys.exit(f"{slug}: STYLE.md has no '> ' essence line")
        base = given.get(slug) or (old[slug]["base"] if slug in old else None)
        if not base:
            unbased.append(f"{slug} ({sj.get('category_en')}: {m.group(1)[:90]}…)")
            continue
        entries.append({
            "id": slug, "name": sj["en"], "category": sj["category_en"], "base": base,
            "essence": m.group(1).strip(), "uses": sj["uses"],
            "poster": f"https://raw.githubusercontent.com/{REPO}/{commit}/styles/{slug}/poster.jpg"
                      if up.exists(f"styles/{slug}/poster.jpg") else None,
            "demo": f"https://github.com/{REPO}/tree/{commit}/styles/{slug}",
        })
        out = kit / "styles" / f"{slug}.md"
        if slug not in old:
            added.append(slug)
        elif not out.exists() or out.read_text(encoding="utf-8") != md:
            changed.append(slug)
        texts.append((out, md))
    if unbased:
        sys.exit("NEW STYLES NEED A BASE FAMILY (nothing written). Give each one with --base <id>=<family>, the nearest of "
                 + ", ".join(FAMILIES) + ":\n  " + "\n  ".join(unbased))

    gone = [s for s in old if s not in slugs and not old[s].get("source")]
    entries += [old[s] for s in gone]                     # kept until a maintainer removes them by hand
    idx["commit"] = commit
    idx["styles"] = entries + own
    total = len(idx["styles"])
    print(f"upstream {commit[:7]}: {len(entries) - len(gone)} styles + {len(gone)} kept + the kit's {len(own)} = {total}")
    print("added:", " ".join(added) or "-")
    print(f"recipe text changed ({len(changed)}):", " ".join(changed) or "-")
    if gone:
        print("removed upstream, kept here:", " ".join(gone))
    if a.dry:
        print("dry run: nothing written")
        return
    for out, md in texts:
        out.write_text(md, encoding="utf-8")
    tmp = idx_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, idx_path)
    if added:
        print("next: known names for the new styles in styles/aliases.json (\"bản tin\" → news-package)")
    if len(old) != total:
        print(f"next: the style count changed ({len(old)} → {total}): update it in README.md, SKILL.md, "
              f"references/looks.md, references/quick-mode.md and the counts in tests/test_context.py")


if __name__ == "__main__":
    if os.name == "nt" and not sys.flags.utf8_mode:   # Windows reads, writes and prints in a legacy code page
        import subprocess
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=dict(os.environ, PYTHONUTF8="1")))
    for _s in (sys.stdin, sys.stdout, sys.stderr):
        getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")
    main()
