#!/usr/bin/env python3
"""One call per Quick-mode step: render, master, check, and print a four-line summary, plus one line per alert (details go to logs/).

  python3 tools/make.py stills [--at 2,9,16,23]   stills (default: one per scene) -> one sheet, 1024 px wide
  python3 tools/make.py draft                     half size, finishing off, full sound -> renders/draft-vN.mp4,
                                                  checks, and <Title>-draft.mp4 in the project folder
  python3 tools/make.py final                     determinism check, full size with the chosen finishing ->
                                                  renders/film-vN.mp4, checks, and <Title>.mp4
Options:
  --sound-only     reuse the last picture of that step and render only the sound (a note about sound alone)
  --size WxH       full frame size (default: the "WxH" on the Format line of STATE.md, else the page's own)
  --workers N      parallel Chrome pages (default 2)       --poster S   poster time (default: 70% of the runtime)
Sound: the page's soundtrack is always captured to audio/film.wav. With audio/mix.json (narration, sound.md) that
file takes the place of the plan's music layer, mix.py mixes the plan into audio/mix-<version>.wav (its own "out" is
not used) and that is mastered; otherwise audio/film.wav is. The user's own song (OWN_MUSIC) is only ever read.
A render that fails the hook, the master or the checks stays in renders/; the delivered <Title>.mp4 is replaced only
by a render that passed.
From STATE.md: "**Loop:** yes" adds the loop-seam check; a final "**Delivered to:**" X, Slack or Discord also writes
<Title>-x.mp4 with the poster on frame 0 (those platforms show the first frame as the cover).
Exit code 1 when a step fails or the hook (a hard rule) fails. The summary is also written to logs/last-make.txt.
Long films: run it in the background (the shell tool's run_in_background, in bash and PowerShell alike), then
`python3 tools/make.py wait` waits for that run and prints its summary (read the summary from wait, never the
output file itself: the guard looks for the SHOW THIS DRAFT NOW line, and a draft shown from a file read is still
unsent to the user)
(never a pgrep loop on "make.py": the loop's own command line matches it).
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import debug, show, write_text  # noqa: E402  (the kit's shared helpers, same folder)
from make_checks import (  # noqa: E402,F401  (moved to make_checks.py; re-exported here)
    CHOICE_WORDS, CLICHES, NOTE, NOT_CHOICE, STARTED, TEMPO,
    VOICES, ai_palette_line, animatic_made, av_start_line, bounds_of, cliche_line,
    clock, colour_line, cover_platforms, delivers, end_card_line, ending_line,
    ending_need, even, guard_off, lead_silence, master_summary, motion_per_second,
    music_palette, narration_line, old_cg_line, own_music_file, page, peaks,
    picked_files, progression_shape, red_items, report_lines, rests_line, rhythm_line,
    same_path, seconds_of, small_sheet, sound_budget_line, sound_by_choice, tempo_card,
    too_dark_line, view_line, wants_loop)

TOOLS = Path(__file__).resolve().parent
PROJECT = TOOLS.parent
LOGS, RENDERS, REVIEW = PROJECT / "logs", PROJECT / "renders", PROJECT / "review"


def missing_tools():
    """The programs check needs besides this Python: ffmpeg and ffprobe."""
    return [b for b in ("ffmpeg", "ffprobe") if not shutil.which(b)]


class Step:
    def __init__(self, name):
        LOGS.mkdir(exist_ok=True)
        self.log = LOGS / f"make-{name}.log"
        self.log.write_text(f"# make.py {name} · {time.strftime('%Y-%m-%d %H:%M:%S')}\n", encoding="utf-8")

    def run(self, cmd, env=None, ok=(0,)):
        with self.log.open("a", encoding="utf-8") as f:
            f.write("\n$ " + " ".join(str(c) for c in cmd) + "\n")
        p = subprocess.run([str(c) for c in cmd], cwd=PROJECT, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        with self.log.open("a", encoding="utf-8") as f:
            f.write(p.stdout)
        if p.returncode not in ok:
            tail = "\n".join(p.stdout.strip().splitlines()[-4:])
            finish([f"FAILED: {Path(str(cmd[1])).name if cmd[0] in ('node', sys.executable) else cmd[0]} "
                    f"(exit {p.returncode})", tail, f"log: {rel(self.log)}"], 1)
        return p.returncode, p.stdout


def rel(p):
    if not p:
        return "-"
    try:
        return Path(p).resolve().relative_to(PROJECT).as_posix()
    except (ValueError, TypeError):
        return Path(p).as_posix()


RUNNING = "make.running"


def mark_running(step):
    """While a step runs, logs/make.running holds its process id, so `make.py wait` waits for this run only."""
    try:
        LOGS.mkdir(exist_ok=True)
        (LOGS / RUNNING).write_text(f"{os.getpid()} {step} {time.time():.3f}\n", encoding="utf-8")
        (LOGS / f"run-{os.getpid()}.txt").unlink(missing_ok=True)   # an earlier process with this number
        for old in LOGS.glob("run-*.txt"):
            if time.time() - old.stat().st_mtime > 86400:
                old.unlink()
    except OSError:
        return
    import atexit
    atexit.register(clear_running)


def clear_running():
    try:
        f = LOGS / RUNNING
        if f.read_text(encoding="utf-8").split()[0] == str(os.getpid()):
            f.unlink()
    except (OSError, IndexError):
        pass


def wait_cmd(limit):
    """Wait for the step running in the background, then print that run's own summary (logs/run-<pid>.txt); exit 1
    when it failed, was held, or ended without a summary. The waiter follows the run in logs/make.running, alive or
    already ended, never a later one; with no run marked it shows a summary written in the last minute."""
    t0, end, run = time.time(), time.time() + limit, None

    def alive(pid):
        if os.name == "nt":                      # os.kill(pid, 0) ends a process on Windows; ask for its exit code
            import ctypes
            k32, code = ctypes.windll.kernel32, ctypes.c_ulong()
            h = k32.OpenProcess(0x1000, False, pid)
            if not h:
                return False
            try:
                return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259
            finally:
                k32.CloseHandle(h)
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        try:                                     # an ended step its parent has not reaped yet is not running
            return subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True,
                                  timeout=5).stdout.strip()[:1] != "Z"
        except (OSError, subprocess.SubprocessError):
            return True
    while time.time() < end:
        if run is None:
            try:
                parts = (LOGS / RUNNING).read_text(encoding="utf-8").split()
                run = int(parts[0])
                continue
            except (OSError, ValueError, IndexError):
                pass
            if time.time() - t0 > 8:
                break
            time.sleep(0.5)
        elif alive(run):
            time.sleep(1)
        else:
            break
    else:
        print(f"still running after {limit:g} s; run make.py wait again")
        sys.exit(3)
    if run is not None:
        try:
            text = (LOGS / f"run-{run}.txt").read_text(encoding="utf-8").rstrip()
        except OSError:
            print("the run ended without its summary (stopped or crashed); read logs/make.out and run it again")
            sys.exit(1)
    else:
        summary = LOGS / "last-make.txt"
        try:
            text, age = summary.read_text(encoding="utf-8").rstrip(), time.time() - summary.stat().st_mtime
        except OSError:
            print("no step is running and no summary is written (read logs/make.out)")
            sys.exit(2)
        if age > 60:
            print(f"no step is running; this summary is from an earlier run, {age / 60:.0f} min ago (read logs/make.out):")
    print(text)
    sys.exit(1 if re.search(r"^FAILED|NOT DELIVERED|HELD", text, re.M) else 0)


def finish(lines, code=0):
    text = "\n".join(l for l in lines if l)
    try:
        LOGS.mkdir(exist_ok=True)
        (LOGS / "last-make.txt").write_text(text + "\n", encoding="utf-8")
        (LOGS / f"run-{os.getpid()}.txt").write_text(text + "\n", encoding="utf-8")   # make.py wait reads its own run
    except OSError:                                    # logs/ on a disk that is not connected: the message still prints
        pass
    print(text)
    sys.exit(code)


ASPECT = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350), "21:9": (1920, 816)}


def frame_size(arg):
    if arg:
        m = re.fullmatch(r"(\d+)x(\d+)", arg)
        if not m:
            finish(["--size needs WxH, for example 1080x1920"], 2)
        return int(m[1]), int(m[2])
    state = PROJECT / "STATE.md"
    if state.exists():
        for line in state.read_text(encoding="utf-8", errors="replace").splitlines():
            if "**format:**" in line.lower():
                m = re.search(r"\b(\d{3,4})\s*[x×]\s*(\d{3,4})\b", line)
                if m:
                    return int(m[1]), int(m[2])
                m = re.search(r"\b(9:16|16:9|1:1|4:5|21:9)\b", line)
                word = re.search(r"\b(vertical|dọc|square|vuông|horizontal|ngang|landscape|縦|横|正方形)", line, re.I)
                ratio = m[1] if m else {"vertical": "9:16", "dọc": "9:16", "縦": "9:16", "square": "1:1", "vuông": "1:1",
                                        "正方形": "1:1"}.get(
                    word[1].lower(), "16:9") if word else None
                if ratio:
                    return ASPECT[ratio]
    return None


def probe(step, film, size):
    params = f"w={size[0]}&h={size[1]}" if size else ""
    _, out = step.run(["node", TOOLS / "capture.mjs", "--url", film, "--probe"] + (["--params", params] if params else []))
    m = re.search(r"page: (\d+)x(\d+), (\d+) frames @ ([\d.]+) fps", out)
    if not m:
        finish(["FAILED: the page did not report its size and frames", f"log: {rel(step.log)}"], 1)
    info = {"w": int(m[1]), "h": int(m[2]), "frames": int(m[3]), "fps": float(m[4])}
    meta = re.search(r"meta: (\{.*\})", out)
    info.update(json.loads(meta[1]) if meta else {})
    for line in out.splitlines():
        if "WARNING" in line or "qc:" in line:
            info.setdefault("warnings", []).append(line.replace("[capture] ", "").strip())
    return info


# Colours every generated design reaches for (#hex -> name); a film's palette near one of them needs a reason.
HOUSE = {"#d97757": "terracotta", "#c96442": "terracotta", "#f5f0e8": "warm cream", "#faf9f5": "warm cream",
         "#f0eee6": "warm cream", "#6366f1": "indigo", "#8b5cf6": "violet", "#a855f7": "purple", "#0f172a": "slate navy",
         "#1e293b": "slate", "#3b82f6": "bright blue", "#10b981": "emerald", "#22c55e": "green", "#f59e0b": "amber"}


def taste_line(info):
    """One line when the film still wears a default: the look's untouched palette, a colour or a font AI designs overuse."""
    rgb = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if isinstance(h, str) and \
        len(h.lstrip("#")) == 6 else None
    pal = {k: v for k, v in (info.get("palette") or {}).items() if rgb(v)}
    notes = []
    if pal and pal == {k: v for k, v in (info.get("lookPalette") or {}).items() if rgb(v)}:
        notes.append("the palette is the look family's untouched default (give the film its own, from its references)")
    near = [] if notes else sorted({name for v in pal.values() for h, name in HOUSE.items()   # untouched says it all
                                    if sum((a - b) ** 2 for a, b in zip(rgb(v), rgb(h))) ** 0.5 < 22})
    if near:
        notes.append("colours AI designs overuse: " + ", ".join(near))
    try:
        sys.path.insert(0, str(TOOLS))
        from fonts import COMMON
        common = [f for f in info.get("families") or [] if f.lower().replace(" ", "-") in COMMON]
        if common:
            notes.append("fonts AI designs overuse: " + ", ".join(common))
    except ImportError:
        pass
    return ("taste: " + "; ".join(notes) + " (a reason on the director card, or change it)") if notes else ""


def title_of(info):
    t = info.get("title") or ""
    if not t or t == "Untitled":
        state = PROJECT / "STATE.md"
        head = next(iter(state.read_text(encoding="utf-8", errors="replace").splitlines()), "") if state.exists() else ""
        m = re.match(r"#\s*State:\s*(.+?)\s*(\(|$)", head)
        t = m[1] if m else PROJECT.name
    t = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", t).strip(" .")
    return t or "film"


def next_version(prefix):
    RENDERS.mkdir(exist_ok=True)
    nums = [int(m[1]) for p in RENDERS.glob(f"{prefix}-v*.mp4") if (m := re.fullmatch(rf"{prefix}-v(\d+)\.mp4", p.name))]
    return max(nums, default=0) + 1


def blank_line(video, report):
    """Blank frames inside the film (0.3 s or more of near black with nothing on it) read as a broken file. A card on
    black is not blank: the middle frame of each stretch is checked for any bright pixel (type, a spark)."""
    text = report.read_text(encoding="utf-8", errors="replace") if report.exists() else ""
    sec = text.split("== black intervals", 1)[1].split("\n==", 1)[0] if "== black intervals" in text else ""
    spans = [(float(a), float(b)) for a, b in re.findall(r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)", sec)]
    if not spans:
        return ""
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                           capture_output=True, text=True).stdout.strip()
    end = float(probe) if probe else max(b for _, b in spans)
    blank = []
    for a, b in spans:
        if a < 0.05 or b > end - 0.05 or b - a < 0.3:
            continue
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{(a + b) / 2:.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                            "signalstats,metadata=print:key=lavfi.signalstats.YMAX:file=-", "-f", "null", "-"],
                           capture_output=True, text=True)
        ymax = [float(l.split("=")[1]) for l in r.stdout.splitlines() if "YMAX=" in l]
        if ymax and ymax[0] < 60:
            blank.append((a, b))
    return ("BLANK FRAMES " + ", ".join(f"{a:.1f}–{b:.1f} s" for a, b in blank[:3]) + ": nothing on screen for 0.3 s or more "
            "inside the film reads as a broken file; fill it (the next picture earlier, the type on black, a light) or "
            "cut it under 0.3 s") if blank else ""


def sound_buried_line(plan, music_file):
    """A designed sound the music covers is no sound: each effect's peak against the music's in the same 0.3 s, both at
    their mix levels (the plan's gain and the bus). Most hits more than 6 dB under the music: they are planned, not
    heard."""
    layers = (plan or {}).get("layers", [])
    events = [L for L in layers if L.get("bus") in ("sfx", "foley")]
    music = next((L for L in layers if L.get("bus") == "music"), None)
    if len(events) < 3 or not music or not Path(music_file).exists():
        return ""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        stem, spec = Path(tmp) / "fx.wav", Path(tmp) / "fx.json"
        spec.write_text(json.dumps(dict(plan, layers=events, out=str(stem))), encoding="utf-8")
        r = subprocess.run([sys.executable, str(TOOLS / "mix.py"), str(spec)], cwd=PROJECT, capture_output=True, text=True)
        if r.returncode or not stem.exists():
            return ""
        fx, mu = peaks(stem), peaks(music_file)
    gain = float(music.get("gain_db", 0) or 0) - 4                      # mix.py's music bus
    diffs = []
    for L in events:
        i = int(float(L.get("at", 0) or 0) * 10)
        a, b = max(fx[i:i + 3] or [-120.0]), max(mu[i:i + 3] or [-120.0]) + gain
        if b > -60:
            diffs.append(a - b)
    if len(diffs) < 3:
        return ""
    mid = sorted(diffs)[len(diffs) // 2]
    if mid >= -6:
        return ""
    return (f"SOUND BURIED: the effects sit {-mid:.0f} dB under the music at their own moments (median of {len(diffs)} "
            "hits): planned, not heard. Raise them (gain_db toward 0 on sfx and foley) or duck the music around the hits, "
            "then draft again (sound.md §5)")


def sound_thin_line(info, plan, state):
    """The floor under SOUND SLOP's ceiling: what the picture does, the sound does (sound.md §5). A film whose words
    slam, lines draw and things land in silence reads unfinished. Event sounds are the page's SFX other than whooshes
    and risers, plus the recorded layers in audio/mix.json outside the music, the voice and the beds; about one every 4 s is the
    least, and review/sound-audit.md lists every on-screen event with its sound. A film silent or music-only by choice
    (said on the card) passes."""
    dur = info["frames"] / info["fps"]
    if dur <= 0 or sound_by_choice(state):
        return ""
    events = [e for e in info.get("sfx") or [] if e[1] not in ("whoosh", "air", "riser")]
    layers = [L for L in (plan or {}).get("layers", []) if L.get("bus") not in ("music", "dialogue", "ambience")]
    music_led = re.search(r"own song|own track|bài hát của (?:tôi|mình)|music video|\bmv\b|video ca nhạc|lyric video", state, re.I)
    have, need = len(events) + len(layers), max(3, round(dur / (30 if music_led else 4)))   # music-video.md: a handful
    audit = REVIEW / "sound-audit.md"
    cover = re.search(r"events\s+(\d+)\s*·\s*sounded\s+(\d+)(?:\s*·\s*silent by choice\s+(\d+))?",
                      audit.read_text(encoding="utf-8")) if audit.exists() else None
    why = []
    if have < need:
        why.append(f"{have} event sounds in {dur:.0f} s (at least {need})")
    if not audit.exists():
        why.append("no review/sound-audit.md")
    elif cover and int(cover[1]) and int(cover[2]) + int(cover[3] or 0) < 0.9 * int(cover[1]):
        why.append(f"the audit sounds {cover[2]} of {cover[1]} events")
    return ("SOUND THIN: " + "; ".join(why) + ". Every word that slams, line that draws, thing that lands or breaks "
            "gets its own sound, ready where it should sound real or designed (sounds.py search / get, asset_search.py "
            "search --type sound; layers on the sfx bus in audio/mix.json), listed with its time in review/sound-audit.md "
            "(references/sound.md §5)") if why else ""


CALM_MUSIC = r"ambient|tension|gerilim|drone|neoclassical|neo-classical|minimal piano|piano solo|solo piano|sakin|contemplative"
KIT = {"kick", "snare", "hat", "clap", "bass", "sub808"}       # the rhythm section: every genre has one
SHOWN_MUSIC = Path(os.environ.get("RUBYDAI_VIDEO_SHOWN_MUSIC") or Path.home() / ".rubydai-video" / "shown-music.json")


def function_body(src, at):
    """The text between a function's own braces, starting at its declaration (a one-line `{}` body is empty)."""
    start = src.find("{", src.find(")", at))
    depth = 0
    for i in range(start, len(src)):
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        if depth == 0:
            return src[start + 1:i]
    return src[start + 1:]


def music_choice_line(film, plan, state):
    """The music is always the user's (SKILL.md): a draft with any music (a score in code, their track, a found
    recording) holds until STATE.md's Music line carries the user's pick, written in, not the template's placeholder."""
    line = re.search(r"\*\*(?:Nhạc|Music):\*\*\s*([^\n]*)", state, re.I)
    said = re.sub(r"<!--.*?-->|<[^<>]*>", " ", line[1] if line else "").strip()
    picked = re.search(r"\(\s*(user|người dùng)\s*\)", said, re.I) and len(re.sub(r"\(\s*\w+\s*\)", "", said).strip()) > 2
    try:
        src = Path(film).read_text(encoding="utf-8") if film else ""
    except OSError:
        src = ""
    own = re.search(r"const OWN_MUSIC\s*=\s*(\{[^}]*\})", src)
    layers = [L for L in (plan or {}).get("layers", []) if isinstance(L, dict) and L.get("bus") == "music"
              and not same_path(L.get("file", ""), "audio/film.wav")]    # the page's whole soundtrack, captured
    at = src.find("function score(")
    body = function_body(src, at) if at >= 0 else ""
    coded = re.sub(r"//[^\n]*|/\*.*?\*/|\breturn\s*;?", "", body, flags=re.S).strip()
    has_music = bool(own or layers or coded)
    claim = said.lower()
    if picked and re.match(r"\s*(none|không|không nhạc|no music)\b", claim) and has_music:
        return ("MUSIC NOT CHOSEN: STATE.md says no music, and the film has music (a score in code, a track or a music "
                "layer); remove it or ask the user again and write their pick")
    named_file = re.search(r"[\w./\\-]+\.(?:mp3|wav|ogg|flac|m4a|aac)", said)
    if picked and (re.match(r"\s*(recording|bản thu|own|của tôi)\b", claim) or named_file) and coded and not (own or layers):
        return ("MUSIC NOT CHOSEN: STATE.md picks a recording, and the film's music is made in code; put the picked "
                "recording in (Quick: OWN_MUSIC in film.html; Film: a music layer in audio/mix.json) or ask the user again")
    named = picked_files(said)
    own_file = own_music_file(src)
    used = [str(L.get("file", "")) for L in layers] + ([own_file] if own_file else [])
    where = lambda p: (PROJECT / str(p).replace("\\", "/")).resolve()
    same = lambda u, n: where(u) == where(n) or ("/" not in n.replace("\\", "/") and os.path.basename(u) == n)
    stray = [u for u in used if not any(same(u, n) for n in named)]
    if picked and not named and re.search(r"\.(?:mp3|wav|ogg|flac|m4a|aac)\b", said, re.I):
        return ("MUSIC NOT CHOSEN: the Music line names a recording the check cannot read; write its path in backticks, "
                "e.g. `audio/music/song.mp3`")
    if picked and named and not used:
        return ("MUSIC NOT CHOSEN: the user picked " + ", ".join(named) + " and the film does not play it; put it in "
                "(Quick: OWN_MUSIC in film.html; Film: a music layer in audio/mix.json) or ask again")
    if picked and named and has_music and stray:
        return ("MUSIC NOT CHOSEN: the film plays " + ", ".join(stray) + ", which the user did not pick (" +
                ", ".join(named) + "); use only the picked files, or ask again")
    if not has_music or picked:
        return ""
    return ("MUSIC NOT CHOSEN: the film has music and STATE.md's Music line does not carry the user's pick. Ask where "
            "the music comes from (★ a real open-licence recording, 2-3 candidates played to pick by ear · their own "
            "track · code · none) and write what they chose, e.g. `Music: recording, audio/music/x.mp3 (user)`")


def music_line(film, video, state, bounds=None, remember=True):
    """Two habits that made the scores sound alike: no beat under a film that moves (the drone-and-arpeggio bed by
    default), and the same instruments film after film (references/sound.md §8)."""
    notes = []
    card = tempo_card(state)
    word = card and re.search(r"\b(energetic|enerjik|tempolu|standard|standart)\b", card[1], re.I)
    lens = [b - a for a, b in zip(bounds or [], (bounds or [])[1:]) if b > a]
    mean = sum(lens) / len(lens) if len(lens) >= 4 else 0
    lively = word[1] if word else f"scenes of {mean:.1f} s on average" if 0 < mean <= 5 else ""
    music = re.search(r"\*\*(Nhạc|Music)[^*]*\*\*\s*([^\n]+)", state, re.I)
    try:
        own = re.search(r"const OWN_MUSIC\s*=\s*\{", Path(film).read_text(encoding="utf-8"))   # null in any spacing is no song
    except OSError:
        own = None
    if lively and not own and not (music and re.search(CALM_MUSIC, music[2], re.I)):   # a recording keeps its own feel
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import beat_grid
            flux = beat_grid.envelope(str(video), 0, 360, "highpass=f=40")
            pulse = beat_grid.tempo(flux)[1] if max(flux) >= 0.5 else 0.0
            if pulse < 2.0:
                notes.append(f"MUSIC WITHOUT A BEAT: pulse {pulse:.1f}x under {'a card that says ' if word else ''}{lively}; a groove from the "
                             "card's genre (grid() steps, a bass on the roots), or a Music line that names a calm genre and why")
        except (Exception, SystemExit):
            pass
    mine = music_palette(film)
    shape = progression_shape(film)
    if mine or shape:
        try:
            seen = json.loads(SHOWN_MUSIC.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            seen = {}
        key = str(PROJECT.resolve())
        others = sorted((v for k, v in seen.items() if k != key and isinstance(v, dict)), key=lambda v: -v.get("time", 0))[:4]
        again = sorted(x for x in mine - KIT if sum(x in v.get("palette", []) for v in others) >= 2)
        last = (mine - KIT) & set(others[0].get("palette", [])) if others else set()
        if len(again) >= 2 or len(last) >= max(2, 0.5 * len(mine - KIT)):
            notes.append(f"music: {', '.join(again or sorted(last))} again, as in your last films; another genre card in "
                         "sound.md §8 or other players (samples.py list) unless this story asks for these")
        heard = [v for v in others if v.get("shape") == shape] if shape else []
        if heard:
            notes.append(f"music: the chord loop {shape} again, as in your last films (in any key); this film's harmony "
                         "comes from its own genre and story, sound.md §8")
        if remember:
            seen[key] = {"time": time.time(), "palette": sorted(mine), "shape": shape}
            seen = dict(sorted(seen.items(), key=lambda kv: -kv[1].get("time", 0) if isinstance(kv[1], dict) else 0)[:30])
            try:
                SHOWN_MUSIC.parent.mkdir(parents=True, exist_ok=True)
                SHOWN_MUSIC.write_text(json.dumps(seen), encoding="utf-8")
            except OSError:
                pass
    return " · ".join(notes)


def format_copy_line(film):
    """A film made in a saved format speaks its language with new content: its score, scenes and sound cues may not be
    the source film's (research/format-reference.html) again."""
    ref = PROJECT / "research" / "format-reference.html"
    try:
        new, old = Path(film).read_text(encoding="utf-8"), ref.read_text(encoding="utf-8")
    except OSError:
        return ""
    import difflib
    def part(src, start):
        a = src.find(start)
        if a < 0:
            return ""
        b = src.find("\n}\n" if start.startswith("function") else "\n];", a)
        return re.sub(r"\s+", " ", src[a:b if b > 0 else a + 4000])
    same = []
    for name, start in (("the score", "function score("), ("the scenes", "const SCENES = ["), ("the sound cues", "const SFX = [")):
        x, y = part(new, start), part(old, start)
        if any(m in y for m in ("fieldGathers", "builds into the impact")):   # template examples
            continue
        if len(x) > 60 and len(y) > 60 and difflib.SequenceMatcher(None, x, y).ratio() > 0.8:
            same.append(name)
    fmt = PROJECT / "FORMAT.md"
    kept = re.search(r"## Kept on purpose[^\n]*\n(.*?)(\n## |\Z)", fmt.read_text(encoding="utf-8"), re.S) if fmt.exists() else None
    if kept and not re.search(r"^-\s*none", kept[1].strip(), re.I) and same == ["the sound cues"]:
        return ""                                    # the format's kept signature; the score and scenes are new
    return (f"FORMAT COPY: {', '.join(same)} {'is' if len(same) == 1 else 'are'} the source film's again; a format keeps "
            "the language (FORMAT.md) and makes the content new: compose a new score in the same genre and tempo range, "
            "write the scenes and cues for this idea") if same else ""


def text_line(step, film, w, h):
    """The film's type, drawn every half second with the page's text check (film.html ?textcheck=1): two lines stacked
    over each other whose letters touch (a stacked Vietnamese mark like Ầ in the line above), and type whose letters do not stand out from
    what is around them (white on a chrome highlight). A page made before the check passes silently."""
    _, out = step.run(["node", TOOLS / "capture.mjs", "--url", film, "--text-check", "0.5",
                       "--params", f"w={w}&h={h}&shutter=0&weave=0&tone=0&textcheck=1"], ok=(0, 1))
    hits = [re.sub(r"^\[capture\]\s*", "", l) for l in out.splitlines() if "TEXT OVERLAP" in l or "LOW CONTRAST" in l]
    if not hits:
        return ""
    more = f" (+{len(hits) - 3} more in {rel(step.log)})" if len(hits) > 3 else ""
    return ("TEXT: " + " · ".join(hits[:3]) + more + ": letters of two lines never touch and every line stands clear "
            "of what is behind it (more space between the lines, a scrim, an outline or another colour); an intended "
            "one (a scatter) is named in STATE.md")


def layer_seconds(L, plan_dur):
    """How long a mix layer sounds, by mix.py's own rule: the file, cut by trim, then a loop or a length (a loop
    without a length runs to the plan's end)."""
    if L.get("dur"):
        return float(L["dur"])
    trim = L.get("trim") if isinstance(L.get("trim"), list) and len(L.get("trim")) == 2 else None
    whole, loop = seconds_of(PROJECT / str(L.get("file", ""))), bool(L.get("loop"))
    if trim and trim[1] is not None:             # mix.py loops the input first, then trims that stream
        t0, t1 = float(trim[0] or 0), float(trim[1])
        base = (t1 - t0) if loop or whole <= 0 else max(0.0, min(t1, whole) - t0)
    else:
        base = float("inf") if loop else whole
    if loop or L.get("length"):
        base = min(base, float(L.get("length") or plan_dur or whole))
    return whole if base == float("inf") else base


def voice_spans(plan, film=None):
    """When the voice speaks: the dialogue layers of audio/mix.json, else the VO list of film.html (at, dur), else the
    lines table of SCRIPT.md (start, estimated seconds), so an animatic is measured before any voice is recorded."""
    spans = []
    for L in (plan or {}).get("layers", []):
        if isinstance(L, dict) and L.get("bus") == "dialogue":
            at = float(L.get("at") or 0)
            d = layer_seconds(L, float((plan or {}).get("duration") or 0))
            if d:
                spans.append((at, at + d))
    if not spans and film:
        try:
            vo = re.search(r"const VO = \[(.*?)\];", Path(film).read_text(encoding="utf-8"), re.S)
        except OSError:
            vo = None
        for m in re.finditer(r"\{[^}]*?\bat:\s*([\d.]+)[^}]*?\bdur:\s*([\d.]+)", vo[1] if vo else ""):
            spans.append((float(m[1]), float(m[1]) + float(m[2])))
    if not spans:
        spans = script_table_spans(("lines", "narration", "dialogue", "lời thoại", "lời dẫn"), ("start", "time", "thời điểm", "at"),
                                   ("est", "sec", "dur", "thời lượng"))
    return sorted(spans)


def script_table_spans(sections, starts, lengths):
    """Spans from SCRIPT.md tables found by their headings and header row: the start column (a time or a range) and
    a length column (seconds); without one, a range's end, or words at 2.5 a second."""
    try:
        script = (PROJECT / "SCRIPT.md").read_text(encoding="utf-8")
    except OSError:
        return []
    spans = []
    parts = re.split(r"^#+\s*", script, flags=re.M)
    if not re.search(r"^#", script, re.M):      # a bare table with no headings is the section itself
        parts = [sections[0] + "\n" + script]
    for part in parts:
        if not part.lower().startswith(sections):
            continue
        head = None
        for row in part.splitlines():
            if not row.startswith("|") or re.match(r"^\|[\s:|-]+\|?\s*$", row):
                continue
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            low = [c.lower() for c in cells]
            if head is None:
                if any(c.startswith(starts) for c in low):
                    head = low
                continue
            si = next((k for k, c in enumerate(head) if c.startswith(starts)), None)
            li = next((k for k, c in enumerate(head) if any(w in c for w in lengths) and not c.startswith(starts)), None)
            wi = next((k for k, c in enumerate(head) if c.startswith(("words", "số chữ"))), None)
            if si is None or si >= len(cells):
                continue
            ends = [clock(x) for x in re.split(r"\s*[–-]\s*", cells[si]) if x.strip()]
            if not ends or ends[0] is None:
                continue
            secs = None
            if li is not None and li < len(cells) and re.match(r"[\d.]+", cells[li]):
                secs = float(re.match(r"[\d.]+", cells[li])[0])
            elif len(ends) > 1 and ends[1] is not None:
                secs = ends[1] - ends[0]
            elif wi is not None and wi < len(cells) and cells[wi].isdigit():
                secs = int(cells[wi]) / 2.5
            else:                                # no length column: the line's own words at 2.5 a second
                ti = next((k for k, c in enumerate(head) if c.startswith(("line", "text", "lời", "chữ"))), None)
                words = len(re.sub(r"\([^)]*\)", "", cells[ti]).split()) if ti is not None and ti < len(cells) else 0
                secs = max(1.0, words / 2.5) if words else None
            if secs:
                spans.append((ends[0], ends[0] + secs))
    return sorted(spans)


def text_spans():
    """When words are on screen: the on-screen text table of SCRIPT.md (its time column, its seconds on screen)."""
    return script_table_spans(("on-screen text", "on screen text", "chữ trên màn hình"), ("time", "start", "thời điểm", "at"),
                              ("on screen (s)", "(s)", "sec", "dur", "thời lượng"))


def words_before_card(dur):
    """Words on screen before the ending. A card that ends with the cut and stays up for the ending's whole time is the
    ending itself; a shorter one, or one that runs past the cut, is a last line like any other."""
    return [s for s in text_spans() if not (abs(s[1] - dur) <= 0.25 and s[1] - s[0] >= ending_need(dur) - 0.05)]


def sound_source_line(film, plan, state, info=None):
    """Code-made effects read cheap where a material acts: a film whose every effect is synthesised (no ready or
    recorded layer on the sfx or foley bus of audio/mix.json) is SOUND ALL CODE, unless the card makes it synthetic by
    choice (8-bit, chiptune). A film made from a format whose sound language names a recording, scored in code
    instead, is named too (quick-mode.md §8)."""
    why = []
    synthetic = re.search(r"8-bit|chiptune|synthetic by choice|sentetik|all synth|retro game", state, re.I)
    ready = [L for L in (plan or {}).get("layers", []) if L.get("bus") in ("sfx", "foley")]
    coded = [e for e in (info or {}).get("sfx") or [] if e[1] not in ("whoosh", "air", "riser")]
    if info is None and ready:                   # Film mode: a layer the licence log does not know was made, not recorded
        norm = lambda p: re.sub(r"^(\./)+", "", str(p).strip().replace("\\", "/"))
        try:
            with open(PROJECT / "LICENSES.csv", encoding="utf-8", newline="") as fh:
                logged = {norm(r.get("file", "")) for r in csv.DictReader(fh)}
        except (OSError, csv.Error):
            logged = set()
        made = [L for L in ready if norm(L.get("file", "")) not in logged]
        ready = [L for L in ready if L not in made]
        coded = made
        if not ready and made and not synthetic and not sound_by_choice(state):
            why.append(f"no effect layer is a logged recording ({len(made)} made in code): every physical event takes a "
                       "recording with its LICENSES.csv row (sounds.py get, asset_search.py fetch)")
            return "SOUND ALL CODE: " + "; ".join(why)
    if ready and len(coded) >= 3 and len(coded) > len(ready) and not synthetic and not sound_by_choice(state):
        why.append(f"most event sounds are made in code ({len(coded)} in code, {len(ready)} recorded): every physical event takes "
                   "a recording (sounds.py search / get, "
                   "asset_search.py search --type sound); code only for what follows the motion or the score (sound.md §5)")
    if not ready and not synthetic and not sound_by_choice(state):
        why.append("no ready or recorded effect: every sound is synthesised in code (sounds.py search / get for the "
                   "designed ones, asset_search.py search --type sound for the long ones; code only where a sound follows the "
                   "motion, lands a whoosh on a cut or sits in the score's key, sound.md §5)")
    fmt = PROJECT / "FORMAT.md"
    if fmt.exists():
        lang = re.search(r"\*\*Sound language:\*\*([^\n]*)", fmt.read_text(encoding="utf-8"))
        own = re.search(r"const OWN_MUSIC\s*=\s*\{", Path(film).read_text(encoding="utf-8")) if Path(film).exists() else None
        if lang and re.search(r"open-licen[cs]e|recording|track|bản thu", lang[1], re.I) and not own:
            why.append("the format's music is a recording and this film's is a code score: a new track in that genre and "
                       "tempo, three previews for the user (sound.md §8, A real recording)")
    return ("SOUND ALL CODE: " + "; ".join(why)) if why else ""


def read_json(path, what):
    """A project file that exists is valid JSON holding an object, or the run stops naming it; a missing one is None."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        finish([f"FAILED: {rel(p)} is not valid JSON ({getattr(e, 'msg', e)}); fix it and run again"], 2)
    if not isinstance(data, dict):
        finish([f"FAILED: {rel(p)} must hold a JSON object ({what}); it holds {type(data).__name__}"], 2)
    return data


def unplugged_line():
    """A film folder linked to another disk (renders/, audio/, review/ on an external drive) whose disk is not mounted."""
    gone = [d for d in ("renders", "audio", "review", "assets", "refs", "logs")
            if (PROJECT / d).is_symlink() and not (PROJECT / d).exists()]
    if not gone:
        return ""
    return (f"FAILED: {', '.join(d + '/' for d in gone)} of this film point to a disk that is not connected "
            f"({os.readlink(PROJECT / gone[0])}). Connect it and run again")


def disk_short(dur, rate):
    """What a render writes, estimated: the picture and the delivered file at the bitrate ceiling, four sound files (the
    page's sound, the mix, the master, a spare) at 48 kHz 24-bit stereo, and 300 MB for checks and sheets. A line when
    the film's disk has less free than that."""
    bits = float(rate.rstrip("M")) * 1e6 if rate.endswith("M") else float(rate)
    need = 2 * bits * dur / 8 + 4 * 48000 * 3 * 2 * dur + 300e6
    free = shutil.disk_usage(RENDERS.resolve() if RENDERS.exists() else PROJECT).free   # renders/ may live on another disk
    if free >= need:
        return ""
    return (f"FAILED: the render needs about {need / 1e9:.1f} GB free and the disk has {free / 1e9:.1f} GB. Free space "
            "first (old drafts and picture-only files in renders/ go with the cleanup question) and run again")


HARD_HIT = re.compile(r"impact|hit|punch|slam|door|thud|crash|knock|clap|snap|stomp|smash|bang|glass|break|cut", re.I)


def sound_sync_line(plan):
    """What is measured: the time from a layer's 'at' (the picture event's time in the plan) to its first audible sound
    (above -45 dBFS) in the file as laid, its trim applied. A downloaded effect often starts with 0.1-0.3 s of silence and
    is heard late. A hard hit (an impact, a slam, a door, a break: by its file name or "kind") may lead by 20 ms at most,
    half a frame at 24 fps; any other effect by 40 ms, about a frame."""
    late = []
    for L in (plan or {}).get("layers", []):
        if L.get("bus") not in ("sfx", "foley") or not (PROJECT / L.get("file", "")).exists():
            continue
        trim = L.get("trim") or [0.0, None]
        lead = lead_silence(PROJECT / L["file"], trim[0], (trim[1] - trim[0]) if trim[1] else None)
        if lead > (0.02 if HARD_HIT.search(f"{L.get('kind', '')} {Path(L['file']).name}") else 0.04):
            at = float(L.get("at", 0))
            late.append(f"{L['file']} at {at:.2f} s is heard at {at + lead:.2f} s (move 'at' to {at - lead:.2f} or trim "
                        f"{lead:.2f} s off its start)")
    if not late:
        return ""
    return "SOUND LATE: " + " · ".join(late[:4]) + (f" (+{len(late) - 4} more)" if len(late) > 4 else "")


def credits_file(title, tag):
    """The film's credits for the video description, never on the picture: one line per outside file in LICENSES.csv
    (its attribution_text), the software the page loads left out. Written beside the film at each final."""
    path = PROJECT / "LICENSES.csv"
    if not path.exists():
        return ""
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames and not {"file", "licence"} <= set(reader.fieldnames):
            finish([f"FAILED: LICENSES.csv has no file/licence header (it reads {reader.fieldnames[:3]}); the kit's "
                    "template header is templates/LICENSES.csv"], 2)
        rows = [r for r in reader if not (r.get("notes") or "").lower().startswith("software")]
    # Files fetched as candidates and never used owe no credit: a row counts as used when its used_in is filled or its
    # path is named by the page, the mix plan or the engine; the rest are listed back so a used one is never lost.
    sources = [p for p in [PROJECT / "film.html", PROJECT / "audio" / "mix.json", *sorted((PROJECT / "engine").glob("*.*"))]
               if p.is_file()]
    refs = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
    tracked = sources and any((r.get("used_in") or "").strip() for r in rows)
    used = lambda r: not tracked or (r.get("used_in") or "").strip() or re.match(r"https?:", r.get("file") or "") or \
        (r.get("file") and (r["file"] in refs or os.path.basename(r["file"]) in refs))
    unused = [r.get("file") for r in rows if not used(r)]
    rows = [r for r in rows if used(r)]
    owed = lambda r: not re.fullmatch(r"\s*(none|none needed|not needed|n/?a|-)?\s*", r.get("attribution_text") or "x", re.I)
    rows = [r for r in rows if owed(r)]
    kenney = [r for r in rows if "source=kenney" in (r.get("notes") or "")]
    rows = [r for r in rows if r not in kenney]
    def line(r):
        text = (r.get("attribution_text") or f"\"{r.get('title')}\" by {r.get('author')}, {r.get('licence')}").strip()
        url = (r.get("licence_url") or "").strip()
        return f"{text} ({url})" if url and re.match(r"\s*cc[\s_-]*by", r.get("licence") or "", re.I) and url not in text else text
    lines = list(dict.fromkeys(line(r) for r in rows if (r.get("title") or r.get("attribution_text"))))
    if kenney:
        lines.append("Sound effects: Kenney (kenney.nl), CC0")
    if not lines:
        return ""
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", str(title)).strip(" .") or "film"
    out = PROJECT / f"{safe}{tag}-credits.txt"
    if out.resolve().parent != PROJECT.resolve():
        finish([f"FAILED: the credits file must sit in the film's folder ({out.name})"], 2)
    out.write_text("Credits\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return (f"CREDITS ({out.name}): the delivery message carries them right under the film's path, headed IN CAPITALS in "
            "the user's language (Tiếng Việt: \"KHI ĐĂNG, DÁN PHẦN GHI CÔNG NÀY VÀO MÔ TẢ VIDEO\"), the lines below in a "
            "code block the user copies as they are, never only the file's name: the video's description (YouTube) or "
            "the post's caption (Instagram, TikTok, X); nothing goes on the picture; one plain line why: the CC BY and "
            "CC BY-SA licences ask for it, and it answers a copyright claim.\n" + "\n".join(lines)
            + ("\nLEFT OUT (used_in empty and not named by film.html, audio/mix.json or engine/): " + ", ".join(unused)
               + "; a file the film does use (cut or processed into another file) gets its used_in filled, then "
               "make.py credits again" if unused else ""))


def sound_plan(film):
    score = PROJECT / "audio" / "film.wav"
    own = own_music_file((PROJECT / film).read_text(encoding="utf-8"))
    if own and (PROJECT / own).resolve() == score.resolve():
        finish(["FAILED: OWN_MUSIC must not be audio/film.wav (that file is the page's rendered sound); "
                "rename the song, e.g. audio/music.wav"], 2)
    plan = read_json(PROJECT / "audio" / "mix.json", "the mix plan: duration, out, layers")
    if plan is None:
        return score, None
    if not isinstance(plan.get("layers"), list) or not all(isinstance(L, dict) for L in plan["layers"]):
        finish(["FAILED: audio/mix.json needs \"layers\": a list of objects (file, at, bus)"], 2)
    music = [L for L in plan.get("layers", []) if L.get("bus") == "music"]
    if not music:
        finish(["FAILED: audio/mix.json needs one layer with \"bus\": \"music\" (the score)"], 1)
    first = str(music[0].get("file") or "")
    plays = own and same_path(own, first)            # the page plays it: it is in film.wav already
    if first and not same_path(first, "audio/film.wav") and not same_path(first, "audio/score.wav") and not plays:
        finish([f"FAILED: audio/mix.json's first music layer is the page's own sound (audio/film.wav), so {first} "
                "would be dropped; the user's recording goes in OWN_MUSIC in film.html, or in a second music layer"], 2)
    music[0]["file"] = str(score.relative_to(PROJECT))   # the page's sound, never the file the plan names
    return score, plan


def state_text():
    p = PROJECT / "STATE.md"
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def variant_of(a, full, page_size=None):
    """Another aspect than the film's own (an ad's 1:1 or 16:9 cut) renders and delivers under its own name. The
    film's own aspect: STATE.md's Format line, else the page's own size (page_size() probes it only when needed)."""
    if a.variant:
        return re.sub(r"[^\w-]+", "-", a.variant).strip("-")
    if not (a.size and full):
        return ""
    own = frame_size(None) or (page_size() if page_size else None)
    if not own or full[0] * own[1] == full[1] * own[0]:
        return ""
    g = math.gcd(*full)
    return f"{full[0] // g}x{full[1] // g}"


def words_line():
    """The film's words before any render: a dash stops here (no render is wasted), other tells become one line."""
    try:
        sys.path.insert(0, str(TOOLS))
        import words_check
    except ImportError:
        return ""
    words_check.PROJECT = str(PROJECT)
    files = words_check.default_files()
    dashes, tells = words_check.check(words_check.gather(files))
    if dashes:
        finish(["FAILED: a dash in the film's words (never on screen or in a line): "
                + "; ".join(f"{w} '{s}'" for w, s in dashes[:4]),
                "replace each with a comma, a full stop, a colon or a line break; python3 tools/words_check.py"], 2)
    buf = __import__("io").StringIO()
    with __import__("contextlib").redirect_stdout(buf):
        words_check.main(["--line"] + files)
    return buf.getvalue().strip()


GATE = "draft-gate.json"


def draft_gate():
    try:
        return json.loads((LOGS / GATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def notes_since(t):
    """True when the user's notes were saved after time t (notes/round-N.md, written verbatim when they reply)."""
    return any(p.stat().st_mtime > t for p in (PROJECT / "notes").glob("*.md")) if (PROJECT / "notes").is_dir() else False


def viewer_report(a):
    """Before a final: the independent viewer's report on the newest draft, when the user asked for one (it is offered
    at the delivery, never required: the user's own OK on the draft is the gate). A report that is there is read: its
    red items hold the final until a later draft's report clears them. --force: the user keeps an item."""
    drafts = sorted(RENDERS.glob("draft-v*.mp4"), key=lambda p: p.stat().st_mtime) if RENDERS.exists() else []
    if not drafts:
        return ""
    version = int(re.search(r"-v(\d+)$", drafts[-1].stem)[1])
    report = REVIEW / f"critique-v{version}.md"
    wait = float(os.environ.get("RUBYDAI_VIDEO_VIEWER_WAIT", "120"))
    verdict_of = lambda: re.search(r"^\W*verdict\W*?:?\s*(APPROVE|FIX|UNVERIFIABLE)\b",
                                   report.read_text(encoding="utf-8", errors="replace"), re.I | re.M) if report.exists() else None
    asked = report.exists() or any(REVIEW.glob("critique-v*.md"))   # a viewer the user asked for, now or on an earlier draft
    if asked and not verdict_of() and time.time() - drafts[-1].stat().st_mtime < 900 and wait > 0:
        print(f"waiting up to {wait:g} s for the independent viewer's {rel(report)} ...", flush=True)
        end = time.time() + wait
        while not verdict_of() and time.time() < end:   # a file the viewer is still writing is not its report
            time.sleep(3)
    if not report.exists():
        earlier = sorted((int(m[1]), f) for f in REVIEW.glob("critique-v*.md")
                         if (m := re.search(r"-v(\d+)\.md$", f.name)) and int(m[1]) < version)
        held = [(n, f) for n, f in earlier if red_items(f.read_text(encoding="utf-8", errors="replace"))]
        if held and held[-1] == earlier[-1] and not a.force:
            finish([f"FAILED: {rel(held[-1][1])} named red items and no viewer has looked at draft v{version} yet, so "
                    f"the fix is not confirmed. Start the independent viewer on renders/draft-v{version}.mp4 and run "
                    "make.py final when its report is in (make.py final --force only when the user keeps an item)"], 2)
        return ""                                   # no viewer was asked for: the user's OK on the draft is the gate
    text = report.read_text(encoding="utf-8", errors="replace")
    items = red_items(text)
    verdict = verdict_of()
    if not verdict and not a.force:
        finish([f"FAILED: the independent viewer's {rel(report)} has no Verdict line (APPROVE, FIX or UNVERIFIABLE): it "
                "is not finished. Wait for it or start the viewer again (make.py final --force only when the user "
                "asks for the final without it)"], 2)
    if verdict and verdict[1].upper() == "FIX" and not items and not a.force:
        finish([f"FAILED: the independent viewer's {rel(report)} says FIX: fix what it names, draft again and let the "
                "viewer look at the new draft (make.py final --force only when the user keeps it)"], 2)
    if items and not a.force:
        finish([f"FAILED: the independent viewer's {rel(report)} names red items:",
                *[f"  - {i[:160]}" for i in items[:5]],
                "fix them, draft again and let the viewer look at the new draft; its report must name no red item "
                "(make.py final --force only when the user keeps one)"], 2)
    if verdict and verdict[1].upper() == "UNVERIFIABLE":
        return (f"viewer: {rel(report)} could not verify the draft (UNVERIFIABLE): tell the user in one line what an "
                "eye or an ear still has to check")
    return f"viewer: {rel(report)} read" + (f" ({len(items)} red item(s) kept by the user)" if items else ", no red items")


def render(a, kind):
    if unplugged_line():
        finish([unplugged_line()], 2)
    step = Step(kind)
    gate = draft_gate() if kind == "draft" and not a.variant and not a.size else {}
    shown = gate.get("delivered")
    if shown and not a.force and not notes_since(shown["time"]):
        finish([f"FAILED: draft v{shown['version']} ({shown['file']}) is ready and the user has not seen it yet: show it "
                f"now (its path, the poster, one question) and wait; polish waits for their notes, saved in notes/. "
                f"--force only when the user asked for another draft without notes"], 2)
    viewer = viewer_report(a) if kind == "final" and not a.variant and not a.size else ""
    if gate.get("held"):
        a.show_anyway = True                  # one fix pass was done after a hold: this one is shown, with what remains
    if kind == "final":
        a.show_anyway = True                  # the user approved the draft: soft flags are told, never held (broken files still are)
    words = words_line()
    state = state_text()
    film = a.film
    if not (PROJECT / film).exists():
        finish([f"FAILED: no {film} in {PROJECT}"], 2)
    full = frame_size(a.size)
    info = probe(step, film, full)
    W, H = full or (info["w"], info["h"])
    dur = info["frames"] / info["fps"]
    bounds = bounds_of(info)
    title = title_of(info)
    variant = variant_of(a, full, lambda: (lambda i: (i["w"], i["h"]))(probe(step, film, None)))
    tag = f"-{variant}" if variant else ""
    v = next_version(("draft" if kind == "draft" else "film") + tag)
    base = f"{'draft' if kind == 'draft' else 'film'}{tag}-v{v}"
    picture = RENDERS / f"{'draft-' if kind == 'draft' else ''}picture{tag}-v{v}.mp4"
    out = RENDERS / f"{base}.mp4"
    score, plan = sound_plan(film)
    score.parent.mkdir(parents=True, exist_ok=True)

    if kind == "draft":
        w, h = even(W / 2), even(H / 2)
        params, quality, rate = f"w={w}&h={h}&shutter=0&weave=0&tone=0", "0.85", "4M"
    else:
        w, h = W, H
        params, quality, rate = f"w={w}&h={h}", "0.95", "10M"
    short = disk_short(dur, rate)
    if short:
        finish([short], 2)
    if kind != "draft":
        step.run(["node", TOOLS / "capture.mjs", "--url", film, "--verify", "--params", params])

    t0 = time.time()
    if a.sound_only:
        prev = sorted(RENDERS.glob(f"{'draft-' if kind == 'draft' else ''}picture{tag}-v*.mp4"),
                      key=lambda p: int(re.search(r"-v(\d+)\.mp4$", p.name)[1]))
        if not prev:
            finish([f"FAILED: --sound-only needs an earlier {kind} picture in renders/"], 2)
        picture = prev[-1]
        step.run(["node", TOOLS / "capture.mjs", "--url", film, "--audio", score, "--params", params])
    else:
        step.run(["node", TOOLS / "capture.mjs", "--url", film, "--video", picture, "--audio", score,
                  "--workers", a.workers, "--format", "jpeg", "--quality", quality, "--maxrate", rate,
                  "--params", params, "--status", RENDERS / f"{kind}.status.json"])
    if plan:
        plan["out"] = f"audio/mix-{base}.wav"
        plan_file = LOGS / f"mix-{base}.json"
        plan_file.write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
        (PROJECT / plan["out"]).unlink(missing_ok=True)   # a half mix left by a failed run of this same version
        step.run([sys.executable, TOOLS / "mix.py", plan_file])
        master_in = PROJECT / plan["out"]
    else:
        master_in = score
    _, m = step.run([sys.executable, TOOLS / "master_audio.py", master_in, out, "--video", picture, "--limit"], ok=(0, 1))
    loud_txt, silent, squeezed = master_summary(m, state)
    master_ok = m.rstrip().endswith("OK") and not (silent and not re.search(r"\b(silent|sessiz|no sound|without sound)\b",
                                                                              state, re.I)) and not squeezed

    qc_dir = REVIEW / f"qc-{base}"
    every = max(2, math.ceil(dur / 18))         # at most 18 tiles; qc.py all draws the sheet once at this pace
    env = dict(os.environ, QC_OUT=str(qc_dir), QC_SHEET_EVERY=str(every))
    qc_args = [sys.executable, TOOLS / "qc.py", "all", out] + ([",".join(f"{b:g}" for b in bounds)] if bounds else [])
    rc, _ = step.run(qc_args, env=env, ok=(0, 1))
    hook, flags, issues = report_lines(qc_dir / "report.txt", bounds)
    sheet = small_sheet(step, qc_dir) if (qc_dir / "sheet.jpg").exists() else None   # a sheet that could not be drawn
    t_poster = a.poster if a.poster is not None else round(dur * 0.7, 2)              # never fails a finished render
    step.run([sys.executable, TOOLS / "qc.py", "thumb", out, "768", f"{t_poster:g}"], env=env)
    poster = next(qc_dir.glob("thumb-*-768.jpg"), None)

    if wants_loop(state):
        _, lo = step.run([sys.executable, TOOLS / "qc.py", "loop", out], env=env, ok=(0, 1))
        verdict = "JUMP" if "JUMP" in lo else "STUTTER" if "STUTTER" in lo else "ok"
        if verdict != "ok":
            issues.append(f"loop seam {verdict} (qc.py loop)")
        else:
            flags.append("loop seam ok")
    deliver = PROJECT / (f"{title}{tag}-draft.mp4" if kind == "draft" else f"{title}{tag}.mp4")
    rhythm = rhythm_line(bounds, state) if bounds else ""
    end_card = end_card_line(bounds, state) if bounds else ""
    dark = too_dark_line(out)
    blank, slop = blank_line(out, qc_dir / "report.txt"), ai_palette_line(out)
    noise = sound_budget_line(info, bounds) if not a.sound_only else ""
    thin = sound_thin_line(info, plan, state)
    buried = sound_buried_line(plan, score) if plan else ""
    late = sound_sync_line(plan)
    coded = sound_source_line(PROJECT / film, plan, state, info)
    copied = format_copy_line(a.film) if kind == "draft" else ""
    text = text_line(step, film, w, h) if not a.sound_only else ""
    oldcg = old_cg_line(state)
    avoff = av_start_line(out) if out.exists() else ""
    spans = voice_spans(plan, PROJECT / film)
    ending = ending_line(spans + words_before_card(dur), dur)
    unchosen = music_choice_line(PROJECT / film, plan, state)
    rests = rests_line(out, spans, dur, bounds, text_spans()) if out.exists() and kind == "draft" else ""
    issues += [x for x in (guard_off(), oldcg, avoff, dark, blank, slop, noise, thin, buried, coded, late, copied, text, ending,
                           unchosen) if x]
    if end_card:
        rhythm = (rhythm + "\n" if rhythm else "") + end_card
    weak = [i.split(":")[0] for i in issues if i.startswith(("TOO STILL", "TOO REPETITIVE"))] + \
        (["EVEN RHYTHM"] if "EVEN RHYTHM" in rhythm else []) + (["LONG END CARD"] if end_card else []) + (["TOO DARK"] if dark else []) + (["BLANK FRAMES"] if blank else []) + (["AI PALETTE"] if slop else []) + (["SOUND SLOP"] if noise else []) + (["SOUND THIN"] if thin else []) + (["SOUND BURIED"] if buried else []) + (["SOUND ALL CODE"] if coded else []) + (["SOUND LATE"] if late else []) + (["FORMAT COPY"] if copied else []) + (["TEXT"] if text else []) + (["OLD CG ROUTE"] if oldcg else []) + (["AV OFFSET"] if avoff else []) + (["ENDING SHORT"] if ending else [])
    passed = delivers(hook, master_ok, rc, avoff or unchosen, weak, a.show_anyway)
    extra = []
    if passed:
        tmp = deliver.with_name(deliver.name + ".part")
        shutil.copyfile(out, tmp)
        os.replace(tmp, deliver)              # atomic: the delivered file is never half written
    else:
        why = ", ".join([x for x, bad in (("the hook", hook != "PASS"), ("the master", not master_ok),
                                           ("the checks", rc != 0), ("sound and picture out of step", bool(avoff)),
                                           ("the music was never chosen", bool(unchosen)))
                         if bad] + [w.lower() for w in weak if not a.show_anyway])
        extra.append(f"NOT DELIVERED ({why}): " + (f"{deliver.name} still holds the last passing render" if deliver.exists() else f"no {kind} has been delivered yet") + f"; this one is {rel(out)}"
                     + ("; one fix pass on the flagged windows (an action in each still one, a new picture for each "
                        "repeat, scene lengths that vary), then make.py draft again: that one is shown, with what remains" if weak else ""))
    if gate is not None and kind == "draft" and not a.variant and not a.size:
        if passed:
            gate = {"held": False, "delivered": {"version": v, "file": deliver.name, "time": time.time()}}
            opened = show(deliver)
            extra.append(f"SHOW THIS DRAFT NOW: the film {deliver.resolve()}" + (f" and its poster {poster.resolve()}" if poster else "")
                         + f" (Claude Code: SendUserFile with display 'render', they open in the side panel; elsewhere their paths"
                         + (f" and the page {page(poster)}" if poster else "") + " in your message)"
                         + f"{' (opened on the user screen)' if opened else ''}; then ALWAYS the delivery question with the question "
                         f"tool, in the user's language: Final ★ · Notes · Jury check (jury.md, six pinpoint questions, two or "
                         f"three minutes); nothing more is rendered until the user's notes are in notes/. The independent "
                         f"viewer (templates/quick/REVIEWER.md, its report review/critique-v{v}.md) is an option the user "
                         f"may ask for, never started by itself and never required for the final")
            if weak:
                extra.append("LEFT AS IS, TELL THE USER: " + ", ".join(weak) + " held the last draft and remain. Say each "
                             "one with the draft in one plain line (what it is, where, why it was left), and let the user "
                             "decide: a note to fix it, or keep it. Never only a line on the card")
        elif weak and hook == "PASS" and master_ok:
            gate["held"] = True
        LOGS.mkdir(exist_ok=True)
        (LOGS / GATE).write_text(json.dumps(gate), encoding="utf-8")
    if kind == "final" and passed:
        extra.append(credits_file(title, tag))
    covers = cover_platforms(state) if kind == "final" and passed else []
    if covers and poster:
        social = PROJECT / f"{title}{tag}-x.mp4"
        part = social.with_name(social.stem + ".part.mp4")
        step.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", out, "-i", poster,
                  "-filter_complex", "[1:v][0:v]scale2ref[p][v];[v][p]overlay=0:0:enable='eq(n,0)'",
                  "-c:a", "copy", "-pix_fmt", "yuv420p", part])
        os.replace(part, social)
        extra.append(f"for {', '.join(covers)}: {social.name} (the poster on frame 0, their cover)")
    if kind == "draft" and v == 1 and not variant:
        extra.append("first draft: the silent test: from the sheet alone, one sentence on what the film is about; a miss is the first known item (engine.md §4)")
    mins = (time.time() - t0) / 60
    lines = [
        f"{kind} v{v}: {deliver.name if passed else rel(out) + ' (not delivered)'} · {dur:g} s · {w}x{h} · {loud_txt}{'' if master_ok else ' · MASTER FAILED'}"
        f" · {mins:.1f} min",
        f"hook {hook} · " + " · ".join(flags) + (" · " + ", ".join(issues) if issues else ""),
        f"look: {rel(sheet)} (a frame every {every} s) · poster: {rel(poster) if poster else '-'}",
        f"files: {rel(out)} · report: {rel(qc_dir / 'report.txt')} · log: {rel(step.log)}",
    ] + extra + [viewer, rhythm, taste_line(info), cliche_line(a.film, state), colour_line(out, state),
                 "" if a.variant or a.size else music_line(a.film, out, state, bounds), narration_line(a.film, dur), rests, words] + \
        [w_ for w_ in info.get("warnings", [])[:2]]
    finish(lines, 0 if passed else 1)


def stills(a):
    if unplugged_line():
        finish([unplugged_line()], 2)
    step = Step("stills")
    words = words_line()
    full = frame_size(a.size)
    info = probe(step, a.film, full)
    W, H = full or (info["w"], info["h"])
    fps, frames = info["fps"], info["frames"]
    if a.at:
        try:
            times = [float(t) for t in a.at.split(",") if t.strip()]
        except ValueError:
            finish(["--at needs seconds, for example 2,9,16,23"], 2)
    else:
        b = bounds_of(info) or [frames / fps * k / 4 for k in range(5)]
        times = [(b[i] + b[i + 1]) / 2 for i in range(len(b) - 1)][:12]
    picks = sorted({min(frames - 1, max(0, int(round(t * fps)))) for t in times})
    n = next((k for k in range(1, 999) if not (REVIEW / f"stills-{k}").exists()), 999)
    out = REVIEW / f"stills-{n}"
    w, h = even(W / 2), even(H / 2)
    step.run(["node", TOOLS / "capture.mjs", "--url", a.film, "--out", out, "--frames", ",".join(map(str, picks)),
              "--format", "jpeg", "--quality", "0.9", "--params", f"w={w}&h={h}"])
    n_pics = len(picks)
    cols = next((c for c in range(min(n_pics, 2 if H <= W else 4), n_pics + 1)
                 if math.ceil(n_pics / c) * (1024 / c) * H / W * 1024 <= 900_000), n_pics)
    rows = math.ceil(n_pics / cols)
    tile = 1024 // cols
    sheet = REVIEW / f"stills-{n}.jpg"
    listing = out / "frames.txt"                 # ffmpeg on Windows has no glob input: the frames are listed
    listing.write_text("".join("file '{}'\nduration 1\n".format(p.resolve().as_posix().replace("'", "'\\''"))
                               for p in sorted(out.glob("*.jpg"))), encoding="utf-8")
    step.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
              "-i", listing, "-vf", f"scale={tile - 4}:-2,pad={tile}:ih+4:2:2:black,tile={cols}x{rows}",
              "-frames:v", "1", "-update", "1", "-q:v", "4", sheet])
    secs = ", ".join(f"{f / fps:.1f}" for f in picks)
    opened = show(sheet)
    finish([f"stills: {rel(sheet)} ({len(picks)} frames at {secs} s, {cols} per row, ≤ 1024 px) · show the user: {sheet.resolve()} (Claude Code: SendUserFile with display 'render', it opens big in the side panel; elsewhere the page {page(sheet)} in your message)"
            + (" · opened on the user's screen" if opened else ""),
            f"full frames: {rel(out)}/ · log: {rel(step.log)}",
            view_line(a.film, state_text()), old_cg_line(state_text()),
            "scene test, each still before you go on: where does its light come from · what is near, middle and far "
            "· which line leads the eye to the subject · the texture on its largest surface, "
            "in words (\"none\", \"flat colour\" or \"clean low-poly\" is old CG: redraw on the card's route, looks.md §5) · in one sentence, what does this still show, and does a stranger "
            "get it? · does anything pass through something solid (a ball inside a building, "
            "a figure in a wall, a camera through a floor)? · does the subject fit the frame (nothing of it cut by the edge "
            "unless framed so on purpose)? A still that misses one is drawn again before the draft",
            rhythm_line(bounds_of(info) or [], state_text()),
            end_card_line(bounds_of(info) or [], state_text()),
            taste_line(info), words])


def page_title():
    """Quick mode: the TITLE the page itself carries (the delivered file's name), when film.html has one."""
    page = PROJECT / "film.html"
    m = re.search(r"^const TITLE\s*=\s*(['\"])(.+?)\1", page.read_text(encoding="utf-8"), re.M) if page.exists() else None
    return m[2].strip() if m and m[2].strip() != "Untitled" else ""


def film_title():
    """Film mode: the title from STATE.md's first line ("# State: <title> ..."), else shots.json, else the folder."""
    m = re.search(r"^#\s*State:\s*(.+?)(?:\s*\((?:Quick|Film) mode\))?\s*$", state_text(), re.M)
    if m:
        return m[1].strip()
    shots = read_json(PROJECT / "shots.json", "fps, title and shots")
    return (shots or {}).get("title") or PROJECT.name


def check(a):
    """Film mode: the same checks a Quick draft gets, on a cut already rendered (renders/draft-vN.mp4), with the mix
    plan in audio/mix.json and the scene bounds from shots.json. Writes logs/check-<cut>.txt; exit 1 when something
    holds the cut back (fix it, or tell the user with the cut what was left and why, for them to decide)."""
    if unplugged_line():
        finish([unplugged_line()], 2)
    video = Path(a.video)
    if not video.is_absolute():
        video = PROJECT / video
    if not video.exists():
        finish([f"FAILED: no {a.video}"], 2)
    missing = missing_tools()
    if missing:
        finish([f"FAILED: {', '.join(missing)} not found; install ffmpeg (macOS: brew install ffmpeg; Windows: "
                "winget install ffmpeg); then run again"], 2)
    step = Step(f"check-{video.stem}")
    _, d = step.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video])
    dur = float(d.strip() or 0)
    state = state_text()
    bounds, fps = [], 24
    sj = read_json(PROJECT / "shots.json", "fps and shots")
    if sj is not None:
        fps = sj.get("fps") or fps
        shots = sj.get("shots")
        if not isinstance(shots, list) or not all(isinstance(s, dict) and isinstance(s.get("start"), (int, float))
                                                  for s in shots):
            finish(["FAILED: shots.json needs \"shots\": a list of objects, each with a frame number \"start\""], 2)
        bounds = [s["start"] / fps for s in shots] + [dur]
    plan = read_json(PROJECT / "audio" / "mix.json", "the mix plan: duration, out, layers")
    if plan is not None and (not isinstance(plan.get("layers"), list) or not all(isinstance(L, dict) for L in plan["layers"])):
        finish(["FAILED: audio/mix.json needs \"layers\": a list of objects (file, at, bus)"], 2)
    qc_dir = REVIEW / f"qc-{video.stem}"
    env = dict(os.environ, QC_OUT=str(qc_dir), QC_SHEET_EVERY=str(max(2, math.ceil(dur / 18))))
    rc, _ = step.run([sys.executable, TOOLS / "qc.py", "all", video] + ([",".join(f"{b:g}" for b in bounds)] if bounds else []),
                     env=env, ok=(0, 1))
    hook, flags, issues = report_lines(qc_dir / "report.txt", bounds)
    sheet = small_sheet(step, qc_dir) if (qc_dir / "sheet.jpg").exists() else None
    info = {"frames": round(dur * fps), "fps": fps, "sfx": []}
    voice = [float(L.get("at") or 0) for L in (plan or {}).get("layers", []) if L.get("bus") == "dialogue"]
    late = (f"NARRATION LATE: the first spoken line starts at {min(voice):.1f} s; over a minute the voice begins in "
            "the first 2 s (film-mode.md, writing.md)") if dur > 60 and voice and min(voice) > 2 else ""
    named = {"TOO DARK": too_dark_line(video), "BLANK FRAMES": blank_line(video, qc_dir / "report.txt"),
             "AI PALETTE": ai_palette_line(video), "SOUND THIN": sound_thin_line(info, plan, state),
             "SOUND ALL CODE": sound_source_line(PROJECT / "film.html", plan, state), "SOUND LATE": sound_sync_line(plan),
             "AV OFFSET": av_start_line(video),
             "SOUND BURIED": sound_buried_line(plan, PROJECT / next((L.get("file", "") for L in (plan or {}).get("layers", [])
                                                                     if L.get("bus") == "music"), "-"))}
    spans = voice_spans(plan)
    named["ENDING SHORT"] = ending_line(spans + words_before_card(dur), dur)
    named["MUSIC NOT CHOSEN"] = music_choice_line(PROJECT / "film.html", plan, state)
    rests = rests_line(video, spans, dur, bounds, text_spans())
    rhythm = rhythm_line(bounds, state) if len(bounds) > 2 else ""
    if "EVEN RHYTHM" in rhythm:
        named["EVEN RHYTHM"] = rhythm
    held = [k for k, v in named.items() if v] + [i.split(":")[0] for i in issues if i.startswith(("TOO STILL", "TOO REPETITIVE"))]
    if hook != "PASS":
        held.insert(0, "HOOK")
    animatic = animatic_made(video)
    if animatic:                                 # timing cards and a temporary bed: only the timing is held here
        held = [k for k in held if k == "ENDING SHORT"]
    lines = ([guard_off()] if guard_off() else []) + [
             f"check {video.name}: {dur:g} s · " + ("HELD: " + ", ".join(held) if held else "passes the draft checks"),
             f"hook {hook} · " + " · ".join(flags) + (" · " + ", ".join(issues) if issues else "")]
    lines += [v for v in named.values() if v] + ([rhythm] if rhythm and "EVEN RHYTHM" not in rhythm else [])
    lines += [late] if late else []
    lines += [rests] if rests else []
    if animatic:
        lines.insert(2, "animatic: only the ending's time is held here (and the pace reported); the picture, sound and "
                        "hook checks wait for the draft cut")
    lines += ["text on screen is not measured in Film mode: read it at phone size on the sheet "
              f"({rel(sheet or qc_dir / 'sheet.jpg')}; the jury reads this one too)",
              "fix each held item; one you leave as it is goes to the user with the cut, in one plain line each "
              "(what, where, why it was left) for them to decide: never only a line on the roadmap's card; then show the cut"]
    LOGS.mkdir(exist_ok=True)
    (LOGS / f"check-{video.stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    finish(lines, 1 if held else 0)


def credits_cmd(a):
    line = credits_file(a.title or page_title() or film_title(), "")
    finish([line or "credits: LICENSES.csv lists no outside material (no credits file needed)"], 0)


def remember_film():
    """The film's idea joins the memory of this user's films (dice.py), which new ideas are checked against."""
    try:
        import dice
        dice.remember(str(PROJECT))
    except Exception as e:                        # the film is delivered either way; only the memory of it is lost
        debug("dice.remember", e)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("stills", "draft", "final", "check"):
        remember_film()
    if len(sys.argv) > 1 and sys.argv[1] == "wait":
        ap = argparse.ArgumentParser(description="wait for the step running in the background and print its summary")
        ap.add_argument("cmd", choices=["wait"])
        ap.add_argument("--max", type=float, default=900, help="seconds to wait at most (default 900)")
        return wait_cmd(ap.parse_args().max)
    if len(sys.argv) > 1 and sys.argv[1] in ("check", "credits"):
        ap = argparse.ArgumentParser(description="Film mode: check a rendered cut, or write the credits file")
        ap.add_argument("cmd", choices=["check", "credits"])
        ap.add_argument("video", nargs="?", help="check: the cut, e.g. renders/draft-v3.mp4")
        ap.add_argument("--title", help="credits: the film's title (default: STATE.md's)")
        a = ap.parse_args()
        if a.cmd == "check" and not a.video:
            ap.error("check needs the cut: make.py check renders/draft-vN.mp4")
        if a.cmd == "check":
            mark_running("check")
        return check(a) if a.cmd == "check" else credits_cmd(a)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["stills", "draft", "final"])
    ap.add_argument("--film", default="film.html")
    ap.add_argument("--size", help="WxH; another aspect than STATE.md's format becomes a variant (<Title>-1x1.mp4)")
    ap.add_argument("--variant", help="name the variant yourself (default: the aspect, e.g. 1x1)")
    ap.add_argument("--workers", default="2")
    ap.add_argument("--poster", type=float)
    ap.add_argument("--at")
    ap.add_argument("--sound-only", action="store_true")
    ap.add_argument("--show-anyway", action="store_true",
                    help="deliver a draft held back for stillness or repeats (the run after a hold does it by itself)")
    ap.add_argument("--force", action="store_true",
                    help="draft: render although the last one has not been shown; final: go ahead over the viewer's "
                         "red items the user chose to keep (only when the user asked)")
    a = ap.parse_args()
    mark_running(a.step)
    for tool in ("node", "ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            finish([f"FAILED: {tool} is not installed"], 2)
    stills(a) if a.step == "stills" else render(a, a.step)


if __name__ == "__main__":
    if os.name == "nt" and not sys.flags.utf8_mode:   # Windows reads, writes and prints in a legacy code page
        import subprocess
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=dict(os.environ, PYTHONUTF8="1")))
    for _s in (sys.stdin, sys.stdout, sys.stderr):
        getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")
    main()
