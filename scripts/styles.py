#!/usr/bin/env python3
"""The style library: 58 detailed style recipes, found by fit and shown as posters (Python 3 stdlib; ffmpeg for board).

  python3 tools/styles.py list                              # one line per style: id · name · base family · essence
  python3 tools/styles.py list --base handmade-ink          # the recipes that build on one of the eight families
  python3 tools/styles.py list --q "paper print folk"       # any word in name, category, essence or uses
  python3 tools/styles.py list --q "kiểu vox"              # a known name ("vox", "ghibli", "wes anderson") first
  python3 tools/styles.py names                             # every known name and the recipes it maps to
  python3 tools/styles.py show woodcut                      # name, uses, base family and the recipe file to read
  python3 tools/styles.py board woodcut ukiyoe shadow-puppet --out review/styles.jpg

Each recipe (KIT/styles/<id>.md) holds what stays true for every film in that style: essence, materials and
rendering, colour logic, type, motion quality, camera grammar, sound palette, native moves, pitfalls and a
variation space. Section 10 (Engine) describes the source project's own demo engine, which is not part of this kit:
build the same grammar in film.html or the scene pages. Read only the chosen recipe, never all of them.

board downloads the posters of 2-6 candidates (the source project's demo films, cached in ~/.rubydai-video/cache/styles)
and tiles them into one numbered image for the user to choose by eye (the kit's own recipes have posters drawn in code,
KIT/styles/posters; a recipe without one shows as a plain numbered tile). Posters are for choosing only; they never enter a film. Recipes: lemo-opuscar by LemoLab,
MIT (KIT/styles/LICENSE-lemo-opuscar), and the kit's own ("source": "rubydai-make-video-skill"). Known names: KIT/styles/aliases.json.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_json, show, write_json, write_text  # noqa: E402  (the kit's shared helpers, same folder)

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.expanduser("~"), ".rubydai-video", "cache", "styles")
SHOWN = os.environ.get("RUBYDAI_VIDEO_SHOWN") or os.path.join(os.path.expanduser("~"), ".rubydai-video", "shown-styles.json")


def shown_boards():
    try:
        return read_json(SHOWN).get("boards", [])
    except (OSError, ValueError):
        return []


def remember(ids):
    """Every board the user saw, so the next films are offered something else (kept: the last 30 boards)."""
    import time
    boards = (shown_boards() + [{"t": int(time.time()), "ids": list(ids)}])[-30:]
    os.makedirs(os.path.dirname(SHOWN), exist_ok=True)
    write_json(SHOWN, {"boards": boards})


def recent(k=6):
    """Styles on the user's last k boards."""
    return {i for b in shown_boards()[-k:] for i in b.get("ids", [])}


def index():
    for p in (os.path.join(HERE, "styles-index.json"), os.path.join(HERE, "..", "styles", "index.json")):
        if os.path.exists(p):
            data = read_json(p)
            data.setdefault("dir", os.path.dirname(os.path.abspath(p)))
            return data
    raise SystemExit("styles index not found (tools/styles-index.json or KIT/styles/index.json)")


def by_id(data, sid):
    for s in data["styles"]:
        if s["id"] == sid:
            return s
    raise SystemExit(f"unknown style: {sid} (styles.py list)")


def aliases(data):
    p = os.path.join(data["dir"], "aliases.json")
    return read_json(p)["aliases"] if os.path.exists(p) else []


GENERIC = {"blockbuster", "phim tài liệu", "documentary", "true crime", "netflix documentary", "80s", "thập niên 80", "vhs",
           "synthwave", "morph", "shape morph", "biến hình", "liquid", "chất lỏng", "metaball", "liquid logo", "swiss",
           "linear", "saas", "saas launch", "stop motion", "stop-motion", "pixel art", "16-bit", "snes", "comic book",
           "slapstick", "goofy", "cartoon comedy", "hoạt hình hài", "line boil", "frame by frame", "cel animation",
           "vẽ từng khung", "variety show", "kinetic captions", "phụ đề hài", "phụ đề hiệu ứng", "sticker explainer",
           "giải thích bằng sticker", "whiteboard explainer", "video essay", "video tiểu luận", "adult animation",
           "data journalism", "1930s cartoon", "hoạt hình thập niên 30", "60s titles", "tiêu đề thập niên 60", "city pop",
           "80s anime", "anime thập niên 80", "ukiyo-e", "ukiyoe", "disney 3d", "apple ad", "quảng cáo apple",
           "giải thích toán học", "math explainer", "chứng minh trực quan", "visual proof"}


def named_hits(data, query):
    """Aliases hit by a proper name (a director, film, studio, artist, brand), not by a word for a technique or genre."""
    q = f" {fold(query)} "
    return [al for al in aliases(data) if any((f" {n} " in q or (len(n) > 4 and n in q)) and n not in GENERIC
                                              for n in al["names"])]


def alias_hits(data, query):
    q = f" {fold(query)} "
    return [al for al in aliases(data) if any(f" {n} " in q or (len(n) > 4 and n in q) for n in al["names"])]


def said_name(al, query):
    """The look's name as the user said it: a group of names answers to any of them."""
    q = f" {fold(query)} "
    return next((n for n in al["names"] if f" {n} " in q or (len(n) > 4 and n in q)), al["names"][0])


def cmd_names(a):
    data = index()
    for al in aliases(data):
        print(f"{' / '.join(al['names'])} → {', '.join(al['styles']) or '(family only)'} · family {al['family']}"
              + (f" · {al['note']}" if al.get("note") else ""))


def fold(text):
    """NFC and lower case: a decomposed Vietnamese word and an all-caps one match the tables."""
    return unicodedata.normalize("NFC", text).lower()


STOP = {"film", "phim", "video", "một", "như", "kiểu", "phong cách", "làm", "và", "cho", "the", "a", "an", "of", "and",
        "like", "style", "movie", "short", "ngắn", "giây", "phút"}
# Vietnamese words and phrases -> the English words the recipes are written in (phrases first, longest first).
VI = {"cà phê": "coffee", "ấm áp": "warm", "quảng cáo": "product", "sản phẩm": "product", "thương hiệu": "brand",
      "giấy": "paper", "tranh in": "print", "ban đêm": "night", "đêm": "night", "biển": "sea", "thành phố": "city",
      "rừng": "forest", "hoạt hình": "cartoon", "cổ điển": "vintage", "hoài cổ": "vintage", "tài liệu": "documentary",
      "bản đồ": "map", "dữ liệu": "data", "bếp": "food", "món ăn": "food", "đồ ăn": "food", "khoa học": "science",
      "vũ trụ": "space", "không gian": "space", "công nghệ": "tech", "ứng dụng": "app", "cổ tích": "storybook",
      "trẻ em": "kids", "thiếu nhi": "kids", "kinh dị": "horror", "lịch sử": "history", "kiến trúc": "architecture",
      "thiên nhiên": "nature", "âm nhạc": "music", "nhạc": "music", "trò chơi": "game", "mực": "ink",
      "màu nước": "watercolor", "gỗ": "wood", "kính": "glass", "thủy tinh": "glass", "ánh sáng": "light",
      "giấc mơ": "dream", "hài hước": "humour", "hài": "humour", "giải thích": "explainer", "giáo dục": "explainer",
      "thể thao": "sport", "bóng đá": "sport", "xe hơi": "car", "ô tô": "car", "mèo": "animal", "chó": "animal",
      "động vật": "animal", "hồi hộp": "thriller", "chiến tranh": "war", "tình yêu": "love", "bảo tàng": "museum",
      "neon": "neon"}


def to_english(text):
    """The words of a query with every known Vietnamese phrase put into the recipes' English."""
    q = f" {fold(text)} "
    for k in sorted(VI, key=len, reverse=True):
        q = q.replace(f" {k} ", f" {VI[k]} ")
    for k in sorted((w for w in STOP if " " in w), key=len, reverse=True):
        q = q.replace(f" {k} ", " ")
    return q


FAMILIES = ("cinematic-realistic", "anime-cel", "pastel-storybook", "claymation", "papercut-collage",
            "retro-synthwave-vhs", "glossy-commercial", "handmade-ink")


def cmd_list(a):
    data = index()
    only = None
    for al in alias_hits(data, a.q or ""):
        picks = al["styles"] or [s["id"] for s in data["styles"] if s["base"] == al["family"]][:4]
        print(f"known name \"{said_name(al, a.q or '')}\" → {', '.join(al['styles']) or 'family ' + al['family'] + ' (no recipe; nearest in the family below)'}"
              + (f" · family {al['family']}" if al["styles"] else "") + (f" · {al['note']}" if al.get("note") else ""))
        only = (only or []) + [i for i in picks if i not in (only or [])]
    words = [w for w in to_english(a.q or "").split() if w not in STOP and len(w) > 1]
    rows = []
    for s in ([by_id(data, i) for i in only] if only is not None else data["styles"]):
        if a.base and s["base"] != a.base:
            continue
        if a.category and a.category.lower() not in s["category"].lower():
            continue
        hay = " ".join([s["id"], s["name"], s["category"], s["essence"], " ".join(s["uses"])]).lower()
        score = sum(w in hay for w in words)
        if only is None and words and not score:
            continue
        rows.append((-score if only is None else 0, s))
    rows.sort(key=lambda r: r[0])                  # most matching words first; known names keep their order
    for _, s in rows[:a.n]:
        ess = s["essence"] if a.long else s["essence"][:110].rstrip() + ("…" if len(s["essence"]) > 110 else "")
        print(f"{s['id']} · {s['name']} · {s['base']} · {ess}")
    print(f"({min(len(rows), a.n)} of {len(data['styles'])}" + (f", {len(rows)} matched)" if len(rows) > a.n else ")"))


def cmd_suggest(a):
    """Six candidates for an idea, different from each other: the best matches first (known names, then words), then
    styles from families and categories not yet on the list, the ties ordered by the idea itself so two ideas do not
    get the same picks. --board draws them at once."""
    import hashlib
    data = index()
    words = [w for w in re.findall(r"[\w'-]+", to_english(a.idea)) if w not in STOP and len(w) > 2]
    named = [i for al in alias_hits(data, a.idea) for i in al["styles"]]   # a name without a recipe brings none
    seed = int(hashlib.sha256(fold(a.idea).encode()).hexdigest(), 16)
    def score(s):
        hay = " ".join([s["id"], s["name"], s["category"], s["essence"], " ".join(s["uses"])]).lower()
        return sum(w in hay for w in words) + (2 if a.purpose and a.purpose.lower() in " ".join(s["uses"]).lower() else 0)
    seen = recent()
    ranked = sorted(data["styles"], key=lambda s: (-(10 if s["id"] in named else 0) - score(s) + (1.5 if s["id"] in seen else 0),
                                                   int(hashlib.sha256(f"{seed}{s['id']}".encode()).hexdigest()[:8], 16)))
    picks, bases, cats = [], set(), set()
    for s in ranked:                              # the matches first, at most two from one family
        if len(picks) >= a.n:
            break
        if (s["id"] in named or score(s) > 0) and sum(p["base"] == s["base"] for p in picks) < 2:
            picks.append(s); bases.add(s["base"]); cats.add(s["category"])
    hits = named_hits(data, a.idea)
    if hits:                                      # a named look: the model's own readings lead, never filler contrasts
        print(f"named look: {', '.join(said_name(al, a.idea) for al in hits)} ({'; '.join(al['note'] for al in hits)}). "
              "Offer your own readings of it beside real stills of it (quick-mode.md §1, question 3); "
              "the rows below are optional, use one only when it truly fits.")
    for s in ranked if not hits else []:          # then contrasts: a family and a category not yet shown
        if len(picks) >= a.n:
            break
        if s not in picks and s["base"] not in bases and s["category"] not in cats and s["id"] not in seen:
            picks.append(s); bases.add(s["base"]); cats.add(s["category"])
    for s in ranked if not hits else []:
        if len(picks) >= a.n:
            break
        if s not in picks and s["base"] not in bases:
            picks.append(s); bases.add(s["base"])
    for i, s in enumerate(picks, 1):
        why = "named" if s["id"] in named else "fits the idea" if score(s) else "a contrast"
        print(f"{i}. {s['id']} · {s['name']} · {s['base']} · {why}{' · shown lately' if s['id'] in seen else ''} · "
              f"{short(s['essence'], 90)}")
    if seen:
        print(f"(styles on the user's last boards are moved back: {', '.join(sorted(seen))}; never swap one of them in)")
    if a.board and len(picks) >= 2:
        cmd_board(argparse.Namespace(ids=[s["id"] for s in picks], out=a.board, width=480))


def cmd_show(a):
    data = index()
    s = by_id(data, a.id)
    recipe = os.path.normpath(os.path.join(data["dir"], s["id"] + ".md"))
    print(f"{s['name']} ({s['id']}) · {s['category']} · base family: {s['base']}")
    print(f"essence: {s['essence']}")
    print(f"uses: {', '.join(s['uses'])}")
    print(f"recipe: {recipe}")
    print(f"source demo (study only): {s['demo']}" if s.get("demo") else "source: the kit's own recipe (no demo)")


def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "rubydai-video-styles/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest + ".part", "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(dest + ".part", dest)
    return dest


def poster_file(data, s):
    """A style's poster on disk: LemoLab's downloaded once into the cache, the kit's own read from KIT/styles/posters."""
    p = s.get("poster")
    if not p:
        return None
    if not p.startswith(("http://", "https://")):
        f = os.path.join(data["dir"], p)
        return f if os.path.exists(f) else None
    return fetch(p, os.path.join(CACHE, data.get("commit", "x")[:12], s["id"] + ".jpg"))


def family_poster(data, fam):
    """A look family has no poster: the Quick starter rendered once in that look stands in (cached)."""
    dest = os.path.join(CACHE, "families", fam + ".jpg")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    kit = os.path.dirname(os.path.normpath(data["dir"]))
    page, capture = os.path.join(kit, "templates", "quick", "film.html"), os.path.join(HERE, "capture.mjs")
    if not (os.path.exists(page) and os.path.exists(capture) and shutil.which("node")):
        return None
    tmp = dest + ".frames"
    r = subprocess.run(["node", capture, "--url", page, "--frames", "84", "--format", "jpeg", "--out", tmp,
                        "--params", f"look={fam}&w=640&h=360"], capture_output=True, text=True)
    frames = sorted(f for f in os.listdir(tmp) if f.endswith(".jpg")) if os.path.isdir(tmp) else []
    if r.returncode != 0 or not frames:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    os.replace(os.path.join(tmp, frames[0]), dest)
    shutil.rmtree(tmp, ignore_errors=True)
    return dest


def page(img, captions=()):
    """A page beside an image that shows it at full width, with optional numbered captions above it. Its path, clicked
    in the Claude Code desktop app, opens it big in the app's own browser pane (elsewhere in the browser); the app does
    not show images inside a chat message."""
    import html as _h
    p = os.path.splitext(str(img))[0] + ".html"
    name = _h.escape(os.path.basename(str(img)))
    caps = "".join(f"<li>{_h.escape(c)}</li>" for c in captions)
    write_text(p, 
        f'<!doctype html><meta charset=utf-8><title>{name}</title><style>body{{margin:0;background:#111;color:#eee;'
        f'font:18px/1.5 -apple-system,Helvetica,Arial,sans-serif}}ul{{margin:0;padding:14px 18px;list-style:none}}'
        f'img{{display:block;width:100%;height:auto}}</style>' + (f"<ul>{caps}</ul>" if caps else "") +
        f'<img src="{name}">')
    return os.path.abspath(p)




def chrome():
    win = [os.path.join(os.environ.get(root, ""), *app) for root in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
           for app in (("Google", "Chrome", "Application", "chrome.exe"), ("Microsoft", "Edge", "Application", "msedge.exe"))
           if os.environ.get(root)]
    for c in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"] + win:
        if os.path.exists(c):
            return c
    return next((shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                                          "microsoft-edge") if shutil.which(n)), None)


def short(text, n):
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def html_board(picks, files, cols, w, h, out):
    """The board as a page shot by headless Chrome: a big number on each tile, the style's name under it, and a text
    card for a recipe without a poster. False when there is no Chrome (the plain board is used then)."""
    exe = chrome()
    if not exe:
        return False
    import html as H
    rows = (len(picks) + cols - 1) // cols
    cap = 46
    tiles = []
    for i, (s, f) in enumerate(zip(picks, files), 1):
        body = (f'<img src="{H.escape(Path(f).resolve().as_uri())}">' if f else
                f'<div class="card"><b>{H.escape(s["name"])}</b><span>{H.escape(short(s["essence"], 170))}</span></div>')
        tiles.append(f'<div class="t">{body}<i>{i}</i><p>{i} · {H.escape(s["name"])}</p></div>')
    page = (f"<!doctype html><meta charset=utf-8><style>body{{margin:0;background:#000;display:grid;"
            f"grid-template-columns:repeat({cols},{w}px);gap:8px;font-family:-apple-system,Helvetica,Arial,sans-serif}}"
            f".t{{position:relative;width:{w}px;height:{h + cap}px;background:#111}}"
            f"img{{width:{w}px;height:{h}px;object-fit:contain;display:block;background:#000}}"
            f".card{{width:{w}px;height:{h}px;box-sizing:border-box;padding:56px 26px 18px;background:#2a2620;color:#f1e6d0;"
            f"display:flex;flex-direction:column;gap:10px}}.card b{{font-size:26px}}.card span{{font-size:15px;line-height:1.35;opacity:.85}}"
            f"i{{position:absolute;left:10px;top:10px;width:40px;height:40px;border-radius:20px;background:#f2c230;color:#111;"
            f"font:700 24px/40px -apple-system,Helvetica,Arial,sans-serif;text-align:center;font-style:normal}}"
            f"p{{margin:0;height:{cap}px;line-height:{cap}px;padding:0 12px;color:#eee;font-size:17px;white-space:nowrap;"
            f"overflow:hidden;text-overflow:ellipsis}}</style>{''.join(tiles)}")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        src, png = os.path.join(tmp, "board.html"), os.path.join(tmp, "board.png")
        write_text(src, page)
        W, Hh = cols * (w + 8) - 8, rows * (h + cap + 8) - 8
        r = subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                            f"--window-size={W},{Hh}", f"--screenshot={png}", Path(src).resolve().as_uri()],
                           capture_output=True, timeout=60)
        if r.returncode != 0 or not os.path.exists(png):
            return False
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", png, "-q:v", "3", out], check=True)
    return True


def cmd_board(a):
    if not 2 <= len(a.ids) <= 6:
        raise SystemExit("board takes 2-6 style ids")
    if not shutil.which("ffmpeg"):
        raise SystemExit("board needs ffmpeg")
    data = index()
    picks = [{"id": i, "name": i.replace("-", " ").title() + " (look family)", "base": i,
              "essence": "the kit's base look, shown on the starter scene", "poster": None, "family": True}
             if i in FAMILIES else by_id(data, i) for i in a.ids]
    files = [family_poster(data, s["id"]) if s.get("family") else poster_file(data, s) for s in picks]
    w = a.width
    h = round(w * 9 / 16 / 2) * 2
    inputs, chains = [], []
    for i, f in enumerate(files):
        inputs += ["-i", f] if f else ["-f", "lavfi", "-i", f"color=c=0x2a2620:s={w}x{h}:d=1"]
        chains.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
                      f"setsar=1[v{i}]")
    cols = {4: 2, 5: 3, 6: 3}.get(len(files), len(files))
    rows = (len(files) + cols - 1) // cols
    layout = "|".join(f"{(i % cols) * (w + 8)}_{(i // cols) * (h + 8)}" for i in range(len(files)))
    graph = ";".join(chains) + ";" + "".join(f"[v{i}]" for i in range(len(files))) + \
        f"xstack=inputs={len(files)}:layout={layout}:fill=black"
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    remember([s["id"] for s in picks if not s.get("family")])
    if not html_board(picks, files, cols, w, h, a.out):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-frames:v", "1", "-q:v", "4",
                        a.out], check=True)
    print(f"board: {a.out} ({cols}x{rows}, left to right, top to bottom) · show the user: {os.path.abspath(a.out)} (Claude Code: SendUserFile with display 'render', it opens big in the side panel; elsewhere the page {page(a.out)} in your message)"
          + (" · opened on the user's screen" if show(a.out) else ""))
    for i, s in enumerate(picks, 1):
        print(f"  {i}. {s['name']} ({s['id']}) · base {s['base']} · {s['essence'][:90]}")
    print("ask after showing it, in the user's language: the ★ and two strong alternatives by number, and as the last "
          "option \"None of these: find a more creative direction\" (Vietnamese: \"Không cái nào: tìm hướng sáng tạo hơn\"); "
          "the other numbers go in Other. On that answer: KIT/references/quick-mode.md §1, question 3 (None of these: find a more creative direction).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("suggest", help="six different candidates for an idea (the style question), --board draws them")
    g.add_argument("idea")
    g.add_argument("--purpose", help="ad, explainer, music video …: favours recipes made for it")
    g.add_argument("--n", type=int, default=6)
    g.add_argument("--board", help="also draw the numbered board to this path (opens on the user's screen)")
    g.set_defaults(fn=cmd_suggest)
    p = sub.add_parser("list")
    p.add_argument("--base", help="one of the eight families (looks.md §1)")
    p.add_argument("--category")
    p.add_argument("--q", help="words; a style matches when any word appears")
    p.add_argument("--long", action="store_true", help="the whole essence line")
    p.add_argument("--n", type=int, default=8, help="at most this many lines (best matches first)")
    p.set_defaults(fn=cmd_list)
    sub.add_parser("names").set_defaults(fn=cmd_names)
    sub.add_parser("recent", help="styles on the user's last boards (never offered again soon)").set_defaults(
        fn=lambda a: print("\n".join(sorted(recent())) or "(none yet)"))
    p = sub.add_parser("show")
    p.add_argument("id")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("board")
    p.add_argument("ids", nargs="+")
    p.add_argument("--out", default="review/styles.jpg")
    p.add_argument("--width", type=int, default=480, help="width of each poster in the board")
    p.set_defaults(fn=cmd_board)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    if os.name == "nt" and not sys.flags.utf8_mode:   # Windows reads, writes and prints in a legacy code page
        import subprocess
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=dict(os.environ, PYTHONUTF8="1")))
    for _s in (sys.stdin, sys.stdout, sys.stderr):
        getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
