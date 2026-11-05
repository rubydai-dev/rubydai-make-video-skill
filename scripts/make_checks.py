#!/usr/bin/env python3
"""The measured checks make.py prints after a render (rhythm, darkness, palette, sound budget, clichés, ending,
motion, A/V start, the report lines): pure functions of what they are given, no project state. make.py re-exports
every name, so tools and tests call them as make.<name>. Python 3 standard library + ffmpeg."""
from pathlib import Path
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write_text  # noqa: E402  (the kit's shared helpers, same folder)


def animatic_made(video):
    """An animatic is the file animatic.py made (its name and its bytes in renders/.animatics.json), never a cut that
    only carries the word in its name."""
    try:
        made = json.loads((Path(video).parent / ".animatics.json").read_text(encoding="utf-8"))
        return made.get(Path(video).name) == hashlib.sha1(Path(video).read_bytes()).hexdigest()
    except (OSError, ValueError, AttributeError):
        return False


def even(x):
    return max(2, int(round(x / 2)) * 2)


def tempo_card(state):
    return re.search(r"\*\*Tempo[^*]*\*\*\s*([^·\n]+)", state, re.I) or re.search(r"\btempo\b:?\s*([^·\n]+)", state, re.I)


TEMPO = {"energetic": 4, "enerjik": 4, "tempolu": 4, "standard": 6, "standart": 6, "contemplative": 10, "sakin": 10}


def rhythm_line(bounds, state):
    """The scene lengths against the card's tempo: an even beat (every scene alike) reads as monotony, and a card
    that says energetic while the scenes run long reads as a promise not kept."""
    lens = [b - a for a, b in zip(bounds, bounds[1:]) if b > a]
    if len(lens) < 5:
        return ""
    mean = sum(lens) / len(lens)
    spread = (sum((x - mean) ** 2 for x in lens) / len(lens)) ** 0.5 / mean
    notes = []
    alike = max(sum(1 for x in lens if abs(x - y) <= 0.15 * y) for y in lens)
    if len(lens) >= 6 and (spread < 0.2 or alike > 0.6 * len(lens)):     # a few long scenes may well match
        notes.append(f"EVEN RHYTHM: {alike} of {len(lens)} scenes run about the same length (spread {spread:.2f}); "
                     "vary them with the beat types: short runs against long holds")
    card = tempo_card(state)
    want = next((v for k, v in TEMPO.items() if card and re.search(rf"\b{k}\b", card[1], re.I)), None)
    if want and mean > want * 1.5:
        notes.append(f"TEMPO: the card says about {want} s a scene; the scenes average {mean:.1f} s")
    return " · ".join(notes)


def too_dark_line(video):
    """A film that is dark almost everywhere and never opens up reads as mud on a phone. Low-key is fine; a film with
    no bright stretch at all is not. Letterbox bars are left out (the middle 70 % of the height is measured)."""
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(video), "-vf",
                            "fps=2,crop=iw:ih*0.7,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                            "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    def lstar(y):
        y = min(max((y - 16) / 219, 0), 1) ** 2.4
        return 116 * y ** (1 / 3) - 16 if y > 0.008856 else 903.3 * y
    L = sorted(lstar(float(l.split("=")[1])) for l in r.stdout.splitlines() if "YAVG=" in l)
    if len(L) < 10:
        return ""
    dark, p90 = sum(x < 20 for x in L) / len(L), L[int(len(L) * 0.9)]
    return (f"TOO DARK: {dark:.0%} of the film is near black and even its brightest tenth sits at L* {p90:.0f}: on a phone "
            f"it reads as mud. Lift the mid-tones of the subject, or give the film a stretch that opens up (a few seconds at L* 50 "
            f"or more); low-key stays, as a choice") if dark > 0.70 and p90 < 35 else ""


def ai_palette_line(video):
    """More than 30 % of the film on the blue-to-violet backgrounds generated design reaches for (a purple gradient, an
    indigo glow) reads as AI slop. A brand that is purple keeps it, named on the card."""
    import colorsys
    w, h = 48, 27
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=1,scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = w * h * 3
    frames = [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]
    if not frames:
        return ""
    def violet(f):
        hits = 0
        for i in range(0, n, 3):
            hue, sat, val = colorsys.rgb_to_hsv(f[i] / 255, f[i + 1] / 255, f[i + 2] / 255)
            hits += 225 <= hue * 360 <= 290 and sat > 0.30 and val > 0.18
        return hits / (w * h) > 0.40
    share = sum(violet(f) for f in frames) / len(frames)
    return (f"AI PALETTE: {share:.0%} of the film sits on a blue-to-violet ground, the palette generated design reaches "
            f"for; give the film its own ground from its references (a brand that is purple keeps it: name it on the "
            f"card and show the draft anyway)") if share > 0.30 else ""


def sound_budget_line(info, bounds):
    """Designed sounds are accents: a whoosh twice is striking and by the fifth it is noise, the big riser into a hit
    lands once or twice a film, and a sound on every cut is a cluttered layer, not design (measured on professional
    launch films: their designed sounds sit on the moments that carry meaning; the music carries the rest)."""
    sfx = info.get("sfx") or []
    dur = info["frames"] / info["fps"]
    if not sfx or dur <= 0:
        return ""
    whoosh = [e for e in sfx if e[1] in ("whoosh", "air")]
    risers = [e for e in sfx if e[1] == "riser"]
    w_max, r_max = max(2, round(2 * dur / 30)), max(2, round(dur / 30))
    peak = lambda e: e[0] + ((e[2] or 0.7) / 2 if e[1] in ("whoosh", "air") else 0)
    cuts = [b for b in bounds[1:-1]] if bounds else []
    on_cut = [c for c in cuts if any(-0.15 <= peak(e) - c <= 0.15 for e in sfx if e[1] in ("whoosh", "air", "hit", "riser"))]
    why = []
    if len(whoosh) > w_max:
        why.append(f"{len(whoosh)} whooshes in {dur:.0f} s (at most {w_max}: keep them for the cuts that carry meaning)")
    if len(risers) > r_max:
        why.append(f"{len(risers)} risers (at most {r_max}: the riser into a hit is the film's one or two big moments)")
    if len(cuts) >= 4 and len(on_cut) / len(cuts) > 0.7:
        why.append(f"a designed sound on {len(on_cut)} of {len(cuts)} cuts (most cuts ride on the music; a sound on every "
                   f"cut is clutter)")
    return ("SOUND SLOP: " + "; ".join(why) + ". Score the rest with the music and the picture's own sounds "
            "(references/sound.md §5)") if why else ""


CHOICE_WORDS = re.compile(r"\b(silent|im lặng|không lời|music[\s-]only|only music|chỉ có nhạc|chỉ nhạc)\b", re.I)


NOT_CHOICE = re.compile(r"\b(not|no|never|without|không|chẳng)\b", re.I)


def sound_by_choice(state):
    """A film silent or music-only by choice says so on its card's sound line ("- **Sound (Q4):** music only, by
    choice", "**Ses / Sound:** sessiz film"); a note elsewhere ("B03 is silent; add the impact") or a negation ("not
    silent") never waives the sound checks."""
    for line in state.splitlines():
        label = re.match(r"\s*[-*]?\s*\*\*([^*]*?)\*\*:?(.*)$", line)
        if not label or not re.search(r"\b(sound|âm thanh)\b", label[1], re.I):
            continue
        for clause in re.split(r"[;,·(]", label[2]):           # "music only; no effects": the "no" is about effects
            m = CHOICE_WORDS.search(clause)
            if not m:
                continue
            before = re.findall(r"[\w']+", clause[:m.start()])[-2:]      # "not silent", "not really silent"
            if not any(NOT_CHOICE.fullmatch(w) for w in before) and not re.match(r"\s*(?:not|thì không)\b", clause[m.end():]):
                return True
    return False


def peaks(path, step=0.1):
    """The peak of each 0.1 s of a sound file, in dBFS (silence -120)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af",
                        f"aresample=48000,asetnsamples=n={int(48000 * step)}:p=0,astats=metadata=1:reset=1,"
                        "ametadata=mode=print:key=lavfi.astats.Overall.Peak_level:file=-", "-f", "null", "-"],
                       capture_output=True, text=True)
    out = []
    for v in re.findall(r"Peak_level=(\S+)", r.stdout):
        try:
            out.append(max(-120.0, float(v)))
        except ValueError:
            out.append(-120.0)
    return out


CLICHES = {   # the moves that make a film read as a template (named on the card with a reason, they are fine)
    "particle burst": r"(particle|confetti|spark)s?\w*[^\n]{0,60}(burst|explo)|(burst|explo)\w*[^\n]{0,60}particle",
    "RGB split": r"rgb ?split|chromatic|channel ?(shift|offset)|aberration",
    "lens flare": r"flare",
    "neon glow": r"neon|shadowBlur\s*=\s*(\d{3}|[3-9]\d)\b",
    "glitch": r"glitch",
    "elastic or bounce easing": r"elastic|bounce(Out|In)|easeOutBounce",
}


def cliche_line(film, state):
    """The template clichés the film's own code uses (particle bursts, RGB split, flares, neon glow, glitch, elastic
    easing) that the director card does not name with a reason (references/looks.md §8)."""
    try:
        src = Path(film).read_text(encoding="utf-8")
    except OSError:
        return ""
    a = src.find("// ============================== FILM")
    b = src.find("// ============================== HELPERS", a + 1)
    code = src[a:b] if a >= 0 else ""
    card = state.lower()
    used = [name for name, rx in CLICHES.items() if re.search(rx, code, re.I) and name.split()[0].lower() not in card]
    return ("cliché: " + ", ".join(used) + " in the film's code: each reads as a template unless the director card names "
            "it with its reason from this story; otherwise take it out (references/looks.md §8)") if used else ""


VOICES = r"\b(pad|drone|pluck|lead|bell|arp|kick|snare|hat|clap|sub808|bass|stab|swell|riser|organ|strings|choir)\s*\("


def music_palette(film):
    """The film's recorded instruments (INSTRUMENTS) and the synth voices its score() calls."""
    try:
        src = Path(film).read_text(encoding="utf-8")
    except OSError:
        return set()
    m = re.search(r"INSTRUMENTS\s*=\s*\[([^\]]*)\]", src)
    names = set(re.findall(r"['\"]([\w-]+)['\"]", m[1])) if m else set()
    a = src.find("function score(")
    b = src.find("\n}\n", a) if a >= 0 else -1
    if a >= 0:
        names |= set(re.findall(VOICES, src[a:b if b > 0 else None]))
    return names


NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def progression_shape(film):
    """The score's chord loop as a shape, the same in any key: each root in semitones above the first, 'm' on minor
    chords (Am F C G and Fm9 Dbmaj7 Ab Eb are both '0m 8 3 10')."""
    try:
        src = Path(film).read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"const prog\w*\s*=\s*\[([^\]]*)\]", src)
    chords = re.findall(r"['\"]([A-G])([#b]?)([^'\"]*)['\"]", m[1]) if m else []
    if len(chords) < 3:
        return ""
    roots = [(NOTE[n] + (1 if acc == "#" else -1 if acc == "b" else 0)) % 12 for n, acc, _ in chords]
    minor = [bool(re.match(r"m(?!aj)", q)) for _, _, q in chords]
    return " ".join(f"{(r - roots[0]) % 12}{'m' if mi else ''}" for r, mi in zip(roots, minor))


def picked_files(said):
    """The recordings a Music line names: backticked or double-quoted paths, then each unquoted path with its spaces,
    from the word that starts it (a folder) or without the words before it (recording, own, and, ...)."""
    audio = r"\.(?:mp3|wav|ogg|flac|m4a|aac)\b"
    said = re.sub(r"\(\s*(?:user|người dùng)\s*\)", " ", said, flags=re.I)
    found = re.findall(r"`([^`\n]+" + audio + r")`", said, re.I) + re.findall(r'"([^"\n]+' + audio + r')"', said, re.I)
    rest = re.sub(r"`[^`\n]*`|\"[^\"\n]*\"", " , ", said)
    for m in re.findall(r"(?:(?![^\s,;]*" + audio + r")[^\s,;]+ )*[^\s,;]+" + audio, rest, re.I):
        words = m.split(" ")
        folder = next((k for k, w in enumerate(words) if "/" in w or "\\" in w), None)
        if folder is not None:
            words = words[folder:]
        while len(words) > 1 and re.fullmatch(r"(?i)recording|bản thu|own|của tôi|track|bài|bài hát|song|music|nhạc|the|a|"
                                              r"and|và|với|&|plus|with|or|hoặc", words[0].strip(":,")):
            words = words[1:]
        found.append(" ".join(words))
    return found


def old_cg_line(state):
    """The card's code-fit line may not route a 3D world through flat polygons (looks.md §5, What reads as old CG)."""
    fit = re.search(r"\*\*(Kod uyumu|Code fit)[^*]*\*\*:?\s*([^\n]+)", state, re.I)
    flat = re.search(r"low[\s-]?poly|flat[\s-]shad\w*|đa giác phẳng|đổ bóng phẳng", fit[2], re.I) if fit else None
    if not flat:
        return ""
    return (f"OLD CG ROUTE: the card's code fit draws its 3D in \"{flat[0]}\"; flat, untextured polygons read as 1990s CG. "
            "Route each 3D world through three.js (light, shadows, materials) or a named drawn medium with its texture "
            "on every face (quick-mode.md Renderer), rewrite the line and redraw before the user sees a still")


def view_line(film, state):
    """The card's Camera line chooses the view (quick-mode.md §2); the code has to draw in it."""
    cam = re.search(r"\*\*(Kamera|Camera)[^*]*\*\*\s*([^\n]+)", state, re.I)
    if not cam:
        return ""
    try:
        src = Path(film).read_text(encoding="utf-8")
    except OSError:
        return ""
    line = cam.group(2).lower()
    if re.search(r"perspekti|perspective|\bview\b", line) and "VIEW.of(" not in src:
        return ("VIEW: the card chose perspective, but the code draws in flat planes: stand the camera in the world with "
                "VIEW.of(CAM.path(keys, t), S) (templates/quick/HELPERS.md)")
    if not re.search(r"perspective|phối cảnh|\bview\b|flat|phẳng|plane|three\.?js|frontal|chính diện", line):
        return ("VIEW: the card's Camera line names no view: perspective (the camera looks along or around something), "
                "flat planes (frontal staging) or three.js (lit solids)")
    return ""


def narration_line(film, dur):
    """A narrated film over a minute: the first line within 2 s (writing.md §14); a late voice loses the opening."""
    try:
        src = Path(film).read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"const VO = \[\s*\{[^}]*?\bat:\s*([\d.]+)", src)
    if dur < 60 or not m or float(m[1]) <= 2.0:
        return ""
    return f"NARRATION LATE: the first line starts at {float(m[1]):.1f} s; in a film this long it starts within 2 s"


def colour_line(video, state):
    """Most public code-made films barely use colour (measured October 2026: 56 % of 300 frames from 703 public Opus 5.5
    films had no saturated colour on more than 3 % of the frame). A film that sits there reads as the average, unless
    it is monochrome by choice and the card says so."""
    import colorsys
    if re.search(r"monochrome|black[ -]and[ -]white|siyah[ -]?beyaz|greyscale|grayscale|duotone", state, re.I):
        return ""
    w, h = 48, 27
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=1,scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = w * h * 3
    frames = [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]
    if len(frames) < 3:
        return ""
    def share(f):
        hits = 0
        for i in range(0, n, 3):
            _, sat, val = colorsys.rgb_to_hsv(f[i] / 255, f[i + 1] / 255, f[i + 2] / 255)
            hits += sat > 0.45 and val > 0.35
        return hits / (w * h)
    shares = sorted(share(f) for f in frames)
    best = shares[int(len(shares) * 0.9)]
    return (f"colour: the film barely uses colour (its most colourful tenth has {best:.0%} saturated pixels), like more "
            f"than half of the public code-made films; let the palette's colour own part of the frame at the key "
            f"moments, or name monochrome on the card (references/looks.md §8)") if best < 0.06 else ""


def seconds_of(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def clock(x):
    m = re.match(r"(?:(\d+):)?(\d+(?:\.\d+)?)$", x.strip())
    return int(m[1] or 0) * 60 + float(m[2]) if m else None


def ending_need(dur):
    return 2.0 if dur <= 60 else 4.0 if dur <= 180 else 6.0


def ending_line(spans, dur):
    """The ending the film chose (writing.md §15) needs its own time after the last line: a film cut to fit its runtime
    loses the held image, the card or the silence it planned."""
    if not spans or dur < 10:
        return ""
    need = ending_need(dur)
    last = max(e for _, e in spans)
    if dur - last >= need - 0.05:
        return ""
    return (f"ENDING SHORT: the last line ends at {last:.1f} s and the film at {dur:.1f} s; the ending it chose (a held "
            f"image, a card, a silence: STATE.md) needs about {need:g} s after it (writing.md §15). Let the film run "
            "longer or bring the last lines earlier; the ending is never cut to fit the runtime")


def motion_per_second(video):
    """Mean frame difference per second (0-255, small grey copy): how much the picture moves."""
    try:
        out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf",
                              "fps=5,scale=160:-2,format=gray,tblend=all_mode=difference,signalstats,"
                              "metadata=print:key=lavfi.signalstats.YAVG:file=-", "-an", "-f", "null", "-"],
                             capture_output=True, text=True, timeout=600).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    v = [float(x) for x in re.findall(r"YAVG=([\d.]+)", out)]
    return [sum(v[i:i + 5]) / len(v[i:i + 5]) for i in range(0, len(v), 5)]


def rests_line(video, spans, dur, bounds, texts=()):
    """A report, never a hold, for a narrated film over a minute: how much of it the voice carries (over 3 minutes,
    minute by minute when it thins), and where voice and picture rest together: the voice silent for 8 s or more while
    the picture is calmer than the film's middle and barely cuts (writing.md §15: voice and picture take turns)."""
    telling = sorted(list(spans) + list(texts))
    if not telling or dur <= 60:
        return ""
    said, merged = [], []
    for s, e in sorted(spans):                   # overlapping lines are counted once
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    share = sum(e - s for s, e in merged) / dur
    if spans and dur > 180 and share < 0.5:
        per_min = [sum(max(0, min(e, m + 60) - max(s, m)) for s, e in spans) for m in range(0, int(dur), 60)]
        said.append(f"the voice speaks {share:.0%} of the film (" + " · ".join(f"min {i + 1}: {x:.0f} s" for i, x in
                    enumerate(per_min)) + "); a long narrated film rests more than it speaks, so check the word budget "
                    "(writing.md §5)")
    reach, gaps = 0.0, []                        # the stretches where neither the voice nor a word on screen tells
    for s, e in telling:
        if s - reach >= 8 and reach > 0:
            gaps.append((reach, s))
        reach = max(reach, e)
    tail_end = dur - (2.0 if dur <= 60 else 4.0 if dur <= 180 else 6.0)        # the ending keeps its own seconds
    if tail_end - reach >= 8:
        gaps.append((reach, tail_end))
    motion = motion_per_second(video) if gaps else []
    if motion:
        middle = sorted(motion)[len(motion) // 2] or 1e-6
        found = []
        for a, b in gaps:
            seg = motion[int(a):max(int(a) + 1, int(b))]
            ratio = sum(seg) / len(seg) / middle if seg else 1
            cuts = sum(1 for x in bounds[1:-1] if a < x < b)
            if ratio < 1.0 and cuts <= max(1, int((b - a) // 8)):
                found.append(f"{int(a // 60)}:{a % 60:04.1f}-{int(b // 60)}:{b % 60:04.1f} ({b - a:.0f} s, picture "
                             f"{ratio:.1f}x the film's motion, {cuts} cut{'s' if cuts != 1 else ''})")
        if found:
            said.append(("voice, words and picture rest together at " if texts else "voice and picture rest together at ") + " · ".join(found[:6]) + "; a marked hold or a key "
                        "moment is fine, elsewhere give the picture an event or the voice a line")
    return ("PACE (a report, not a hold): " + "; ".join(said)) if said else ""


def end_card_line(bounds, state):
    """An ad's end card holds 2.5-4 s (purpose-ad.md §4): held longer, it takes the seconds the payoff should have had."""
    if len(bounds) < 3 or not re.search(r"\*\*Purpose:\*\*\s*ad", state, re.I):
        return ""
    last = bounds[-1] - bounds[-2]
    return (f"LONG END CARD: the last scene holds {last:.1f} s; an ad's end card holds 2.5-4 s (purpose-ad.md §4): "
            f"start it at about {bounds[-1] - 3.5:.1f} s and give the seconds before it to the payoff") if last > 4.05 else ""


def bounds_of(info):
    b = info.get("bounds") or []
    dur = info["frames"] / info["fps"]
    b = sorted({round(float(x), 3) for x in b if 0 <= float(x) <= dur} | {0.0, round(dur, 3)})
    return b if len(b) > 2 else []


def lead_silence(path, start=0.0, length=None):
    """Seconds of silence (under -45 dBFS) before a sound file, or its trimmed part, is first heard."""
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-ss", f"{start}"] + (["-t", f"{length}"] if length else []) + \
          ["-i", str(path), "-af", "silencedetect=n=-45dB:d=0.005", "-f", "null", "-"]
    err = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="replace").stderr
    m = re.search(r"silence_start: (-?[\d.e-]+)\s.*?silence_end: ([\d.]+)", err, re.S)
    return float(m[2]) if m and abs(float(m[1])) < 0.002 else 0.0


def av_start_line(video):
    """The delivered file's sound and picture start together: their streams' start times may differ by half a frame
    (20 ms) at most, or every hit in the film lands that much off."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,start_time", "-of", "csv=p=0",
                        str(video)], capture_output=True, text=True)
    starts = {}
    for line in r.stdout.split():
        kind, _, at = line.partition(",")
        try:
            starts.setdefault(kind, float(at))
        except ValueError:
            continue
    if "audio" not in starts or "video" not in starts or abs(starts["audio"] - starts["video"]) <= 0.02:
        return ""
    return (f"AV OFFSET: the sound starts {starts['audio'] - starts['video']:+.3f} s from the picture in {Path(video).name}; "
            "remux with both streams from 0 (master_audio.py does) and check again")


def own_music_file(src):
    """The file OWN_MUSIC plays, read between its own quotes (an apostrophe inside double quotes is part of the name)."""
    m = re.search(r"OWN_MUSIC\s*=\s*\{[^}]*?\bfile\s*:\s*(['\"`])((?:\\.|(?!\1).)*)\1", src, re.S)
    return re.sub(r"\\(.)", r"\1", m[2]) if m else ""


def same_path(a, b):
    return Path(str(a).replace("\\", "/")).as_posix().lstrip("./") == Path(str(b).replace("\\", "/")).as_posix().lstrip("./")


def small_sheet(step, qc_dir):
    """The sheet qc.py all drew, scaled to about 0.9 megapixels: small enough for the chat, large enough to judge."""
    src, dst = qc_dir / "sheet.jpg", qc_dir / "sheet-small.jpg"
    _, wh = step.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                      "-of", "csv=s=x:p=0", src])
    iw, ih = (int(x) for x in wh.strip().split("x"))
    width = min(1024, iw, int((900_000 * iw / ih) ** 0.5)) // 2 * 2
    step.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", src,
              "-vf", f"scale={width}:-2", "-q:v", "4", "-update", "1", dst])
    return dst


def report_lines(report, bounds):
    text = report.read_text(encoding="utf-8", errors="replace") if report.exists() else ""
    hook = "PASS" if re.search(r"^\s+PASS\s*$", text, re.M) else "FAIL"
    flags, stats = [], {}
    for kind, head in (("action", "== action per scene"), ("sound", "== sound per scene")):
        sec = text.split(head, 1)[1].split("\n==", 1)[0] if head in text else ""
        rows = [l for l in sec.splitlines() if re.match(r"\s+#\d+", l)]
        bad = [l.strip() for l in rows if not l.rstrip().endswith("ok")]
        stats[kind] = (len(bad), len(rows))
        flags.append(f"{kind} {len(bad)} flag{'s' if len(bad) != 1 else ''}" + (": " + "; ".join(
            re.sub(r"\s{2,}", " ", b) for b in bad[:3]) if bad else ""))
    issues = []
    for head, label in (("== black intervals", "black"), ("== frozen intervals", "frozen")):
        sec = text.split(head, 1)[1].split("\n==", 1)[0] if head in text else ""
        hits = [l for l in sec.splitlines()[1:] if l.strip() and not l.startswith("(") and l.strip() != "none"]
        body = "\n".join(hits)                   # freezedetect prints start, duration and end on separate lines
        found = [(float(m[0]), float(m[1]))
                 for m in re.findall(r"_start:\s*([\d.]+)(?:(?!_start)[\s\S])*?_end:\s*([\d.]+)", body)]
        spans = [f"{x:.1f}–{y:.1f} s" for x, y in found]
        if hits:
            issues.append(f"{label} " + (", ".join(spans[:3]) if spans else str(len(hits))))
        if label == "black" and spans and spans[0].startswith("0.0–"):
            issues.append("OPENS DARK: if this is a fade from black, the hook rule is broken (a dark scene "
                          "with visible action is fine; check the strip)")
        end = bounds[-1] if bounds else max((y for _, y in found), default=0)   # the film's end, not the last black
        inside = [(x, y) for x, y in found if label == "black" and x > 0.05 and y - x > 1.0 and y < end - 0.05]
        if inside:
            issues.append("LONG BLACK " + ", ".join(f"{x:.1f}–{y:.1f} s" for x, y in inside[:3]) + ": black is "
                          "punctuation (< 1 s); a line there needs its image, unless it is a card (purpose-cinematic.md §5)")
    rep = re.search(r"repeated compositions[^:]*: (\d+) repeats?, (\d+) s of (\d+)", text)
    if rep and int(rep[1]):
        at = re.findall(r"(\d\d:\d\d)\.00-\d\d:\d\d\.00 repeats (\d\d:\d\d)", text)
        issues.append(f"repeated pictures {rep[2]} s" + (": " + ", ".join(f"{x} = {y}" for x, y in at[:3]) if at else ""))
    still, windows = stats.get("action", (0, 0))
    if windows and still / windows > 0.45:          # calm films sit near 30 %; a frozen one passes half
        issues.append(f"TOO STILL: {still} of {windows} windows show nothing acting")
    if rep and int(rep[3]) and int(rep[2]) / int(rep[3]) > 0.1:
        issues.append(f"TOO REPETITIVE: {rep[2]} of {rep[3]} s repeat earlier pictures")
    pops = re.search(r"one-frame pops[^:]*: (\d+)", text)
    if pops and int(pops[1]):
        at = re.findall(r"frame \d+ \((\d\d:\d\d\.\d\d)\)", text)
        issues.append(f"one-frame pops {pops[1]}" + (f" at {', '.join(at[:3])}" if at else ""))
    dup = re.search(r"duplicates: (\d+)", text)
    if dup and int(dup[1]):
        issues.append(f"duplicate frames {dup[1]}")
    if not bounds:
        flags.append("per-scene checks on 2 s windows (the page gives no scene bounds)")
    return hook, flags, issues


def wants_loop(state):
    return bool(re.search(r"\*\*Loop:\*\*\s*yes", state, re.I))


def cover_platforms(state):
    m = re.search(r"\*\*Delivered to:\*\*\s*([^\n*]+)", state)
    if not m or m[1].strip().startswith("<"):
        return []
    return [p for p in ("X", "Slack", "Discord") if re.search(rf"\b{p}\b", m[1], re.I if p != "X" else 0)]


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


def delivers(hook, master_ok, rc, avoff, weak, show_anyway):
    """A render is delivered when its hook, master and checks pass and its sound and picture start together; the soft
    holds (stillness, repeats, sound and look flags) give way after one fix pass, a broken file never does."""
    return hook == "PASS" and master_ok and rc == 0 and not avoff and not (weak and not show_anyway)


def red_items(text):
    """The red items a viewer's report names ("Red items: none" names none)."""
    red = re.search(r"^\W*red items?\W*?:?[ \t]*(.*)\n?((?:[ \t]*[-*\d].*\n?)*)", text, re.I | re.M)
    items = [l.strip(" -*\t") for l in (red[2].splitlines() if red else []) if l.strip(" -*\t")]
    if red and red[1].strip() and not re.match(r"\W*(none|không|no\b)", red[1].strip(), re.I):
        items.insert(0, red[1].strip())
    return items


STARTED = time.time()


def guard_off():
    """In a Claude Code session the guard leaves a trace for the session's folder each time it runs (guard.py); none
    for this folder or the folders above it in the last half hour means its hooks do not run here."""
    if not os.environ.get("CLAUDECODE"):
        return ""
    seen = Path(os.environ.get("RUBYDAI_VIDEO_GUARD_SEEN") or Path.home() / ".rubydai-video" / "guard-seen")
    d = os.path.realpath(os.getcwd())
    for _ in range(5):
        key = hashlib.sha1(os.path.normcase(d).replace("\\", "/").encode()).hexdigest()[:16]
        try:
            if (seen / key).stat().st_mtime >= STARTED - 1800:   # the hook that ran this command, however long it ran
                return ""
        except OSError:
            pass
        d = os.path.dirname(d)
    return ("GUARD OFF: the rubydai-make-video-skill guard has not run in this Claude Code session, so the kit's checks will not hold. "
            "Its hooks need Node.js and Python (on Windows: Python from python.org), then a new session. Tell the user in "
            "one line before going on.")


def master_summary(m, state):
    """master_audio.py's answer read back: the last attempt's loudness and peak (it may encode more than once), a
    silent soundtrack, and whether the final pass ran in dynamic mode."""
    loud = (re.findall(r"re-measured from .*?: I=(\S+) LUFS .*?true peak=(\S+) dBFS", m) or [None])[-1]
    silent = "SILENT SOUNDTRACK" in m
    chosen = re.search(r"\b(silent|sessiz|no sound|without sound|sessiz film)\b", state, re.I)
    text = ("silent by choice" if chosen else "SILENT SOUNDTRACK (no score, effects or ambience yet)") if silent else \
        f"{loud[0]} LUFS, peak {loud[1]} dBFS" if loud else "loudness: see log"
    squeezed = "normalization_type=dynamic" in ([l for l in m.splitlines() if l.startswith("pass 2:")] or [""])[-1]
    if squeezed:
        text += (" · MASTER COMPRESSED: loudnorm ran in dynamic mode and squeezed the mix; bring the loud and quiet "
                 "moments closer (lower the loudest layer's gain in audio/mix.json) and draft again")
    return text, silent, squeezed
