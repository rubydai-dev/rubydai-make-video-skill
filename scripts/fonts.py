#!/usr/bin/env python3
"""Search 2,000+ open-licence fonts by the film's tone (Python 3 standard library; no key).

  python3 tools/fonts.py search "hài hước hoạt hình"            # display faces that carry the tone (Vietnamese)
  python3 tools/fonts.py search "tài liệu bình yên" --role text  # text faces: readable, the same tone
  python3 tools/fonts.py search "kinh dị" --category serif --n 12
  python3 tools/fonts.py role be-vietnam-pro                     # the TYPE role for film.html, version pinned
  python3 tools/fonts.py search "やさしい 絵本" --lang ja          # Japanese faces (the japanese subset)
  python3 tools/fonts.py role zen-maru-gothic --lang ja          # a role that loads the whole font file

Sources: the Fontsource catalogue (every family with its licence, subsets and versions; files on the jsDelivr CDN
that the kit's type loader already uses) and the expressive tags of the Google Fonts repository (each family scored
0-100 for Playful, Calm, Rugged, Vintage, Sophisticated, Futuristic and more). Both are cached for 30 days in
~/.rubydai-video/cache/fonts. Only open licences, only families with the on-screen language's letters: --lang vi
(default; the vietnamese subset, Ă Đ Ơ Ư and the stacked vowels read from the font's own files), --lang ja (the
japanese subset; its role loads the whole font file from the pinned Google Fonts repository, because Fontsource cuts
Japanese into ~120 slices) or --lang en / --latin-only (no letter filter).
The fonts every generated design overuses (Inter, Roboto, Montserrat, Poppins, Space Grotesk,
Instrument, Playfair, DM, Geist and the like) are left out unless --allow-common: a film's type is chosen, not
defaulted. The tone words may be Vietnamese, English or Japanese; `fonts.py tones` lists them.
"""
import argparse
import csv
import json
import os
import sys
import time
import struct
import unicodedata
import urllib.request
import zlib

CACHE = os.path.join(os.path.expanduser("~"), ".rubydai-video", "cache", "fonts")
CATALOGUE = "https://api.fontsource.org/v1/fonts"
GF_CONTENTS = "https://api.github.com/repos/google/fonts/contents/ofl/{dir}"   # Japanese roles: the whole font files
GF_COMMIT = "https://api.github.com/repos/google/fonts/commits/main"
GF_FILE = "https://cdn.jsdelivr.net/gh/google/fonts@{sha}/ofl/{dir}/{name}"
TAGS = "https://raw.githubusercontent.com/google/fonts/main/tags/all/families.csv"
# Licences that allow any film, commercial included, with nothing owed on screen or in the description: the font is
# used, never sold or shared as a file. Attribution (CC-BY), share-alike and GPL licences are left out on purpose.
OPEN = {"OFL-1.1", "APACHE-2.0", "MIT", "CC0-1.0", "UFL-1.0", "UNLICENSE"}


def open_licence(lic):
    return str(lic or "").upper() in OPEN

# What every generated design defaults to; allowed only with --allow-common and a reason on the director card.
COMMON = {"inter", "roboto", "open-sans", "montserrat", "poppins", "lato", "raleway", "nunito", "nunito-sans",
          "space-grotesk", "instrument-sans", "instrument-serif", "dm-sans", "dm-serif-display", "dm-serif-text",
          "playfair-display", "geist", "geist-mono", "manrope", "plus-jakarta-sans", "outfit", "work-sans",
          "source-sans-3", "roboto-mono", "jetbrains-mono", "noto-sans", "noto-serif", "oswald", "bebas-neue",
          "lora", "merriweather", "rubik", "mulish", "figtree", "archivo", "sora", "urbanist", "libre-baskerville",
          "lobster", "pacifico", "dancing-script", "great-vibes", "comic-neue", "bangers", "abril-fatface", "cinzel"}

# Tone words (Vietnamese, English and Japanese; two-word phrases match too) -> the Google Fonts tags that carry them.
TONES = {
    ("comedy", "cartoon", "goofy", "slapstick", "fun", "playful", "hài", "hài hước", "vui nhộn", "hoạt hình",
     "tinh nghịch", "コメディ", "ギャグ", "楽しい", "ポップ"):
        ["/Expressive/Playful", "/Expressive/Happy", "/Expressive/Excited", "/Theme/Wacky", "/Theme/Blobby"],
    ("kids", "children", "toy", "cute", "trẻ em", "thiếu nhi", "đồ chơi", "dễ thương", "đáng yêu", "子供", "かわいい",
     "可愛い", "絵本"):
        ["/Expressive/Childlike", "/Expressive/Cute", "/Expressive/Happy"],
    ("horror", "thriller", "dark", "kinh dị", "rùng rợn", "u tối", "hồi hộp", "ホラー", "怖い", "ダーク"):
        ["/Theme/Distressed", "/Expressive/Rugged", "/Expressive/Awkward", "/Seasonal/Halloween"],
    ("documentary", "history", "news", "serious", "tài liệu", "lịch sử", "tin tức", "nghiêm túc", "phóng sự",
     "ドキュメンタリー", "歴史", "ニュース", "真面目"):
        ["/Expressive/Sincere", "/Expressive/Competent", "/Expressive/Calm", "/Expressive/Business"],
    ("luxury", "premium", "fashion", "elegant", "sang trọng", "cao cấp", "thời trang", "thanh lịch", "高級",
     "エレガント", "上品"):
        ["/Expressive/Sophisticated", "/Expressive/Fancy"],
    ("tech", "future", "scifi", "app", "saas", "công nghệ", "tương lai", "khoa học viễn tưởng", "viễn tưởng",
     "ứng dụng", "テック", "未来", "SF", "アプリ"):
        ["/Expressive/Futuristic", "/Expressive/Innovative", "/Theme/Techno"],
    ("retro", "nostalgic", "vintage", "western", "hoài cổ", "cổ điển", "xưa", "レトロ", "昭和", "懐かしい"):
        ["/Expressive/Vintage", "/Theme/Woodtype", "/Expressive/Rugged"],
    ("fairy", "folk", "myth", "fable", "artistic", "cổ tích", "dân gian", "huyền thoại", "nghệ thuật", "昔話",
     "民話", "和風", "伝説"):
        ["/Expressive/Artistic", "/Expressive/Sincere", "/Theme/Brush"],
    ("sport", "action", "energy", "fast", "thể thao", "hành động", "năng lượng", "nhanh", "スポーツ", "アクション",
     "元気"):
        ["/Expressive/Active", "/Expressive/Loud", "/Expressive/Excited"],
    ("romance", "love", "poetic", "calm", "lãng mạn", "tình yêu", "thơ", "êm dịu", "bình yên", "恋愛", "ロマンチック",
     "やさしい", "優しい", "静か"):
        ["/Expressive/Calm", "/Expressive/Fancy", "/Expressive/Sincere"],
    ("pixel", "game", "arcade", "trò chơi", "điện tử", "ゲーム", "ドット"): ["/Theme/Pixel", "/Expressive/Playful"],
    ("rugged", "industrial", "street", "punk", "bụi bặm", "công nghiệp", "đường phố", "ストリート", "パンク"):
        ["/Expressive/Rugged", "/Theme/Distressed", "/Expressive/Loud"],
    ("corporate", "business", "trust", "doanh nghiệp", "công ty", "tin cậy", "企業", "ビジネス", "信頼"):
        ["/Expressive/Business", "/Expressive/Competent"],
    ("warm", "cozy", "friendly", "home", "ấm áp", "gần gũi", "thân thiện", "gia đình", "温かい", "家族", "親しみ"):
        ["/Expressive/Sincere", "/Expressive/Calm", "/Expressive/Happy"],
}


def fetch(url, dest, max_age_days=30):
    os.makedirs(CACHE, exist_ok=True)
    if os.path.exists(dest) and time.time() - os.path.getmtime(dest) < max_age_days * 86400:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "rubydai-video-fonts/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest + ".part", "wb") as f:
            f.write(r.read())
        os.replace(dest + ".part", dest)
    except OSError as e:
        if not os.path.exists(dest):
            sys.exit(f"fonts: cannot reach {url.split('/')[2]} ({e}); try again online")
    return dest


def catalogue():
    with open(fetch(CATALOGUE, os.path.join(CACHE, "fontsource.json")), encoding="utf-8") as f:
        return {x["id"]: x for x in json.load(f)}


def tags():
    out = {}
    with open(fetch(TAGS, os.path.join(CACHE, "gf-tags.csv")), encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 4 and row[2].startswith("/"):
                try:
                    out.setdefault(row[0].lower(), {})[row[2]] = float(row[3])
                except ValueError:
                    pass
    return out


def fold(text):
    """NFC and lower case, so a Vietnamese word typed decomposed (a Mac keyboard can send ê + combining marks) matches
    its table entry, and "KIDS" finds "kids"."""
    return unicodedata.normalize("NFC", text).lower()


def phrases(text):
    """The words of a tone and every two-word phrase in it ("kinh dị", "hoạt hình")."""
    ws = [fold(w.strip(" ,.;、。")) for w in text.replace("、", " ").replace("・", " ").split()]
    return {w for w in ws if w} | {f"{x} {y}" for x, y in zip(ws, ws[1:]) if x and y}


def tone_tags(words):
    ws = phrases(words)
    folded = {keys: {fold(k) for k in keys} for keys in TONES}
    found = [t for keys, ts in TONES.items() if ws & folded[keys] for t in ts]
    known = {p for keys in TONES for p in folded[keys] if p in ws}
    unknown = sorted(w for w in ws if " " not in w and not any(w in folded[keys] for keys in TONES)
                     and not any(w in p.split() for p in known))
    return list(dict.fromkeys(found)), unknown


# Vietnamese: Ă Đ Ĩ Ũ Ơ Ư (both cases) and a sample of the stacked and dot-below vowels (ạ ầ ẫ ệ ộ ữ ỹ…) live in the
# vietnamese subset; Â Ê Ô Ã Õ Ý (both cases) in latin.
VIETNAMESE = {"vietnamese": (0x0102, 0x0103, 0x0110, 0x0111, 0x0128, 0x0129, 0x0168, 0x0169, 0x01A0, 0x01A1, 0x01AF,
                             0x01B0, 0x1EA0, 0x1EA1, 0x1EA6, 0x1EA7, 0x1EAA, 0x1EAB, 0x1EC6, 0x1EC7, 0x1ED8, 0x1ED9,
                             0x1EEE, 0x1EEF, 0x1EF8, 0x1EF9),
              "latin": (0x00C2, 0x00E2, 0x00CA, 0x00EA, 0x00D4, 0x00F4, 0x00C3, 0x00E3, 0x00D5, 0x00F5, 0x00DD, 0x00FD)}
# The film's on-screen language -> the subset a font must have, the code points read from its files, how to name them.
LETTERS = {"vi": {"name": "Vietnamese", "subset": "vietnamese", "codes": VIETNAMESE, "show": "Ă Đ Ơ Ư ầ ệ ữ", "lack": "Ơ Ư ầ ệ",
                  "memo": "vietnamese.json", "role_subsets": ["latin", "latin-ext", "vietnamese"]},
           # Japanese: kana and kanji live in ~120 numbered slices on Fontsource; the role loads the whole file instead
           # and the browser's type check renders a kana + kanji test before every render.
           "ja": {"name": "Japanese", "subset": "japanese", "codes": None, "show": "かな カナ 漢字", "lack": "",
                  "memo": None, "role_subsets": None}}


def cmap_codes(woff, wanted):
    """The wanted code points a WOFF 1.0 font really maps to a glyph (its cmap table; stdlib only)."""
    if woff[:4] != b"wOFF":
        return None
    n = struct.unpack(">H", woff[12:14])[0]
    for i in range(n):
        tag, off, comp, orig, _ = struct.unpack(">4sIIII", woff[44 + 20 * i:64 + 20 * i])
        if tag == b"cmap":
            t = woff[off:off + comp]
            cmap = zlib.decompress(t) if comp < orig else t
            break
    else:
        return None
    subs = {}
    for i in range(struct.unpack(">H", cmap[2:4])[0]):
        pid, eid, off = struct.unpack(">HHI", cmap[4 + 8 * i:12 + 8 * i])
        subs[(pid, eid)] = off
    found = set()
    for key in ((3, 10), (0, 4), (3, 1), (0, 3)):
        if key not in subs:
            continue
        o = subs[key]
        fmt = struct.unpack(">H", cmap[o:o + 2])[0]
        if fmt == 12:
            for g in range(struct.unpack(">I", cmap[o + 12:o + 16])[0]):
                lo, hi, _ = struct.unpack(">III", cmap[o + 16 + 12 * g:o + 28 + 12 * g])
                found |= {c for c in wanted if lo <= c <= hi}
            return found
        if fmt == 4:
            seg = struct.unpack(">H", cmap[o + 6:o + 8])[0] // 2
            ends = struct.unpack(f">{seg}H", cmap[o + 14:o + 14 + 2 * seg])
            base = o + 16 + 2 * seg
            starts = struct.unpack(f">{seg}H", cmap[base:base + 2 * seg])
            deltas = struct.unpack(f">{seg}h", cmap[base + 2 * seg:base + 4 * seg])
            ro_at = base + 4 * seg
            ranges = struct.unpack(f">{seg}H", cmap[ro_at:ro_at + 2 * seg])
            for c in wanted:
                for k in range(seg):
                    if starts[k] <= c <= ends[k]:
                        if ranges[k] == 0:
                            gid = (c + deltas[k]) & 0xFFFF
                        else:
                            at = ro_at + 2 * k + ranges[k] + 2 * (c - starts[k])
                            gid = struct.unpack(">H", cmap[at:at + 2])[0]
                            gid = (gid + deltas[k]) & 0xFFFF if gid else 0
                        if gid:
                            found.add(c)
                        break
            return found
    return found


def letters_in_files(fid, f, lang="vi"):
    """True / False from the font's own subset files (a subset label can still lack Ơ Ư or đ); None if unreadable.
    A font whose only subset is latin ships every glyph in that one file, so it is read for all of them."""
    weights = [int(w) for w in f.get("weights", [400])] or [400]
    w = 400 if 400 in weights else weights[0]
    codes = LETTERS[lang]["codes"]
    if f.get("subsets") == ["latin"]:
        codes = {"latin": tuple(c for cs in codes.values() for c in cs)}
    for subset, want in codes.items():
        url = (f"https://cdn.jsdelivr.net/npm/@fontsource/{fid}@{f.get('npmVersion') or 'latest'}"
               f"/files/{fid}-{subset}-{w}-normal.woff")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rubydai-video-fonts/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                found = cmap_codes(r.read(), want)
        except (OSError, ValueError, struct.error, zlib.error):
            return None
        if found is None:
            return None
        if len(found) < len(want):
            return False
    return True


def verify_letters(cands, lang="vi"):
    """{id: True/False/None} for (id, font) pairs, read in parallel, cached for good per version and language.
    A language without code points to read (ja) is left to the browser's type check: None for every font."""
    if not LETTERS[lang]["codes"]:
        return {fid: None for fid, _ in cands}
    memo_path = os.path.join(CACHE, LETTERS[lang]["memo"])
    try:
        with open(memo_path, encoding="utf-8") as fh:
            memo = json.load(fh)
    except (OSError, ValueError):
        memo = {}
    key = lambda fid, f: f"{fid}@{f.get('npmVersion') or 'latest'}"
    todo = [(fid, f) for fid, f in cands if key(fid, f) not in memo]
    if todo:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as pool:
            for (fid, f), ok in zip(todo, pool.map(lambda c: letters_in_files(*c, lang), todo)):
                if ok is not None:
                    memo[key(fid, f)] = ok
        os.makedirs(CACHE, exist_ok=True)
        with open(memo_path, "w", encoding="utf-8") as fh:
            json.dump(memo, fh)
    return {fid: memo.get(key(fid, f)) for fid, f in cands}


def github_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rubydai-video-fonts/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


WEIGHT_NAMES = {"Thin": 100, "ExtraLight": 200, "Light": 300, "Regular": 400, "Medium": 500, "SemiBold": 600,
                "Bold": 700, "ExtraBold": 800, "Black": 900}


def whole_files(family):
    """{weight or 'var': pinned URL} of a family's whole font files in the Google Fonts repository (ofl/), the commit
    pinned so a re-render loads the same bytes; {} when the family is not there."""
    folder = "".join(ch for ch in family.lower() if ch.isalnum())
    try:
        listing = github_json(GF_CONTENTS.format(dir=folder))
        sha = github_json(GF_COMMIT)["sha"]
    except (OSError, ValueError, KeyError):
        return {}
    out = {}
    for x in listing if isinstance(listing, list) else []:
        name = x.get("name", "")
        if not name.endswith((".ttf", ".otf")) or "Italic" in name:
            continue
        url = GF_FILE.format(sha=sha, dir=folder, name=name)
        if "[" in name:
            out["var"] = url
        else:
            out[WEIGHT_NAMES.get(name.rsplit("-", 1)[-1].split(".")[0], 0) or name] = url
    return {k: v for k, v in out.items() if k == "var" or isinstance(k, int)}


def cmd_search(a):
    a.n = max(1, min(a.n, 40))                   # each result's font file is read for the language's letter check
    lang = getattr(a, "lang", None) or "vi"
    L = LETTERS.get(lang)
    want, unknown = tone_tags(a.tone)
    if not want:
        sys.exit(f"fonts: no known tone in '{a.tone}'; see: python3 tools/fonts.py tones")
    cat, tg = catalogue(), tags()
    rows = []
    for fid, f in cat.items():
        if not open_licence(f.get("license")) or f.get("category") == "icons":
            continue
        if lang == "ja":                         # Japanese faces: the japanese subset, never a hentaigana-only face
            if "japanese" not in f.get("subsets", []) or "hentaigana" in fid:
                continue
        else:
            other = {x for x in f.get("subsets", []) if x not in ("latin", "latin-ext", "cyrillic", "cyrillic-ext", "greek",
                                                                  "greek-ext", "vietnamese", "math", "symbols")}
            if f.get("defSubset") not in ("latin", "latin-ext") or any(x in fid for x in other) or \
                    fid.endswith(("-jp", "-kr", "-sc", "-tc", "-hk", "-thai", "-arabic", "-hebrew", "-devanagari")) or \
                    "hentaigana" in fid:
                continue                         # made for another script (Noto Sans Avestan, IBM Plex Sans Devanagari…)
            if L and not a.latin_only and L["subset"] not in f.get("subsets", []):
                continue                         # vi needs the vietnamese subset (then read for the letters)
        if fid in COMMON and not a.allow_common:
            continue
        if a.category and f.get("category") != a.category:
            continue
        if a.role == "text" and f.get("category") not in ("serif", "sans-serif"):
            continue
        t = tg.get(f["family"].lower(), {})
        score = sum(t.get(w, 0) for w in want) / len(want)
        if a.role == "text":                       # a text face must also read: calm, competent, business
            score = 0.6 * score + 0.4 * (t.get("/Expressive/Calm", 0) + t.get("/Expressive/Competent", 0)) / 2
            if len(f.get("weights", [])) < 2 and not f.get("variable"):
                continue
        if score > 0:
            rows.append((score, fid, f))
    rows.sort(key=lambda r: (-r[0], r[1]))
    seen, kept = set(), []                       # one face per family stem (Rubik Distressed, Rubik Wet Paint…)
    for r in rows:
        stem = r[2]["family"].split()[0].lower()
        if stem not in seen:
            seen.add(stem)
            kept.append(r)
    if not a.category:                           # spread the shortlist across categories, best first in each
        by = {}
        for r in kept:
            by.setdefault(r[2]["category"], []).append(r)
        top = kept[0][0] if kept else 0          # a category joins the spread only with a real fit (≥ 40% of the best)
        order = [c for c in sorted(by, key=lambda c: -by[c][0][0]) if by[c][0][0] >= 0.4 * top]
        mixed = []
        while any(by[c] for c in order) and len(mixed) < a.n:
            for c in order:
                if by[c] and len(mixed) < a.n:
                    mixed.append(by[c].pop(0))
        kept = sorted(mixed, key=lambda r: -r[0]) + [r for c in order for r in by[c]]
    rows = kept
    if unknown:
        print(f"(not a known tone word: {', '.join(unknown)})")
    what = f"with a {L['name']} subset" + (f" (each one shown checked for {L['show']})" if L["codes"] else "") if L else ""
    print(f"tone: {', '.join(w.split('/')[-1] for w in want)} · {len(rows)} open fonts {what}"
          + (" (fonts AI designs overuse left out)" if not a.allow_common else ""))
    shown, dropped = 0, []
    pool = rows[:3 * a.n]
    checked = {} if a.latin_only or not L else verify_letters([(fid, f) for _, fid, f in pool], lang)
    for score, fid, f in pool:
        if shown >= a.n:
            break
        ok = True if a.latin_only or not L or not L["codes"] else checked.get(fid)
        if ok is False:
            dropped.append(fid)
            continue
        var = "variable" if f.get("variable") else f"{len(f.get('weights', []))} weights"
        print(f"  {fid:<28} {f['category']:<11} {score:5.1f}  {var:<11} {f['license']}"
              + ("" if ok else f"  ({L['name']} letters not verified)"))
        shown += 1
    if dropped:
        print(f"(left out, missing {L['lack']} in the font itself: {', '.join(dropped)})")
    print(f"next: python3 tools/fonts.py role <id>{'' if lang == 'vi' else ' --lang ' + lang}  (the TYPE role for film.html, version pinned)")


def cmd_role(a):
    req = urllib.request.Request(f"{CATALOGUE}/{a.id}", headers={"User-Agent": "rubydai-video-fonts/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            f = json.load(r)
    except OSError as e:
        sys.exit(f"fonts: cannot read {a.id} ({e})")
    if not open_licence(f.get("license")):
        sys.exit(f"fonts: {a.id} is {f.get('license')}, not an open licence")
    lang = getattr(a, "lang", None) or "vi"
    L = LETTERS.get(lang)
    n = L["name"] if L else "Latin"
    if lang == "ja":
        if "japanese" not in f.get("subsets", []):
            sys.exit(f"fonts: {a.id} has no japanese subset")
        files = whole_files(f["family"])
        if not files:
            sys.exit(f"fonts: the whole files of {f['family']} are not in the Google Fonts repository (or it cannot be "
                     f"reached): pick another face, or download the font into fonts/ and give the role local files")
        role = {"family": f["family"], "files": {str(k): v for k, v in sorted(files.items(), key=lambda kv: str(kv[0]))}}
        if "var" in files:
            role["axes"] = {"wght": [min(int(w) for w in f.get("weights", [400])), max(int(w) for w in f.get("weights", [400]))]}
        print(json.dumps(role, ensure_ascii=False))
        print(f"{f['family']} · {f.get('category')} · {f.get('license')} · Japanese (whole files, {len(files)} file(s), a few MB "
              f"each, pinned; the type check renders kana and kanji before every render) · log it in LICENSES.csv")
        return
    checked = verify_letters([(a.id, f)], lang)[a.id] if L and L["subset"] in f.get("subsets", []) else False
    has = checked is not False
    have = [int(w) for w in f.get("weights", [400])]
    pick = [w for w in (400, 700, 900) if w in have] or have[:2]   # static cuts: every family ships them, pinned
    role = {"family": f["family"], "pkg": f["id"], "version": f.get("npmVersion"), "weights": pick,
            "subsets": L["role_subsets"] if L and has else ["latin", "latin-ext"]}
    print(json.dumps(role, ensure_ascii=False))
    status = (f"{n} letters" if checked else f"{n} letters NOT VERIFIED (the font file could not be read)" if has
              else f"NO {n} letters (latin only)") if L else "Latin (no letter check)"
    print(f"{f['family']} · {f.get('category')} · {f.get('license')} · {status}"
          f" · source {f.get('source', 'fontsource')} · log it in LICENSES.csv")


def cmd_tones(a):
    for keys, ts in TONES.items():
        print(f"{' / '.join(keys[:4])} -> {', '.join(t.split('/')[-1] for t in ts)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("search")
    p.add_argument("tone", help="the film's tone in a few words (Vietnamese, English or Japanese)")
    p.add_argument("--role", choices=["display", "text"], default="display")
    p.add_argument("--category", choices=["serif", "sans-serif", "display", "handwriting", "monospace"])
    p.add_argument("--n", type=int, default=10, help="how many (at most 40)")
    p.add_argument("--latin-only", action="store_true")
    p.add_argument("--lang", choices=["vi", "ja", "en"], default="vi", help="the on-screen language whose letters are checked")
    p.add_argument("--allow-common", action="store_true", help="include the fonts AI designs overuse (needs a reason)")
    p.set_defaults(fn=cmd_search)
    p = sub.add_parser("role")
    p.add_argument("id", help="the Fontsource id from search, e.g. shrikhand")
    p.add_argument("--lang", choices=["vi", "ja", "en"], default="vi", help="the on-screen language whose letters are checked")
    p.set_defaults(fn=cmd_role)
    sub.add_parser("tones").set_defaults(fn=cmd_tones)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    if os.name == "nt" and not sys.flags.utf8_mode:   # Windows reads, writes and prints in a legacy code page
        import subprocess
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=dict(os.environ, PYTHONUTF8="1")))
    for _s in (sys.stdin, sys.stdout, sys.stderr):
        getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")
    main()
