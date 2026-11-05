#!/usr/bin/env python3
"""Temp and final narration from the script, with Gemini TTS (default), ElevenLabs (optional), or a free local engine
(VieNeu-TTS for Vietnamese; VOICEVOX or Irodori-TTS for Japanese).
Python 3 standard library + ffmpeg. The key is entered once for every film (tools/keys.py set GEMINI_API_KEY) and
never printed; the environment or a film's own .env can override it.

  tts.py --lines audio/vo-lines.json --out audio/vo                           # Gemini, default voice and style
  tts.py --lines audio/vo-lines.json --out audio/vo --style "<the delivery, from the sound identity>"
  tts.py --lines audio/vo-lines.json --out audio/vo --voice <voice> --style "<the delivery>"
  tts.py --engine elevenlabs --voice <voice_id> --lines audio/vo-lines.json --out audio/vo --style "<the delivery>"
  tts.py --text "<one line of the script>" --id VO1 --out audio/vo --dry-run   # show the request, send nothing
  tts.py --engine vieneu --voice "<preset>" --lines audio/vo-lines.json --out audio/vo   # local VieNeu server
  tts.py --voices vieneu                                                   # the presets the VieNeu server offers
  tts.py --engine edge --voice en-US-EmmaNeural --lines audio/vo-lines.json --out audio/vo   # a local edge-tts server
  tts.py --voices edge                                                     # the voices that server offers
  tts.py --voices voicevox                                                 # VOICEVOX characters and their style ids
  tts.py --engine voicevox --voice "ずんだもん:ノーマル" --lines audio/vo-lines.json --out audio/vo
  tts.py --engine irodori --voice "落ち着いた、近い距離感の女性話者" --lines audio/vo-lines.json --out audio/vo
  tts.py --install irodori                                                 # once, only after the user's OK
  tts.py --audition "gemini:<voice>,gemini:<voice>,elevenlabs:<voice_id>" --text "<one line of the script>" \
         --style "<the delivery>" --out review/voices      # one short file per candidate voice, never joined

vo-lines.json (the writer exports it from SCRIPT.md; the style follows the film's sound identity):
  {"lines": [{"id": "VO1", "text": "<line>", "style": "<its delivery>"},
             {"id": "VO2", "text": "<line>", "style": "<its delivery>"}]}
A line's own "style" overrides --style. Output: <out>/<id>.wav (48 kHz mono, 24-bit) + <out>/tts-log.json.
The raw lines are never the film's voice: voice_treat.py gives them the film's own treatment next (sound.md §4b).
A chorus is one run per voice. No style is the default: it follows the film's voice treatment.

Engines
  gemini      GEMINI_API_KEY · model gemini-3.8-flash-tts (or gemini-3.8-flash-lite-tts) · named voices (e.g. Kore,
              Puck, Charon) · delivery in plain words through speech_metadata.style ("warm and curious", "deadpan")
  elevenlabs  ELEVENLABS_API_KEY · --voice <voice_id> from your voice library · model eleven_v3 (70+ languages,
              audio tags such as [excited], [laughs], [whispers]) or eleven_multilingual_v2 (steady multilingual
              narration, no tags)
  vieneu      VieNeu-TTS (Vietnamese, free, offline, no key) through a local HTTP server the user runs themselves
              (POST /tts, GET /voices; VIENEU_URL, default http://127.0.0.1:8000). Named presets (--voice; none = the
              server's default), no free-text style: cues such as [cười] or [thở dài] go in the line itself. Its
              quality is below Gemini and ElevenLabs, so it is never the default: offer it in the voice question every
              time, beside the others, and let the user's ear decide (an audition take is the fair test). Apache-2.0.
  edge        Microsoft Edge neural voices (free, no key; English, Vietnamese, Japanese, Chinese, Korean and more)
              through an edge-tts server the user runs themselves (POST /tts/free/base64 {text, voiceId, speed, style}
              -> {base64: mp3}; GET /voices; EDGE_TTS_URL, default http://127.0.0.1:8787). --voice is a voiceId from
              --voices edge (e.g. en-US-EmmaNeural); --speed 0.5-1.5; --style only a named style some voices support
              (cheerful, sad), not free text. An option the user may choose, never the default and never the ★; the
              voices belong to Microsoft's online service, so its terms apply before commercial use.
  voicevox    VOICEVOX (Japanese, free, local, no key) through the VOICEVOX app's engine (VOICEVOX_URL, default
              http://127.0.0.1:50021). --voice "<character>[:<style>]" or a style id (tts.py --voices voicevox);
              --speed. Commercial use is free but every character has its own terms and a credit is required
              ("VOICEVOX:<character>"): each run writes the credit into LICENSES.csv and saves the character's terms
              beside the takes (VOICEVOX-<character>-terms.txt) for the user to read before publishing.
  irodori     Irodori-TTS v4.1 Small (Aratako, MIT; Japanese only): a voice designed from a caption (--voice
              "落ち着いた女性話者…"), or cloned from a clean reference (--ref audio/ref.wav, about 30 s, with the
              speaker's consent). A local install the user OKs first (tts.py --install irodori: git + uv, PyTorch, a few
              GB; IRODORI_DIR to use an existing clone). Its output carries an inaudible watermark (SilentCipher).

VieNeu, edge, VOICEVOX and Irodori are offered in the voice question of a film in their language, never preselected and
never the ★: they are free, the paid engines usually sound better, and the user's ear decides.
"""
import argparse
import base64
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keys  # noqa: E402  (same folder: the key store shared by every film)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
ENGINES = ("gemini", "elevenlabs", "vieneu", "edge", "voicevox", "irodori")
LOCAL = ("voicevox", "irodori")                  # engines that are not one HTTP request per take


def vieneu_url():
    return os.environ.get("VIENEU_URL", "http://127.0.0.1:8000").rstrip("/")


def vieneu_down(e):
    return RuntimeError(f"the VieNeu server does not answer at {vieneu_url()} ({str(e)[:80]}): ask the user to start it "
                        "(its README: uv run uvicorn app.main:app --port 8000), or set VIENEU_URL to where it runs")


def vieneu_voices():
    """[(label, id)] of the server's presets."""
    try:
        with urllib.request.urlopen(vieneu_url() + "/voices", timeout=10) as r:
            return [(v.get("label"), v.get("id")) for v in json.load(r)]
    except (OSError, ValueError) as e:
        raise vieneu_down(e) from None


def edge_url():
    return os.environ.get("EDGE_TTS_URL", "http://127.0.0.1:8787").rstrip("/")


def edge_down(e):
    return RuntimeError(f"the edge-tts server does not answer at {edge_url()} ({str(e)[:80]}): ask the user to start it "
                        "(its README, e.g. npm run dev), or set EDGE_TTS_URL to where it runs")


def edge_voices():
    """[(label, voiceId)] from the server's GET /voices (every language)."""
    try:
        with urllib.request.urlopen(edge_url() + "/voices", timeout=10) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError) as e:
        raise edge_down(e) from None
    langs = data.get("voices", data) if isinstance(data, dict) else {"": data}
    return [(f"{v.get('voiceId')} · {v.get('gender', '')} · {lang}", v.get("voiceId"))
            for lang, vs in langs.items() for v in (vs or [])]


def edge_request(text, style, voice, a):
    body = {"text": text, "voiceId": voice or "en-US-JennyNeural", "speed": max(0.5, min(1.5, getattr(a, "speed", 1.0)))}
    if style and re.fullmatch(r"[a-z-]+", style.strip()):
        body["style"] = style.strip()
    elif style:
        print(f"   note: edge takes only a named style (cheerful, sad); '{style[:40]}' is not applied")
    return body


def vieneu_request(text, style, voice):
    if style:
        print(f"   note: VieNeu takes no free-text style; '{style[:40]}' is not applied (cues such as [cười] go in the line)")
    body = {"text": text, "format": "wav"}
    if voice:
        body["voice"] = voice
    return body


def request_for(engine, text, style, voice, model, a):
    """(url, body, headers, key name) for one take on an HTTP engine."""
    if engine == "gemini":
        key = keys.get("GEMINI_API_KEY")
        return GEMINI_URL, gemini_request(text, style, voice, model), \
            {"x-goog-api-key": key or "", "Content-Type": "application/json"}, "GEMINI_API_KEY"
    if engine == "elevenlabs":
        key = keys.get("ELEVENLABS_API_KEY")
        return ELEVEN_URL.format(voice=voice or "<voice_id>"), eleven_request(text, style, model, a.seed, a.stability), \
            {"xi-api-key": key or "", "Content-Type": "application/json"}, "ELEVENLABS_API_KEY"
    if engine == "edge":
        return edge_url() + "/tts/free/base64", edge_request(text, style, voice, a), {"Content-Type": "application/json"}, None
    return vieneu_url() + "/tts", vieneu_request(text, style, voice), {"Content-Type": "application/json"}, None


def take(engine, url, body, headers):
    """The audio bytes of one take."""
    if engine == "edge":
        try:
            raw, _ = post(url, body, headers, timeout=120)
        except urllib.error.URLError as e:
            raise edge_down(e.reason) from None
        except OSError as e:
            raise edge_down(e) from None
        try:
            return base64.b64decode(json.loads(raw)["base64"])
        except (ValueError, KeyError, TypeError):
            raise RuntimeError("the edge-tts server answered without audio: " + raw[:160].decode("utf-8", "replace")) from None
    if engine == "vieneu":
        try:
            raw, _ = post(url, body, headers, timeout=600)   # a CPU model: a long line takes a while
        except urllib.error.URLError as e:
            raise vieneu_down(e.reason) from None
        except OSError as e:
            raise vieneu_down(e) from None
        return raw
    raw, _ = post_patiently(url, body, headers)
    return gemini_audio(raw) if engine == "gemini" else raw


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A request that carries a key is never followed to another address (the key would travel with it)."""
    def redirect_request(self, *args, **kwargs):
        return None


def post(url, body, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as r:
            return r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        for value in headers.values():                   # a service that echoes the key never gets it printed
            if value and len(str(value)) >= 8 and "/" not in str(value):
                detail = detail.replace(str(value), "<key>")
        raise RuntimeError(f"HTTP {e.code}: {detail}") from None


def post_patiently(url, body, headers, wait=time.sleep):
    """A per-minute limit (HTTP 429 with a retry delay) waits and tries again, up to three times; a daily quota raises
    QuotaSpent at once, so the run stops with what is left instead of failing line after line."""
    for attempt in range(4):
        try:
            return post(url, body, headers)
        except RuntimeError as e:
            text = str(e)
            if not text.startswith("HTTP 429"):
                raise
            if re.search(r"per[ _]?day|daily", text, re.I) or attempt == 3:
                raise QuotaSpent(text) from None
            delay = re.search(r'"retryDelay":\s*"(\d+)', text)
            wait(min(65, int(delay[1]) + 2) if delay else 25)


class QuotaSpent(RuntimeError):
    pass


def gemini_request(text, style, voice, model):
    content = {"type": "text", "text": text}
    if style:
        content["annotations"] = [{"type": "speech_metadata", "style": style}]
    return {"model": model, "input": [{"type": "user_input", "content": [content]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice}]}}


def gemini_audio(resp):
    data = json.loads(resp)
    blocks = [c for st in data.get("steps", []) if st.get("type") == "model_output"
              for c in st.get("content", []) if c.get("type") == "audio"]
    if not blocks:
        raise RuntimeError("no audio in the Gemini response")
    return base64.b64decode(blocks[-1]["data"])


ELEVEN_TAGS = {"whisper": "whispers", "thì thầm": "whispers", "囁": "whispers", "excit": "excited", "energ": "excited", "curious": "curious",
               "sad": "sad", "calm": "calm", "warm": "warmly", "sarcas": "sarcastic", "deadpan": "deadpan", "laugh": "laughs",
               "shout": "shouting", "playful": "playfully", "tired": "tired", "mysteri": "mysteriously"}


def eleven_request(text, style, model, seed, stability):
    if style and not text.lstrip().startswith("["):
        tags = sorted({t for k, t in ELEVEN_TAGS.items() if k in style.lower()})
        if model in ("eleven_v3", "eleven_v4") and tags:
            text = "".join(f"[{t}] " for t in tags[:2]) + text   # audio tags: delivery direction, not spoken
        else:
            print(f"   note: ElevenLabs {model} takes no free-text style; '{style[:40]}' is not applied"
                  + ("" if model in ("eleven_v3", "eleven_v4") else " (eleven_v3 understands tags such as [calm], [excited])"))
    body = {"text": text, "model_id": model,
            "voice_settings": {"stability": stability, "similarity_boost": 0.75, "style": 0.0, "speed": 1.0}}
    if seed is not None:
        body["seed"] = seed
    return body


def to_wav(data, dst):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "pipe:0", "-ac", "1", "-ar", "48000",
                        "-c:a", "pcm_s24le", dst], input=data, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg could not decode the audio: " + p.stderr.decode()[-200:])
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", dst],
                       stdout=subprocess.PIPE, text=True).stdout.strip()
    return float(d or 0)


VOICEVOX_SITE = "https://voicevox.hiroshiba.jp/"
IRODORI_REPO = "https://github.com/Aratako/Irodori-TTS.git"
IRODORI_MODEL = "Aratako/Irodori-TTS-v4.1-Small"


def voicevox_url():
    return os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021").rstrip("/")


def voicevox_down(e):
    return RuntimeError(f"VOICEVOX does not answer at {voicevox_url()} ({str(e)[:80]}): ask the user to open the VOICEVOX "
                        "app (its engine starts with it), or set VOICEVOX_URL to where the engine runs")


def voicevox_get(path):
    try:
        with urllib.request.urlopen(voicevox_url() + path, timeout=10) as r:
            return json.load(r)
    except (OSError, ValueError) as e:
        raise voicevox_down(e) from None


def voicevox_speakers():
    """[(character, style, id, uuid)] of the talk styles the engine offers."""
    return [(s["name"], st["name"], st["id"], s.get("speaker_uuid", "")) for s in voicevox_get("/speakers")
            for st in s.get("styles", []) if st.get("type", "talk") == "talk"]


def voicevox_voice(voice):
    """(character, style, id, uuid) for "ずんだもん", "ずんだもん:ノーマル" or a style id."""
    rows = voicevox_speakers()
    v = str(voice or "").strip()
    if v.isdigit():
        hit = [x for x in rows if x[2] == int(v)]
    else:
        name, _, style = v.partition(":")
        hit = [x for x in rows if x[0] == name.strip() and (not style or x[1] == style.strip())]
    if not hit:
        raise RuntimeError(f"VOICEVOX has no voice '{v}': tts.py --voices voicevox lists them as <character>:<style> (id)")
    return hit[0]


def voicevox_take(text, voice, speed=1.0):
    character, style, sid, _ = voicevox_voice(voice)
    q = urllib.parse.urlencode({"text": text, "speaker": sid})
    try:
        req = urllib.request.Request(f"{voicevox_url()}/audio_query?{q}", data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            query = json.load(r)
        query["speedScale"] = speed
        req = urllib.request.Request(f"{voicevox_url()}/synthesis?speaker={sid}", data=json.dumps(query).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"VOICEVOX HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from None
    except OSError as e:
        raise voicevox_down(e) from None


def voicevox_credit(voice, out):
    """The character's own terms saved beside the takes, and its credit row in LICENSES.csv (the credits file reads it)."""
    character, style, _, uuid = voicevox_voice(voice)
    policy = voicevox_get(f"/speaker_info?speaker_uuid={urllib.parse.quote(uuid)}").get("policy", "") if uuid else ""
    terms = os.path.join(out, f"VOICEVOX-{character}-terms.txt")
    with open(terms, "w", encoding="utf-8") as f:
        f.write(policy or f"(no terms text from the engine: read {VOICEVOX_SITE} and the character's own page)\n")
    url = (re.findall(r"https?://\S+", policy) or [VOICEVOX_SITE])[0]
    licence_row(f"{out.rstrip('/')}/", f"VOICEVOX:{character} ({style})", character, VOICEVOX_SITE,
                "VOICEVOX terms + the character's terms", url, f"VOICEVOX:{character}",
                f"read {terms} before publishing (some characters limit uses)")
    return terms


def irodori_dir():
    return os.environ.get("IRODORI_DIR") or os.path.join(os.path.expanduser("~"), ".rubydai-video", "tts-irodori")


def irodori_missing():
    return None if os.path.exists(os.path.join(irodori_dir(), "infer.py")) else (
        f"Irodori-TTS is not installed in {irodori_dir()}: a local install of a few GB (PyTorch and the model), only if "
        "the user wants it: python3 tools/tts.py --install irodori (or IRODORI_DIR=<an existing clone>)")


def irodori_take(text, voice, style, ref, dst):
    """One take with the Irodori CLI (it loads the model per take: a line takes a while on a CPU or Apple GPU)."""
    if irodori_missing():
        raise RuntimeError(irodori_missing())
    caption = "、".join(x for x in (voice, style) if x)
    cmd = ["uv", "run", "--no-sync", "python", "infer.py", "--hf-checkpoint", IRODORI_MODEL, "--text", text,
           "--output-wav", os.path.abspath(dst)]
    cmd += ["--ref-wav", os.path.abspath(ref)] if ref else ["--no-ref"]
    if caption:
        cmd += ["--caption", caption]
    p = subprocess.run(cmd, cwd=irodori_dir(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError("Irodori-TTS failed: " + (p.stderr or p.stdout).strip()[-300:])
    with open(dst, "rb") as f:
        data = f.read()
    os.remove(dst)                               # the caller keeps the take at 48 kHz 24-bit like every engine's
    return data


def install_irodori():
    """A clone of the Irodori-TTS repository with its own uv environment (the backend picked for this machine)."""
    import shutil
    for tool in ("git", "uv"):
        if not shutil.which(tool):
            sys.exit(f"Irodori-TTS needs {tool}: install it first (uv: https://docs.astral.sh/uv/), then run this again")
    d = irodori_dir()
    if not os.path.exists(os.path.join(d, "infer.py")):
        subprocess.run(["git", "clone", "--depth", "1", IRODORI_REPO, d], check=True)
    extra = "cu128" if shutil.which("nvidia-smi") else "cpu"          # macOS: the cpu extra brings CPU and MPS
    subprocess.run(["uv", "sync", "--extra", extra], cwd=d, check=True)
    print(f"Irodori-TTS installed in {d} (remove that folder to uninstall); the model ({IRODORI_MODEL}) downloads on "
          "first use")
    return 0


def licence_row(file, title, author, source, licence, licence_url, attribution, notes):
    """One row in the film's LICENSES.csv (when the chat runs in the film's folder), once."""
    path = "LICENSES.csv"
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        if any(row and row[0] == file and len(row) > 1 and row[1] == title for row in csv.reader(f)):
            return
    with open(path, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([file, title, author, source, licence, licence_url, attribution, "voice treatment",
                                time.strftime("%Y-%m-%d"), "narration", notes])


def local_licence(engine, voice, out):
    """The licence row of a free engine's voice, written when its takes are made."""
    if engine == "voicevox":
        return voicevox_credit(voice, out)
    if engine == "vieneu":
        licence_row(f"{out.rstrip('/')}/", "VieNeu-TTS v3 Turbo" + (f" ({voice})" if voice else ""), "pnnbao97",
                    "https://github.com/pnnbao97/VieNeu-TTS", "Apache-2.0", "https://www.apache.org/licenses/LICENSE-2.0",
                    "Voice: VieNeu-TTS (Apache-2.0)", "synthetic voice, run locally")
    if engine == "edge":
        licence_row(f"{out.rstrip('/')}/", "Microsoft Edge neural voice" + (f" ({voice})" if voice else ""), "Microsoft",
                    "https://learn.microsoft.com/azure/ai-services/speech-service/language-support", "Microsoft service terms",
                    "https://www.microsoft.com/servicesagreement", f"Voice: Microsoft {voice or 'Edge'} neural voice",
                    "synthetic voice through the user's own edge-tts server; read the service terms before commercial use")
    if engine == "irodori":
        licence_row(f"{out.rstrip('/')}/", IRODORI_MODEL, "Aratako", f"https://huggingface.co/{IRODORI_MODEL}", "MIT",
                    f"https://huggingface.co/{IRODORI_MODEL}", "Voice: Irodori-TTS (MIT)",
                    "synthetic voice with a SilentCipher watermark; no cloning of a person without consent")


def synth(engine, model, voice, text, style, a, dst):
    """One take to dst (48 kHz WAV); returns its length in seconds."""
    if engine == "voicevox":
        return to_wav(voicevox_take(text, voice, a.speed), dst)
    if engine == "irodori":
        return to_wav(irodori_take(text, voice, style, getattr(a, "ref", None), dst + ".irodori.wav"), dst)
    url, body, headers, key_name = request_for(engine, text, style, voice, model, a)
    if key_name and not keys.get(key_name):
        raise RuntimeError(f"{key_name} is not set (tools/keys.py open)")
    return to_wav(take(engine, url, body, headers), dst)


def auditioned(root="."):
    """An audition was made in this project (tts.py --audition leaves AUDITION.json beside its takes)."""
    for top, dirs, files in os.walk(root):
        if "AUDITION.json" in files:
            return True
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("tools", "renders", "frames", "node_modules")]
        if top.count(os.sep) - root.count(os.sep) >= 3:
            dirs[:] = []
    return False


def audition(a):
    if not a.text:
        sys.exit("--audition needs --text: one line of the script (about 8-15 words), the same for every voice")
    os.makedirs(a.out, exist_ok=True)
    made, cands = [], [c.strip() for c in a.audition.split(",") if c.strip()]
    for n, cand in enumerate(cands, 1):
        engine, _, voice = cand.partition(":")
        voice = voice or ({"vieneu": "default"}.get(engine, ""))
        if engine not in ENGINES or not voice:
            print(f"{n}. skipped '{cand}': write engine:voice (gemini:Kore, elevenlabs:<voice_id>, vieneu:<preset>, edge:<voiceId>, "
                  "voicevox:<character>[:<style>], irodori:<caption>)")
            continue
        model = {"vieneu": "vieneu", "edge": "edge", "voicevox": "voicevox", "irodori": IRODORI_MODEL}.get(engine) or \
            (a.model if a.model and (a.model.startswith("gemini") == (engine == "gemini")) else
             ("gemini-3.8-flash-tts" if engine == "gemini" else "eleven_v3"))
        name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in voice)[:24]
        dst = os.path.join(a.out, f"{n}-{engine}-{name}.wav")
        if a.dry_run:
            print(f"{n}. {engine} {model} {voice} -> {dst}")
            continue
        try:
            dur = synth(engine, model, None if voice == "default" and engine == "vieneu" else voice, a.text, a.style, a, dst)
            made.append(dst)
            print(f"{n}. {dst}  {dur:.1f} s  ({engine} · {voice})")
        except Exception as e:
            print(f"{n}. {engine} · {voice}: failed ({str(e)[:140]})")
    if a.dry_run:
        return 0
    if made:
        with open(os.path.join(a.out, "AUDITION.json"), "w", encoding="utf-8") as f:
            json.dump({"text": a.text, "takes": made}, f, ensure_ascii=False, indent=1)
        print(f"{len(made)} separate takes of the same line; play each on its own and let the user pick (no joined file)"
              + (f"; {len(cands) - len(made)} failed or skipped" if len(made) < len(cands) else ""))
        return 0
    print("no take was made: nothing to play (see the lines above)")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", choices=list(ENGINES), default=os.environ.get("TTS_ENGINE", "gemini"))
    ap.add_argument("--voices", choices=["vieneu", "edge", "voicevox"], help="list the voices of a local engine")
    ap.add_argument("--install", choices=["irodori"], help="irodori: install Irodori-TTS (a few GB, once; ask the user first)")
    ap.add_argument("--speed", type=float, default=1.0, help="voicevox: 0.5 to 2; edge: 0.5 to 1.5")
    ap.add_argument("--ref", help="irodori: a clean reference recording to clone (about 30 s; the speaker's consent)")
    ap.add_argument("--lines", help="vo-lines.json")
    ap.add_argument("--text", help="one line instead of --lines")
    ap.add_argument("--id", default="VO1")
    ap.add_argument("--out", help="the folder for the takes (needed for everything but --install)")
    ap.add_argument("--voice", help="gemini: voice name (default Charon); elevenlabs: voice_id (required); "
                                     "vieneu: a preset from --voices vieneu (default: the server's); edge: a voiceId "
                                     "from --voices edge; voicevox: "
                                     "<character>[:<style>] or a style id; irodori: a caption that designs the voice")
    ap.add_argument("--model", help="gemini-3.8-flash-tts | gemini-3.8-flash-lite-tts | eleven_v3 | eleven_multilingual_v2")
    ap.add_argument("--style", default="", help='delivery from the sound identity (default: none)')
    ap.add_argument("--seed", type=int, default=7, help="elevenlabs: best-effort repeatable takes")
    ap.add_argument("--stability", type=float, default=0.45, help="elevenlabs: lower = more expressive")
    ap.add_argument("--only", help="comma list of line ids to (re)generate")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--voice-chosen", action="store_true", help="the user already picked this voice (no audition)")
    ap.add_argument("--audition", help='candidate voices for the user to choose by ear, "engine:voice,..."; with --text '
                                       '(one line of the script): one short file per candidate in --out, never joined')
    a = ap.parse_args()
    if a.install:
        return install_irodori()
    if a.voices:
        try:
            if a.voices == "voicevox":
                for character, style, sid, _ in voicevox_speakers():
                    print(f"  {character}:{style}  ({sid})")
                print(f"every VOICEVOX character has its own terms and needs a credit (VOICEVOX:<character>): {VOICEVOX_SITE}")
            elif a.voices == "edge":
                for label, _ in edge_voices():
                    print(f"  {label}")
            else:
                for label, vid in vieneu_voices():
                    print(f"  {label}" + (f"  ({vid})" if vid and vid != label else ""))
        except RuntimeError as e:
            sys.exit(str(e))
        return 0
    if not a.out:
        ap.error("the following arguments are required: --out")
    if a.audition:
        return audition(a)

    if a.lines:
        with open(a.lines, encoding="utf-8") as source:
            lines = json.load(source)["lines"]
        if len(lines) > 3 and not a.voice_chosen and not a.dry_run and not auditioned():
            sys.exit("tts: the whole narration waits for the voice the user picked by ear: first --audition (2-3 voices "
                     "reading one line, KIT/references/sound.md §4b step 0), the user listens and picks; or "
                     "--voice-chosen when the user already named this voice")
    elif a.text:
        lines = [{"id": a.id, "text": a.text}]
    else:
        sys.exit("give --lines or --text")
    if a.only:
        keep = set(a.only.split(","))
        lines = [l for l in lines if l["id"] in keep]

    if a.engine == "gemini":
        key_name, model, voice = "GEMINI_API_KEY", a.model or "gemini-3.8-flash-tts", a.voice or "Charon"
    elif a.engine == "elevenlabs":
        key_name, model, voice = "ELEVENLABS_API_KEY", a.model or "eleven_v3", a.voice
        if not voice and not a.dry_run:
            sys.exit("elevenlabs needs --voice <voice_id> (from your ElevenLabs voice library)")
    else:
        key_name, model, voice = None, {"vieneu": "vieneu", "edge": "edge", "voicevox": "voicevox", "irodori": IRODORI_MODEL}[a.engine], a.voice
        if a.engine == "voicevox" and not voice:
            sys.exit('voicevox needs --voice "<character>[:<style>]" (tts.py --voices voicevox)')
        if not a.dry_run:
            try:                                  # the engine answers before any line is sent
                if a.engine == "vieneu":
                    vieneu_voices()
                elif a.engine == "edge":
                    edge_voices()
                elif a.engine == "voicevox":
                    voicevox_voice(voice)
                elif irodori_missing():
                    sys.exit(irodori_missing())
            except RuntimeError as e:
                sys.exit(str(e))
    if key_name and not keys.get(key_name) and not a.dry_run:
        sys.exit(f"{key_name} is not set yet. Enter it once for every film: python3 tools/keys.py set {key_name}")

    os.makedirs(a.out, exist_ok=True)
    log_path = os.path.join(a.out, "tts-log.json")
    log = []
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as source:
            log = json.load(source)
    total, failed, spent = 0.0, [], None
    for ln in lines:
        if spent:
            failed.append(ln["id"])
            continue
        style = ln.get("style", a.style)
        if a.engine in LOCAL:
            if a.dry_run:
                print(f"{ln['id']}: {a.engine} {model} voice={voice}: {ln['text'][:80]}")
                continue
            url, body, headers = None, None, None
        else:
            url, body, headers, _ = request_for(a.engine, ln["text"], style, voice, model, a)
        if a.dry_run:
            print(f"{ln['id']}: {a.engine} {model} voice={voice} POST {url.split('?')[0]}")
            print("   " + json.dumps(body, ensure_ascii=False)[:240])
            continue
        dst = os.path.join(a.out, f"{ln['id']}.wav")
        tmp = os.path.join(a.out, f".{ln['id']}.new.wav")
        try:
            dur = synth(a.engine, model, voice, ln["text"], style, a, tmp) if a.engine in LOCAL else \
                to_wav(take(a.engine, url, body, headers), tmp)
            os.replace(tmp, dst)                       # a new take replaces the old one only when it is complete
        except QuotaSpent:
            spent = ln["id"]
            failed.append(ln["id"])
            continue
        except Exception as e:
            print(f"{ln['id']}: failed ({str(e)[:160]})" + (" · the previous take is kept" if os.path.exists(dst) else ""))
            failed.append(ln["id"])
            if os.path.exists(tmp):
                os.remove(tmp)
            continue
        total += dur
        log.append({"id": ln["id"], "engine": a.engine, "model": model, "voice": voice, "style": style,
                    "chars": len(ln["text"]), "seconds": round(dur, 2), "file": dst})
        print(f"{ln['id']}: {dst}  {dur:.2f} s  ({len(ln['text'])} chars)")
    if not a.dry_run:
        with open(log_path, "w", encoding="utf-8") as destination:
            json.dump(log, destination, indent=1, ensure_ascii=False)
        print(f"total {total:.1f} s of narration · log {log_path} · next: voice_treat.py (the film's own voice)")
        if total and a.engine in ("vieneu", "edge") + LOCAL:
            terms = local_licence(a.engine, voice, a.out)
            if terms:
                print(f"credit: VOICEVOX:{voicevox_voice(voice)[0]} written into LICENSES.csv; the character's terms: {terms} "
                      "(show the user before the film is published)")
        if spent:
            sys.exit(f"QUOTA SPENT at {spent}: the {a.engine} key's daily quota is used up; {len(failed)} line(s) wait: "
                     f"{', '.join(failed)}. Tell the user and offer: rerun tomorrow with --only {','.join(failed)} · fewer, "
                     f"longer lines (one per beat group) · a free local engine in the film's language (VieNeu for "
                     f"Vietnamese, VOICEVOX or Irodori for Japanese) · "
                     f"billing on the key. Meanwhile the OS voice stands in, said so")
        if failed:
            sys.exit(f"{len(failed)} line(s) failed: {', '.join(failed)} (fix and rerun with --only {','.join(failed)})")


if __name__ == "__main__":
    if os.name == "nt" and not sys.flags.utf8_mode:   # Windows reads, writes and prints in a legacy code page
        import subprocess
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=dict(os.environ, PYTHONUTF8="1")))
    for _s in (sys.stdin, sys.stdout, sys.stderr):
        getattr(_s, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")
    sys.exit(main())
