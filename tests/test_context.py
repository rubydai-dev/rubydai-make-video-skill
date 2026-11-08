"""Checks for the small-context tools: the guard hooks, the chat meter and make.py's summary."""
import contextlib
import io
import json
import random
import re
import os
import tempfile
import threading
import time
import shutil

os.environ["RUBYDAI_VIDEO_VIEWER_WAIT"] = "0"   # a final never waits for a viewer in tests
os.environ["RUBYDAI_VIDEO_NO_OPEN"] = "1"   # boards and drafts never pop up during tests
os.environ["RUBYDAI_VIDEO_SHOWN"] = os.path.join(tempfile.gettempdir(), "rubydai-video-test-shown.json")
os.environ["RUBYDAI_VIDEO_SHOWN_MUSIC"] = os.path.join(tempfile.gettempdir(), "rubydai-video-test-music.json")
os.environ["RUBYDAI_VIDEO_SHOWN_SOUNDS"] = os.path.join(tempfile.gettempdir(), "rubydai-video-test-sounds.json")
os.environ["RUBYDAI_VIDEO_SOUNDS_CACHE"] = os.path.join(tempfile.gettempdir(), "rubydai-video-test-sound-cache")
os.environ["RUBYDAI_VIDEO_SAMPLES_CACHE"] = os.path.join(tempfile.gettempdir(), "rubydai-video-test-samples")
os.environ["RUBYDAI_VIDEO_GUARD_SEEN"] = os.path.join(tempfile.gettempdir(), "rubydai-video-test-guard-seen")
os.environ.pop("CLAUDECODE", None)   # run inside Claude Code, every draft would also name its own guard
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fonts
import keys
import make
import usage

GUARD = ROOT / "scripts" / "guard.py"


def source(tool):
    """A tool's source as one text, with the module it was split into (make + make_checks, guard + guard_words)."""
    parts = {"make": ("make.py", "make_checks.py"), "guard": ("guard.py", "guard_words.py")}[tool]
    return "\n".join((ROOT / "scripts" / p).read_text(encoding="utf-8") for p in parts)


def png(path, w, h):
    raw = b"".join(b"\x00" + b"\x00" * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def ran(cmd, **kw):
    """subprocess.run that fails with the command's own error output."""
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        out = r.stderr if isinstance(r.stderr, str) else (r.stderr or b"").decode("utf-8", "replace")
        raise AssertionError(f"{' '.join(map(str, cmd))} exited {r.returncode}:\n{out[-1500:]}")
    return r


class Context(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rubydai-video-context-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.film = self.root / "film"
        (self.film / "tools").mkdir(parents=True)
        (self.film / "review").mkdir()
        (self.film / "STATE.md").write_text("# State: Test (Quick mode)\n", encoding="utf-8")
        (self.film / "tools" / "qc.py").write_text("", encoding="utf-8")
        self.env = dict(os.environ, TMPDIR=str(self.root / "tmp"))
        self.env.pop("CLAUDE_CODE_ENTRYPOINT", None)   # a desktop session must not steer a test that does not set it
        (self.root / "tmp").mkdir()

    def guard(self, mode, event):
        p = subprocess.run([sys.executable, GUARD, mode], input=json.dumps(event), capture_output=True, text=True,
                           env=self.env)
        return p.returncode, p.stdout + p.stderr

    def test_large_image_is_refused_small_one_passes(self):
        big, small = self.film / "review" / "big.png", self.film / "review" / "small.png"
        png(big, 1080, 1920)
        png(small, 768, 1366)
        code, out = self.guard("tool", {"tool_name": "Read", "tool_input": {"file_path": str(big)}, "cwd": str(self.root)})
        self.assertEqual(code, 2)
        self.assertIn("qc.py thumb", out)
        self.assertEqual(self.guard("tool", {"tool_name": "Read", "tool_input": {"file_path": str(small)}})[0], 0)

    def test_every_brief_kind_quotes_rules_that_still_exist(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import brief
        must = {"sound": ["What the picture does", "## 3. Layers", "Accents, not a sound per cut"],
                "music": ["## 8. Music"], "predict": ["The prediction test (independent)"],
                "overlap": ["The overlap check (independent)", "research/overlap.md"], "voice": ["## 4b."], "picture": ["**Picture:**", "## Step 4: Style frame"],
                "sourcing": ["## 2. Searching", "## 3. The licence log", "## 6. Never", "relevance test", "## 16. Real people"],
                "script": ["## Step 3: Script", "## 5. Words", "## 13. Long films", "## 8. First-time viewer", "## 16. Real people"],
                "roadmap": ["## Step 2: Roadmap", "## 12. Specificity", "curiosity map", "## 1. Sound identity"],
                "review": ["## 8. First-time viewer", "comprehension test"], "revision": ["What the user praised is locked"],
                "files": ["## 3. The licence log"]}
        self.assertEqual(set(must), set(brief.KINDS))
        for kind, (_, parts, model, effort) in brief.KINDS.items():
            self.assertIn(model, ("inherit", "sonnet", "haiku"), kind)
            text = "\n".join(brief.piece(*p) for p in parts)
            for heading in must[kind]:
                self.assertIn(heading, text, f"{kind}: {heading}")
        self.assertNotIn("overlap check", brief.piece(*brief.PREDICT), "the predictor sees the first message alone")
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "sound", "--task", "mix B01-B08", "--writes", "audio/sfx/*",
                              "--reads", "shots.json", "--done", "every event has its sound"],
                             capture_output=True, text=True).stdout
        self.assertTrue(out.startswith("<!-- rubydai-make-video-skill brief: sound -->"))
        self.assertIn("What the picture does, the sound does", out)

    def test_a_film_mode_helper_needs_its_brief(self):
        (self.film / "engine").mkdir()
        ev = {"tool_name": "Agent", "cwd": str(self.film), "session_id": "s"}
        code, out = self.guard("tool", dict(ev, tool_input={"prompt": "Build the sound for B01"}))
        self.assertEqual(code, 2)
        self.assertIn("brief.py", out)
        marker_only = dict(ev, tool_input={"prompt": "<!-- rubydai-make-video-skill brief: sound -->\n# Task\nBuild the sound for B01"})
        self.assertEqual(self.guard("tool", marker_only)[0], 2)
        ok = dict(ev, tool_input={"prompt": "<!-- rubydai-make-video-skill brief: sound -->\n# Task\nB01\nWRITES: audio/sfx/*\n# The kit's rules for this task\n...",
                                  "model": "inherit"})
        self.assertEqual(self.guard("tool", ok)[0], 0)
        (self.film / "engine").rmdir()
        (self.film / "film.html").write_text("", encoding="utf-8")                    # Quick mode: helpers are free
        self.assertEqual(self.guard("tool", dict(ev, tool_input={"prompt": "render VO takes"}))[0], 0)

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_a_long_film_mode_draft_is_shown_after_the_comprehension_test(self):
        (self.film / "engine").mkdir()
        (self.film / "renders").mkdir()
        draft = self.film / "renders" / "draft-v2.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x36:d=200:r=1", "-pix_fmt", "yuv420p",
                        str(draft)], check=True)
        ev = {"tool_name": "SendUserFile", "cwd": str(self.film), "session_id": "s", "tool_input": {"files": [str(draft)]}}
        (self.film / "logs").mkdir(exist_ok=True)
        (self.film / "logs" / "check-draft-v2.txt").write_text("check draft-v2.mp4: passes\n", encoding="utf-8")
        code, out = self.guard("tool", ev)
        self.assertEqual(code, 2)
        self.assertIn("comprehension", out)
        (self.film / "review" / "comprehension-v1.md").write_text("x" * 600, encoding="utf-8")   # another version
        self.assertEqual(self.guard("tool", ev)[0], 2)
        (self.film / "review" / "comprehension-v2.md").write_text("# Placeholder", encoding="utf-8")
        self.assertEqual(self.guard("tool", ev)[0], 2)
        (self.film / "review" / "comprehension-v2.md").write_text("what happened: " + "a full account " * 40, encoding="utf-8")
        self.assertEqual(self.guard("tool", ev)[0], 0)
        old = draft.stat().st_mtime - 600                     # a report written before this cut is not its test
        os.utime(self.film / "review" / "comprehension-v2.md", (old, old))
        self.assertEqual(self.guard("tool", ev)[0], 2)

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_a_film_mode_cut_is_checked_before_it_is_shown_and_the_check_holds_a_dark_silent_cut(self):
        (self.film / "engine").mkdir()
        (self.film / "renders").mkdir()
        cut = self.film / "renders" / "draft-v1.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=0x080808:s=160x90:d=8:r=12", "-f", "lavfi",
                        "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-pix_fmt", "yuv420p", str(cut)], check=True)
        ev = {"tool_name": "SendUserFile", "cwd": str(self.film), "session_id": "s", "tool_input": {"files": [str(cut)]}}
        code, out = self.guard("tool", ev)
        self.assertEqual(code, 2)
        self.assertIn("make.py check renders/draft-v1.mp4", out)
        tools = self.film / "tools"
        __import__("shutil").copytree(ROOT / "scripts", tools, dirs_exist_ok=True)
        (self.film / "shots.json").write_text(json.dumps({"fps": 12, "shots": [{"start": 0}, {"start": 48}]}), encoding="utf-8")
        run = subprocess.run([sys.executable, str(tools / "make.py"), "check", "renders/draft-v1.mp4"], cwd=self.film,
                             capture_output=True, text=True, env=dict(os.environ, RUBYDAI_VIDEO_NO_OPEN="1"))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("HELD:", run.stdout)
        self.assertIn("TOO DARK", run.stdout)
        self.assertIn("SOUND THIN", run.stdout)
        self.assertTrue((self.film / "logs" / "check-draft-v1.txt").exists())
        self.assertEqual(self.guard("tool", ev)[0], 0)

    def test_a_notes_round_starts_with_what_the_user_praised(self):
        notes = str(self.film / "notes" / "round-2.md")
        ev = {"tool_name": "Write", "cwd": str(self.film), "session_id": "s"}
        code, out = self.guard("tool", dict(ev, tool_input={"file_path": notes, "content": "# Notes round 2\n| N1 | ..."}))
        self.assertEqual(code, 2)
        self.assertIn("keep list", out)
        good = "# Notes round 2\n\n## Keep\n- \"cảnh mở đầu rất hay\"\n\n| N1 | ..."
        self.assertEqual(self.guard("tool", dict(ev, tool_input={"file_path": notes, "content": good}))[0], 0)
        (self.film / "notes").mkdir(exist_ok=True)
        Path(notes).write_text("# Notes round 2\n| N1 | ...\n", encoding="utf-8")
        edit = {"tool_name": "Edit", "cwd": str(self.film), "session_id": "s",
                "tool_input": {"file_path": notes, "old_string": "| N1 |", "new_string": "| N1 | more |"}}
        self.assertEqual(self.guard("tool", edit)[0], 2)
        Path(notes).write_text(good, encoding="utf-8")
        self.assertEqual(self.guard("tool", edit)[0], 0)

    def test_film_mode_mix_waits_for_the_picture_event_audit(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import mix
        (self.film / "audio").mkdir()
        plan = str(self.film / "audio" / "mix.json")
        self.assertIn("picture-event audit", mix.audit_missing(plan))
        audit = self.film / "review" / "sound-audit.md"
        audit.write_text("| 0:01 | a cup set on the table | cup-01 | transient, body, room |\nevents 12 · sounded 10 · silent by choice 1\n")
        self.assertIn("1 of 12 on-screen events have no sound", mix.audit_missing(plan))
        audit.write_text("events 12 · sounded 11 · silent by choice 1\n")
        self.assertEqual(mix.audit_missing(plan), "")
        (self.film / "film.html").write_text("", encoding="utf-8")
        audit.unlink()
        self.assertEqual(mix.audit_missing(plan), "")                                   # Quick mode: not asked

    def test_a_long_film_needs_its_curiosity_map(self):
        shots = self.film / "shots.json"
        shots.write_text(json.dumps({"fps": 24, "shots": [{"id": "S01", "start": 0, "end": 24 * 420}]}), encoding="utf-8")
        run = lambda: subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_shots.py"), str(shots)],
                                     capture_output=True, text=True).stdout
        (self.film / "ROADMAP.md").write_text("## 4b. Curiosity map\n| Question | Opens at | Paid at | How |\n|---|---|---|---|\n"
                                              "| <the big one> | 0:0x | | |\n", encoding="utf-8")
        self.assertIn("curiosity map", run())
        (self.film / "ROADMAP.md").write_text("## 4b. Curiosity map\n| Question | Opens at | Paid at | How |\n|---|---|---|---|\n"
                                              "| Why did the bridge sway? | 0:02 | 2:10 | a drawing of the joint |\n| Who signed it off? | 0:31 | 6:12 | the signature |\n"
                                              "| What changed after? | 0:48 | 4:31 | one line |\n", encoding="utf-8")
        self.assertNotIn("curiosity map", run())
        (self.film / "ROADMAP.md").unlink()
        self.assertIn("curiosity map", run())                                          # no roadmap is no map

    def test_footage_cut_finds_the_failed_take_and_keeps_reduplications(self):
        words, t = [], 0.5
        def say(text, gap=0.08):
            nonlocal t
            for x in text.split():
                d = 0.18 + 0.03 * len(x)
                words.append({"word": x, "start": round(t, 2), "end": round(t + d, 2)})
                t += d + gap
        say("Xin chào các bạn"); t += 1.6
        say("tôi tôi pha trà"); t += 0.4
        say("giờ tôi hướng dẫn"); t += 0.9
        say("giờ tôi từ từ hướng dẫn"); t += 2.0
        say("đun sôi nước rồi cho trà vào ấm")
        (self.root / "words.json").write_text(json.dumps({"words": words}), encoding="utf-8")
        run = lambda *extra: subprocess.run([sys.executable, str(ROOT / "scripts" / "footage_cut.py"), "cut",
                                             str(self.root / "words.json"), "--out", str(self.root / "edit"), *extra],
                                            capture_output=True, text=True)
        run("--duration", "16")
        flags = (self.root / "edit" / "flags.md").read_text(encoding="utf-8")
        self.assertIn("| stutter | high | tôi | tôi |", flags)
        self.assertIn("| false start | high | giờ tôi hướng dẫn | giờ tôi từ từ hướng dẫn |", flags)
        self.assertIn("| doubled word (a reduplication is often meant) | look | từ | từ |", flags)
        run("--duration", "16", "--apply", "F1,F2")
        cut = json.loads((self.root / "edit" / "cut-list.json").read_text())
        self.assertTrue(all(b - a >= 0.15 for a, b in cut["keep"]))                  # no 2-frame slivers
        self.assertLessEqual(cut["keep"][-1][1], 16)
        self.assertAlmostEqual(sum(b - a for a, b in cut["keep"]), cut["edited_duration"], places=2)
        kept = " ".join(w["word"] for w in json.loads((self.root / "edit" / "words-retimed.json").read_text()))
        self.assertIn("tôi pha trà giờ tôi từ từ hướng dẫn", kept)

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_type_contrast_fails_yellow_on_orange_and_passes_cream_on_black(self):
        tool = str(ROOT / "scripts" / "type_extract.py")
        for name, bg, ink in (("low", "0xE07A2E", "0xF2C14E"), ("high", "0x101010", "0xF2EFE6")):
            boxes = ",".join(f"drawbox=x={80 + 40 * i}:y=600:w=24:h=60:color={ink}:t=fill" for i in range(12))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={bg}:s=1080x1350", "-frames:v",
                            "1", "-vf", boxes, str(self.root / f"{name}.png")], check=True)
        low = subprocess.run([sys.executable, tool, "contrast", str(self.root / "low.png"), "--box", "0.05,0.42,0.6,0.08",
                              "--ink", "f2c14e"], capture_output=True, text=True).stdout
        high = subprocess.run([sys.executable, tool, "contrast", str(self.root / "high.png"), "--box", "0.05,0.42,0.6,0.08",
                               "--ink", "f2efe6"], capture_output=True, text=True).stdout
        self.assertIn("FAIL", low)
        self.assertIn("pass", high)
        code = subprocess.run([sys.executable, tool, "contrast", str(self.root / "low.png"), "--box", "0.05,0.42,0.6,0.08",
                               "--ink", "f2c14e"], capture_output=True).returncode
        self.assertEqual(code, 1)

    def test_art_of_the_title_puts_the_exact_title_first_and_explains_a_genre_miss(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import type_refs
        page = "".join(f'<a href="/title/{s}/" class="thumb">\n<img data-original="/i/{s}.jpg" alt="{a}"></a>'
                       for s, a in (("men", "Men"), ("watchmen", "Watchmen"), ("mad-men", "Mad Men")))
        with patch.object(type_refs, "get", lambda *a, **k: page):
            got = type_refs.src_artofthetitle("Mad Men", 2)
            self.assertEqual(got[0]["title"] if "title" in got[0] else got[0].get("name"), "Mad Men")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(type_refs.src_artofthetitle("thriller", 3), [])
            self.assertIn("not by genre", err.getvalue())

    def test_the_users_language_comes_from_the_user_not_from_hooks_or_helpers(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        log = self.root / "t.jsonl"
        rows = [{"type": "user", "message": {"content": "<command-message>rubydai-make-video-skill</command-message>\n<command-args>"
                                                         "làm một video về một thành phố bị mất dưới đáy biển</command-args>"}},
                {"type": "user", "message": {"content": "Stop hook feedback:\n rubydai-make-video-skill: the user has not seen what the board "
                                                         "made. Send it first and then ask the question"}},
                {"type": "user", "message": {"content": "Another Claude session sent a message:\n<agent-message>[Subagent "
                                                         "hand-back] The board is ready and the three directions are in the file"}}]
        log.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        self.assertEqual(guard.user_language(str(log)), "vi")
        child = ("Background (from the session that started this one):\nThe user asked for a 60-second film in Quick mode."
                 "\n\nTask:\nTiếp tục từ STATE.md. Load the rubydai-make-video-skill skill with the Skill tool; read STATE.md and the "
                 "notes it names; reply in the user's language.")
        log.write_text(json.dumps({"type": "user", "message": {"content": child}}), encoding="utf-8")
        self.assertEqual(guard.user_language(str(log)), "vi", "a new chat a handoff started keeps the user's language")
        log.write_text(json.dumps({"type": "user", "message": {"content": child.replace("Tiếp tục từ STATE.md", "Continue from STATE.md")}}), encoding="utf-8")
        self.assertEqual(guard.user_language(str(log)), "en")

    def test_question_language_ignores_names_in_any_language(self):
        def ask(user, question, options):
            log = self.root / "lang.jsonl"
            log.write_text(json.dumps({"type": "user", "message": {"content": user}}), encoding="utf-8")
            return self.guard("tool", {"tool_name": "AskUserQuestion", "cwd": str(self.film), "transcript_path": str(log),
                                       "tool_input": {"questions": [{"question": question, "header": "Q", "options": options}]}})[0]
        tr, en = "Làm cho tôi một quảng cáo cà phê, ấm áp và gần gũi nhé", "Make me an ad for my bicycle shop, it is called Đạp Bạc in Hội An"
        films = [{"label": "1 · In the Mood for Love ★", "description": "The Grand Budapest Hotel và Art of the Title"}]
        self.assertEqual(ask(tr, "Mình dùng phim tham chiếu nào cho hướng hình ảnh?", films), 0)
        self.assertEqual(ask(en, "Đạp Bạc draft v1 is ready. Render final?", [{"label": "Render final ★", "description": "Đạp Bạc, Hội An"}]), 0)
        self.assertEqual(ask(tr, "Which of the six styles on the board do you want for this film?", films), 2)
        self.assertEqual(ask(en, "Bạn muốn chọn phong cách nào trong sáu phong cách trên bảng cho phim này?", films), 2)
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        for short in ("Tôi muốn làm phim ngắn", "Làm một quảng cáo 30 giây đi", "được", "tiếp tục"):
            self.assertEqual(guard.language(short), "vi", "a short Vietnamese opener is Vietnamese: " + short)
        self.assertEqual(guard.language("Make me a short film"), "en")
        self.assertIsNone(guard.language("Đạp Bạc draft v1 is ready. Render final?"), "a Vietnamese name is not the language")

    def test_the_guard_is_silent_outside_films_and_watches_the_films_folder_below(self):
        away = self.root / "elsewhere" / "deep"
        away.mkdir(parents=True)
        self.assertEqual(self.guard("tool", {"tool_name": "Bash", "cwd": str(away), "tool_input": {"command": "open report.pdf"}})[0], 0)
        parent = self.root / "workspace"
        (parent / "Filmler").mkdir(parents=True)
        __import__("shutil").copytree(self.film, parent / "Filmler" / "x")
        self.assertEqual(self.guard("tool", {"tool_name": "Bash", "cwd": str(parent),
                                             "tool_input": {"command": "open Filmler/x/audio/preview.mka"}})[0], 2)

    def test_a_wrap_up_question_waits_for_the_unshown_board(self):
        log = self.root / "w.jsonl"
        log.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "u1", "name": "Bash",
                       "input": {"command": "python3 tools/styles.py suggest x --board research/style-board.jpg"}}]}}) + "\n"
                       + json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "u1",
                                                                              "content": "board: research/style-board.jpg (2x3) · show the user: /f/research/style-board.jpg"}]}}),
                       encoding="utf-8")
        self.env["CLAUDE_CODE_ENTRYPOINT"] = "claude-desktop"
        ev = {"tool_name": "mcp__ccd_turn__wrap_up", "cwd": str(self.film), "transcript_path": str(log),
              "tool_input": {"ask": "Phong cách nào?", "recap": "bảng đã xong"}}
        self.assertEqual(self.guard("tool", ev)[0], 2)

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_a_silent_soundtrack_is_named_and_the_picture_is_kept(self):
        silent, video, out = self.root / "s.wav", self.root / "v.mp4", self.root / "o.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "2", str(silent)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=64x36:d=2", "-pix_fmt", "yuv420p",
                        str(video)], check=True)
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "master_audio.py"), str(silent), str(out), "--video",
                            str(video), "--limit"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn("SILENT SOUNDTRACK", p.stdout)
        self.assertTrue(out.exists())

    def test_all_caps_cliches_are_caught_and_plain_words_are_not(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import words_check
        _, tells = words_check.check([("a", "MỘT HÀNH TRÌNH"), ("b", "ĐỪNG BỎ LỠ"), ("c", "Đèn đỏ bật lên"), ("d", "THIS IS IT"),
                                      ("e", "息をのむ景色"), ("f", "朝五時に茶を淹れる")])
        self.assertEqual(sorted(w for w, _, _ in tells), ["a", "b", "e"])

    def test_warm_is_a_font_tone_and_kana_faces_are_not_offered(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import fonts
        self.assertTrue(any("ấm áp" in k and "warm" in k and "温かい" in k for k in fonts.TONES))
        self.assertIn('"hentaigana" in fid', (ROOT / "scripts" / "fonts.py").read_text(encoding="utf-8"))

    def test_the_form_reads_a_continuous_journey_and_a_list(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import moves
        train = ("A single unbroken take follows a glassblower's breath into a bowl that cools from orange to clear.")
        self.assertEqual(moves.form(train, 25)[0], "one shot")
        self.assertEqual(moves.form("quảng cáo cao cấp xoay quanh chiếc bát gốm mới", 20)[0], "one shot")
        self.assertEqual(moves.form("một trăm năm của cối xay cũ, phim tài liệu 5 phút, người dẫn", 300)[0], "cuts")
        self.assertEqual(moves.form("a drone flies through the city for two minutes, one take", 120)[0], "one shot with hidden cuts")

    @unittest.skipUnless(__import__("shutil").which("node"), "needs node")
    def test_the_camera_path_flows_through_its_keys(self):
        script = r"""
const fs = require('fs'); const s = fs.readFileSync(process.argv[1], 'utf8');
const lerp = (a, b, k) => a + (b - a) * k, noise1 = () => 0.5;
const a = s.indexOf('const CAM = {'), b = s.indexOf('\n};', a) + 3;
eval(s.slice(a, b).replace('const CAM', 'globalThis.CAM'));
const keys = [{ t: 0, x: -3, dist: 6 }, { t: 5, x: -1, dist: 2.5 }, { t: 11, x: 0.2, dist: 0.35 }, { t: 25, x: 3.5, dist: 7 }];
let jump = 0, last = null;
for (let f = 0; f <= 600; f++) { const c = CAM.path(keys, f / 24); if (last) jump = Math.max(jump, Math.abs(c.dist - last.dist), Math.abs(c.x - last.x)); last = c; }
const at = (t) => CAM.path(keys, t);
console.log(JSON.stringify({ hit: [0, 5, 11, 25].map((t) => +at(t).dist.toFixed(3)), jump,
  start: (at(1 / 24).x - at(0).x) * 24, through: (at(5 + 1 / 24).x - at(5).x) * 24 }));
"""
        out = subprocess.run(["node", "-e", script, str(ROOT / "templates" / "quick" / "film.html")], capture_output=True,
                             text=True)
        r = json.loads(out.stdout)
        self.assertEqual(r["hit"], [6, 2.5, 0.35, 7])                   # every key is reached
        self.assertLess(r["jump"], 0.08)                                # no jump between frames
        self.assertLess(abs(r["start"]), 0.05)                          # it starts from rest
        self.assertGreater(abs(r["through"]), 0.1)                      # and does not stop on a middle key

    @unittest.skipUnless(__import__("shutil").which("node"), "needs node")
    def test_the_perspective_view_projects_like_a_camera(self):
        script = r"""
const fs = require('fs'); const s = fs.readFileSync(process.argv[1], 'utf8');
const lerp = (a, b, k) => a + (b - a) * k, noise1 = () => 0.5, clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const cut = (start) => { const a = s.indexOf(start), b = s.indexOf('\n};', a) + 3; return s.slice(a, b).replace(/^const (\w+)/, 'globalThis.$1'); };
eval(cut('const CAM = {')); eval(cut('const VIEW = {'));
const S = { W: 1920, H: 1080 };
const v = VIEW.of({ x: 0, y: 2, z: 10, tx: 0, ty: 2, tz: 0, fov: 50 }, S);
const ahead = v.p(0, 2, 0), far = v.p(1, 2, -30), near = v.p(1, 2, 5), behind = v.p(0, 2, 20);
const c = CAM.path([{ t: 0, x: 0, z: 10, tz: 0 }, { t: 4, x: 6, z: 2, tz: -5 }], 2);
console.log(JSON.stringify({ ahead, farScale: far[2], nearScale: near[2], behind, mid: [c.x, c.z, c.tz], haze: [v.haze(1), v.haze(60)] }));
"""
        out = subprocess.run(["node", "-e", script, str(ROOT / "templates" / "quick" / "film.html")], capture_output=True,
                             text=True)
        r = json.loads(out.stdout)
        self.assertAlmostEqual(r["ahead"][0], 960, places=3)              # straight ahead lands in the centre
        self.assertAlmostEqual(r["ahead"][1], 540, places=3)
        self.assertGreater(r["nearScale"], r["farScale"] * 5)            # near things are bigger
        self.assertIsNone(r["behind"])                                   # nothing behind the camera is drawn
        self.assertEqual(r["mid"], [3, 6, -2.5])                         # CAM.path moves any field it is given
        self.assertEqual(r["haze"], [0, 1])

    def test_the_card_view_is_drawn_in_the_code(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        film = self.root / "film.html"
        film.write_text("function scene(g, k, t, S) { plane(g, S, CAM.base(), 0, () => {}); }", encoding="utf-8")
        persp = "- **Kamera / Camera:** perspective: the camera descends and passes the glass bowl at three quarters"
        self.assertIn("the card chose perspective", make.view_line(film, persp))
        self.assertIn("names no view", make.view_line(film, "- **Kamera / Camera:** flowing dolly and crane"))
        self.assertEqual(make.view_line(film, "- **Kamera / Camera:** flat planes, a side-on frieze"), "")
        film.write_text("const v = VIEW.of(CAM.path(KEYS, t), S);", encoding="utf-8")
        self.assertEqual(make.view_line(film, persp), "")

    def test_the_delivery_question_keeps_its_jury_check(self):
        log = self.root / "d.jsonl"
        log.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "d1", "name": "Bash",
                       "input": {"command": "python3 tools/make.py draft"}}]}}) + "\n" + json.dumps({"type": "user", "message":
                       {"content": [{"type": "tool_result", "tool_use_id": "d1", "content": "SHOW THIS DRAFT NOW: the film"}]}}),
                       encoding="utf-8")
        ask = lambda labels: self.guard("tool", {"tool_name": "AskUserQuestion", "cwd": str(self.film), "transcript_path":
                                                 str(log), "tool_input": {"questions": [{"question": "Bản nháp này, mình làm tiếp thế nào?",
                                                                                         "options": [{"label": x} for x in labels]}]}})
        code, out = ask(["Render final ★", "I have notes", "New chat ★"])
        self.assertEqual(code, 2)
        self.assertIn("no jury check", out)
        self.assertIn("more than one choice carries the star", out)
        self.assertEqual(ask(["Final ★", "Góp ý", "Vòng giám khảo", "Chat mới"])[0], 0)
        b = lambda label: {"label": label, "message": label}
        code, out = self.guard("tool", {"tool_name": "mcp__ccd_turn__wrap_up", "cwd": str(self.film), "transcript_path": str(log),
                                        "tool_input": {"ask": "Bản nháp này, mình làm tiếp thế nào?", "recap": "x",
                                                       "actions": [b("Final ★"), b("Góp ý"), b("Vòng giám khảo")]}})
        self.assertEqual(code, 2, "the app's wrap_up box shows two buttons and drops the third")
        self.assertIn("two", out)

    def test_a_session_on_the_films_folder_keeps_the_film_gates(self):
        shelf = self.root / "shelf"
        film = shelf / "Films" / "kahve"
        (film / "tools").mkdir(parents=True)
        (film / "engine").mkdir()
        (film / "notes").mkdir()
        (film / "STATE.md").write_text("# State: Kahve (Film mode)\n", encoding="utf-8")
        (film / "tools" / "qc.sh").write_text("", encoding="utf-8")
        helper = {"tool_name": "Agent", "cwd": str(shelf), "session_id": "s", "tool_input": {"prompt": "Build the sound for B01"}}
        code, out = self.guard("tool", helper)
        self.assertEqual(code, 2)
        self.assertIn("brief.py", out)
        notes = film / "notes" / "round-1.md"
        notes.write_text("# Notes round 1\n## Keep\n- the logo\n## Verbatim\nmore light\n", encoding="utf-8")
        cut = {"tool_name": "Edit", "cwd": str(shelf), "session_id": "s",
               "tool_input": {"file_path": str(notes), "old_string": "## Keep\n- the logo\n", "new_string": ""}}
        self.assertEqual(self.guard("tool", cut)[0], 2)
        fine = dict(cut, tool_input={"file_path": str(notes), "old_string": "more light", "new_string": "more light, warmer"})
        self.assertEqual(self.guard("tool", fine)[0], 0)
        multi = {"tool_name": "MultiEdit", "cwd": str(shelf), "session_id": "s",
                 "tool_input": {"file_path": str(notes), "edits": [{"old_string": "## Keep\n- the logo\n", "new_string": ""}]}}
        self.assertEqual(self.guard("tool", multi)[0], 2)

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_each_film_on_a_shelf_is_judged_as_itself(self):
        shelf = self.root / "shelf"
        def make(name, film_mode_film):
            f = shelf / "Films" / name
            (f / "tools").mkdir(parents=True)
            (f / "renders").mkdir()
            (f / "logs").mkdir()
            (f / "STATE.md").write_text(f"# State: {name}\n", encoding="utf-8")
            (f / "tools" / "qc.sh").write_text("", encoding="utf-8")
            (f / "engine" if film_mode_film else f / "film.html").mkdir() if film_mode_film else (f / "film.html").write_text("", encoding="utf-8")
            cut = f / "renders" / "draft-v1.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x36:d=2:r=4", "-pix_fmt", "yuv420p",
                            str(cut)], check=True)
            return f, cut
        film_a, cut_a = make("alfa", True)
        film_b, cut_b = make("beta", True)
        quick, _ = make("kahve", False)
        os.utime(quick / "STATE.md")                        # the Quick film is the one touched last
        (film_a / "logs" / "check-draft-v1.txt").write_text("check: passes\n", encoding="utf-8")
        ev = lambda **kw: dict({"cwd": str(shelf), "session_id": "s"}, **kw)
        named = ev(tool_name="Agent", tool_input={"prompt": f"Build the sound for {film_a}, no brief"})
        self.assertEqual(self.guard("tool", named)[0], 2)
        by_name = ev(tool_name="Agent", tool_input={"prompt": "Render the VO takes for kahve"})
        self.assertEqual(self.guard("tool", by_name)[0], 0)
        batch = ev(tool_name="SendUserFile", tool_input={"files": [str(cut_a), str(cut_b)]})
        code, out = self.guard("tool", batch)
        self.assertEqual(code, 2)
        self.assertIn("make.py check", out)
        from_quick = dict(ev(tool_name="SendUserFile", tool_input={"files": [str(cut_b)]}), cwd=str(quick))
        self.assertEqual(self.guard("tool", from_quick)[0], 2)

    def test_a_film_mode_delivery_and_a_failed_question_keep_the_question_owed(self):
        log = self.root / "f.jsonl"
        rows = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "c1", "name": "Bash",
                 "input": {"command": "python3 tools/make.py check renders/draft-v1.mp4"}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "c1", "content": "passes"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "s1", "name": "SendUserFile",
                 "input": {"files": [str(self.film / "renders" / "draft-v1.mp4")]}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "s1", "content": "sent"}]}}]
        log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        stop = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log)}
        self.assertEqual(self.guard("stop", stop)[0], 2)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "q1",
                    "name": "AskUserQuestion", "input": {"questions": []}}]}}) + "\n")
            f.write(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "q1",
                    "content": "the question was not shown", "is_error": True}]}}) + "\n")
        self.assertEqual(self.guard("stop", stop)[0], 2)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "q2",
                    "name": "AskUserQuestion", "input": {"questions": []}}]}}) + "\n")
            f.write(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "q2",
                    "content": "Final"}]}}) + "\n")
        self.assertEqual(self.guard("stop", stop)[0], 0)

    def test_the_sound_choice_is_read_from_the_card_line_only(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        info, plan = {"frames": 24 * 24, "fps": 24, "sfx": []}, {"layers": [{"bus": "music"}]}
        card = "- **Sound:** ambience and picture-locked effects\n"
        with patch.object(make, "PROJECT", self.root), patch.object(make, "REVIEW", self.root):
            for waived in ("- **Sound:** music-only by choice\n", "- **Âm thanh / Sound:** phim im lặng\n", "- **Sound (Q4):** silent\n",
                           "- **Sound:** music only; no sound effects\n", "- **Sound:** silent by choice, no music\n",
                           "- **Sound:** no sound effects — music only\n"):
                self.assertEqual(make.sound_thin_line(info, plan, waived), "", waived)
                self.assertEqual(make.sound_source_line(self.root / "none.html", plan, waived), "", waived)
            for held in (card + "- **Open notes:** B03 is silent; add the missing impact.\n", "- **Sound:** not silent; use recorded effects\n",
                         "- **Âm thanh:** không im lặng; hiệu ứng thu sẵn\n"):
                self.assertIn("SOUND THIN", make.sound_thin_line(info, plan, held), held)
                self.assertIn("SOUND ALL CODE", make.sound_source_line(self.root / "none.html", plan, held), held)

    def test_a_helper_works_on_the_film_its_prompt_names(self):
        shelf = self.root / "shelf" / "Films"
        quick, full = shelf / "kahve", shelf / "alfa"
        for f in (quick, full):
            (f / "tools").mkdir(parents=True)
            (f / "STATE.md").write_text(f"# State: {f.name}\n", encoding="utf-8")
            (f / "tools" / "qc.sh").write_text("", encoding="utf-8")
        (quick / "film.html").write_text("", encoding="utf-8")
        (full / "engine").mkdir()
        agent = lambda cwd, prompt: self.guard("tool", {"tool_name": "Agent", "cwd": str(cwd), "session_id": "s",
                                                        "tool_input": {"prompt": prompt}})
        self.assertEqual(agent(quick, f"Build the sound in {full}/audio, no brief")[0], 2)
        self.assertEqual(agent(quick, "Build the sound for alfa, no brief")[0], 2)
        self.assertEqual(agent(full, f"Render the VO takes for {quick}")[0], 0)
        self.assertEqual(agent(full, "Render the VO takes for kahve")[0], 0)
        self.assertEqual(agent(full, "Build the sound for B01")[0], 2)

    def test_a_resumed_quick_draft_and_an_empty_question_keep_the_jury(self):
        (self.film / "film.html").write_text("", encoding="utf-8")
        log = self.root / "r.jsonl"
        rows = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "s1", "name": "SendUserFile",
                 "input": {"files": [str(self.film / "renders" / "draft-v2.mp4")]}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "s1", "content": "sent"}]}}]
        log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        ask = lambda inp: self.guard("tool", {"tool_name": "mcp__ccd_turn__wrap_up", "cwd": str(self.film),
                                              "transcript_path": str(log), "tool_input": inp})
        b = lambda label: {"label": label, "message": label}
        code, out = ask({"ask": "Bản nháp này, mình làm tiếp thế nào?", "actions": [b("Final ★"), b("Tôi có góp ý")]})
        self.assertEqual(code, 2)
        self.assertIn("AskUserQuestion", out, "two buttons cannot hold the jury check: the question tool can")
        self.assertEqual(ask({"ask": "Bản nháp này, mình làm tiếp thế nào?", "actions": []})[0], 2)
        self.assertEqual(ask({"ask": "Bản nháp này, mình làm tiếp thế nào?"})[0], 2)
        self.assertEqual(ask({"ask": "Bản nháp này, mình làm tiếp thế nào?", "actions": [b("Final ★"), b("Góp ý"), b("Vòng giám khảo")]})[0], 2)
        code, _ = self.guard("tool", {"tool_name": "AskUserQuestion", "cwd": str(self.film), "transcript_path": str(log),
                                      "tool_input": {"questions": [{"question": "Bản nháp này, mình làm tiếp thế nào?", "options":
                                                     [{"label": "Final ★"}, {"label": "Góp ý"}, {"label": "Vòng giám khảo"}]}]}})
        self.assertEqual(code, 0)

    def test_a_failed_send_leaves_the_stills_unshown(self):
        log = self.root / "u.jsonl"
        def row(kind, **kw):
            return json.dumps({"type": "assistant" if kind == "tool_use" else "user",
                               "message": {"content": [dict({"type": kind}, **kw)]}}) + "\n"
        log.write_text(row("tool_use", id="m1", name="Bash", input={"command": "python3 tools/make.py stills"})
                       + row("tool_result", tool_use_id="m1", content="stills: review/stills.jpg · show the user: /f/review/stills.jpg")
                       + row("tool_use", id="s1", name="SendUserFile", input={"files": ["review/stills.jpg"]})
                       + row("tool_result", tool_use_id="s1", content="file too large", is_error=True), encoding="utf-8")
        stop = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log)}
        code, out = self.guard("stop", stop)
        self.assertEqual(code, 2)
        self.assertIn("SendUserFile", out)
        with log.open("a", encoding="utf-8") as f:
            f.write(row("tool_use", id="s2", name="SendUserFile", input={"files": ["review/stills.jpg"]})
                    + row("tool_result", tool_use_id="s2", content="sent"))
        self.assertEqual(self.guard("stop", stop)[0], 0)
        log.write_text(row("tool_use", id="m1", name="Bash", input={"command": "python3 tools/make.py stills"})
                       + row("tool_result", tool_use_id="m1", content="stills: review/stills.jpg · show the user: /f/review/stills.jpg")
                       + row("tool_use", id="s1", name="SendUserFile", input={"files": ["review/stills.jpg"]}), encoding="utf-8")
        self.assertEqual(self.guard("stop", stop)[0], 0, "a send and its question in one turn: the send's result comes later")
        log.write_text(row("tool_use", id="f1", name="Bash", input={"command": "python3 tools/make.py final 2>&1 | head -3"})
                       + row("tool_result", tool_use_id="f1", content="final v1: renders/film-v1.mp4 (not delivered) · 30 s"),
                       encoding="utf-8")
        self.assertEqual(self.guard("stop", stop)[0], 0, "a final that was not delivered is nothing to show")

    def test_a_tool_named_in_text_is_not_a_render_the_user_must_see(self):
        log = self.root / "h.jsonl"
        def row(kind, **kw):
            return json.dumps({"type": "assistant" if kind == "tool_use" else "user",
                               "message": {"content": [dict({"type": kind}, **kw)]}}) + "\n"
        note = "python3 - <<'E'\ns = 'Next action: python3 tools/make.py final'\nE"
        log.write_text(row("tool_use", id="w1", name="Bash", input={"command": note})
                       + row("tool_result", tool_use_id="w1", content="snapshot: draft v2")
                       + row("tool_use", id="s1", name="SendUserFile", input={"files": ["x.png"]}), encoding="utf-8")
        stop = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log)}
        self.assertEqual(self.guard("stop", stop)[0], 0)
        with log.open("a", encoding="utf-8") as f:
            f.write(row("tool_use", id="m1", name="Bash", input={"command": "cd /f && python3 tools/make.py stills --at 1"})
                    + row("tool_result", tool_use_id="m1", content="stills: review/stills-2.jpg · show the user: /f/s.jpg"))
        self.assertEqual(self.guard("stop", stop)[0], 2)

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_effects_the_music_covers_are_named_buried(self):
        audio = self.root / "audio"
        audio.mkdir()
        run = lambda *a: subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)
        run("-f", "lavfi", "-i", "anoisesrc=d=8:c=pink:a=0.5", "-ar", "48000", str(audio / "film.wav"))
        run("-f", "lavfi", "-i", "sine=f=900:d=0.15", "-af", "volume=17dB", "-ar", "48000", str(audio / "hit.wav"))
        hits = [{"file": "audio/hit.wav", "at": t, "bus": "sfx", "gain_db": -20} for t in (1, 2.5, 4, 5.5)]
        plan = {"duration": 8, "out": "audio/mix.wav", "layers": [{"file": "audio/film.wav", "at": 0, "bus": "music"}] + hits}
        with patch.object(make, "PROJECT", self.root), patch.object(make, "TOOLS", ROOT / "scripts"):
            self.assertIn("SOUND BURIED", make.sound_buried_line(plan, audio / "film.wav"))
            for h in hits:
                h["gain_db"] = 0
            self.assertEqual(make.sound_buried_line(plan, audio / "film.wav"), "")

    def test_a_helper_without_a_model_is_noted_not_stopped(self):
        (self.film / "engine").mkdir()
        brief = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "sourcing", "--task", "find maps", "--writes", "assets/maps/*",
                                "--reads", "STATE.md", "--done", "three maps with licences"],
                               capture_output=True, text=True)
        self.assertIn("model sonnet, effort medium", brief.stderr)
        self.assertNotIn("model sonnet", brief.stdout)
        ev = {"tool_name": "Agent", "cwd": str(self.film), "session_id": "s", "tool_input": {"prompt": brief.stdout}}
        code, out = self.guard("tool", ev)
        self.assertEqual(code, 0)
        self.assertIn("without a model", json.loads(out)["hookSpecificOutput"]["additionalContext"])
        named = dict(ev, tool_input={"prompt": brief.stdout, "model": "sonnet", "effort": "medium"})
        self.assertEqual(self.guard("tool", named), (0, ""))

    def test_a_helper_writes_only_its_own_files_and_the_viewer_only_looks(self):
        (self.film / "engine").mkdir()
        chat = self.root / "chat.jsonl"
        chat.write_text("", encoding="utf-8")
        brief = lambda kind, writes: subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "brief.py"), kind, "--task", "t", "--writes", writes, "--reads", "x",
             "--done", "y"], capture_output=True, text=True).stdout
        def helper(agent, prompt):
            d = self.root / "chat" / "subagents"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"agent-{agent}.jsonl").write_text(json.dumps({"isSidechain": True, "type": "user", "message":
                                                                {"role": "user", "content": prompt}}) + "\n", encoding="utf-8")
            return lambda name, inp: self.guard("tool", {"tool_name": name, "tool_input": inp, "cwd": str(self.film),
                                                         "session_id": "s", "agent_id": agent, "transcript_path": str(chat)})[0]
        sound = helper("a1", brief("sound", "audio/sfx/*,review/sound-v2.md"))
        self.assertEqual(sound("Write", {"file_path": str(self.film / "audio" / "sfx" / "hit.wav"), "content": "x"}), 0)
        self.assertEqual(sound("Write", {"file_path": str(self.film / "STATE.md"), "content": "x"}), 2)
        self.assertEqual(sound("Edit", {"file_path": str(self.film / "film.html"), "old_string": "a", "new_string": "b"}), 2)
        self.assertEqual(sound("Write", {"file_path": str(self.film / "review" / "sound-handoff.md"), "content": "x"}), 0)
        viewer = helper("v1", brief("review", "review/critique-v2.md"))
        self.assertEqual(viewer("Bash", {"command": "bash tools/qc.sh strip renders/draft-v2.mp4 3 2 6"}), 0)
        self.assertEqual(viewer("Bash", {"command": "ffprobe -v error renders/draft-v2.mp4 | head -3"}), 0)
        self.assertEqual(viewer("Bash", {"command": "python3 tools/make.py draft"}), 2)
        self.assertEqual(viewer("Bash", {"command": "cat a > film.html"}), 2)
        self.assertEqual(viewer("Write", {"file_path": str(self.film / "review" / "critique-v2.md"), "content": "x"}), 0)
        self.assertEqual(viewer("Bash", {"command": "sed -n 'w STATE.md' review/x.txt"}), 2)
        self.assertEqual(viewer("Bash", {"command": "bash tools/qc.sh strip renders/draft-v2.mp4 ../../x 2 6"}), 2)
        self.assertEqual(viewer("Bash", {"command": "QC_OUT=/tmp/x bash tools/qc.sh sheet renders/draft-v2.mp4 1 6"}), 2)
        self.assertEqual(viewer("Bash", {"command": "ffprobe -o STATE.md renders/draft-v2.mp4"}), 2)
        self.assertEqual(viewer("Bash", {"command": "cat $(echo STATE.md)"}), 2)
        self.assertEqual(viewer("Bash", {"command": "python3 tools/qc.py strip renders/draft-v2.mp4 3 2 6"}), 0)
        self.assertEqual(viewer("PowerShell", {"command": "py -3 tools\\qc.py strip renders\\draft-v2.mp4 3 2 6"}), 0)
        self.assertEqual(viewer("PowerShell", {"command": "python tools/qc.py sheet C:\\f\\renders\\draft-v2.mp4 1 6"}), 0)
        self.assertEqual(viewer("PowerShell", {"command": "Get-ChildItem renders; Get-Content review\\x.md | Select-String peak"}), 0)
        self.assertEqual(viewer("PowerShell", {"command": "ffprobe -v error renders\\draft-v2.mp4 2>$null"}), 0)
        self.assertEqual(viewer("PowerShell", {"command": "py -3 tools\\qc.py sheet renders\\draft-v2.mp4 1 6 2>$null"}), 0)
        self.assertEqual(viewer("Bash", {"command": "python3 tools/qc.py sheet renders/draft-v2.mp4 1 6 2>&1"}), 0)
        template = (ROOT / "templates" / "quick" / "REVIEWER.md").read_text(encoding="utf-8").split("```")[1]
        for i, block in enumerate((template, template.replace("vN", "v2"),
                                   "<!-- rubydai-make-video-skill brief: review -->\nWRITES: review/critique-v2.md (nothing else; you only look: "
                                   "qc.py, ffprobe, reading files)\n")):
            briefed = helper(f"t{i}", block)
            self.assertEqual(briefed("Write", {"file_path": str(self.film / "review" / "critique-v2.md"), "content": "x"}), 0,
                             "the viewer briefed as the kit writes it may write its report")
            self.assertEqual(briefed("Write", {"file_path": str(self.film / "STATE.md"), "content": "x"}), 2)
        self.assertEqual(viewer("PowerShell", {"command": "Set-Content STATE.md x"}), 2)
        self.assertEqual(viewer("PowerShell", {"command": "py -3 tools\\make.py draft"}), 2)
        self.assertEqual(sound("Write", {"file_path": str(self.root / "outside.txt"), "content": "x"}), 2)
        unknown = lambda name, inp: self.guard("tool", {"tool_name": name, "tool_input": inp, "cwd": str(self.film),
                                                        "session_id": "s", "agent_id": "zz", "transcript_path": str(chat)})[0]
        self.assertEqual(unknown("Write", {"file_path": str(self.film / "shots.json"), "content": "x"}), 2)
        self.assertEqual(unknown("Write", {"file_path": str(self.film / "review" / "x.md"), "content": "x"}), 0)

    def test_type_cards_use_the_films_words_and_a_new_look_deals_again(self):
        deal = lambda *args: subprocess.run([sys.executable, str(ROOT / "scripts" / "deal.py"), "deal", "type", "--project",
                                             str(self.root), *args], capture_output=True, text=True,
                                            env=dict(self.env, RUBYDAI_VIDEO_TASTE=str(self.root / "taste.json"))).stdout
        out = deal("--purpose", "ad")
        self.assertIn("no cards are made", out)
        self.assertNotIn("capture.mjs", out)
        out = deal("--purpose", "ad", "--title", "Buổi sáng yên tĩnh nhất của thành phố", "--cta", "Thử ngay")
        self.assertIn("already open", out)
        self.assertIn("title=Bu%E1%BB%95i%20s%C3%A1ng%20y%C3%AAn%20t%C4%A9nh%20nh%E1%BA%A5t%20c%E1%BB%A7a%20th%C3%A0nh%20ph%E1%BB%91&cta=Th%E1%BB%AD%20ngay", out)
        out = deal("--purpose", "ad", "--look", "linocut", "--title", "x")
        self.assertNotIn("already open", out)
        hist = json.loads((self.root / "history.json").read_text(encoding="utf-8"))
        self.assertEqual(hist["deals"][0]["pick"], "(context changed)")
        page = (ROOT / "templates" / "type-specimen.html").read_text(encoding="utf-8")
        for invented in ("249.000 ₫", "Nguyễn Thị Lan", "thử ngay", "Khuyến mãi 31.12"):
            self.assertNotIn(invented, page)

    def test_a_one_shot_films_text_track_is_checked_and_reaches_the_animatic(self):
        data = json.loads((ROOT / "templates" / "shots.example.json").read_text(encoding="utf-8"))
        end = data["shots"][-1]["end"] / data["fps"]
        p = self.root / "shots.json"
        run = lambda: subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_shots.py"), str(p)],
                                     capture_output=True, text=True)
        data["text_on_screen"] = [{"text": "Buổi sáng yên tĩnh", "t": [0.2, 2.6]}]
        p.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(run().returncode, 0, run().stdout)
        data["text_on_screen"] = [{"text": "too late", "t": [end - 0.2, end + 3]}]
        p.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("film text 'too late'", run().stdout)
        data["text_on_screen"] = "a string"
        p.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("FAILED", run().stderr)
        src = (ROOT / "scripts" / "animatic.py").read_text(encoding="utf-8")
        self.assertIn('film.get("text_on_screen")', src)

    def test_a_quick_film_moves_to_film_mode_keeping_its_files(self):
        init = lambda *args: subprocess.run([sys.executable, str(ROOT / "scripts" / "init_film.py"), *args], cwd=self.root,
                                            capture_output=True, text=True, env=dict(self.env, RUBYDAI_VIDEO_REINIT="1"))
        init("hook", "--quick", "--title", "Kanca Testi")
        film = next(self.root.glob("**/hook"))
        (film / "film.html").write_text("<!-- the quick build -->", encoding="utf-8")
        out = init(str(film), "--to-film")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue((film / "engine" / "scene.html").exists())
        self.assertEqual((film / "research" / "quick-film.html").read_text(encoding="utf-8"), "<!-- the quick build -->")
        self.assertTrue((film / "research" / "quick-STATE.md").exists())
        self.assertFalse((film / "film.html").exists())
        self.assertIn("Kanca Testi", (film / "STATE.md").read_text(encoding="utf-8").splitlines()[0])
        self.assertIn("already a Film mode film", init(str(film), "--to-film").stderr)

    def test_no_tool_call_names_the_key_file(self):
        call = lambda name, inp: self.guard("tool", {"tool_name": name, "tool_input": inp, "cwd": str(self.root)})[0]
        keys = str(self.root / ".rubydai-video" / "keys.env")
        self.assertEqual(call("Read", {"file_path": keys}), 2)
        self.assertEqual(call("Bash", {"command": f"cat {keys}"}), 2)
        self.assertEqual(call("Bash", {"command": f"cat {keys} # keys.py"}), 2)
        self.assertEqual(call("Grep", {"pattern": "keys.py", "path": keys}), 2)
        self.assertEqual(call("Glob", {"pattern": "**/keys.env", "path": str(self.root / "keys.py")}), 2)
        self.assertEqual(call("Bash", {"command": "python3 tools/keys.py list"}), 0)
        self.assertEqual(call("Write", {"file_path": str(self.root / "notes.md"), "content": "keys live in keys.env"}), 0)
        raw = lambda text: subprocess.run([sys.executable, GUARD, "tool"], input=text, capture_output=True, text=True,
                                          env=self.env).returncode
        self.assertEqual(raw('{"tool_name":"Read","tool_input":{"file_path":"/x/keys.env"},"unrelated":"keys.py"'), 2)
        self.assertEqual(raw('{"tool_name":"Read"'), 0)

    def test_load_weighs_each_model_and_names_what_it_cannot_price(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import usage
        self.assertAlmostEqual(usage.cost_of({"input_tokens": 1000}, "claude-haiku-5-5"), 0.0001)
        self.assertAlmostEqual(usage.cost_of({"input_tokens": 100001}, "claude-haiku-5-5"), 0.0500005)
        self.assertAlmostEqual(usage.cost_of({"output_tokens": 1000}, "claude-opus-5-5"), 0.02)
        self.assertIsNone(usage.cost_of({"input_tokens": 1000}, "claude-unknown-9"))
        base = "/tmp" if os.path.isdir("/tmp") else tempfile.gettempdir()   # a short base, so the mirrored name is one
        film = Path(tempfile.mkdtemp(dir=base, prefix="uf"))                # folder; a long TMPDIR would pass 255 chars
        self.addCleanup(shutil.rmtree, film, ignore_errors=True)
        chats = self.root / "chats" / usage.re.sub(r"[^A-Za-z0-9]", "-", str(film.resolve()))
        (chats / "s1" / "subagents").mkdir(parents=True)
        turn = lambda i, model: json.dumps({"type": "assistant", "timestamp": "2026-10-26T10:00:00Z", "message": {
            "id": i, "model": model, "usage": {"input_tokens": 1000, "output_tokens": 1000}}}) + "\n"
        (chats / "s1.jsonl").write_text(turn("a", "claude-opus-5-5"), encoding="utf-8")
        (chats / "s1" / "subagents" / "agent-x.jsonl").write_text(turn("b", "unknown-helper-model"), encoding="utf-8")
        with patch.object(usage, "CLAUDE_PROJECTS", self.root / "chats"), patch.object(sys, "argv", ["usage.py", "--project", str(film)]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            usage.main()
        self.assertIn("1 turn(s) of an unknown model left out", out.getvalue())
        self.assertNotIn("$", out.getvalue())

    def test_a_film_with_folders_on_another_disk(self):
        (self.film / "engine").mkdir()
        disk = self.root / "external"
        (disk / "review").mkdir(parents=True)
        (self.film / "review").rmdir()
        (self.film / "review").symlink_to(disk / "review")
        chat = self.root / "chat.jsonl"
        chat.write_text("", encoding="utf-8")
        brief = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "review", "--task", "t", "--writes",
                                "review/critique-v1.md", "--reads", "x", "--done", "y"], capture_output=True, text=True).stdout
        (self.root / "chat" / "subagents").mkdir(parents=True)
        (self.root / "chat" / "subagents" / "agent-v1.jsonl").write_text(json.dumps({"type": "user", "message": {
            "role": "user", "content": brief}}) + "\n", encoding="utf-8")
        ev = {"tool_name": "Write", "cwd": str(self.film), "session_id": "s", "agent_id": "v1", "transcript_path": str(chat),
              "tool_input": {"file_path": str(self.film / "review" / "critique-v1.md"), "content": "x"}}
        self.assertEqual(self.guard("tool", ev)[0], 0)
        (self.film / "renders").symlink_to(self.root / "unplugged" / "renders")
        with patch.object(make, "PROJECT", self.film), contextlib.redirect_stdout(io.StringIO()):
            self.assertIn("not connected", make.unplugged_line())
        (self.film / "renders").unlink()
        (disk / "renders").mkdir()
        (self.film / "renders").symlink_to(disk / "renders")
        import collections
        seen = []
        usage = collections.namedtuple("usage", "total used free")
        with patch.object(make, "PROJECT", self.film), patch.object(make, "RENDERS", self.film / "renders"), \
                patch.object(make.shutil, "disk_usage", side_effect=lambda p: seen.append(Path(p)) or usage(1, 1, 50e9)):
            self.assertEqual(make.unplugged_line(), "")
            make.disk_short(10, "4M")
        self.assertEqual(seen[0], (disk / "renders").resolve())

    def test_a_new_chat_continues_the_film_without_a_task_scope(self):
        start = lambda prompt: {"cwd": str(self.root), "session_id": "s", "tool_name": "mcp__ccd_session__start_session",
                                "tool_input": {"prompt": prompt, "cwd": str(self.film)}}
        code, out = self.guard("tool", start("Tiếp tục từ STATE.md, bắt đầu bằng lộ trình.\n\nNhiệm vụ: bước 2 của chế độ Film."
                                            "\n\nXong khi: lộ trình đã được cho xem, câu hỏi đã được hỏi."))
        self.assertEqual(code, 2)
        self.assertIn("never a helper's brief", out)
        self.assertEqual(self.guard("tool", start("Tiếp tục từ STATE.md, bắt đầu bằng lộ trình. Lựa chọn của người dùng: "
                                                 "\"Đêm xanh\".  Viết bằng tiếng Việt."))[0], 0)

    def test_the_script_is_read_before_its_gate(self):
        (self.film / "review" / "script-cold.md").write_text("# Cold read of the script\\n" + "The reader understood every line; no guesses needed about who, what or why.\\n" * 4, encoding="utf-8")
        script = self.film / "SCRIPT.md"
        script.write_text("## Lines\n| # | Start | Line | Words |\n|---|---|---|---|\n"
                          "| VO1 | 0:00 | Một sáng tháng năm. Bảy giờ. | 4 |\n| VO2 | 0:04 | Người nuôi ong chậm rãi mở nắp tổ. | 5 |\n"
                          "| VO3 | 0:10 | Những tầng sáp giữ lấy ánh sáng. | 3 |\n", encoding="utf-8")
        log = self.root / "s.jsonl"
        wrote = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "w", "name": "Write", "input": {"file_path": str(script), "content": "…"}}]}})
        said = lambda text: json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
        ask = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log), "tool_name": "AskUserQuestion",
               "tool_input": {"questions": [{"question": "Kịch bản ổn chưa?", "header": "Kịch bản",
                                             "options": [{"label": "Được ★"}, {"label": "Một góp ý"}]}]}}
        log.write_text(wrote + "\n" + said("Kịch bản đã viết xong.") + "\n", encoding="utf-8")
        code, out = self.guard("tool", ask)
        self.assertEqual(code, 2)
        self.assertIn("has not read the script", out)
        log.write_text(wrote + "\n" + said("VO1 Một sáng tháng năm. Bảy giờ.\nVO2 Người nuôi ong chậm rãi mở nắp tổ.\n"
                                            "VO3 Những tầng sáp giữ lấy ánh sáng.") + "\n", encoding="utf-8")
        self.assertEqual(self.guard("tool", ask)[0], 0)
        script.write_text("## Lines (archive audio)\n| # | Start | Line (archive) | On screen (translation) | What it adds |\n"
                          "|---|---|---|---|---|\n| R1 | 0:07 | \"Smoke first, then the lid.\" (Beekeeper) | "
                          "Khói trước, nắp sau. | the real voice |\n| R3 | 0:52 | \"They know my hands.\" (Beekeeper) | Chúng nhận ra tay tôi. | warm |\n"
                          "## On-screen text\n| Time | Text | On screen (s) | Placement |\n|---|---|---|---|\n"
                          "| 0:21 | Tháng năm · Mùa hoa | 2.5 | lower left |\n", encoding="utf-8")
        log.write_text(wrote + "\n" + said("Tôi đã viết kịch bản.") + "\n", encoding="utf-8")
        self.assertEqual(self.guard("tool", ask)[0], 2)
        log.write_text(wrote + "\n" + said("R1 Khói trước, nắp sau.\nR3 They know my hands.\n0:21 Tháng năm · Mùa hoa")
                       + "\n", encoding="utf-8")
        self.assertEqual(self.guard("tool", ask)[0], 0)

    def test_a_script_written_any_way_is_read_before_its_gate(self):
        (self.film / "review" / "script-cold.md").write_text("# Cold read of the script\\n" + "The reader understood every line; no guesses needed about who, what or why.\\n" * 4, encoding="utf-8")
        other = self.root / "kovan"
        (other / "tools").mkdir(parents=True)
        (other / "STATE.md").write_text("# State: Kovan\n", encoding="utf-8")
        (other / "tools" / "qc.sh").write_text("", encoding="utf-8")
        (self.film / "SCRIPT.md").write_text("# Script: Test\n\nStatus: DRAFT\n\n## Narration\n"
                                            "Sáng tháng năm, ong bay ra hoa.\n"
                                            "Người nuôi ong chuẩn bị khói.\n"
                                            "Tầng sáp đầu tiên được giơ lên ánh sáng.\n", encoding="utf-8")
        log = self.root / "p.jsonl"
        row = lambda block: json.dumps({"type": "assistant", "message": {"content": [block]}}) + "\n"
        by_shell = row({"type": "tool_use", "id": "b", "name": "Bash",
                        "input": {"command": "cd film && cat > SCRIPT.md <<'EOF'\n…\nEOF"}})
        ask = {"cwd": str(self.root), "session_id": "s", "transcript_path": str(log), "tool_name": "AskUserQuestion",
               "tool_input": {"questions": [{"question": "Kịch bản ổn chưa?", "options": [{"label": "Được ★"}]}]}}
        log.write_text(by_shell + row({"type": "text", "text": "Tôi đã viết kịch bản."}), encoding="utf-8")
        code, out = self.guard("tool", ask)
        self.assertEqual(code, 2, "a script written by a shell command and never shown")
        log.write_text(by_shell + row({"type": "text", "text": "Sáng tháng năm, ong bay ra hoa.\n"
                                       "Người nuôi ong chuẩn bị khói.\n"
                                       "Tầng sáp đầu tiên được giơ lên ánh sáng."}), encoding="utf-8")
        self.assertEqual(self.guard("tool", ask)[0], 0, "a prose script shown in full")
        elsewhere = row({"type": "tool_use", "id": "g", "name": "Bash", "input": {"command": "cd kovan && head SCRIPT.md"}})
        log.write_text(elsewhere + row({"type": "text", "text": "Kovan."}), encoding="utf-8")
        self.assertEqual(self.guard("tool", ask)[0], 0, "another film's chat is never held by this film's script")
        (self.film / "SCRIPT.md").write_text((ROOT / "templates" / "SCRIPT.md").read_text(encoding="utf-8"), encoding="utf-8")
        log.write_text(by_shell + row({"type": "text", "text": "Lộ trình đã sẵn sàng."}), encoding="utf-8")
        self.assertEqual(self.guard("tool", ask)[0], 0, "the untouched template is not a script yet")

    def test_a_resumed_chat_carries_the_round_of_ideas_on(self):
        import datetime
        log = self.root / "r.jsonl"
        log.write_text(json.dumps({"type": "user", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                   "message": {"content": "Tiếp tục từ STATE.md."}}) + "\n", encoding="utf-8")
        ask = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log), "tool_name": "AskUserQuestion",
               "tool_input": {"questions": [{"question": "Mình đi theo cách hiểu nào?", "header": "Ý tưởng",
                                             "options": [{"label": "1 ★"}]}]}}
        hour_ago = time.time() - 3600
        research = self.film / "research"
        research.mkdir(exist_ok=True)
        for name, text in (("predict.md", "1. a kite over a field\n2. a greenhouse at noon\n3. a windmill at dusk\n"),
                           ("candidates.md", "1. a\n2. b\n"), ("overlap.md", "1: CLEAR\n2: CLEAR\n")):
            (research / name).write_text(text, encoding="utf-8")
            os.utime(research / name, (hour_ago, hour_ago))
        dealt = datetime.datetime.fromtimestamp(hour_ago - 100).isoformat(timespec="minutes")
        (self.film / "history.json").write_text(json.dumps({"deals": [{"category": "spark", "dealt": ["s1"], "pick": ["s1"],
                                                                       "at": dealt}]}), encoding="utf-8")
        self.assertEqual(self.guard("tool", ask)[0], 0, "the hand picked and the files written by the chat before")
        (research / "predict.md").write_text("1. a kite\n2. a greenhouse at noon\n3. a windmill at dusk\n", encoding="utf-8")
        code, out = self.guard("tool", ask)
        self.assertEqual(code, 2, "a new round in this chat deals its own sparks")
        self.assertIn("sparks", out)

    def test_every_written_step_is_wired_to_its_moment(self):
        log = self.root / "w.jsonl"
        say = lambda *texts: log.write_text("".join(json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "r", "content": x}]}}) + "\n" for x in texts), encoding="utf-8")
        ask = lambda q, h: {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log), "tool_name": "AskUserQuestion",
                            "tool_input": {"questions": [{"question": q, "header": h, "options": [{"label": "1 ★"}]}]}}
        say("nothing yet")
        code, out = self.guard("tool", ask("Mình chọn ý tưởng nào?", "Ý tưởng"))
        self.assertEqual(code, 2)
        self.assertIn("prediction test", out)
        self.assertIn("sparks", out)
        self.assertEqual(self.guard("tool", ask("Giám khảo: ý tưởng chắc nhưng nhịp chậm; làm gì tiếp?", "Giám khảo"))[0], 0)
        say("python3 tools/brief.py predict --task …", "python3 tools/deal.py deal spark")
        self.assertEqual(self.guard("tool", ask("Mình chọn ý tưởng nào?", "Ý tưởng"))[0], 2, "words in the log are no proof")
        (self.film / "research").mkdir(exist_ok=True)
        (self.film / "research" / "predict.md").write_text("1. a kite over a winter field, one long take\n"
                                                          "2. a greenhouse at noon, drifting seeds, montage\n"
                                                          "3. a windmill at dusk, gusts, slow push\n", encoding="utf-8")
        (self.film / "history.json").write_text(json.dumps({"deals": [{"category": "spark", "dealt": ["s1"]}]}), encoding="utf-8")
        code, out = self.guard("tool", ask("Mình chọn ý tưởng nào?", "Ý tưởng"))
        self.assertEqual(code, 2, "the candidates are checked against the predictions and the user's films first")
        self.assertIn("overlap check", out)
        (self.film / "research" / "candidates.md").write_text("1. a\n2. b\n3. c\n", encoding="utf-8")
        (self.film / "research" / "overlap.md").write_text("1: CLEAR\n2: OVERLAP with the film Kettle: the subject\n"
                                                           "3: CLEAR\n", encoding="utf-8")
        self.assertEqual(self.guard("tool", ask("Mình chọn ý tưởng nào?", "Ý tưởng"))[0], 0)
        later = time.time() + 5
        os.utime(self.film / "research" / "candidates.md", (later, later))
        self.assertEqual(self.guard("tool", ask("Mình chọn ý tưởng nào?", "Ý tưởng"))[0], 2,
                         "candidates rewritten after the check are checked again")
        os.utime(self.film / "research" / "overlap.md", (later + 1, later + 1))
        self.assertEqual(self.guard("tool", ask("Mình chọn ý tưởng nào?", "Ý tưởng"))[0], 0)
        board = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log), "tool_name": "Bash",
                 "tool_input": {"command": "python3 tools/direction.py board --row \"1|A||research/a\" --out review/d.jpg"}}
        code, out = self.guard("tool", board)
        self.assertEqual(code, 2)
        self.assertIn("Medium", out, "the board waits for the medium the user chose")
        (self.film / "STATE.md").write_text("# State: Test (Quick mode)\n- **Medium:** <the user's choice in their words: "
                                            "3D realistic · 2D animation>\n", encoding="utf-8")
        self.assertIn("Medium", self.guard("tool", board)[1], "the template's placeholder is not a choice")
        (self.film / "STATE.md").write_text("# State: Test (Quick mode)\n- **Medium:** 2B animasyon\n", encoding="utf-8")
        code, out = self.guard("tool", board)
        self.assertEqual(code, 2)
        self.assertIn("deal look", out)
        (self.film / "history.json").write_text(json.dumps({"deals": [{"category": "spark", "dealt": ["s1"]},
                                                                      {"category": "look", "dealt": ["Deakins"]}]}),
                                                encoding="utf-8")
        self.assertEqual(self.guard("tool", board)[0], 0)

    def test_the_idea_reaches_state_only_after_the_predictions_and_the_sparks(self):
        log = self.root / "idea.jsonl"
        log.write_text(json.dumps({"type": "user", "message": {"content": "rubydai-make-video-skill, chế độ nhanh. Làm tôi bất ngờ đi."}}) + "\n",
                       encoding="utf-8")
        state = self.film / "STATE.md"
        state.write_text("# State: Test (Quick mode)\n- **Idea:** <one line>\n", encoding="utf-8")
        edit = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log), "tool_name": "Edit",
                "tool_input": {"file_path": str(state), "old_string": "- **Idea:** <one line>",
                               "new_string": "- **Idea:** a beam through the rain, then a command line"}}
        own = dict(edit, tool_input=dict(edit["tool_input"], new_string="- **Idea:** a kettle that sings at dawn (user)"))
        self.assertEqual(self.guard("tool", own)[0], 0, "a complete brief's own idea is written as given, no question")
        code, out = self.guard("tool", edit)
        self.assertEqual(code, 2, "an idea the agent picked alone still waits for the predictions and the sparks")
        self.assertIn("prediction test", out)
        self.assertIn("làm tôi bất ngờ đi", out)
        (self.film / "research").mkdir(exist_ok=True)
        (self.film / "research" / "predict.md").write_text("1. someone typing code at a screen\n2. a rain of falling code\n"
                                                           "3. a projector beam in a dark room\n", encoding="utf-8")
        (self.film / "history.json").write_text(json.dumps({"deals": [{"category": "spark", "dealt": ["s1"]}]}),
                                                encoding="utf-8")
        self.assertEqual(self.guard("tool", edit)[0], 0)
        state.write_text("# State: Test (Quick mode)\n- **Idea:** an idea already chosen\n", encoding="utf-8")
        (self.film / "research" / "predict.md").unlink()
        later = dict(edit, tool_input={"file_path": str(state), "old_string": "an idea already chosen",
                                       "new_string": "the same idea, tightened"})
        self.assertEqual(self.guard("tool", later)[0], 0, "an idea already in STATE.md is edited freely")

    def test_a_plan_brings_in_a_habit_image_only_when_the_user_asked(self):
        log = self.root / "habit.jsonl"
        say = lambda *texts: log.write_text("".join(json.dumps({"type": "user", "message": {"content": t}}) + "\n"
                                                    for t in texts), encoding="utf-8")
        say("rubydai-make-video-skill, chế độ nhanh. Làm tôi bất ngờ đi.")
        state = self.film / "STATE.md"
        state.write_text("# State: Test (Quick mode)\n- **Director card:** <card>\n", encoding="utf-8")
        edit = lambda new: {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log), "tool_name": "Edit",
                            "tool_input": {"file_path": str(state), "old_string": "<card>", "new_string": new}}
        code, out = self.guard("tool", edit("0 s: a lighthouse beam cuts through the rain"))
        self.assertEqual(code, 2, "the model's default image is not the user's choice")
        self.assertIn("lighthouse", out)
        self.assertEqual(self.guard("tool", edit("0 s: một ngọn hải đăng trong bão"))[0], 2)
        self.assertEqual(self.guard("tool", edit("0 s: một con phố neon, nhựa đường ướt"))[0], 2)
        self.assertEqual(self.guard("tool", edit("0 s: một trận bóng bàn, một tiếng hô"))[0], 0, "a phrase that only starts like it (bóng bàn, not bóng bay)")
        self.assertEqual(self.guard("tool", edit("0 s: a kite over a winter field"))[0], 0)
        self.assertEqual(self.guard("tool", edit("0 s: a lighthouse beam cuts through the rain\n- **Habit image:** lighthouse: "
                                                 "the film is the last night of a lighthouse keeper"))[0], 0,
                         "a story that needs it says why, and it is made")
        say("Làm tôi bất ngờ đi nhưng đừng dùng hải đăng, neon và bóng bay.")
        self.assertEqual(self.guard("tool", edit("0 s: a lighthouse beam cuts through the rain"))[0], 2,
                         "naming it to refuse it is not asking for it")
        say("rubydai-make-video-skill, chế độ nhanh. Một ngọn hải đăng trong bão nhé.")
        self.assertEqual(self.guard("tool", edit("0 s: a lighthouse beam cuts through the rain"))[0], 0, "the user asked for it")

    def test_claims_are_checked_against_the_film(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, guard
        film = self.root / "film.html"
        film.write_text("const OWN_MUSIC = null;\nfunction score(ctx, out) {\n  pad(ctx, out, 0, 4, [220], 0.1);\n}\n",
                        encoding="utf-8")
        self.assertIn("says no music", make.music_choice_line(film, None, "- **Music:** none (user)\n"))
        self.assertIn("picks a recording", make.music_choice_line(film, None, "- **Music:** recording, x.mp3 (user)\n"))
        self.assertEqual(make.music_choice_line(film, None, "- **Music:** code, a slow piano (user)\n"), "")
        self.assertIn("ENDING SHORT", make.ending_line([(28.0, 29.5)], 30.0), "words on screen end a film too")
        script = self.film / "SCRIPT.md"
        script.write_text("## Lines\n| # | Start | Line |\n|---|---|---|\n" + "".join(
            f"| VO{i} | 0:0{i} | line number {i} is here |\n" for i in range(1, 6)), encoding="utf-8")
        log = self.root / "s5.jsonl"
        log.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "w", "name": "Write",
                                                                                 "input": {"file_path": str(script)}}]}}) + "\n" +
                       json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                                   "text": "line number 1 is here / line number 2 is here / line number 3 is here"}]}}) + "\n",
                       encoding="utf-8")
        self.assertTrue(guard.script_unread(str(log), {"questions": [{"question": "Kịch bản ổn chưa?"}]}, str(self.film)),
                        "three of five lines are not the script")
        (self.film / "review" / "script-cold.md").write_text("x", encoding="utf-8")
        self.assertTrue(guard.cold_read_missing({"cwd": str(self.film)}, {"questions": [{"question": "Kịch bản ổn chưa?"}]}),
                        "a one-byte cold read is not one")

    def test_helpers_carry_the_rules_they_act_on(self):
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "predict", "--task", "the message"],
                             capture_output=True, text=True, cwd=self.film)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("WRITES: research/predict.md", out.stdout)
        env = dict(os.environ, RUBYDAI_VIDEO_FILMS=str(self.root / "films.json"))
        check = lambda: subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "overlap", "--task",
                                        "làm tôi bất ngờ đi"], capture_output=True, text=True, cwd=self.film, env=env)
        first = check()
        self.assertNotEqual(first.returncode, 0)
        self.assertIn("research/candidates.md", first.stdout + first.stderr, "the candidates are written first")
        (self.film / "research").mkdir(exist_ok=True)
        (self.film / "research" / "candidates.md").write_text("1. a\n", encoding="utf-8")
        out = check()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("WRITES: research/overlap.md", out.stdout)
        self.assertIn("làm tôi bất ngờ đi", out.stdout)
        self.assertIn("This user's films", (self.film / "research" / "past-films.md").read_text(encoding="utf-8"))
        pic = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "picture", "--task", "t", "--writes",
                              "engine/scene.html", "--reads", "STATE.md", "--done", "d"], capture_output=True, text=True,
                             cwd=self.film)
        self.assertIn("never as a blockout", pic.stdout)
        self.assertIn("# Finish: the quality toolbox", pic.stdout)
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        chat = self.root / "chat.jsonl"
        chat.write_text("", encoding="utf-8")
        sub = self.root / "chat" / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-h1.jsonl").write_text(json.dumps({"message": {"role": "user", "content": "build the mill, no rules"}})
                                            + "\n", encoding="utf-8")
        ev = {"transcript_path": str(chat), "agent_id": "h1", "cwd": str(self.film)}
        self.assertTrue(guard.build_rules_unread(ev, "Write", {"file_path": str(self.film / "engine" / "scene.html")}))
        (sub / "agent-h1.jsonl").write_text(json.dumps({"message": {"role": "user", "content": pic.stdout}}) + "\n",
                                            encoding="utf-8")
        (self.film / "engine").mkdir(exist_ok=True)
        (self.film / "ROADMAP.md").write_text("# Roadmap\n- **Motion design:** <the devices and the job each does>\n",
                                              encoding="utf-8")
        self.assertIn("still the template", guard.build_rules_unread(ev, "Write", {"file_path": str(self.film / "engine" / "scene.html")}),
                      "a helper's picture waits for the card too")
        (self.film / "ROADMAP.md").write_text("# Roadmap\n- **Motion design:** none: the archive carries the facts, and why\n",
                                              encoding="utf-8")
        self.assertEqual(guard.build_rules_unread(ev, "Write", {"file_path": str(self.film / "engine" / "scene.html")}), "")

    def test_picture_code_written_from_the_shell_counts(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        log = self.root / "sh.jsonl"
        log.write_text(json.dumps({"type": "user", "message": {"content": "film"}}) + "\n", encoding="utf-8")
        ev = {"transcript_path": str(log), "cwd": str(self.film)}
        writes = ["cat > film.html <<'EOF'\n<html>\nEOF", "python3 - <<'EOF'\nopen('film.html','w').write(s)\nEOF",
                  "cp ~/kit/templates/quick/film.html film.html", "sed -i '' 's/a/b/' engine/scene.html"]
        reads = ["grep -n score film.html", "sed -i '' 's/x/y/' STATE.md && grep -n x film.html",
                 "python3 tools/make.py draft > logs/make.out 2>&1", "cp film.html research/film.html.bak",
                 "python3 - <<'EOF'\nprint(open('film.html').read()[:200])\nEOF"]
        for cmd in writes:
            self.assertTrue(guard.build_rules_unread(ev, "Bash", {"command": cmd}), cmd)
        for cmd in reads:
            self.assertFalse(guard.build_rules_unread(ev, "Bash", {"command": cmd}), cmd)

    def test_film_mode_script_waits_for_its_cold_read(self):
        (self.film / "SCRIPT.md").write_text("## Lines\n| # | Start | Line |\n|---|---|---|\n| VO1 | 0:00 | Một dòng nằm ở đây |\n",
                                            encoding="utf-8")
        log = self.root / "c.jsonl"
        log.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text",
                       "text": "VO1 Một dòng nằm ở đây"}]}}) + "\n", encoding="utf-8")
        ask = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log), "tool_name": "AskUserQuestion",
               "tool_input": {"questions": [{"question": "Kịch bản ổn chưa?", "header": "Kịch bản"}]}}
        code, out = self.guard("tool", ask)
        self.assertEqual(code, 2)
        self.assertIn("cold read", out)
        (self.film / "review" / "script-cold.md").write_text("# Cold read of the script\\n" + "The reader understood every line; no guesses needed about who, what or why.\\n" * 4, encoding="utf-8")
        self.assertEqual(self.guard("tool", ask)[0], 0)

    def test_picture_code_waits_for_the_build_rules(self):
        log = self.root / "b.jsonl"
        write = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log), "tool_name": "Write",
                 "tool_input": {"file_path": str(self.film / "film.html"), "content": "<html>"}}
        log.write_text(json.dumps({"type": "user", "message": {"content": "film yap"}}) + "\n", encoding="utf-8")
        code, out = self.guard("tool", write)
        self.assertEqual(code, 2)
        self.assertIn("finish.md", out)
        read = (ROOT / "references" / "quick-mode.md").read_text(encoding="utf-8") + \
            (ROOT / "references" / "finish.md").read_text(encoding="utf-8") + "\n[capture] renderer: ANGLE (Apple M4)"
        log.write_text(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "r",
                                                                            "content": read}]}}) + "\n", encoding="utf-8")
        (self.film / "film.html").write_text("<html>", encoding="utf-8")
        code, out = self.guard("tool", write)
        self.assertEqual(code, 2)
        self.assertIn("director card is missing", out)
        (self.film / "STATE.md").write_text("# State: Test (Quick mode)\n- **Director card:** frontal frames · finish: grain "
                                            "on the night scenes · motion design: none, the picture carries it\n",
                                            encoding="utf-8")
        self.assertEqual(self.guard("tool", write)[0], 0)

    def test_a_new_film_carries_the_decks_in_both_modes(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import init_film
        self.assertIn("sparks.json", init_film.QUICK_TOOLS)
        self.assertIn("sparks.json", init_film.TOOLS)
        self.assertIn("deal.py", init_film.QUICK_TOOLS)
        for tools in (init_film.TOOLS, init_film.QUICK_TOOLS):       # deal.py and brief.py import dice
            self.assertIn("dice.py", tools)
            self.assertIn("seeds.json", tools)

    def test_sparks_differ_from_film_to_film(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import deal
        with patch.dict(os.environ, {"RUBYDAI_VIDEO_SPARKS": str(self.root / "seen.json"), "RUBYDAI_VIDEO_DICE": "offline"}):
            a, seeds = deal.spark_hand("2026-10-29:film-a#1", 3)
            cards = [p.split(": ", 1)[1] for h in a.values() for p in h.split(" · ")]
            self.assertEqual(len(cards), len(set(cards)), "no card twice in a hand")
            self.assertTrue(all(h.startswith("seed: ") and "place: " in h and "medium: " in h for h in a.values()))
            self.assertFalse(any(re.search(r"\b(light|air|subject): ", h) for h in a.values()),
                             "light and weather come from the story, the subject from the seed")
            self.assertEqual(len({s["pool"] for s in seeds.values()}), 2, "the seeds come from different pools")
            self.assertTrue(all(s["name"] and s["link"] for s in seeds.values()))
            looks = deal.look_hand("2026-10-29:film-a#1", 6)
            self.assertEqual(len(set(looks.values())), 6)
            again = deal.look_hand("2026-10-29:film-b#1", 6)
            self.assertFalse(set(looks.values()) & set(again.values()), "the last film's references stay out")
            b, _ = deal.spark_hand("2026-10-29:film-b#1", 3)
            later = [p.split(": ", 1)[1] for h in b.values() for p in h.split(" · ")]
            self.assertFalse(set(cards) & set(later), "the last film's cards and seeds stay out")
            worlds, full = deal.seed_hand("2026-10-29:film-b#1|worlds", 5)
            self.assertEqual(len(set(worlds.values())), 5, "one seed for each world")
            self.assertFalse(set(worlds.values()) & set(later))

    def test_a_seed_comes_from_another_pool_when_one_does_not_answer(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import dice

        def reply(url, wait=8):
            if "clevelandart" in url:
                return {"data": [{"title": "A Fluted Armour", "type": "Arms and Armor", "creation_date": "c. 1520",
                                  "url": "https://clevelandart.org/art/x"}]}
            raise OSError("no answer")
        with patch.dict(os.environ, {"RUBYDAI_VIDEO_DICE": ""}), patch.object(dice, "get", side_effect=reply), \
                patch.object(dice, "POOLS", {"museum": "a museum object", "sky": "something in space",
                                             "place": "a heritage site"}):
            got = dice.draw("x", 3)
        self.assertEqual(sorted(s["pool"] for s in got), ["custom", "museum", "place"],
                         "the museum answered; the sky gave way to a list no other hand used")
        armour = next(s for s in got if s["pool"] == "museum")
        self.assertEqual(armour["name"], "A Fluted Armour")
        self.assertIn("Arms and Armor", armour["fact"])

        def slow(url, wait=8):
            if "clevelandart" in url:
                time.sleep(3)                    # answers, a little at a time, past the whole pool's time
            return reply(url, wait)
        with patch.dict(os.environ, {"RUBYDAI_VIDEO_DICE": ""}), patch.object(dice, "get", side_effect=slow), \
                patch.object(dice, "DEADLINE", 0.5), patch.object(dice, "POOLS", {"museum": "a museum object"}):
            began = time.monotonic()
            got = dice.draw("y", 1)
        self.assertLess(time.monotonic() - began, 2, "the deal never waits past its deadline")
        self.assertIn(got[0]["pool"], ("place", "custom"))

        page = ("* '''1884:''' [[Steam turbine]] by Charles Parsons\n"
                "* '''4th millennium BC:''' [[Wheel]] in Mesopotamia\n"
                "* See [[Timeline of transportation technology]] and [[1800 in science]].\n"
                "* A note on [[Printing press]] history, 1450 and after\n"
                "* '''1903:''' [[1903 in aviation]]\n"
                "== See also ==\n* '''1999:''' [[List of inventors]]\n").encode()

        class Raw(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        with patch.object(dice.urllib.request, "urlopen", lambda *a, **k: Raw(page)), \
                patch.object(dice, "summary", lambda *a, **k: ""):
            drawn = {dice.invention(random.Random(k), ())["name"] for k in range(40)}
        self.assertEqual(drawn, {"1884: Steam turbine by Charles Parsons", "4th millennium BC: Wheel in Mesopotamia"},
                         "only an entry that starts with its date, never a year page or a list")

    def test_the_users_films_are_remembered_and_listed_for_the_check(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import dice
        shelf = self.root / "shelf"
        for name, text in (("kettle", "# State: Kettle (Quick mode)\n- **Idea:** a kettle that sings at dawn\n"
                                      "- **Medium:** 2B animasyon\n"),
                           ("doc", "# State: Doc (working title)\n- **Phase:** 2 roadmap\n"),
                           ("blank", "# State: <working title> (Quick mode)\n- **Idea:** <one line>\n")):
            (shelf / name).mkdir(parents=True)
            (shelf / name / "STATE.md").write_text(text, encoding="utf-8")
        (shelf / "doc" / "ROADMAP.md").write_text("- **Logline:** a pier counts its last ferries\n", encoding="utf-8")
        (shelf / "new").mkdir()
        with patch.dict(os.environ, {"RUBYDAI_VIDEO_FILMS": str(self.root / "films.json")}):
            listed = {f["title"]: f for f in dice.past(shelf / "new")}
            self.assertEqual(set(listed), {"Kettle", "Doc"}, "the shelf's films with an idea, never the template")
            self.assertEqual(listed["Doc"]["idea"], "a pier counts its last ferries", "Film mode: the roadmap's logline")
            other = self.root / "elsewhere" / "rain-film"
            other.mkdir(parents=True)
            (other / "STATE.md").write_text("# State: Rain (Quick mode)\n- **Idea (v2, re-plan):** a bus stop at dawn\n",
                                            encoding="utf-8")
            self.assertEqual(dice.scan(self.root / "elsewhere"), 1)
            self.assertTrue(dice.remember(shelf / "kettle"))
            self.assertIn("Rain", {f["title"] for f in dice.past(shelf / "new")}, "the memory reaches other shelves")
            self.assertNotIn("Kettle", {f["title"] for f in dice.past(shelf / "kettle")}, "never the film itself")
            (shelf / "new" / "research").mkdir()
            self.assertEqual(dice.write_past(shelf / "new"), 3)
            text = (shelf / "new" / "research" / "past-films.md").read_text(encoding="utf-8")
            self.assertIn("- Kettle · a kettle that sings at dawn · 2B animasyon", text)
            many = []
            for k in range(8):
                (shelf / f"f{k}").mkdir()
                (shelf / f"f{k}" / "STATE.md").write_text(f"# State: F{k}\n- **Idea:** film {k}\n", encoding="utf-8")
                many.append(threading.Thread(target=dice.remember, args=(shelf / f"f{k}",)))
            for w in many:
                w.start()
            for w in many:
                w.join()
            titles = {v["title"] for v in dice.load_films().values()}
            self.assertTrue({f"F{k}" for k in range(8)} <= titles, "chats writing at once lose no film")
            memory = self.root / "films.json"
            memory.write_text('{"half": ', encoding="utf-8")
            self.assertFalse(dice.remember(shelf / "kettle"))
            self.assertEqual(memory.read_text(encoding="utf-8"), '{"half": ', "a memory it cannot read is never written over")

    def test_script_gate_holes_are_closed(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        template = (ROOT / "templates" / "SCRIPT.md").read_text(encoding="utf-8")
        wordless = template.replace("<working title>", "Rain")
        self.assertEqual(guard.script_rows(wordless), [], "a wordless template's instructions are not lines")
        script = self.film / "SCRIPT.md"
        script.write_text("## Lines\n| # | Start | Line |\n|---|---|---|\n| VO1 | 0:00 | The whole line is hidden here |\n"
                          "| VO2 | 0:04 | And a second line nobody saw |\n", encoding="utf-8")
        log = self.root / "a8.jsonl"
        rel = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "w", "name": "Write", "input": {"file_path": "SCRIPT.md", "content": "…"}}]}})
        sent = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "s", "name": "mcp__x__SendUserFile", "input": {"files": [str(script)]}}]}})
        log.write_text(rel + "\n" + sent + "\n", encoding="utf-8")
        ask = {"questions": [{"question": "Kịch bản ổn chưa?"}]}
        self.assertIn("has not read the script", guard.script_unread(str(log), ask, str(self.film)),
                      "a relative path and a sent file are not the lines in the message")
        code, out = self.guard("tool", {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log),
                                        "tool_name": "mcp__ccd_turn__wrap_up", "tool_input": {"ask": "Kịch bản ổn chưa?"}})
        self.assertEqual(code, 2, "the desktop wrap_up question is checked too")

    def test_sparks_dealt_before_the_film_folder_exists(self):
        env = dict(os.environ, RUBYDAI_VIDEO_SPARKS=str(self.root / "sparks-seen.json"), RUBYDAI_VIDEO_DICE="offline")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "deal.py"), "deal", "spark", "--project", "new-film"],
                           cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.root / "new-film" / "history.json").is_file(), "the hand is kept for the film to come")
        (self.root / "package.json").write_text("{}", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "init_film.py"), "new-film", "--quick", "--films-folder",
                            "Filmler"], cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        film = self.root / "Filmler" / "new-film"
        self.assertTrue((film / "STATE.md").is_file() and (film / "history.json").is_file(),
                        "the dealt folder moves into the films folder with its hand")
        self.assertFalse((self.root / "new-film").exists())
        inner = film / "inner"
        subprocess.run([sys.executable, str(ROOT / "scripts" / "deal.py"), "deal", "spark", "--project", str(inner)],
                       cwd=self.root, env=env, capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "init_film.py"), str(inner), "--quick"],
                           cwd=self.root, env=env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, "a dealt folder given by its full path is checked too")
        self.assertFalse((inner / "STATE.md").exists(), "never a film inside a film")
        shelf = self.root / "shelf-of-films"
        shelf.mkdir()
        ran([sys.executable, str(ROOT / "scripts" / "init_film.py"), "kettle", "--quick", "--films-folder", "Filmler"],
            cwd=shelf, env=env, capture_output=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "deal.py"), "deal", "spark", "--project", "reel"],
                       cwd=shelf, env=env, capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "init_film.py"), "reel", "--quick", "--films-folder",
                            "Filmler"], cwd=shelf, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((shelf / "reel" / "STATE.md").is_file(), "a shelf of films takes the next film beside the others")
        self.assertFalse((shelf / "Filmler").exists(), "never a films folder inside the films folder")

    def test_approval_answers_are_read_one_by_one(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        log = self.root / "ap.jsonl"
        ask = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "q", "name": "AskUserQuestion",
                                                                        "input": {"questions": [{"question": "S?"}, {"question": "P?"}]}}]}})
        res = lambda s: json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "q", "content": s}]}})
        bash = lambda c, out="ok": json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "b", "name": "Bash", "input": {"command": c}}]}}) + "\n" + json.dumps(
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "b", "content": out}]}})
        def idle(*rows):
            log.write_text("\n".join(rows) + "\n", encoding="utf-8")
            return guard.approved_and_idle(str(log))
        self.assertFalse(idle(ask, res('"S?"="Một thay đổi: VO2", "P?"="Từng bước ★"')), "a change is not a go")
        self.assertFalse(idle(ask, res('"S?"="Chat mới ★"'), bash("python3 tools/handoff.py")), "a handoff moved on")
        self.assertFalse(idle(ask, res('"S?"="Final ★"'), bash("python3 tools/make.py final")), "a final moved on")
        self.assertTrue(idle(ask, res('"S?"="Được ★"'), json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "e", "name": "Edit", "input": {"file_path": "/f/STATE.md"}}]}})), "bookkeeping alone")
        q = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Render bản cuối nhé?"}]}})
        self.assertTrue(idle(q, json.dumps({"type": "user", "message": {"content": "được, tiếp tục"}})), "a typed go")
        self.assertFalse(idle(ask, res('"S?"="Tôi sẽ gom file trước ★"')), "the user's own plan is not a go")
        self.assertIn("handoff", guard.scoped_handoff("mcp__ccd_session__start_session",
                                                      {"prompt": "Đọc STATE.md. Nhiệm vụ: bước 4 · Xong khi: khung hình đã sẵn sàng."}))

    def test_render_reads_the_masters_last_attempt(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        out = ("pass 1: measured I=-19.20 LUFS\n"
               "re-measured from out.mp4: I=-13.4 LUFS  LRA=3.0 LU  true peak=-0.6 dBFS\n"
               "lowering by 0.6 dB and encoding again\n"
               "re-measured from out.mp4: I=-14.0 LUFS  LRA=3.0 LU  true peak=-1.2 dBFS\nOK\n")
        self.assertEqual(make.master_summary(out, "")[0], "-14.0 LUFS, peak -1.2 dBFS", "the last attempt, as two numbers")
        self.assertEqual(make.master_summary("SILENT SOUNDTRACK\nOK", "Sound: sessiz film")[0], "silent by choice")
        self.assertIn("MASTER COMPRESSED", make.master_summary("pass 2: loudnorm normalization_type=dynamic\nOK", "")[0])
        src = source("make")
        self.assertNotIn("loud[2]", src)

    def test_music_choice_holds_every_delivery_and_the_picked_file(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        src = source("make")
        self.assertIn("unchosen = music_choice_line(PROJECT / film, plan, state)\n", src, "drafts, finals and variants")
        f = self.root / "pick.html"
        f.write_text("const OWN_MUSIC = { file: 'audio/music/other.mp3', gain: 0.8 };\nfunction score(ctx, out) {\n}\n",
                     encoding="utf-8")
        self.assertIn("did not pick", make.music_choice_line(f, None, "- **Music:** recording, audio/music/picked.mp3 (user)\n"))
        self.assertEqual(make.music_choice_line(f, None, "- **Music:** recording, audio/music/other.mp3 (user)\n"), "")
        g = self.root / "noop.html"
        g.write_text("const OWN_MUSIC = null;\nfunction score(ctx, out) {\n  return;\n}\n", encoding="utf-8")
        self.assertEqual(make.music_choice_line(g, None, "- **Music:** none (user)\n"), "", "a score that makes no sound is no music")

    def test_voice_time_follows_the_mix(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        make.PROJECT = self.root
        self.assertEqual(make.layer_seconds({"file": "x.wav", "loop": True}, 12.0), 12.0, "a loop runs to the plan's end")
        self.assertEqual(make.layer_seconds({"file": "x.wav", "trim": [1, 4], "length": 2}, 12.0), 2.0, "trim, then length")
        self.assertEqual(make.layer_seconds({"file": "x.wav", "trim": [1, 4]}, 12.0), 3.0)
        src = source("make")
        self.assertIn("spans = voice_spans(plan, PROJECT / film)\n", src, "a sound-only draft is measured too")

    def test_wait_follows_its_own_run(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, subprocess as sp, time
        film = self.root / "w"
        (film / "logs").mkdir(parents=True)
        (film / "tools").mkdir()
        for tool in ("make.py", "make_checks.py", "common.py"):   # a film's tools/ always carries what make.py imports
            shutil.copy(ROOT / "scripts" / tool, film / "tools" / tool)
        (film / "logs" / "last-make.txt").write_text("draft v1: draft-v1.mp4 · 30 s\n", encoding="utf-8")
        sleeper = sp.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
        (film / "logs" / "make.running").write_text(f"{sleeper.pid} draft {time.time() + 5:.3f}\n", encoding="utf-8")
        r = sp.run([sys.executable, str(film / "tools" / "make.py"), "wait", "--max", "20"], cwd=film,
                   capture_output=True, text=True, timeout=30)
        sleeper.wait()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ended without its summary", r.stdout, "a run that died never shows the earlier success as its own")

    def test_film_effects_are_recorded_by_their_licence(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        make.PROJECT = self.root
        (self.root / "LICENSES.csv").write_text("file,source\naudio/sfx/door.wav,freesound\n", encoding="utf-8")
        plan = {"layers": [{"bus": "sfx", "file": f"audio/sfx/gen{i}.wav"} for i in range(4)]
                + [{"bus": "sfx", "file": "audio/sfx/door.wav"}]}
        self.assertIn("SOUND ALL CODE", make.sound_source_line(self.root / "none.html", plan, ""), "made outnumber recorded")
        plan = {"layers": [{"bus": "sfx", "file": f"audio/sfx/gen{i}.wav"} for i in range(3)]}
        self.assertIn("no effect layer is a logged recording", make.sound_source_line(self.root / "none.html", plan, ""))

    def test_end_card_is_the_ending(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        src = source("make")
        self.assertEqual(src.count("ending_line(spans + words_before_card(dur), dur)"), 2, "render and check")
        with patch.object(make, "text_spans", lambda: [(26.0, 30.0)]):
            self.assertEqual(make.words_before_card(30.0), [], "a card held for the ending's time is the ending")
        with patch.object(make, "text_spans", lambda: [(29.0, 30.0)]):
            self.assertEqual(make.words_before_card(30.0), [(29.0, 30.0)], "a word flashed at the cut is a last line")
        with patch.object(make, "text_spans", lambda: [(29.0, 32.0)]):
            self.assertEqual(make.words_before_card(30.0), [(29.0, 32.0)], "a card past the cut is not the ending")
        self.assertIn("animatic = animatic_made(video)", src, "an animatic is held on its timing only")

    def test_refusals_are_not_a_go(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        for no in ("Không duyệt", "Đừng tiếp tục", "Không được", "Chưa ok", "Don't continue", "không"):
            self.assertFalse(guard.is_go([no]), no)
        for yes in ("Đồng ý", "Tiếp tục", "Được ★", "Ok, làm đi"):
            self.assertTrue(guard.is_go([yes]), yes)
        self.assertTrue(guard.is_go(['"Dựng ★ (đề xuất)"', '"Biển không im. Ta lắng nghe."']),
                        "a picked line of the film is not the user's decision")

    def test_the_narrator_or_a_draft_is_not_the_script_question(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        (self.film / "SCRIPT.md").write_text("# Script\n\n## Lines\n\n| # | Line |\n|---|---|\n| VO1 | Gió để cửa mở |\n"
                                            "| VO2 | Không ai trở về sau đêm đó |\n", encoding="utf-8")
        log = self.root / "s.jsonl"
        log.write_text("", encoding="utf-8")
        q = lambda s: {"questions": [{"question": s, "header": "x"}]}
        self.assertEqual(guard.script_unread(str(log), q("Giọng nào cho người dẫn?"), str(self.film)), "")
        self.assertEqual(guard.script_unread(str(log), q("Bản nháp thế nào? Chữ có đọc được không?"), str(self.film)), "")
        self.assertIn("has not read the script", guard.script_unread(str(log), q("Kịch bản ổn chưa, mình sang dựng nhé?"),
                                                                     str(self.film)), "a named script question always counts")

    def test_script_rows_are_the_words_not_the_notes(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        text = ("# Script\n\n## Lines\n\n| # | Start | Line | Words | Est. s | Over shot | What it adds |\n"
                "|---|---|---|---|---|---|---|\n| VO1 | 0:00 | Gió để cửa mở | 4 | 1.6 | cánh cửa | the absence of the father |\n\n"
                "## On-screen text\n\n| Time | Text (≤ 6 words) | On screen (s) | Placement |\n|---|---|---|---|\n"
                "| 0:05 | Không ai trở về | 2.1 | lower third left |\n")
        rows = guard.script_rows(text)
        flat = " ".join(" ".join(r) for r in rows)
        self.assertIn("gió để cửa mở", flat.lower())
        self.assertNotIn("absence of the father", flat.lower(), "the notes column is not a line to show")
        self.assertNotIn("lower third", flat.lower())
        self.assertTrue(any("không ai" in guard.plain(" ".join(r)) for r in rows))

    def test_preparation_is_the_target_films(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard, time
        shelf = self.root / "shelf"
        for name, age in (("old", 3600), ("new", 0)):
            f = shelf / name
            (f / "tools").mkdir(parents=True)
            (f / "tools" / "qc.sh").write_text("", encoding="utf-8")
            (f / "STATE.md").write_text("# State\n", encoding="utf-8")
            os.utime(f / "STATE.md", (time.time() - age, time.time() - age))
        self.assertEqual([p.name for p in guard.films_here(str(shelf))], ["new"], "the shelf's active film, not every film")
        self.assertEqual([p.name for p in guard.films_here(str(shelf), "cd old && python3 tools/direction.py board")], ["old"])
        (shelf / "old" / "history.json").write_text(json.dumps({"deals": [{"category": "look", "dealt": []}]}), encoding="utf-8")
        self.assertFalse(guard.dealt([shelf / "old"], "look"), "an empty hand is no deal")
        (shelf / "old" / "history.json").write_text(json.dumps({"deals": [{"category": "look", "dealt": ["Deakins"]}]}),
                                                    encoding="utf-8")
        os.utime(shelf / "old" / "history.json", (time.time() - 20 * 3600, time.time() - 20 * 3600))
        self.assertTrue(guard.dealt([shelf / "old"], "look"), "a hand dealt last night is still the hand")

    def test_picture_writes_and_build_markers(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        pic = r"film\.html|engine[\\/][^\\/\s'\"]+\.(?:html|mjs)"
        self.assertTrue(guard.writes_picture("""python3 -c "open('film.html','w').write(x)" """, pic))
        self.assertTrue(guard.writes_picture("""node -e "require('fs').writeFileSync('engine/world.mjs', s)" """, pic))
        self.assertFalse(guard.writes_picture("python3 -c \"print(open('film.html').read())\"", pic))
        self.assertTrue(guard.writes_picture('python3 -c "import pathlib; pathlib.Path(\\"film.html\\").write_text(s)"', pic))
        card = ("python3 - <<'PY'\np = 'STATE.md'; s = open(p).read()\ns = s.replace('<code fit', 'three.js drawn in "
                "film.html; finish: grain')\nopen(p, 'w').write(s)\nPY\nwc -l film.html")
        self.assertFalse(guard.writes_picture(card, pic), "a card written into STATE.md that names the picture")
        self.assertTrue(guard.writes_picture("python3 -c \"open('/films/My Film/film.html','w').write(s)\"", pic))
        self.assertTrue(guard.writes_picture("node -e \"require('fs').writeFileSync('C:/Films/My Film/film.html', s)\"", pic),
                        "a quoted path with a space in it")
        quick = (ROOT / "references" / "quick-mode.md").read_text(encoding="utf-8").splitlines()
        told = "\n".join(l for l in quick if l.startswith(("- **Renderer:", "**Half size, never half detail"))) + \
            (ROOT / "references" / "finish.md").read_text(encoding="utf-8")
        self.assertTrue(all(m in told for m in guard.BUILD_READ), "the commands the guard names produce its markers")

    def test_a_done_history_is_not_a_stop_line(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        self.assertEqual(guard.scoped_handoff("mcp__ccd_session__start_session",
                                              {"prompt": "STATE.md oku. Done: interview, roadmap, script. Next: step 4."}), "")
        self.assertIn("handoff", guard.scoped_handoff("mcp__ccd_session__start_session",
                                                      {"prompt": "Tiếp tục: bước 4. Done when: style frame ready."}, str(self.film)))

    def test_a_budgeted_probe_does_not_sleep_on_429(self):
        src = (ROOT / "scripts" / "asset_search.py").read_text(encoding="utf-8")
        self.assertIn("if e.code != 429 or attempt or deadline is not None:", src)
        self.assertIn("for attempt in ((0,) if deadline is not None else (0, 1)):", src)

    def test_docs_agree_on_finishing_helpers_and_looks(self):
        film = (ROOT / "references" / "film-mode.md").read_text(encoding="utf-8")
        self.assertNotIn("The look is not dealt", film)
        proto = (ROOT / "references" / "context-protocol.md").read_text(encoding="utf-8")
        self.assertNotIn("I am routing, not building", proto)
        for doc in ("SKILL.md", "references/context-protocol.md", "references/film-mode.md"):
            self.assertIn("prediction test", (ROOT / doc).read_text(encoding="utf-8"), doc)
        quick = (ROOT / "references" / "quick-mode.md").read_text(encoding="utf-8")
        self.assertIn("The three finishing passes (motion blur, print tone, gate weave) stay off unless the user", quick)

    def test_the_hooks_run_without_a_shell_and_find_a_python_or_stay_out_of_the_way(self):
        import re as _re
        head = (ROOT / "SKILL.md").read_text(encoding="utf-8").split("\n---", 1)[0]
        self.assertNotIn("shell:", head, "no shell between Claude Code and the guard, so no bash is needed on Windows")
        self.assertEqual(head.count("command: node"), 3)
        finders = _re.findall(r'^\s+- "(.+)"$', head, _re.M)
        self.assertEqual((len(finders), len(set(finders))), (3, 1))
        self.assertEqual(_re.findall(r"^\s+- (prompt|stop|tool)$", head, _re.M), ["prompt", "stop", "tool"])
        self.assertEqual(head.count("onFailure: continue"), 3, "a hook in trouble never blocks a prompt, a tool or a turn end")
        node = shutil.which("node")
        if not node:
            self.skipTest("needs node")
        kit = self.root / "kit" / "scripts"
        kit.mkdir(parents=True)
        for name in ("guard.py", "guard_words.py", "hook.cjs"):
            shutil.copy(ROOT / "scripts" / name, kit / name)
        home = self.root / "home"
        home.mkdir()
        event = json.dumps({"cwd": str(self.root), "session_id": "s", "transcript_path": "/nonexistent",
                            "tool_name": "Read", "tool_input": {"file_path": "/x/.rubydai-video/keys.env"}})
        def run(path, cache, skill_dir=str(self.root / "kit")):
            env = {"PATH": path, "HOME": str(home), "USERPROFILE": str(home), "CLAUDE_SKILL_DIR": skill_dir,
                   "RUBYDAI_VIDEO_PYTHON_CACHE": str(self.root / cache), "RUBYDAI_VIDEO_GUARD_SEEN": str(self.root / "seen"),
                   "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
            return subprocess.run([node, "-e", finders[0], "tool"], input=event, env=env, capture_output=True,
                                  text=True).returncode
        if os.name == "nt":                      # as Claude Code starts it on Windows: no bash, only node and Python
            self.assertEqual(run(os.path.dirname(sys.executable), "a.txt"), 2, "the machine's Python: the guard runs")
            self.assertEqual(run(os.path.dirname(node), "b.txt"), 0, "no Python found: the session goes on")
            return
        def wrapper(folder, name):
            folder.mkdir(exist_ok=True)
            (folder / name).write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
            os.chmod(folder / name, 0o755)
            return folder
        has3, only = wrapper(self.root / "has-python3", "python3"), wrapper(self.root / "only-python", "python")
        stub = self.root / "WindowsApps"
        stub.mkdir()
        (stub / "python3").write_text("#!/bin/sh\necho 'Python was not found'\nexit 9009\n", encoding="utf-8")
        os.chmod(stub / "python3", 0o755)
        self.assertEqual(run(f"{has3}:/bin", "1.txt"), 2, "python3 found: the guard runs")
        self.assertEqual((self.root / "1.txt").read_text(encoding="utf-8").strip(), sys.executable,
                         "the Python found is remembered, so later hooks skip the search")
        self.assertEqual(run("/nonexistent", "1.txt"), 2, "the remembered Python runs with nothing on PATH")
        self.assertEqual(run(f"{only}:/bin", "2.txt"), 2, "only python: the guard runs")
        self.assertEqual(run(f"{stub}:{only}:/bin", "3.txt"), 2, "the Store's python3 stub is passed over")
        self.assertEqual(run("/nonexistent", "4.txt"), 0, "no Python at all: the session goes on")
        (self.root / "7.txt").write_text(str(stub / "python3") + "\n", encoding="utf-8")
        self.assertEqual(run(f"{has3}:/bin", "7.txt"), 2, "a remembered Python that no longer runs is searched again")
        self.assertEqual((self.root / "7.txt").read_text(encoding="utf-8").strip(), sys.executable)
        (self.root / "8.txt").write_text(str(stub / "python3") + "\n", encoding="utf-8")
        self.assertEqual(run("/nonexistent", "8.txt"), 0, "and with no other Python, the session goes on")
        self.assertEqual(run(f"{has3}:/bin", "5.txt", skill_dir=""), 0, "no kit found: the guard stays out")
        (home / ".claude" / "skills").mkdir(parents=True)
        shutil.copytree(self.root / "kit", home / ".claude" / "skills" / "another-skill")
        self.assertEqual(run(f"{has3}:/bin", "6.txt", skill_dir=""), 0,
                         "another skill's folder is never searched: its scripts never run from this skill's hooks")
        shutil.copytree(self.root / "kit", home / ".claude" / "skills" / "rubydai-make-video-skill")
        self.assertEqual(run(f"{has3}:/bin", "9.txt", skill_dir=""), 2, "the kit's own folder name is found")

    def test_windows_powershell_commands_are_read_like_bash(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        picture = r"film\.html|engine[\\/](?:[^\s'\"]+[\\/])?[^\\/\s'\"]+\.(?:html|mjs)"
        for cmd in ("Set-Content -Path film.html -Value $html", "Copy-Item research\\film.html.bak film.html",
                    "py -3 -c \"open('film.html','w').write(s)\"", "@'\nPath('film.html').write_text(x)\n'@ | python -",
                    "[IO.File]::WriteAllText('film.html', $s)", "$s | Out-File engine\\scene.html"):
            self.assertTrue(guard.writes_picture(cmd, picture, True), cmd)
        self.assertFalse(guard.writes_picture("Get-Content film.html | Select-String score", picture, True))
        for cmd in ("Set-Content notes.md 'see film.html later'", "Set-Content -Path notes.md -Value 'engine/scene.html is it'",
                    "Add-Content STATE.md 'Copy-Item film.html'", "Set-Content notes.md 'py -c open(\"film.html\",\"w\")'"):
            self.assertFalse(guard.writes_picture(cmd, picture, True), "a note that names the picture is not a write: " + cmd)
        self.assertTrue(guard.writes_picture("Set-Content -Value $x -Path C:\\f\\film.html", picture, True))
        for cmd in ("Set-Content -Encoding utf8 film.html $html", "$html | Out-File -Encoding utf8 engine\\scene.html",
                    "New-Item -ItemType File -Force -Path film.html -Value $html", "ni engine\\scene.mjs -Value $s -Force",
                    "Copy-Item -Destination film.html -Path draft.html", "Copy-Item draft.html film.html -Force",
                    "cpi draft.html film.html", "mi draft.html engine\\scene.html", "ac film.html $more",
                    "Set-Content -Path \"D:\\Film Projeleri\\kase\\film.html\" -Value $x",
                    "if ($ok) { Set-Content -Encoding utf8 film.html $x }",
                    "(Get-Content film.html -Raw).Replace('a','b') | Set-Content -NoNewline film.html"):
            self.assertTrue(guard.writes_picture(cmd, picture, True), "PowerShell binds the path written: " + cmd)
        for cmd in ("Copy-Item film.html backup\\film-old.txt", "Copy-Item -Path film.html -Destination backup\\",
                    "New-Item -ItemType Directory -Path engine\\scenes -Force",
                    "Set-Content -Path notes.md -Value 'done; Set-Content film.html next'",
                    "Get-ChildItem engine -Filter *.html | Out-File review\\list.txt",
                    "Set-Content notes.md @'\nCopy-Item old.html film.html\n'@", "Set-Content notes.md @'\ncp draft.html film.html\n'@"):
            self.assertFalse(guard.writes_picture(cmd, picture, True), "the picture is read or named, not written: " + cmd)
        self.assertFalse(guard.writes_picture("sc film.html $x", picture), "sc is an alias in PowerShell only")
        for cmd in ("Rename-Item draft.html film.html", "Rename-Item -Path a.html -NewName engine\\scene.mjs",
                    "ren draft.html film.html", "Set-Content -Pa film.html -Value $x",
                    "Set-Content -Path @('a.html','film.html') -Value $x", "Set-Content -Path FILM.HTML -Value $x",
                    "[IO.File]::WriteAllText('FILM.HTML', $x)"):
            self.assertTrue(guard.writes_picture(cmd, picture, True), "PowerShell binds and the name's case does not matter: " + cmd)
        for cmd in ("Set-Content notes.md 'cp draft.html film.html'", "Set-Content notes.md 'tee film.html'",
                    "Set-Content -Path notes.md -Value 'Rename-Item a film.html'",
                    "Rename-Item film.html film.html.bak", "Write-Output 'see film.html' > notes.md"):
            self.assertFalse(guard.writes_picture(cmd, picture, True), "the picture is only named, not written: " + cmd)
        self.assertFalse(guard.writes_picture("echo 'cp a film.html' > notes.md", picture), "a bash note that quotes a copy")
        for cmd in ("Set-Content -LP film.html -Value $x", "[IO.File]::AppendAllText('film.html', $s)",
                    "[IO.File]::Copy('draft.html','film.html')", "[IO.File]::Copy('draft.html','film.html','true')",
                    "Invoke-WebRequest http://x -OutFile film.html", "iwr http://x -OutFile engine\\scene.mjs"):
            self.assertTrue(guard.writes_picture(cmd, picture, True), "a PowerShell 7 alias or an append/copy/download: " + cmd)
        for cmd in ("[IO.File]::Copy('film.html','backup.txt')", "[IO.File]::Copy('film.html','film.html.bak')",
                    "Set-Content notes.md 'curl.exe -o film.html http://x'",
                    "Add-Content notes.md \"[IO.File]::AppendAllText('film.html', x)\""):
            self.assertFalse(guard.writes_picture(cmd, picture, True), "a copy FROM the picture, or a note quoting a write: " + cmd)
        self.assertTrue(guard.writes_picture("curl.exe -o film.html http://x", picture), "curl -o onto the picture")
        self.assertFalse(guard.writes_picture("echo 'curl -o film.html' > notes.md", picture), "a bash note quoting a download")
        for short in ("I like Đạp Bạc", "I'll take Đạp Bạc, Hội An", "ok, Đà Nẵng then"):
            self.assertIsNone(guard.language(short), "an English line with a Vietnamese name is not Vietnamese: " + short)
        self.assertEqual(guard.whole_reference("PowerShell", {"command": "Get-Content KIT\\references\\quick-mode.md -TotalCount 5"}), "")
        self.assertEqual(guard.shown_by("py -3.12 tools\\make.py draft"), "make.py draft")
        self.assertTrue(guard.LOOKING.match("py -3.12 tools\\qc.py strip renders\\draft-v2.mp4 3 2 6"))
        self.assertEqual(guard.shown_by("py -3 tools\\make.py draft"), "make.py draft")
        self.assertEqual(guard.shown_by("Set-Location film; python .\\tools\\make.py stills --at 2"), "make.py stills")
        self.assertEqual(guard.shown_by("& python tools/make.py final"), "make.py final")
        self.assertEqual(guard.shown_by('& "C:\\Program Files\\Python312\\python.exe" "D:\\Film Projeleri\\kase\\tools\\make.py" draft'),
                         "make.py draft")
        self.assertTrue(guard.LOOKING.match(guard.unquoted('& "C:\\Program Files\\Python312\\python.exe" '
                                                           '"D:\\Film Projeleri\\kase\\tools\\qc.py" sheet "renders\\draft v2.mp4" 1 6')))
        for cmd in ("Start-Process renders\\film-v1.mp4", "Invoke-Item film.html", "ii review\\sheet.jpg",
                    "start review\\x.png", "cmd /c start film-v1.mp4", "explorer.exe renders\\film-v1.mp4"):
            self.assertTrue(guard.VIEWER.match(cmd), cmd)
        self.assertEqual(guard.key_touch("PowerShell", {"command": "Get-Content $HOME\\.rubydai-video\\keys.env"}), guard.KEYS_SAY)
        self.assertTrue(guard.whole_reference("PowerShell", {"command": "Get-Content KIT\\references\\quick-mode.md"}))
        self.assertEqual(guard.films_here(str(self.root), "Set-Location film; py -3 tools\\make.py draft"), [self.film])
        self.assertTrue(guard.is_film(self.film), "a new film: tools/qc.py")
        (self.film / "tools" / "qc.py").rename(self.film / "tools" / "qc.sh")
        self.assertTrue(guard.is_film(self.film), "a film made before: tools/qc.sh")

    def test_the_key_file_stays_out_of_reach_in_any_spelling_and_through_its_folder(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        for name, inp in (("Read", {"file_path": "~/.rubydai-video/KEYS.ENV"}),
                          ("Write", {"file_path": "~/.rubydai-video/Keys.Env", "content": "X=1"}),
                          ("PowerShell", {"command": "Get-Content ~/.rubydai-video/k`eys.env"}),
                          ("Bash", {"command": "cat ~/.rubydai-video/k''eys.env"}),
                          ("Bash", {"command": "grep -rn PIXABAY ~/.rubydai-video"}),
                          ("Bash", {"command": "cat ~/.rubydai-video/*.env"}),
                          ("PowerShell", {"command": "Select-String -Path $HOME/.rubydai-video/* -Pattern KEY"}),
                          ("PowerShell", {"command": "Get-ChildItem ~/.rubydai-video | Get-Content"}),
                          ("PowerShell", {"command": "Get-ChildItem ~/.rubydai-video | Select-String KEY"}),
                          ("Bash", {"command": "find ~/.rubydai-video -name '*.env' | xargs cat"}),
                          ("Grep", {"pattern": "PIXABAY", "path": "~/.rubydai-video"}),
                          ("PowerShell", {"command": "Get-Content ~/.rubydai-video/./*"}),            # the folder through ./
                          ("Bash", {"command": "cat ~/.rubydai-video/formats/../keys.env"}),         # and through ../
                          ("PowerShell", {"command": "Get-ChildItem ~/.rubydai-video | & Get-Content"}),  # a call operator
                          ("PowerShell", {"command": "gci ~/.rubydai-video | Import-Csv"}),
                          ("Bash", {"command": "cat ~/.rubydai-video/$(printf keys).env"}),           # built by a substitution
                          ("Bash", {"command": "python3 -c \"import keys; print(keys.get('GEMINI_API_KEY'))\""}),  # printed
                          ("Bash", {"command": "grep -r API_KEY ~"}),                            # the whole home searched
                          ("Grep", {"pattern": "KEY", "path": "~", "glob": "*.env"}),
                          ("PowerShell", {"command": "Get-Content $env:RUBYDAI_VIDEO_KEYS"}),          # the store by its var
                          ("PowerShell", {"command": "Get-Content ${env:RUBYDAI_VIDEO_KEYS}"}),        # and its brace form
                          ("Bash", {"command": "cd ~/.rubydai-video; cat *.env"}),                     # a read after a cd in
                          ("Bash", {"command": "cd ~/.rubydai-video && cat k*"}),
                          ("Bash", {"command": "python3 -c \"from tools.keys import get; print(get('X'))\""}),
                          ("Bash", {"command": "python3 -c \"import tools.keys as k\""}),               # module-qualified
                          ("Bash", {"command": "grep -r API_KEY ~ --include='*.env'"}),                 # home, then an option
                          ("Bash", {"command": "rg KEY ~ -g '*.env'"}),
                          ("Bash", {"command": "ls ~/.rubydai-video | /usr/bin/xargs cat"}),                 # a reader behind a path
                          ("Bash", {"command": "ls ~/.rubydai-video | sudo xargs cat"}),                     # and behind a wrapper
                          ("Bash", {"command": "cd ~/.rubydai-video; head *.env"}),                          # a content read after cd
                          ("Bash", {"command": "cd ~/.rubydai-video && grep -r KEY ."})):
            self.assertEqual(guard.key_touch(name, inp), guard.KEYS_SAY, inp)
        for name, inp in (("Bash", {"command": "ls -la ~/.rubydai-video"}),
                          ("PowerShell", {"command": "Get-ChildItem $HOME/.rubydai-video"}),
                          ("Bash", {"command": "node -v; df -h . | tail -1; ls ~/.rubydai-video 2>/dev/null; python3 -V"}),
                          ("Bash", {"command": "du -sh ~/.rubydai-video/* 2>/dev/null | sort -h | tail -4"}),
                          ("Bash", {"command": "for p in ~/.rubydai-video/*/bin/python3; do [ -x \"$p\" ] && echo $p; done"}),
                          ("Bash", {"command": "cat ~/.rubydai-video/formats/bilim/source.md"}),
                          ("Grep", {"pattern": "Format", "path": "~/.rubydai-video/formats"}),
                          ("Bash", {"command": "python3 tools/keys.py list"}),
                          ("Bash", {"command": "df -h ~ | cat; du -sh ~/clips/x/* | sort"}),  # a home path, not the target
                          ("Bash", {"command": "cd ~/clips/x/logs; grep -P '^a' review.txt | awk '{print}'"}),
                          ("Bash", {"command": "grep -rn TODO ~/clips/x"}),           # a subfolder, not the whole home
                          ("Grep", {"pattern": "x", "path": "~/clips"}),
                          ("Bash", {"command": "grep -c '~' film.html"}),             # ~ is the pattern, not the target
                          ("Bash", {"command": "ls ~/.rubydai-video | grep type"}),        # grep filters names, reads nothing
                          ("Bash", {"command": "cd ~/.rubydai-video; ls"}),                # a cd then a listing
                          ("Bash", {"command": "grep -n '^## ' ~/.claude/skills/rubydai-make-video-skill/references/steering.md"}),  # a file under home
                          ("Bash", {"command": "grep -o pkg ~/.claude/skills/rubydai-make-video-skill/references/type-library.json"}),
                          ("Bash", {"command": "cd ~/.rubydai-video; ls; cd ~/clips/x; cat STATE.md"}),      # cd back out, then read
                          ("Bash", {"command": "cd ~/.rubydai-video; pwd"})):              # not a read of a file there
            self.assertEqual(guard.key_touch(name, inp), "", "names only, or another file: " + str(inp))
        code, _ = self.guard("tool", {"tool_name": "PowerShell", "cwd": str(self.film),
                                      "tool_input": {"command": "Get-Content $HOME\\.rubydai-video\\KEYS.ENV"}})
        self.assertEqual(code, 2, "Windows opens KEYS.ENV as keys.env")

    def test_windows_console_code_page_never_crashes_a_tool(self):
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "predict", "--task", "Một con mèo trong mưa ★ → ≥"],
                           cwd=self.film, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertNotIn("UnicodeEncodeError", r.stderr)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        missing = [p.name for p in (ROOT / "scripts").glob("*.py")
                   if 'if __name__ == "__main__":' in p.read_text(encoding="utf-8")
                   and "legacy code page" not in p.read_text(encoding="utf-8")]
        self.assertEqual(missing, [], "every tool speaks UTF-8")
        self.assertNotIn('["python3", TOOLS', source("make"),
                         "make.py runs its own tools with the Python it runs on")

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_windows_tools_restart_in_utf8_mode(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "predict", "--task", "Đường mưa ★ →"],
                           cwd=self.film, env=env, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace")[-500:])
        self.assertIn("Đường mưa ★ →", r.stdout.decode("utf-8"), "the words come out as they went in")

    def test_a_session_whose_guard_never_ran_is_told(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import init_film, time as _t
        seen = self.root / "guard-seen"
        env = dict(self.env, RUBYDAI_VIDEO_GUARD_SEEN=str(seen))
        hook = lambda cwd: subprocess.run([sys.executable, GUARD, "prompt"], input=json.dumps(
            {"cwd": str(cwd), "session_id": "s", "prompt": "merhaba"}), env=env, capture_output=True, text=True)
        here = os.getcwd()
        os.chdir(self.film)
        try:
            with patch.dict(os.environ, {"CLAUDECODE": "1", "RUBYDAI_VIDEO_GUARD_SEEN": str(seen)}):
                self.assertIn("GUARD OFF", init_film.guard_off())
                hook(self.root.parent / "another-session-folder")
                self.assertIn("GUARD OFF", init_film.guard_off(), "another folder's session is not this one")
                hook(self.root)
                self.assertTrue(seen.is_dir(), "the guard leaves its trace")
                self.assertEqual(init_film.guard_off(), "", "the session's folder holds the film")
                for f in seen.iterdir():
                    os.utime(f, (_t.time() - 3600, _t.time() - 3600))
                self.assertIn("GUARD OFF", init_film.guard_off())
            with patch.dict(os.environ, {"RUBYDAI_VIDEO_GUARD_SEEN": str(seen)}):
                os.environ.pop("CLAUDECODE", None)
                self.assertEqual(init_film.guard_off(), "", "outside Claude Code no hooks are expected")
        finally:
            os.chdir(here)

    def test_a_films_own_brief_finds_its_kit_on_any_path(self):
        film = self.root / "shelf" / "kit-path"
        ran([sys.executable, str(ROOT / "scripts" / "init_film.py"), str(film), "--quick"], capture_output=True)
        r = subprocess.run([sys.executable, str(film / "tools" / "brief.py"), "predict", "--task", "Một con mèo"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertIn(f"PROJECT: {film}", r.stdout, "a helper started from anywhere knows its film")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "predict", "--task", "Một con mèo"],
                           cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertIn("film's folder", r.stderr, "the prediction test waits for the film's folder")
        spaced = self.root / "My Kit"
        shutil.copytree(ROOT / "references", spaced / "references")
        shutil.copytree(ROOT / "templates", spaced / "templates")
        (film / "AGENTS.md").write_text(f"Read `{spaced}{os.sep}SKILL.md` once.\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(film / "tools" / "brief.py"), "predict", "--task", "Một con mèo"],
                           capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, RUBYDAI_VIDEO_KIT=""))
        self.assertEqual(r.returncode, 0, "a kit path with spaces: " + r.stderr[-400:])
        (film / "AGENTS.md").write_text("no kit here\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(film / "tools" / "brief.py"), "predict", "--task", "x"],
                           capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, RUBYDAI_VIDEO_KIT=""))
        self.assertIn("the kit is not found", r.stdout + r.stderr, "a clear setup message, never a stack trace")

    def test_an_animatic_is_the_file_animatic_py_made(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, hashlib
        renders = self.root / "renders"
        renders.mkdir()
        (renders / "animatic-v1.mp4").write_bytes(b"made by animatic.py")
        (renders / ".animatics.json").write_text(json.dumps(
            {"animatic-v1.mp4": hashlib.sha1(b"made by animatic.py").hexdigest()}), encoding="utf-8")
        self.assertTrue(make.animatic_made(renders / "animatic-v1.mp4"))
        shutil.copy(renders / "animatic-v1.mp4", renders / "draft-animatic-v1.mp4")
        self.assertFalse(make.animatic_made(renders / "draft-animatic-v1.mp4"), "a name is not a phase")
        (renders / "animatic-v1.mp4").write_bytes(b"a production cut renamed")
        self.assertFalse(make.animatic_made(renders / "animatic-v1.mp4"), "other bytes under the name")
        src = (ROOT / "scripts" / "animatic.py").read_text(encoding="utf-8")
        self.assertIn(".animatics.json", src)

    def test_the_picked_music_is_matched_by_its_path(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        pick = "- **Music:** recording, audio/picked.mp3 (user)\n"
        hold = lambda files: make.music_choice_line(None, {"layers": [{"bus": "music", "file": f} for f in files]}, pick)
        self.assertIn("did not pick", hold(["audio/not-picked.mp3"]), "a suffix is another file")
        self.assertIn("did not pick", hold(["audio/b/picked.mp3"]), "the same name in another folder")
        self.assertIn("did not pick", hold(["audio/picked.mp3", "audio/extra.mp3"]), "an unpicked track beside it")
        self.assertEqual(hold(["audio/picked.mp3"]), "")
        self.assertEqual(hold(["./audio/picked.mp3"]), "")

    def test_loop_then_trim_is_one_trimmed_stretch(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, wave
        with wave.open(str(self.root / "one.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"\0\0" * 8000)
        make.PROJECT = self.root
        self.assertAlmostEqual(make.layer_seconds({"file": "one.wav", "loop": True, "trim": [0, 1], "length": 3}, 12), 1.0,
                               places=1, msg="mix.py loops, then trims: one second")
        self.assertAlmostEqual(make.layer_seconds({"file": "one.wav", "loop": True, "length": 3}, 12), 3.0, places=1)
        self.assertAlmostEqual(make.layer_seconds({"file": "one.wav", "trim": [0, 5]}, 12), 1.0, places=1,
                               msg="without a loop the file ends first")

    def test_a_licence_row_certifies_its_own_file_only(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        make.PROJECT = self.root
        (self.root / "LICENSES.csv").write_text(
            "file,title,notes\nassets/recorded-hit.wav,hit,\nassets/recorded-tap.wav,tap,\n"
            "assets/other.wav,other,hit.wav tap.wav clink.wav\n", encoding="utf-8")
        plan = {"layers": [{"bus": "sfx", "file": f"audio/{n}.wav"} for n in ("hit", "tap", "clink")]}
        self.assertIn("SOUND ALL CODE", make.sound_source_line(self.root / "none.html", plan, ""),
                      "names inside other rows certify nothing")
        plan = {"layers": [{"bus": "sfx", "file": "assets/recorded-hit.wav"}]}
        self.assertEqual(make.sound_source_line(self.root / "none.html", plan, ""), "")

    def test_check_needs_ffmpeg_and_never_bash(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        with patch.object(make.shutil, "which", lambda b: None if b == "bash" else "/x/" + b):
            self.assertEqual(make.missing_tools(), [], "no bash anywhere is fine")
        with patch.object(make.shutil, "which", lambda b: None):
            self.assertEqual(make.missing_tools(), ["ffmpeg", "ffprobe"])
        code = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "scripts").glob("*.py"))
        self.assertNotRegex(code, r"[\[(,]\s*[\"']bash[\"']\s*[,\])]", "no tool starts bash")
        self.assertFalse((ROOT / "scripts" / "qc.sh").exists())
        self.assertIn('encoding="utf-8", errors="replace"', source("make"))

    def test_guard_holds_that_were_still_open(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard, time as _t
        log = self.root / "q.jsonl"
        row = lambda kind, **kw: json.dumps({"type": "assistant" if kind == "tool_use" else "user",
                                             "message": {"content": [dict({"type": kind}, **kw)]}})
        ask = row("tool_use", id="q", name="AskUserQuestion", input={"questions": [{"question": "Kế hoạch này được không?"}]})
        ok = row("tool_result", tool_use_id="q", content='"Kế hoạch này được không?"="Được ★"')
        nxt = row("tool_use", id="n", name="AskUserQuestion", input={"questions": [{"question": "Kịch bản?"}]})
        log.write_text("\n".join([ask, ok, nxt, row("tool_result", tool_use_id="n", is_error=True, content="FAILED")]) + "\n",
                       encoding="utf-8")
        self.assertTrue(guard.approved_and_idle(str(log)), "a next question that failed did not move the film on")
        log.write_text("\n".join([ask, ok, nxt]) + "\n", encoding="utf-8")
        self.assertFalse(guard.approved_and_idle(str(log)), "a next question on its way moves it on")
        self.assertEqual(guard.scoped_handoff("mcp__ccd_session__start_session", {
            "cwd": str(self.root / "elsewhere"), "prompt": "Review the CSV parser. Done when: the error cases are listed."},
            str(self.film)), "", "a task elsewhere is not this film's handoff")
        shelf = self.root / "shelf"
        for name, title in (("quick", "Cửa Xanh"), ("other", "Phim Khác")):
            f = shelf / name
            (f / "tools").mkdir(parents=True)
            (f / "tools" / "qc.sh").write_text("", encoding="utf-8")
            (f / "STATE.md").write_text(f"# State: {title} (Quick mode)\n", encoding="utf-8")
        os.utime(shelf / "quick" / "STATE.md", (_t.time() - 3600, _t.time() - 3600))
        self.assertEqual([f.name for f in guard.films_here(str(shelf), "", "ý tưởng cho Cửa Xanh")], ["quick"],
                         "the film the user names, not the newest")
        self.assertEqual([f.name for f in guard.films_here(str(shelf), "", "bir film")], ["other"])
        (shelf / "quick" / "STATE.md").write_text("# State: Cửa Xanh (Quick mode)\n- **Look named:** Wes Anderson\n",
                                                  encoding="utf-8")
        board = {"cwd": str(shelf / "quick"), "transcript_path": str(log),
                 "tool_input": {"command": "python3 tools/direction.py board --row 1|a||research/look-1"}}
        self.assertEqual(guard.board_unprepared(board, "Bash", board["tool_input"]), "", "a named look has its own route")

    def test_the_cold_read_is_this_scripts_and_comes_before_it_is_shown(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard, time as _t
        (self.film / "STATE.md").write_text("# State: Test (Film mode)\n", encoding="utf-8")
        (self.film / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (self.film / "SCRIPT.md").write_text("# Script\n\n## Lines\n\n| # | Line |\n|---|---|\n| VO1 | Gió để cửa mở |\n",
                                             encoding="utf-8")
        log = self.root / "c.jsonl"
        log.write_text(json.dumps({"timestamp": "2099-01-01T00:00:00Z", "type": "user", "message": {"content": "x"}}) + "\n",
                       encoding="utf-8")
        ev = {"cwd": str(self.film), "transcript_path": str(log)}
        ask = {"questions": [{"question": "Kịch bản ổn chưa?"}]}
        if not guard.film_mode(self.film):
            self.skipTest("this fixture is not read as Film mode")
        cold = self.film / "review" / "script-cold.md"
        cold.write_text("Verdict: OK\n" + "x" * 300, encoding="utf-8")
        old = _t.time() - 86400
        os.utime(cold, (old, old))
        self.assertIn("cold read", guard.cold_read_missing(ev, ask), "yesterday's report, today's script")
        cold.write_text("Verdict: FIX\n" + "x" * 300, encoding="utf-8")
        self.assertIn("cold read", guard.cold_read_missing(ev, ask), "a FIX with no change since")
        cold.write_text("Verdict: OK\n" + "x" * 300, encoding="utf-8")
        self.assertEqual(guard.cold_read_missing(ev, ask), "")
        cold.unlink()
        self.assertIn("cold read", guard.cold_read_missing(ev, {}, shown=True, films=[self.film]),
                      "sending SCRIPT.md is showing it")

    def test_the_card_names_finishing_and_motion_before_the_first_picture(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        (self.film / "film.html").write_text("<html>", encoding="utf-8")
        (self.film / "STATE.md").write_text("# State\n", encoding="utf-8")
        self.assertIn("is missing", guard.card_unwritten(self.film), "no card at all")
        (self.film / "STATE.md").write_text("# State\nDirector card: frontal frames and pastel light\n", encoding="utf-8")
        self.assertIn("does not name", guard.card_unwritten(self.film), "a card without bold or a list is still read")
        (self.film / "STATE.md").write_text("# State\n- **Director card:** <code fit (how each thing is seen) · ...>\n",
                                            encoding="utf-8")
        self.assertIn("still the template", guard.card_unwritten(self.film))
        (self.film / "STATE.md").write_text("# State\n- **Director card:** frontal frames · pastel · whip pans\n",
                                            encoding="utf-8")
        self.assertIn("does not name", guard.card_unwritten(self.film))
        (self.film / "STATE.md").write_text("# State\n- **Director card:** frontal frames · motion design: none, the "
                                            "picture carries it · finish: grain and halation on the night scenes\n",
                                            encoding="utf-8")
        self.assertEqual(guard.card_unwritten(self.film), "")
        (self.film / "renders").mkdir(exist_ok=True)
        (self.film / "STATE.md").write_text("# State\n- **Director card:** an older film's card\n", encoding="utf-8")
        (self.film / "renders" / "draft-v1.mp4").write_bytes(b"x")
        self.assertEqual(guard.card_unwritten(self.film), "", "a film past its first render is never stopped by this")

    def test_a_user_who_stops_is_never_pushed_and_steps_are_not_the_script(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        log = self.root / "u.jsonl"
        row = lambda kind, **kw: json.dumps({"type": "assistant" if kind == "tool_use" else "user",
                                             "message": {"content": [dict({"type": kind}, **kw)]}})
        ask = row("tool_use", id="q", name="AskUserQuestion", input={"questions": [{"question": "Ổn chưa?"}]})
        ok = row("tool_result", tool_use_id="q", content='"Ổn chưa?"="Được ★"')
        nxt = row("tool_use", id="n", name="AskUserQuestion", input={"questions": [{"question": "Format?"}]})
        no = row("tool_result", tool_use_id="n", is_error=True,
                 content="The user doesn't want to proceed with this tool use. The tool use was rejected")
        log.write_text("\n".join([ask, ok, nxt, no]) + "\n", encoding="utf-8")
        self.assertFalse(guard.approved_and_idle(str(log)), "the user turned it down")
        cut = json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "[Request interrupted by user]"}]}})
        log.write_text("\n".join([ask, ok, cut]) + "\n", encoding="utf-8")
        self.assertFalse(guard.approved_and_idle(str(log)), "the user stopped the turn")
        (self.film / "SCRIPT.md").write_text("# Script\n\n## Lines\n\n| # | Line |\n|---|---|\n| VO1 | Gió để cửa mở |\n"
                                            "| VO2 | Không ai trở về sau đêm đó |\n", encoding="utf-8")
        log.write_text("", encoding="utf-8")
        q = lambda s: {"questions": [{"question": s, "header": "x"}]}
        for s in ("Lộ trình ổn chưa, mình chuyển sang kịch bản nhé?", "Kịch bản màu ổn chưa?",
                  "Kết thúc phần lời dẫn thế nào?", "Thêm phụ đề dưới lời dẫn nhé?",
                  "Bắt đầu bước kịch bản ở chat mới nhé?", "Roadmap đã duyệt thì sang bước kịch bản và danh sách cảnh nhé?"):
            self.assertEqual(guard.script_unread(str(log), q(s), str(self.film)), "", s)
        for s in ("Kịch bản ổn chưa, mình sang style frame nhé?", "Bạn duyệt lời thoại của hồi mở đầu chứ?", "Can we lock the script now?"):
            self.assertIn("has not read the script", guard.script_unread(str(log), q(s), str(self.film)), s)

    def test_a_locked_script_is_reopened_only_by_name(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        script = "# Script\nStatus: LOCKED on 2026-10-29 · Version: 3\n\n## Lines\n\n| # | Line |\n|---|---|\n| VO1 | Gió để cửa mở |\n"
        (self.film / "SCRIPT.md").write_text(script, encoding="utf-8")
        log = self.root / "l.jsonl"
        log.write_text("", encoding="utf-8")
        q = lambda s: {"questions": [{"question": s, "header": "x"}]}
        self.assertEqual(guard.script_unread(str(log), q("Chữ trên màn hình đủ lớn chưa?"), str(self.film)), "",
                         "a locked script is not reopened by a question about the text on screen")
        self.assertIn("has not read the script", guard.script_unread(str(log), q("Mở lại kịch bản nhé?"), str(self.film)))
        self.assertFalse(guard.script_question(q("Bản nháp thế nào? Chữ có đọc được không?")), "the cold read uses the same test")

    def test_revision_helpers_carry_the_build_rules_and_nested_engine_files_count(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "brief.py"), "revision", "--task", "x", "--writes",
                              "engine/x.mjs", "--reads", "STATE.md", "--done", "ok"], capture_output=True, text=True).stdout
        self.assertTrue(all(m in out for m in (guard.BUILD_READ[0], guard.BUILD_READ[2], guard.BUILD_READ[3])))
        pic = r"film\.html|engine[\\/](?:[^\s'\"]+[\\/])?[^\\/\s'\"]+\.(?:html|mjs)"
        self.assertIn(pic, source("guard"))
        self.assertTrue(re.search(r"(?:" + pic + r")$", "/f/engine/kinds/glass.mjs"))

    def test_a_recording_is_never_dropped_and_a_named_file_needs_one(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        f = self.root / "film.html"
        f.write_text("const OWN_MUSIC = null;\nfunction score(ctx, out) {\n  pad(ctx, out, 'A2');\n}\n", encoding="utf-8")
        self.assertIn("picks a recording", make.music_choice_line(f, None, "- **Music:** audio/music/picked.mp3 (user)\n"))
        (self.root / "audio").mkdir()
        (self.root / "audio" / "mix.json").write_text(json.dumps({"duration": 10, "layers": [
            {"bus": "music", "file": "audio/music/song.mp3"}]}), encoding="utf-8")
        with patch.object(make, "PROJECT", self.root), patch.object(make, "LOGS", self.root / "logs"), \
                self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as out:
            make.sound_plan("film.html")
        self.assertIn("would be dropped", out.getvalue())

    def test_an_animatic_voice_mix_needs_no_event_audit(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import mix
        (self.film / "engine").mkdir()
        (self.film / "audio").mkdir()
        plan = self.film / "audio" / "temp-vo.json"
        plan.write_text(json.dumps({"duration": 10, "layers": [{"bus": "dialogue", "file": "audio/vo-t/VO1.wav", "at": 1}]}),
                        encoding="utf-8")
        self.assertEqual(mix.audit_missing(str(plan)), "")
        plan.write_text(json.dumps({"duration": 10, "layers": [{"bus": "sfx", "file": "a.wav"}]}), encoding="utf-8")
        self.assertIn("picture-event audit", mix.audit_missing(str(plan)))

    def test_helpers_at_work_and_picked_lines_are_not_idle_or_refusals(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        log = self.root / "h.jsonl"
        row = lambda kind, **kw: json.dumps({"type": "assistant" if kind == "tool_use" else "user",
                                             "message": {"content": [dict({"type": kind}, **kw)]}})
        ask = row("tool_use", id="q", name="AskUserQuestion", input={"questions": [{"question": "Phong cách?"}]})
        ok = row("tool_result", tool_use_id="q", content='"Phong cách?"="Vòng 2 ★"')
        send = row("tool_use", id="s", name="SendMessage", input={"to": "a1", "message": "round 2"})
        sent = row("tool_result", tool_use_id="s", content='{"success":true}')
        log.write_text("\n".join([ask, ok, send, sent]) + "\n", encoding="utf-8")
        self.assertFalse(guard.approved_and_idle(str(log)), "resuming a helper moves the film on")
        bg = row("tool_use", id="a", name="Agent", input={"prompt": "research"})
        bgr = row("tool_result", tool_use_id="a", content="Async agent launched successfully.")
        log.write_text("\n".join([bg, bgr, ask, ok]) + "\n", encoding="utf-8")
        self.assertFalse(guard.approved_and_idle(str(log)), "a helper still at work: the turn waits for it")
        done = json.dumps({"type": "user", "message": {"content": "<task-notification>\n<tool-use-id>a</tool-use-id>\n</task-notification>"}})
        log.write_text("\n".join([bg, bgr, done, ask, ok]) + "\n", encoding="utf-8")
        self.assertTrue(guard.approved_and_idle(str(log)), "a finished helper is not a reason to stop")
        self.assertTrue(guard.is_go(['"Biển không im ★ (đề xuất)"']), "a picked line is not a refusal")
        self.assertFalse(guard.is_go(['"Được ★"', '"Đừng tiếp tục"']), "a refusal beside a go")
        self.assertFalse(guard.is_go(['"Được ★"', '"đổi màu xanh"']), "a note beside a go")

    def test_a_film_already_here_is_not_an_ideas_offer(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        self.assertFalse(guard.offers_ideas({"questions": [{"question": "Ở đây đã có một phim mở với cùng ý tưởng: "
                                                                        "tiem-cu. Làm gì tiếp?", "header": "Phim đã có"}]}))
        self.assertTrue(guard.offers_ideas({"questions": [{"question": "Mình tiếp cận ý tưởng theo góc nhìn nào?", "header": "Ý tưởng"}]}))
        for name, text in (("make", source("make")), ("init_film.py", (ROOT / "scripts" / "init_film.py").read_text(encoding="utf-8"))):
            self.assertIn("STARTED - 1800", text, name)

    def test_windows_paths_browsers_and_frames(self):
        make = source("make")
        self.assertNotIn('"-pattern_type", "glob"', make, "ffmpeg on Windows has no glob input")
        for name in ("styles.py", "direction.py"):
            src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotIn('"file://" + src', src, name)
            self.assertIn("as_uri()", src, name)
        sys.path.insert(0, str(ROOT / "scripts"))
        import styles
        with patch.dict(os.environ, {"PROGRAMFILES": str(self.root)}):
            exe = self.root / "Google" / "Chrome" / "Application" / "chrome.exe"
            exe.parent.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")
            with patch.object(styles.os.path, "exists", lambda c: str(c) == str(exe)):
                self.assertEqual(styles.chrome(), str(exe))
        cap = (ROOT / "scripts" / "capture.mjs").read_text(encoding="utf-8")
        self.assertIn("LOCALAPPDATA", cap)
        self.assertIn("C:\\\\Program Files\\\\Microsoft\\\\Edge\\\\Application\\\\msedge.exe", cap)
        self.assertIn('["uv", "run", "--no-sync", "python"', (ROOT / "scripts" / "tts.py").read_text(encoding="utf-8"),
                      "the local Japanese voice runs through uv, the same on Windows")

    def test_the_picked_music_is_in_the_film_by_its_own_path(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        f = self.root / "film.html"
        f.write_text("const OWN_MUSIC = null;\nfunction score(ctx) {\n  return;\n}\n", encoding="utf-8")
        self.assertIn("does not play it", make.music_choice_line(f, None, "**Music:** audio/picked.mp3 (user)"),
                      "a picked recording missing from the film")
        self.assertEqual(make.music_choice_line(None, {"layers": [{"bus": "music", "file": "audio/my song.mp3"}]},
                                                "**Music:** audio/my song.mp3 (user)"), "", "a name with a space")
        with patch.object(make, "PROJECT", self.root):
            self.assertEqual(make.music_choice_line(None, {"layers": [{"bus": "music", "file": "audio/a.mp3"}]},
                                                    f"**Music:** {self.root / 'audio' / 'a.mp3'} (user)"), "",
                             "the same file, written whole")
        (self.root / "audio").mkdir()
        (self.root / "audio" / "mix.json").write_text(json.dumps({"duration": 12, "layers": [
            {"file": "assets/score.wav", "bus": "music"}]}), encoding="utf-8")
        with patch.object(make, "PROJECT", self.root), patch.object(make, "LOGS", self.root / "logs"), \
                self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as out:
            make.sound_plan("film.html")
        self.assertIn("would be dropped", out.getvalue(), "the page's sound is audio/score.wav, not any score.wav")

    def test_refusals_end_the_obligation_whatever_was_turned_down(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        log = self.root / "r.jsonl"
        row = lambda kind, **kw: json.dumps({"type": "assistant" if kind == "tool_use" else "user",
                                             "message": {"content": [dict({"type": kind}, **kw)]}})
        ask = row("tool_use", id="q", name="AskUserQuestion", input={"questions": [{"question": "Roadmap?"}]})
        ok = row("tool_result", tool_use_id="q", content='"Roadmap?"="Approve"')
        for name in ("Bash", "Agent", "SendMessage"):
            nxt = row("tool_use", id="n", name=name, input={"command": "python3 tools/make.py stills", "prompt": "x"})
            no = row("tool_result", tool_use_id="n", is_error=True,
                     content="The user doesn't want to proceed with this tool use. The tool use was rejected")
            log.write_text("\n".join([ask, ok, nxt, no]) + "\n", encoding="utf-8")
            self.assertFalse(guard.approved_and_idle(str(log)), name)
        self.assertTrue(guard.is_go(['"No one knows ★ (recommended)"']), "a picked line's own words")
        self.assertFalse(guard.is_go(['"Tôi sẽ gom file trước ★"']), "the user's own plan first")
        self.assertFalse(guard.offers_ideas({"questions": [{"question": "There is an existing film here with this idea. "
                                                                        "Continue it?", "header": "Idea"}]}))

    def test_the_cold_read_is_bound_to_the_words(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        (self.film / "engine").mkdir(exist_ok=True)
        (self.film / "SCRIPT.md").write_text("# Script\n\n## Lines\n\n| # | Line |\n|---|---|\n| VO1 | Gió để cửa mở |\n",
                                             encoding="utf-8")
        log = self.root / "c.jsonl"
        log.write_text(json.dumps({"timestamp": "2099-01-01T00:00:00Z", "type": "user", "message": {"content": "x"}}) + "\n",
                       encoding="utf-8")
        ev, ask = {"cwd": str(self.film), "transcript_path": str(log)}, {"questions": [{"question": "Kịch bản ổn chưa?"}]}
        cold = self.film / "review" / "script-cold.md"
        cold.write_text("Verdict: OK\n" + "x" * 300, encoding="utf-8")
        guard.note_script(self.film, "cold")
        self.assertEqual(guard.cold_read_missing(ev, ask), "")
        (self.film / "SCRIPT.md").write_text((self.film / "SCRIPT.md").read_text(encoding="utf-8") + "| VO2 | Dòng mới |\n",
                                             encoding="utf-8")
        self.assertIn("cold read", guard.cold_read_missing(ev, ask), "words changed after an OK read, before any showing")
        cold.write_text("Verdict: FIX\n- the letter's sender is unclear\n" + "x" * 300, encoding="utf-8")
        guard.note_script(self.film, "cold")
        os.utime(self.film / "SCRIPT.md", (time.time() + 60, time.time() + 60))
        self.assertIn("cold read", guard.cold_read_missing(ev, ask), "a FIX is not answered by a file time")
        (self.film / "SCRIPT.md").write_text((self.film / "SCRIPT.md").read_text(encoding="utf-8") + "| VO3 | Lá thư do mẹ viết |\n",
                                             encoding="utf-8")
        self.assertEqual(guard.cold_read_missing(ev, ask), "", "the words changed after the FIX")
        cold.write_text("Verdict: OK\n" + "x" * 300, encoding="utf-8")
        guard.note_script(self.film, "cold")
        guard.note_script(self.film, "shown")
        (self.film / "SCRIPT.md").write_text((self.film / "SCRIPT.md").read_text(encoding="utf-8") + "| VO4 | Notla gelen |\n",
                                             encoding="utf-8")
        self.assertEqual(guard.cold_read_missing(ev, ask), "", "after the user has read it, their notes need no new cold read")

    def test_the_named_film_and_a_resumed_hand(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        shelf = self.root / "shelf"
        for name in ("quick", "other"):
            f = shelf / name
            (f / "tools").mkdir(parents=True)
            (f / "tools" / "qc.sh").write_text("", encoding="utf-8")
            (f / "STATE.md").write_text(f"# State: {name} (Quick mode)\n", encoding="utf-8")
        os.utime(shelf / "quick" / "STATE.md", (time.time() - 3600, time.time() - 3600))
        self.assertEqual([f.name for f in guard.films_here(str(shelf), "", "Which idea for quick?\nContinue quick, not other.")],
                         ["quick"])
        f = shelf / "quick"
        (f / "history.json").write_text(json.dumps({"deals": [{"category": "spark", "dealt": ["s1", "s2", "s3"], "pick": None,
                                                               "at": "2020-01-01T10:00"}]}), encoding="utf-8")
        self.assertTrue(guard.dealt([f], "spark", time.time()), "a hand still open is this round's hand")
        (f / "history.json").write_text(json.dumps({"deals": [{"category": "spark", "dealt": ["s1"], "pick": "s1",
                                                               "at": "2020-01-01T10:00"}]}), encoding="utf-8")
        self.assertFalse(guard.dealt([f], "spark", time.time()), "a closed hand from another day is not")

    def test_a_viewer_report_counts_when_it_is_finished(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, types
        renders, review = self.root / "renders", self.root / "review"
        renders.mkdir()
        review.mkdir()
        (renders / "draft-v1.mp4").write_bytes(b"x")
        report = review / "critique-v1.md"
        with patch.object(make, "RENDERS", renders), patch.object(make, "REVIEW", review), \
                patch.object(make, "LOGS", self.root / "logs"), patch.dict(os.environ, {"RUBYDAI_VIDEO_VIEWER_WAIT": "0"}):
            for text, want in (("", "no Verdict line"), ("# Review\nWorking...\n", "no Verdict line"),
                               ("Verdict: FIX\nRed items: none\n", "says FIX")):
                report.write_text(text, encoding="utf-8")
                with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as out:
                    make.viewer_report(types.SimpleNamespace(force=False))
                self.assertIn(want, out.getvalue(), text)
            report.write_text("Verdict: APPROVE\n", encoding="utf-8")
            self.assertIn("no red items", make.viewer_report(types.SimpleNamespace(force=False)))

    def test_runs_and_animatics_by_their_own_record(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, hashlib
        logs = self.root / "logs"
        logs.mkdir()
        (logs / f"run-{os.getpid()}.txt").write_text("OLD PID SUCCESS\n", encoding="utf-8")
        with patch.object(make, "LOGS", logs), patch("atexit.register"):
            make.mark_running("draft")
        self.assertFalse((logs / f"run-{os.getpid()}.txt").exists(), "a run starts without an earlier process's summary")
        renders = self.root / "renders"
        renders.mkdir()
        (renders / "custom.mp4").write_bytes(b"animatic")
        (renders / ".animatics.json").write_text(json.dumps({"custom.mp4": hashlib.sha1(b"animatic").hexdigest()}),
                                                 encoding="utf-8")
        self.assertTrue(make.animatic_made(renders / "custom.mp4"), "any name animatic.py wrote")

    def test_own_songs_and_picked_files_keep_their_whole_names(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        f = self.root / "film.html"
        f.write_text('const OWN_MUSIC = {file: "audio/John\'s song.mp3"};\nfunction score(ctx) {\n return;\n}\n', encoding="utf-8")
        self.assertEqual(make.music_choice_line(f, None, "**Music:** `audio/John's song.mp3` (user)"), "", "an apostrophe in a name")
        self.assertEqual(make.music_choice_line(None, {"layers": [{"bus": "music", "file": "assets/film.wav"}]},
                                                "**Music:** assets/film.wav (user)"), "", "only audio/film.wav is the page's sound")
        for said, files in (("`audio/a song.mp3` and audio/b song.mp3 (user)", ["audio/a song.mp3", "audio/b song.mp3"]),
                            ("a.mp3 and b.mp3 (user)", ["a.mp3", "b.mp3"]), ("audio/Song (live).mp3 (user)", ["audio/Song (live).mp3"])):
            self.assertEqual(sorted(make.picked_files(said)), sorted(files), said)
        self.assertIn("did not pick", make.music_choice_line(None, {"layers": [{"bus": "music", "file": "audio/UNPICKED.MP3"}]},
                                                             "**Music:** audio/PICKED.MP3 (user)"), "upper-case extensions")

    def test_a_bare_refusal_picked_from_the_options_is_a_refusal(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        for no in ('"No ★"', '"Wait ★"', '"Không ★ (đề xuất)"', '"Chờ đã ★"'):
            self.assertFalse(guard.is_go([no]), no)
        for yes in ('"Yes ★"', '"Chờ đã, sang âm thanh ★"', '"No one knows ★ (recommended)"'):
            self.assertTrue(guard.is_go([yes]), yes)

    def test_a_cold_read_fingerprint_counts_once_its_report_is_written(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        review = self.film / "review"
        (self.film / "SCRIPT.md").write_text("# Script\nA\n", encoding="utf-8")
        cold = review / "script-cold.md"
        cold.write_text("Verdict: OK\n" + "x" * 300, encoding="utf-8")
        os.utime(cold, (time.time() - 600, time.time() - 600))
        guard.note_script(self.film, "cold")
        self.assertEqual(guard.noted(self.film, "cold"), "", "a write that never happened certifies nothing")
        cold.write_text("Verdict: OK\n" + "y" * 300, encoding="utf-8")
        self.assertEqual(guard.noted(self.film, "cold"), guard.script_sha(self.film), "the written report confirms it")
        ev = {"cwd": str(self.film), "transcript_path": str(self.root / "x.jsonl"), "tool_name": "Bash",
              "tool_input": {"command": "cp report-source.md review/script-cold.md"}}
        (review / ".script-cold.pending").unlink(missing_ok=True)
        subprocess.run([sys.executable, GUARD, "tool"], input=json.dumps(ev), capture_output=True, text=True, env=self.env)
        self.assertTrue((review / ".script-cold.pending").exists(), "a shell copy into the report counts as its write")

    def test_on_a_shelf_the_film_worked_in_last_and_never_one_refused(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        shelf = self.root / "shelf"
        for name, phase in (("other", "done"), ("quick", "script")):
            f = shelf / name
            (f / "tools").mkdir(parents=True)
            (f / "tools" / "qc.sh").write_text("", encoding="utf-8")
            (f / "STATE.md").write_text(f"# State: {name}\n- **Phase:** {phase}\n", encoding="utf-8")
        log = self.root / "shelf.jsonl"
        log.write_text("Read other/STATE.md\nRead quick/STATE.md\n", encoding="utf-8")
        self.assertFalse(guard.film_done(str(shelf), str(log)), "the current film is not done because another is")
        os.utime(shelf / "quick" / "STATE.md", (time.time() - 3600, time.time() - 3600))
        self.assertEqual([f.name for f in guard.films_here(str(shelf), "", "Which idea?\nNot other.")], ["quick"])

    def test_an_empty_motion_line_never_takes_the_heading_after_it(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        (self.film / "engine").mkdir(exist_ok=True)
        (self.film / "ROADMAP.md").write_text("# Roadmap\n- **Motion design:**\n\n## Shot plan\nShots follow.\n", encoding="utf-8")
        self.assertIn("no Motion design line", guard.card_unwritten(self.film))
        for doc in ("README.md", "README.en.md"):
            if (ROOT / doc).is_file():                      # the English page is optional
                self.assertNotIn("macOS on every push", (ROOT / doc).read_text(encoding="utf-8"), doc)

    def test_docs_agree_on_notes_recipes_and_named_looks(self):
        film = (ROOT / "references" / "film-mode.md").read_text(encoding="utf-8")
        self.assertNotIn("send each affected shot to its own fresh subagent", film)
        self.assertNotIn("Film mode never offers them", film)
        self.assertNotIn("every task and revision goes to a fresh subagent",
                         (ROOT / "scripts" / "init_film.py").read_text(encoding="utf-8"))
        for t in (ROOT / "templates").rglob("*.md"):         # a new film's files tell the next chat the same method
            self.assertNotIn("fresh subagent per task", t.read_text(encoding="utf-8"), t.name)
        if (ROOT / "README.en.md").is_file():               # the English page is optional
            self.assertIn("prediction test", (ROOT / "README.en.md").read_text(encoding="utf-8"))
        self.assertIn("kiểm tra dự đoán", (ROOT / "README.md").read_text(encoding="utf-8"))
        quick = (ROOT / "references" / "quick-mode.md").read_text(encoding="utf-8")
        self.assertIn("**Look named:**", quick)
        self.assertIn("(Quick mode's code score)", (ROOT / "references" / "sound.md").read_text(encoding="utf-8"))

    def test_supply_keeps_each_source_to_its_time(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import asset_search as A, io, contextlib, types, time as _t
        old = A.get, A.MAX_WAIT[0]
        def met(url, as_json=True):
            if "/search?" in url:
                return {"objectIDs": list(range(80))}
            if _t.time() > getattr(A.BUDGET, "deadline", None) or 0:
                raise TimeoutError("over its time")
            _t.sleep(0.05)
            return {"isPublicDomain": False}
        try:
            A.get, A.MAX_WAIT[0] = met, 0.5
            buf, t0 = io.StringIO(), _t.time()
            with contextlib.redirect_stdout(buf):
                A.supply(types.SimpleNamespace(q=["Voyager 1"], sources="met", n=20))
            self.assertLess(_t.time() - t0, 3)
            self.assertIn("not judged yet", buf.getvalue())
        finally:
            A.get, A.MAX_WAIT[0] = old

    def test_spans_follow_trim_and_any_row_name(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, wave, struct
        with tempfile.TemporaryDirectory() as tmp:
            old, make.PROJECT = make.PROJECT, Path(tmp)
            try:
                Path(tmp, "audio").mkdir()
                with wave.open(str(Path(tmp, "audio", "long.wav")), "w") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(struct.pack("<h", 1) * 8000 * 40)
                self.assertEqual(make.voice_spans({"layers": [{"bus": "dialogue", "file": "audio/long.wav", "at": 25,
                                                               "trim": [0, 1]}]}), [(25.0, 26.0)])
                Path(tmp, "SCRIPT.md").write_text("## Lines\n| # | Start | Line | Words | Est. s |\n|---|---|---|---|---|\n"
                                                  "| R1 | 0:01 | First line | 2 | 1.5 |\n| R2 | 0:29 | Last one | 2 | 1.0 |\n",
                                                  encoding="utf-8")
                self.assertEqual(make.voice_spans(None), [(1.0, 2.5), (29.0, 30.0)])
            finally:
                make.PROJECT = old

    def test_an_approved_gate_moves_on_in_the_same_turn(self):
        log = self.root / "g.jsonl"
        def row(kind, **kw):
            return json.dumps({"type": "assistant" if kind == "tool_use" else "user",
                               "message": {"content": [dict({"type": kind}, **kw)]}}) + "\n"
        ask = row("tool_use", id="q1", name="AskUserQuestion", input={"questions": [{"question": "Style frame ổn chưa?"}]})
        answer = lambda text: row("tool_result", tool_use_id="q1",
                                  content=f'Your questions have been answered: "Style frame ổn chưa?"="{text}".')
        stop = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log)}
        log.write_text(ask + answer("Được ★ (đề xuất)"), encoding="utf-8")
        code, out = self.guard("stop", stop)
        self.assertEqual(code, 2)
        self.assertIn("approved", out)
        self.assertEqual(self.guard("stop", dict(stop, stop_hook_active=True))[0], 0)
        log.write_text(ask + answer("Được ★ (đề xuất)") + row("tool_use", id="q2", name="AskUserQuestion",
                       input={"questions": [{"question": "Font nào?"}]}), encoding="utf-8")
        self.assertEqual(self.guard("stop", stop)[0], 0)
        log.write_text(ask + answer("Tôi có góp ý"), encoding="utf-8")
        self.assertEqual(self.guard("stop", stop)[0], 0)
        started = ask + answer("Kur ★") + row("tool_use", id="b1", name="Bash",
                                             input={"command": "python3 tools/make.py draft", "run_in_background": True})
        log.write_text(started + row("tool_result", tool_use_id="b1", content="Command running in background with ID: x"),
                       encoding="utf-8")
        self.assertEqual(self.guard("stop", stop)[0], 0)
        log.write_text(started + row("tool_result", tool_use_id="b1", is_error=True, content="Exit code 1"), encoding="utf-8")
        self.assertEqual(self.guard("stop", stop)[0], 2, "a next step that failed has not moved the film on")

    def test_a_long_reference_is_read_by_section(self):
        ref = str(ROOT / "references" / "quick-mode.md")
        read = lambda inp: self.guard("tool", {"tool_name": "Read", "cwd": str(self.root), "tool_input": inp})
        code, out = read({"file_path": ref})
        self.assertEqual(code, 2)
        self.assertIn("the Grep tool for '^## '", out)
        self.assertEqual(read({"file_path": ref, "offset": 90, "limit": 40})[0], 0)
        bash = lambda c: self.guard("tool", {"tool_name": "Bash", "cwd": str(self.root), "tool_input": {"command": c}})[0]
        self.assertEqual(bash(f"cat {ref}"), 2)
        self.assertEqual(bash(f"grep -n '^## ' {ref}"), 0)

    def test_broken_project_files_stop_with_their_name(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        logs = self.root / "logs"
        with patch.object(make, "PROJECT", self.root), patch.object(make, "LOGS", logs), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            (self.root / "STATE.md").write_text("", encoding="utf-8")
            self.assertEqual(make.title_of({}), self.root.name)
            (self.root / "audio").mkdir()
            (self.root / "film.html").write_text("", encoding="utf-8")
            for bad in ("null", "[]", "{", '{"layers": "x"}'):
                (self.root / "audio" / "mix.json").write_text(bad, encoding="utf-8")
                with self.assertRaises(SystemExit):
                    make.sound_plan("film.html")
            (self.root / "LICENSES.csv").write_text("this is not a CSV file\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                make.credits_file("Film", "")
            (self.root / "LICENSES.csv").write_text(
                "file,title,author,source_url,licence,licence_url,attribution_text,modifications,downloaded_at,used_in,notes\n"
                "a.jpg,Map,Author,,CC0,,Map by Author,,,,\n", encoding="utf-8")
            make.credits_file("../../escape/Film: one", "")
            for bad in ("null", "[]", "{", ""):
                (self.root / "shots.json").write_text(bad, encoding="utf-8")
                with self.assertRaises(SystemExit):
                    make.film_title()
            (self.root / "shots.json").unlink()
        self.assertIn("mix.json", out.getvalue())
        self.assertIn("LICENSES.csv", out.getvalue())
        self.assertEqual([p.name for p in self.root.glob("*-credits.txt")], ["escapeFilm one-credits.txt"])
        self.assertFalse((self.root.parent / "escape").exists())

    def test_a_music_video_keeps_its_sound_effects_sparse(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        info = {"frames": 24 * 60, "fps": 24, "sfx": [(5, "hit"), (20, "tick"), (41, "hit")]}
        plan = {"layers": [{"bus": "music"}]}
        (self.root / "review").mkdir()
        (self.root / "review" / "sound-audit.md").write_text("events 3 · sounded 3", encoding="utf-8")
        with patch.object(make, "PROJECT", self.root), patch.object(make, "REVIEW", self.root / "review"):
            self.assertIn("SOUND THIN", make.sound_thin_line(info, plan, "- **Sound:** score and effects\n"))
            self.assertEqual(make.sound_thin_line(info, plan, "- **Route:** music video on the user's own song\n"), "")

    def test_a_kept_signature_sound_is_not_a_format_copy(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        (self.root / "research").mkdir()
        cues = "const SFX = [\n" + "".join(f"  {{t: {i}.5, kind: 'tap', gain: 0.4}},  // the format's three-note motif\n" for i in range(6)) + "];\n"
        old = "function score(t) {\n  return Math.sin(t * 440) * 0.2 + tone(220, t);\n}\nconst SCENES = [\n  {at: 0, line: 'old one'},\n  {at: 4, line: 'old two'},\n];\n" + cues
        new = "function score(t) {\n  return pad(t, [196, 247, 294]) * drum(t * 2.1) + bassline(t);\n}\nconst SCENES = [\n  {at: 0, title: 'Hai đầu nam châm'},\n  {at: 5, title: 'Lực hút'},\n];\n" + cues
        (self.root / "research" / "format-reference.html").write_text(old, encoding="utf-8")
        (self.root / "film.html").write_text(new, encoding="utf-8")
        with patch.object(make, "PROJECT", self.root):
            self.assertIn("the sound cues", make.format_copy_line(self.root / "film.html"))
            (self.root / "FORMAT.md").write_text("# Format\n## Kept on purpose\n- the three-note motif at the end\n", encoding="utf-8")
            self.assertEqual(make.format_copy_line(self.root / "film.html"), "")
            (self.root / "FORMAT.md").write_text("# Format\n## Kept on purpose\n- none\n", encoding="utf-8")
            self.assertIn("the sound cues", make.format_copy_line(self.root / "film.html"))

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_film_check_stops_on_broken_files_and_names_late_narration(self):
        (self.film / "engine").mkdir()
        (self.film / "renders").mkdir()
        (self.film / "audio").mkdir()
        tools = self.film / "tools"
        __import__("shutil").copytree(ROOT / "scripts", tools, dirs_exist_ok=True)
        cut = self.film / "renders" / "draft-v1.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=160x90:d=64:r=2", "-f", "lavfi", "-i",
                        "sine=f=300:r=48000:d=64", "-shortest", "-pix_fmt", "yuv420p", str(cut)], check=True)
        check = lambda: subprocess.run([sys.executable, str(tools / "make.py"), "check", "renders/draft-v1.mp4"], cwd=self.film,
                                       capture_output=True, text=True, env=dict(os.environ, RUBYDAI_VIDEO_NO_OPEN="1"))
        for bad in ("{", "", "null", "[]", '{"fps": 2, "shots": [{"id": "S01"}]}'):
            (self.film / "shots.json").write_text(bad, encoding="utf-8")
            run = check()
            self.assertEqual(run.returncode, 2, bad + run.stdout + run.stderr)
            self.assertIn("FAILED: shots.json", run.stdout)
            self.assertNotIn("Traceback", run.stderr)
        (self.film / "shots.json").write_text(json.dumps({"fps": 2, "shots": [{"start": 0}, {"start": 64}]}), encoding="utf-8")
        (self.film / "audio" / "mix.json").write_text("[]", encoding="utf-8")
        run = check()
        self.assertEqual(run.returncode, 2)
        self.assertIn("FAILED: audio/mix.json", run.stdout)
        (self.film / "audio" / "mix.json").write_text(json.dumps({"duration": 64, "out": "audio/mix.wav", "layers": [
            {"file": "audio/score.wav", "at": 0, "bus": "music"}, {"file": "audio/VO1.wav", "at": 6.5, "bus": "dialogue"}]}),
            encoding="utf-8")
        run = check()
        self.assertIn("NARRATION LATE", run.stdout)
        self.assertTrue((self.film / "review" / "qc-draft-v1" / "sheet-small.jpg").exists())

    def test_tts_never_prints_the_key_and_never_follows_a_redirect(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import tts, urllib.error
        key = "AIzaSyFAKE-not-a-real-key-123456"
        body = io.BytesIO(json.dumps({"error": f"API key {key} not valid"}).encode())
        err = urllib.error.HTTPError("https://x.test", 400, "bad", {}, body)
        with patch("urllib.request.OpenerDirector.open", side_effect=err):
            with self.assertRaises(RuntimeError) as caught:
                tts.post("https://x.test", {}, {"x-goog-api-key": key, "Content-Type": "application/json"})
        self.assertNotIn(key, str(caught.exception))
        self.assertIn("<key>", str(caught.exception))
        self.assertIsNone(tts.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://elsewhere.test"))

    def test_printed_commands_survive_spaces_and_apostrophes(self):
        import shlex
        wav = str(self.root / "Phim Đường Mưa" / "giọng của Đường.wav")
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "captions.py"), "cmd", wav], capture_output=True,
                             text=True).stdout.splitlines()
        whisper = shlex.split(out[1])
        self.assertEqual(whisper[1], wav)
        code = shlex.split(out[3].strip())[2]
        compile(code, "faster_whisper", "exec")
        self.assertIn(repr(wav), code)
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "lyrics_align.py"), "cmd", wav], capture_output=True,
                             text=True).stdout.splitlines()
        self.assertEqual(shlex.split(out[1])[1], wav)

    def test_shots_json_in_another_shape_fails_by_name(self):
        p = self.root / "shots.json"
        for bad in ('{"fps": 24, "shots": [{"id": "S01", "start": 0, "end": 48, "reads": ["a"]}]}', "[]", "{"):
            p.write_text(bad, encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_shots.py"), str(p)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, bad)
            self.assertIn("FAILED", run.stderr)
            self.assertNotIn("Traceback", run.stderr)
        shot = {"id": "S01", "start": 0, "end": 48, "description": "a cup", "reads": [{"read": "a cup", "t": [0, 2]}],
                "camera": "locked, 2 s"}
        p.write_text(json.dumps({"title": "T", "fps": 24, "width": 1080, "height": 1920, "duration_frames": 48,
                                 "shots": [shot]}), encoding="utf-8")
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_shots.py"), str(p)], capture_output=True, text=True)
        self.assertNotIn("FAILED", run.stdout + run.stderr)

    def test_a_final_reads_the_independent_viewer_and_waits_only_briefly(self):
        import argparse, time
        renders, review = self.root / "renders", self.root / "review"
        renders.mkdir()
        review.mkdir()
        (self.root / "film.html").write_text("", encoding="utf-8")
        (renders / "draft-v2.mp4").write_bytes(b"")
        a = argparse.Namespace(film="film.html", force=False)
        with patch.object(make, "PROJECT", self.root), patch.object(make, "RENDERS", renders), \
                patch.object(make, "REVIEW", review), patch.object(make, "LOGS", self.root / "logs"), \
                patch.dict(os.environ, {"RUBYDAI_VIDEO_VIEWER_WAIT": "0.2"}), contextlib.redirect_stdout(io.StringIO()) as out:
            start = time.time()
            self.assertEqual(make.viewer_report(a), "")           # no viewer asked for: the user's OK is the gate, no wait
            self.assertLess(time.time() - start, 5)
            red = "1. 3.2 s · text cut by the edge · move it in\nVerdict: FIX\nRed items:\n- 5.1 s a blank frame\n"
            (review / "critique-v2.md").write_text(red, encoding="utf-8")
            with self.assertRaises(SystemExit):
                make.viewer_report(a)
            self.assertIn("5.1 s a blank frame", out.getvalue())
            (self.root / "film.html").write_text("<!-- touched -->", encoding="utf-8")   # a changed file is no proof
            with self.assertRaises(SystemExit):
                make.viewer_report(a)
            (renders / "draft-v3.mp4").write_bytes(b"")                              # a new draft, not yet watched
            with self.assertRaises(SystemExit):
                make.viewer_report(a)
            self.assertIn("no viewer has looked at draft v3", out.getvalue())
            (review / "critique-v3.md").write_text("1. 3.2 s · slow middle · cut 2 s\nVerdict: APPROVE\nRed items: none\n",
                                                   encoding="utf-8")
            self.assertIn("no red items", make.viewer_report(a))
            (review / "critique-v3.md").write_text("Verdict: UNVERIFIABLE\nRed items: none\n", encoding="utf-8")
            self.assertIn("UNVERIFIABLE", make.viewer_report(a))
            (review / "critique-v3.md").write_text(red, encoding="utf-8")
            self.assertIn("kept by the user", make.viewer_report(argparse.Namespace(film="film.html", force=True)))

    def test_a_broken_file_is_never_shown_anyway(self):
        self.assertTrue(make.delivers("PASS", True, 0, "", ["TOO STILL"], True))
        self.assertFalse(make.delivers("PASS", True, 0, "", ["TOO STILL"], False))
        self.assertFalse(make.delivers("PASS", True, 0, "AV OFFSET: +0.176 s", [], True))
        self.assertFalse(make.delivers("PASS", True, 0, "AV OFFSET: +0.176 s", ["AV OFFSET"], True))

    def test_a_card_that_routes_3d_through_flat_polygons_is_named(self):
        bad = "- **Code fit:** Không có người. Low-poly đổ bóng phẳng 3D, giấy, chữ.\n"
        good = "- **Code fit:** three.js, nhựa đường ướt và lưới cửa sổ sáng đèn; con thuyền khắc linoleum, vết khắc trên mọi mặt.\n"
        self.assertIn("OLD CG ROUTE", make.old_cg_line(bad))
        self.assertEqual(make.old_cg_line(good), "")
        self.assertEqual(make.old_cg_line("- **Code fit:** flat-shaded is avoided? no\n")[:12], "OLD CG ROUTE")

    def test_a_human_readable_cc_by_label_keeps_its_licence_link(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        (self.root / "LICENSES.csv").write_text(
            "file,title,author,source_url,licence,licence_url,attribution_text,modifications,downloaded_at,used_in,notes\n"
            "a.jpg,Map,Author,,CC BY 4.0,https://creativecommons.org/licenses/by/4.0/,Map by Author,,,,\n"
            "b.jpg,Plan,Author,,CC BY-SA 4.0,https://creativecommons.org/licenses/by-sa/4.0/,Plan by Author,,,,\n", encoding="utf-8")
        with patch.object(make, "PROJECT", self.root):
            make.credits_file("Deneme", "")
        text = (self.root / "Deneme-credits.txt").read_text(encoding="utf-8")
        self.assertIn("Map by Author (https://creativecommons.org/licenses/by/4.0/)", text)
        self.assertIn("Plan by Author (https://creativecommons.org/licenses/by-sa/4.0/)", text)

    def test_a_turn_that_shows_a_draft_ends_on_its_question(self):
        log = self.root / "d.jsonl"
        log.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "d1", "name": "Bash",
                       "input": {"command": "python3 tools/make.py draft"}}]}}) + "\n" + json.dumps({"type": "user", "message":
                       {"content": [{"type": "tool_result", "tool_use_id": "d1", "content": "SHOW THIS DRAFT NOW: the film"}]}}) + "\n",
                       encoding="utf-8")
        stop = {"cwd": str(self.film), "session_id": "s", "transcript_path": str(log)}
        code, out = self.guard("stop", stop)
        self.assertEqual(code, 2)
        self.assertIn("Jury", out)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "q1",
                    "name": "AskUserQuestion", "input": {"questions": []}}]}}) + "\n")
        self.assertEqual(self.guard("stop", stop)[0], 0)

    def test_null_music_in_any_spacing_and_a_music_only_card_are_read_right(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        film = self.root / "film.html"
        drone = self.root / "drone.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=110:d=8", str(drone)], check=True)
        with patch.object(make, "SHOWN_MUSIC", self.root / "music.json"), patch.object(make, "PROJECT", self.root):
            for spelling in ("const OWN_MUSIC = null;", "const OWN_MUSIC=null;"):
                film.write_text(spelling + "\n", encoding="utf-8")
                self.assertIn("MUSIC WITHOUT A BEAT", make.music_line(film, drone, "tempo energetic", [0, 2, 4, 6, 8], remember=False))
        with patch.object(make, "PROJECT", self.root):
            music_only = "- **Âm thanh / Sound:** music only, by choice"
            coded = {"layers": [{"bus": "music", "file": "audio/beat.wav"}]}
            self.assertEqual(make.sound_source_line(film, coded, music_only), "")
            self.assertEqual(make.sound_thin_line({"frames": 240, "fps": 24, "sfx": []}, coded, music_only), "")

    def test_a_named_print_medium_brings_its_recipe(self):
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "styles.py"), "suggest",
                              "A glassblower's workshop as a linocut, blue ink on cream paper"],
                             capture_output=True, text=True).stdout
        self.assertIn("named look: linocut", out)
        self.assertIn("woodcut", out.split("\n2.")[0] + out.split("\n3.")[0])

    def test_the_guard_never_crashes_on_common_events(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        png(self.film / "review" / "a.png", 64, 64)
        (self.film / "notes").mkdir(exist_ok=True)
        events = [{"tool_name": n, "tool_input": i, "cwd": str(self.film), "session_id": "s"} for n, i in [
            ("Read", {"file_path": str(self.film / "review" / "a.png")}), ("Read", {}), ("Bash", {"command": "ls"}),
            ("Write", {"file_path": str(self.film / "review" / "a.png"), "content": "x"}),
            ("Edit", {"file_path": str(self.film / "notes" / "round-1.md"), "old_string": "a", "new_string": "b"}),
            ("MultiEdit", {"file_path": str(self.film / "STATE.md"), "edits": [{"old_string": "a", "new_string": "b"}]}),
            ("Agent", {"prompt": "x"}), ("SendUserFile", {"files": [str(self.film / "missing.mp4")]}),
            ("AskUserQuestion", {"questions": []}), ("mcp__ccd_turn__wrap_up", {"recap": "x"}), ("Grep", {"pattern": "x"})]]
        for ev in events:
            try:
                guard.tool(ev)
            except Exception as e:                                              # main() would hide it and open every gate
                self.fail(f"{ev['tool_name']}: {e!r}")

    def test_image_outside_a_film_is_left_alone(self):
        big = self.root / "big.png"
        png(big, 3000, 3000)
        self.assertEqual(self.guard("tool", {"tool_name": "Read", "tool_input": {"file_path": str(big)}})[0], 0)

    def test_helper_stops_after_its_budget_but_may_write_its_report(self):
        ev = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(self.root), "session_id": "s",
              "agent_id": "a"}
        codes = [self.guard("tool", dict(ev, tool_use_id=f"t{i}"))[0] for i in range(25)]
        self.assertEqual(self.guard("tool", dict(ev, tool_use_id="t24"))[0], 0)   # a second hook on the same call
        codes += [self.guard("tool", dict(ev, tool_use_id="t25"))[0]]
        self.assertEqual(codes[:25], [0] * 25)
        self.assertEqual(codes[25], 2)
        report = dict(ev, tool_name="Write", tool_input={"file_path": str(self.film / "review" / "x-handoff.md")})
        self.assertEqual(self.guard("tool", report)[0], 0)
        main_chat = {k: v for k, v in ev.items() if k != "agent_id"}
        self.assertEqual(self.guard("tool", main_chat)[0], 0)

    def test_prompt_reminds_once_per_level(self):
        transcript = self.root / "chat.jsonl"
        turn = {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 1,
                "cache_creation_input_tokens": 9_999, "cache_read_input_tokens": 270_000, "output_tokens": 5}}}
        transcript.write_text(json.dumps(turn) + "\n", encoding="utf-8")
        ev = {"cwd": str(self.root), "session_id": "s", "transcript_path": str(transcript)}
        code, out = self.guard("prompt", ev)
        self.assertEqual(code, 0)
        self.assertIn("280 K", out)
        self.assertEqual(self.guard("prompt", ev)[1], "")
        self.assertEqual(usage.last_context(transcript), 280_000)

    def test_guard_never_blocks_on_its_own_error(self):
        p = subprocess.run([sys.executable, GUARD, "tool"], input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)

    def test_make_summary_reads_flags_and_black_spans(self):
        report = self.root / "report.txt"
        report.write_text(
            "== hook (first 2 s):\n  steps=47 mean=14.7\n  PASS\n"
            "== black intervals (>= 0.1 s, 98% of pixels dark):\nblack_start:0 black_end:2.29 black_duration:2.29\n"
            "== frozen intervals (>= 1.5 s):\nnone\n(grain hides freezes)\n"
            "== exact duplicate consecutive frames:\nframes: 192, duplicates: 0\n"
            "== one-frame pops (a frame unlike both neighbours, 48 px grey): 1\n     frame 30 (00:01.25)  step 131.9\n"
            "== action per scene (camera move removed):\n     #1 00:00.00-00:03.00  residual 2.1  total 3.0  ok\n"
            "  0 scene(s) flagged\n"
            "== sound per scene (median -13.3 LUFS):\n     #1 00:00.00-00:03.00   -19.2 LUFS  harsh -24.3 dB  QUIETER by 5.9 LU\n"
            "     #2 00:03.00-00:08.00   -13.0 LUFS  harsh -25.1 dB  ok\n", encoding="utf-8")
        hook, flags, issues = make.report_lines(report, [0, 3, 8])
        self.assertEqual(hook, "PASS")
        self.assertEqual(flags[0], "action 0 flags")
        self.assertTrue(flags[1].startswith("sound 1 flag: #1"))
        self.assertEqual(issues[0], "black 0.0–2.3 s")
        self.assertTrue(issues[1].startswith("OPENS DARK"))
        self.assertEqual(issues[2], "one-frame pops 1 at 00:01.25")
        report.write_text(report.read_text().replace("  PASS", "  FAIL: open on the motion itself"), encoding="utf-8")
        self.assertEqual(make.report_lines(report, [])[0], "FAIL")

    def test_known_style_name_lists_its_recipes_first(self):
        out = subprocess.run([sys.executable, ROOT / "scripts" / "styles.py", "list", "--q", "một phim kiểu vox"],
                             capture_output=True, text=True).stdout.splitlines()
        self.assertTrue(out[0].startswith('known name "vox" → vox-explainer'))
        self.assertTrue(out[1].startswith("vox-explainer ·"))
        self.assertEqual(out[-1], f"(3 of {len(json.loads((ROOT / "styles" / "index.json").read_text(encoding="utf-8"))["styles"])})")
        aliases = json.loads((ROOT / "styles" / "aliases.json").read_text(encoding="utf-8"))["aliases"]
        ids = {s["id"] for s in json.loads((ROOT / "styles" / "index.json").read_text(encoding="utf-8"))["styles"]}
        self.assertTrue(all(i in ids for al in aliases for i in al["styles"]))

    def test_the_guard_wants_pictures_shown_before_a_question_or_the_end_of_a_turn(self):
        tool_def = {"type": "x", "tools": [{"name": "SendUserFile"}]}
        use = lambda i, name, inp: {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": i, "name": name, "input": inp}]}}
        res = lambda i, text: {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": i, "content": text}]}}
        draft = [use("a", "Bash", {"command": "python3 tools/make.py draft"}), res("a", "draft v1: Film-draft.mp4 · 30 s\nSHOW THIS DRAFT NOW: the film /f/Film-draft.mp4")]
        sent = [use("b", "SendUserFile", {"files": ["Film-draft.mp4"], "status": "normal", "display": "render"}), res("b", "1 file delivered")]
        failed = [use("c", "Bash", {"command": "python3 tools/make.py draft"}), res("c", "FAILED: capture.mjs (exit 1)")]
        def run(events, mode, extra=None):
            with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
                f.write("\n".join(json.dumps(e) for e in [tool_def] + events))
            ev = dict({"tool_name": "AskUserQuestion", "tool_input": {}, "transcript_path": f.name, "cwd": str(self.film)}, **(extra or {}))
            r = subprocess.run([sys.executable, ROOT / "scripts" / "guard.py", mode], input=json.dumps(ev), text=True,
                               capture_output=True)
            os.unlink(f.name)
            return r.returncode
        self.assertEqual(run(draft, "tool"), 2)
        self.assertEqual(run(draft, "stop"), 2)
        self.assertEqual(run(draft, "stop", {"stop_hook_active": True}), 0)
        choices = {"tool_input": {"questions": [{"options": [{"label": "Final ★"}, {"label": "Góp ý"}, {"label": "Vòng giám khảo"}]}]}}
        self.assertEqual(run(draft + sent, "tool", choices), 0)
        self.assertEqual(run(failed, "stop"), 0)

    def test_a_delivered_draft_turn_never_ends_without_its_question(self):
        use = lambda i, name, inp: {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": i, "name": name, "input": inp}]}}
        res = lambda i, text: {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": i, "content": text}]}}
        draft = [use("a", "Bash", {"command": "python3 tools/make.py draft"}), res("a", "SHOW THIS DRAFT NOW: the film x.mp4")]
        asked = [use("b", "AskUserQuestion", {"questions": []}), res("b", "answered")]
        def run(events, inp):
            with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
                f.write("\n".join(json.dumps(e) for e in events))
            ev = {"tool_name": "mcp__ccd_turn__wrap_up", "tool_input": inp, "transcript_path": f.name, "cwd": str(self.film)}
            r = subprocess.run([sys.executable, ROOT / "scripts" / "guard.py", "tool"], input=json.dumps(ev), text=True,
                               capture_output=True)
            os.unlink(f.name)
            return r.returncode
        self.assertEqual(run(draft, {"recap": "done"}), 2)
        self.assertEqual(run(draft, {"recap": "done", "ask": "Bản nháp này, mình làm tiếp thế nào?"}), 2)   # a question with no choices
        choices = [{"label": x, "message": x} for x in ("Final ★", "Góp ý", "Vòng giám khảo")]
        self.assertEqual(run(draft, {"recap": "done", "ask": "Bản nháp này, mình làm tiếp thế nào?", "actions": choices}), 2,
                         "three buttons: the box shows two")
        self.assertEqual(run(draft + asked, {"recap": "done"}), 0)
        bg = [use("a", "Bash", {"command": "python3 tools/make.py draft"}), res("a", "Command running in background (shell 7)"),
              use("r", "Read", {"file_path": str(self.film / "logs" / "last-make.txt")}),
              res("r", "draft-v1.mp4 51 s\nSHOW THIS DRAFT NOW: the film draft-v1.mp4")]
        self.assertEqual(run(bg, {"recap": "done"}), 2, "a background draft read back from its file still owes its question")
        quoted = [use("a", "PowerShell", {"command": '& "C:/Python/python.exe" "C:/My Films/f/tools/make.py" draft'}),
                  res("a", "SHOW THIS DRAFT NOW: the film draft-v1.mp4")]
        self.assertEqual(run(quoted, {"recap": "done"}), 2, "a quoted make.py path is still a delivered draft")
        send = use("s", "SendUserFile", {"files": [str(self.film / "renders" / "draft-v1.mp4")]})
        ask = use("q", "AskUserQuestion", {"questions": [{"question": "Bản nháp này, mình làm tiếp thế nào?",
                  "options": [{"label": x, "message": x} for x in ("Final ★", "Góp ý", "Vòng giám khảo")]}]})
        done = bg + [send, res("s", "sent"), ask, res("q", "Góp ý")]
        self.assertEqual(run(done, {"recap": "done"}), 0, "the draft was sent and its question asked")
        reread = done + [use("r2", "Read", {"file_path": str(self.film / "logs" / "last-make.txt")}),
                         res("r2", "SHOW THIS DRAFT NOW: the film draft-v1.mp4")]
        self.assertEqual(run(reread, {"recap": "done"}), 0, "re-reading the same summary never re-opens the gate")
        kitread = done + [use("k", "Read", {"file_path": str(ROOT / "SKILL.md")}),
                          res("k", "put it in wrap_up ... show the user: the draft, SHOW THIS DRAFT NOW line")]
        self.assertEqual(run(kitread, {"recap": "done"}), 0, "a kit line that quotes the marker is not a delivery")
        v2 = reread + [use("a2", "Bash", {"command": "python3 tools/make.py draft"}),
                       res("a2", "SHOW THIS DRAFT NOW: the film draft-v2.mp4")]
        self.assertEqual(run(v2, {"recap": "done"}), 2, "a genuine new draft re-opens the gate")
        waitrep = done + [use("w", "Bash", {"command": "python3 tools/make.py wait"}),
                          res("w", "SHOW THIS DRAFT NOW: the film draft-v1.mp4 (from an earlier run)")]
        self.assertEqual(run(waitrep, {"recap": "done"}), 0, "a make.py wait re-print of the same draft does not re-open")
        same_turn = bg + [send, ask, res("s", "sent"), res("q", "Góp ý")]
        self.assertEqual(run(same_turn, {"recap": "done"}), 0, "the send and its question in one turn, results after")
        unanswered = bg + [send, ask, res("s", "sent"), {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "q",
                                                                    "content": "failed", "is_error": True}]}}]
        self.assertEqual(run(unanswered, {"recap": "done"}), 2, "a question that failed leaves the sent draft unasked")

    def test_the_guard_never_lets_a_picture_open_in_a_window(self):
        def run(cmd):
            ev = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(self.film)})
            return subprocess.run([sys.executable, ROOT / "scripts" / "guard.py", "tool"], input=ev, text=True,
                                  capture_output=True).returncode
        self.assertEqual(run("open research/style-board.jpg"), 2)
        self.assertEqual(run('cd x && open "Film-draft.mp4"'), 2)
        self.assertEqual(run("open -a Terminal handoff.command"), 0)
        self.assertEqual(run("python3 tools/make.py draft"), 0)

    def test_a_film_folder_in_use_is_never_entered_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda: subprocess.run([sys.executable, ROOT / "scripts" / "init_film.py", "kase", "--quick"], cwd=tmp,
                                         capture_output=True, text=True, env=dict(os.environ, RUBYDAI_VIDEO_NO_OPEN="1"))
            self.assertEqual(run().returncode, 0)
            again = run()
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("IN USE", again.stderr)

    def test_blank_frames_and_a_violet_ground_hold_a_draft(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as tmp:
            def film(name, mid):
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0xc04020:s=160x90:d=1",
                                "-f", "lavfi", "-i", mid, "-f", "lavfi", "-i", "color=c=0xc04020:s=160x90:d=1",
                                "-filter_complex", "[0][1][2]concat=n=3", "-pix_fmt", "yuv420p", f"{tmp}/{name}.mp4"], check=True)
                rep = P(tmp) / f"{name}.txt"
                rep.write_text(subprocess.run([sys.executable, ROOT / "scripts" / "qc.py", "black", f"{tmp}/{name}.mp4"],
                                              capture_output=True, text=True).stdout)
                return make.blank_line(f"{tmp}/{name}.mp4", rep)
            self.assertTrue(film("gap", "color=c=black:s=160x90:d=0.6").startswith("BLANK FRAMES"))
            self.assertEqual(film("card", "color=c=black:s=160x90:d=0.6,drawbox=x=60:y=40:w=40:h=8:color=white:t=fill"), "")
            self.assertEqual(film("blink", "color=c=black:s=160x90:d=0.2"), "")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x4b2fb0:s=160x90:d=4",
                            "-pix_fmt", "yuv420p", f"{tmp}/violet.mp4"], check=True)
            self.assertTrue(make.ai_palette_line(f"{tmp}/violet.mp4").startswith("AI PALETTE"))
            self.assertEqual(make.ai_palette_line(f"{tmp}/gap.mp4"), "")

    def test_the_move_deck_varies_neighbours_and_pushes_back_the_last_films(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import moves
        deck = moves.deal(8, "energetic", "a rain jacket", set())
        self.assertEqual(deck, moves.deal(8, "energetic", "a rain jacket", set()))   # the same idea, the same deck
        for a, b in zip(deck, deck[1:]):
            self.assertNotEqual(a["move"], b["move"])
            self.assertNotEqual(a["size"], b["size"])
            self.assertNotEqual(a["cut"], b["cut"])
        self.assertEqual(sum(1 for d in deck if d.get("big")), 1)
        self.assertIsNone(deck[0]["cut"])
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, RUBYDAI_VIDEO_SHOWN_MOVES=os.path.join(tmp, "m.json"))
            run = lambda film: subprocess.run([sys.executable, ROOT / "scripts" / "moves.py", "deal", "--shots", "6",
                                               "--seed", "x", "--film", film], env=env, capture_output=True, text=True).stdout
            run(os.path.join(tmp, "a"))
            self.assertIn("pushed back", run(os.path.join(tmp, "b")))

    def test_lyrics_keep_the_users_words_on_whispers_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            P = lambda n: os.path.join(tmp, n)
            open(P("l.txt"), "w", encoding="utf-8").write("[Verse]\nĐêm không tàn nếu em chưa tới\nĐèn xanh thắp sáng phố đêm\n")
            heard = [("Đêm", 1.0, 1.2), ("không", 1.2, 1.45), ("tàn", 1.45, 1.7), ("nếu", 1.8, 2.0), ("em", 2.0, 2.2),
                     ("chưa", 2.2, 2.5), ("tới", 2.5, 2.8),
                     ("đèn", 4.0, 4.3), ("xanh", 4.3, 4.6), ("thap", 4.6, 4.9), ("sáng", 4.9, 5.2), ("phó", 5.2, 5.6),
                     ("đêm", 5.6, 6.0)]                   # Whisper drops an accent (thap) and mishears a word (phó)
            json.dump({"segments": [{"words": [{"word": w, "start": a, "end": b} for w, a, b in heard]}]},
                      open(P("s.json"), "w"))
            r = subprocess.run([sys.executable, ROOT / "scripts" / "lyrics_align.py", "align", P("l.txt"), P("s.json"),
                                "--json", P("o.json"), "--lrc", P("o.lrc")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            lrc = open(P("o.lrc"), encoding="utf-8").read().splitlines()
            self.assertEqual(lrc, ["[00:01.00]Đêm không tàn nếu em chưa tới", "[00:04.00]Đèn xanh thắp sáng phố đêm"])
            words = json.load(open(P("o.json")))["lines"][1]["words"]
            self.assertEqual([w["w"] for w in words], ["Đèn", "xanh", "thắp", "sáng", "phố", "đêm"])   # the user's words win

    def test_template_cliches_in_the_film_code_are_named_unless_the_card_gives_a_reason(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "film.html")
            open(p, "w").write("// ============================== FILM ===\nburst(particles, 300); g.shadowBlur = 40;\n"
                               "// ============================== HELPERS ===\nfunction flare() {}\n")
            line = make.cliche_line(p, "")
            self.assertIn("particle burst", line)
            self.assertIn("neon glow", line)
            self.assertNotIn("lens flare", line)            # the engine's own helpers are not the film's choice
            self.assertEqual(make.cliche_line(p, "neon glow from the signs; particle sparks at the slam"), "")

    def test_a_source_that_did_not_answer_is_never_counted_as_empty(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import asset_search as A
        import io, contextlib, types
        def slow(q, n, k):
            raise TimeoutError("The read operation timed out")
        few = lambda q, n, k: [A.rec("x", i, f"t{i}", "", "cc0", "", "", "", "image") for i in range(2)]
        A.SOURCES.update(slowsrc=slow, fewsrc=few)
        old = A.MAX_WAIT[0]
        try:
            for sources, want, never in (("slowsrc,fewsrc", "not judged yet", "Tell the user now"),
                                         ("fewsrc", "Tell the user now", "Not judged yet")):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    A.supply(types.SimpleNamespace(q=["Voyager 1 team"], sources=sources, n=5))
                self.assertIn(want, buf.getvalue())
                self.assertNotIn(never, buf.getvalue())
        finally:
            A.MAX_WAIT[0] = old
            for k in ("slowsrc", "fewsrc"):
                A.SOURCES.pop(k, None)

    def test_make_wait_waits_for_the_running_step_only(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, io, contextlib
        with tempfile.TemporaryDirectory() as tmp:
            old = make.LOGS
            make.LOGS = Path(tmp)
            try:
                (make.LOGS / "last-make.txt").write_text("draft v1: an earlier run\n", encoding="utf-8")
                busy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
                (make.LOGS / make.RUNNING).write_text(f"{busy.pid} draft\n", encoding="utf-8")
                with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(io.StringIO()):
                    make.wait_cmd(1)
                self.assertEqual(stop.exception.code, 3)
                busy.kill()
                busy.wait()
                buf = io.StringIO()
                with self.assertRaises(SystemExit) as died, contextlib.redirect_stdout(buf):
                    make.wait_cmd(5)
                self.assertEqual(died.exception.code, 1, "a run that died never borrows an earlier success")
                self.assertIn("ended without its summary", buf.getvalue())
                (make.LOGS / f"run-{busy.pid}.txt").write_text("draft v2: done\n", encoding="utf-8")
                buf = io.StringIO()
                with self.assertRaises(SystemExit) as done, contextlib.redirect_stdout(buf):
                    make.wait_cmd(5)
                self.assertEqual(done.exception.code, 0)
                self.assertIn("draft v2: done", buf.getvalue())
                (make.LOGS / f"run-{busy.pid}.txt").write_text("draft v2: NOT DELIVERED (the hook)\n", encoding="utf-8")
                with self.assertRaises(SystemExit) as held, contextlib.redirect_stdout(io.StringIO()):
                    make.wait_cmd(5)
                self.assertEqual(held.exception.code, 1)
            finally:
                make.LOGS = old

    def test_music_made_in_code_is_the_users_choice_never_a_default(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        self.assertEqual(make.music_choice_line(ROOT / "templates" / "quick" / "film.html", None, ""), "")   # no house score
        film = self.root / "film.html"
        film.write_text("const OWN_MUSIC = null;\nfunction score(ctx, out) {\n  // the film's own\n  pad(ctx, out, 0, 4, [220], 0.1);\n}\n",
                        encoding="utf-8")
        self.assertIn("MUSIC NOT CHOSEN", make.music_choice_line(film, None, "- **Music:** wind-chime minimal score\n"))
        self.assertEqual(make.music_choice_line(film, None, "- **Music:** code (user): a wind-chime score\n"), "")
        self.assertIn("says no music", make.music_choice_line(film, None, "- **Music:** none (user)\n"))   # the claim is checked
        song = {"layers": [{"file": "audio/music/nocturne.mp3", "bus": "music"}]}
        self.assertIn("MUSIC NOT CHOSEN", make.music_choice_line(ROOT / "none.html", song, ""))     # any music is asked
        self.assertEqual(make.music_choice_line(ROOT / "none.html", song, "- **Music:** recording, nocturne (user)\n"), "")
        template = (ROOT / "templates" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("MUSIC NOT CHOSEN", make.music_choice_line(ROOT / "none.html", song, template))  # placeholder is no pick

    def test_the_ending_keeps_its_time_after_the_last_line(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        with tempfile.TemporaryDirectory() as tmp:
            old, make.PROJECT = make.PROJECT, Path(tmp)
            try:
                Path(tmp, "SCRIPT.md").write_text("| # | Start | Line | Words | Est. s |\n|---|---|---|---|---|\n"
                                                  "| VO1 | 0:00.8 | Một sáng tháng năm. | 3 | 2.4 |\n"
                                                  "| VO49 | 4:55.5 | Chiều xuống, tổ ong im lặng. | 4 | 2.6 |\n", encoding="utf-8")
                spans = make.voice_spans(None)
                self.assertEqual(spans[-1], (295.5, 298.1))
                self.assertIn("ENDING SHORT", make.ending_line(spans, 300.0))
                self.assertEqual(make.ending_line(spans, 305.0), "")
                film = Path(tmp, "film.html")
                film.write_text("const VO = [{ id: 'VO1', at: 0.6, dur: 2.3 }, { id: 'VO2', at: 26.5, dur: 2.0 }];", encoding="utf-8")
                self.assertEqual(make.voice_spans(None, film), [(0.6, 2.9), (26.5, 28.5)])
                self.assertIn("needs about 2 s", make.ending_line(make.voice_spans(None, film), 30.0))
                self.assertEqual(make.ending_line([], 30.0), "")       # a wordless film has no last line
            finally:
                make.PROJECT = old

    def test_the_same_chord_loop_in_any_key_is_named(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        film = self.root / "film.html"
        shapes = set()
        for prog in ("['Am', 'F', 'C', 'G']", "['Fm9', 'Dbmaj7', 'Ab', 'Eb']", "['Dm9', 'Bbmaj7', 'F', 'C']"):
            film.write_text(f"const prog = {prog};\n", encoding="utf-8")
            shapes.add(make.progression_shape(film))
        self.assertEqual(len(shapes), 1)                  # one loop, three keys
        film.write_text("const prog = ['Dmaj7', 'G6', 'Bm7', 'A'];\n", encoding="utf-8")
        self.assertEqual(make.progression_shape(film), "0 5 9m 7")

    def test_a_board_of_one_tone_is_named(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import direction
        night = [{"p50": 15, "chroma": 18}, {"p50": 21, "chroma": 12}, {"p50": 40, "chroma": 4}]
        self.assertIn("every row is low-key", direction.one_tone(night))
        self.assertIn("no row carries colour", direction.one_tone(night))
        self.assertEqual(direction.one_tone(night + [{"p50": 62, "chroma": 38}]), "")
        self.assertEqual(direction.one_tone(night[:1]), "")

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_a_tall_board_brings_a_small_copy_to_read(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import direction
        board = self.root / "readings.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x305070:s=1280x1376",
                        "-frames:v", "1", str(board)], check=True)
        said = direction.small_copy(str(board))
        small = self.root / "readings-small.jpg"
        self.assertIn(str(small), said)
        size = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
                               str(small)], capture_output=True, text=True).stdout.strip().split("x")
        self.assertLessEqual(int(size[0]) * int(size[1]), 1_000_000, "the guard lets the agent read it")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x500", "-frames:v", "1",
                        str(board)], check=True)
        self.assertEqual(direction.small_copy(str(board)), "")

    def test_words_on_screen_count_as_telling(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        with tempfile.TemporaryDirectory() as tmp:
            old, make.PROJECT = make.PROJECT, Path(tmp)
            try:
                Path(tmp, "SCRIPT.md").write_text("## On-screen text\n| Time | Text | On screen (s) | Placement |\n"
                                                  "|---|---|---|---|\n| 0:21 | 9 tháng 5 | 2.5 | lower left |\n"
                                                  "| 1:12 | Tổ ong, đồng cỏ lắng nghe. | 2.0 | bottom |\n## Key moments\n"
                                                  "| 0:14 | the flash | 3 | bang |\n", encoding="utf-8")
                self.assertEqual(make.text_spans(), [(21.0, 23.5), (72.0, 74.0)])
            finally:
                make.PROJECT = old

    def test_a_long_narrated_film_reports_a_thin_voice(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        thin = [(m * 60 + 2, m * 60 + 20) for m in range(5)]
        line = make.rests_line(Path("/nonexistent.mp4"), thin, 300.0, [])
        self.assertIn("PACE (a report, not a hold): the voice speaks 30%", line)
        self.assertIn("min 1: 18 s", line)
        full = [(x, x + 3.5) for x in range(0, 296, 4)]
        self.assertEqual(make.rests_line(Path("/nonexistent.mp4"), full, 300.0, []), "")

    def test_too_many_designed_sounds_are_sound_slop(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        bounds = [0, 5, 10, 15, 20, 25, 30]
        info = lambda sfx: {"frames": 720, "fps": 24, "sfx": sfx}
        whooshes = [[c - 0.35, "whoosh", 0.7] for c in (5, 10, 15, 20, 25)]
        line = make.sound_budget_line(info(whooshes), bounds)
        self.assertIn("5 whooshes in 30 s (at most 2", line)
        self.assertIn("a designed sound on 5 of 5 cuts", line)
        calm = [[9.65, "whoosh", 0.7], [20, "hit", None], [27, "tick", None]]
        self.assertEqual(make.sound_budget_line(info(calm), bounds), "")
        self.assertEqual(make.sound_budget_line({"frames": 720, "fps": 24}, bounds), "")   # an older film reports none

    def test_a_film_whose_picture_acts_in_silence_is_sound_thin(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        info = lambda sfx: {"frames": 45 * 24, "fps": 24, "sfx": sfx}
        sparse = [[2, "hit", None], [15, "hit", None], [37.5, "riser", 2.0], [39.5, "hit", None]]
        with tempfile.TemporaryDirectory() as tmp, patch.object(make, "REVIEW", Path(tmp)):
            line = make.sound_thin_line(info(sparse), None, "")
            self.assertIn("3 event sounds in 45 s (at least 11)", line)
            self.assertIn("no review/sound-audit.md", line)
            plan = {"layers": [{"bus": "music"}, {"bus": "dialogue"}, {"bus": "ambience"}]
                    + [{"bus": "sfx"} for _ in range(6)] + [{"bus": "foley"} for _ in range(2)]}
            (Path(tmp) / "sound-audit.md").write_text("events 14 · sounded 14\n", encoding="utf-8")
            self.assertEqual(make.sound_thin_line(info(sparse), plan, ""), "")
            (Path(tmp) / "sound-audit.md").write_text("events 20 · sounded 11\n", encoding="utf-8")
            self.assertIn("the audit sounds 11 of 20 events", make.sound_thin_line(info(sparse), plan, ""))
            self.assertEqual(make.sound_thin_line(info([]), None, "- **Âm thanh / Sound:** music only, by choice"), "")

    def test_music_without_a_beat_under_a_lively_card_and_the_same_players_again(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=110:d=8", f"{tmp}/drone.wav"], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "aevalsrc='sin(2*PI*60*t)*exp(-30*mod(t,0.5))':d=8", f"{tmp}/beat.wav"], check=True)
            bounds = [0, 2, 4, 6, 8]
            with patch.object(make, "SHOWN_MUSIC", t / "music.json"), patch.object(make, "PROJECT", t / "a"):
                self.assertIn("MUSIC WITHOUT A BEAT", make.music_line(t / "none.html", t / "drone.wav", "tempo energetic", bounds))
                self.assertIn("MUSIC WITHOUT A BEAT", make.music_line(t / "none.html", t / "drone.wav", "tempo 4 shots", bounds))
                self.assertEqual(make.music_line(t / "none.html", t / "beat.wav", "tempo energetic", bounds), "")
                self.assertEqual(make.music_line(t / "none.html", t / "drone.wav",
                                                 "tempo energetic\n- **Music:** ambient tension, the night is waiting", bounds), "")
                self.assertEqual(make.music_line(t / "none.html", t / "drone.wav", "tempo contemplative", [0, 8]), "")
                (t / "own.html").write_text("const OWN_MUSIC = { file: 'audio/music.wav', gain: 0.9 };\n", encoding="utf-8")
                self.assertEqual(make.music_line(t / "own.html", t / "drone.wav", "tempo energetic", bounds), "")
                film = t / "film.html"
                film.write_text("const INSTRUMENTS = ['glock', 'harp'];\nfunction score(ctx, out) {\n  pad(ctx, out, 0, 4, [220], 0.1);\n"
                                "  kick(ctx, out, 0, 0.5);\n}\n", encoding="utf-8")
                self.assertEqual(make.music_palette(film), {"glock", "harp", "pad", "kick"})
                for name in ("a", "b"):
                    make.PROJECT = t / name
                    first = make.music_line(film, t / "beat.wav", "", bounds)
                self.assertIn("glock, harp, pad again", first)
                make.PROJECT = t / "c"
                film.write_text("const INSTRUMENTS = ['marimba'];\nfunction score(ctx, out) {\n  kick(ctx, out, 0, 0.5);\n}\n")
                self.assertEqual(make.music_line(film, t / "beat.wav", "", bounds), "")

    def test_a_film_with_no_bright_stretch_is_too_dark(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        with tempfile.TemporaryDirectory() as tmp:
            for name, colour in (("dark", "0x141414"), ("lit", "0x8a8a8a")):
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=320x180:d=6",
                                "-pix_fmt", "yuv420p", f"{tmp}/{name}.mp4"], check=True)
            self.assertTrue(make.too_dark_line(f"{tmp}/dark.mp4").startswith("TOO DARK"))
            self.assertEqual(make.too_dark_line(f"{tmp}/lit.mp4"), "")

    def test_an_ad_end_card_over_four_seconds_is_held_back(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        ad, film = "- **Purpose:** ad & product", "- **Purpose:** cinematic"
        self.assertTrue(make.end_card_line([0, 3, 7, 12, 18, 24, 30], ad).startswith("LONG END CARD: the last scene holds 6.0 s"))
        self.assertEqual(make.end_card_line([0, 3, 7, 12, 18, 26.5, 30], ad), "")
        self.assertEqual(make.end_card_line([0, 3, 7, 12, 18, 24, 30], film), "")

    def test_suggest_gives_six_different_candidates_or_leaves_a_named_look_to_the_model(self):
        run = lambda q: subprocess.run([sys.executable, ROOT / "scripts" / "styles.py", "suggest", q],
                                       capture_output=True, text=True).stdout.splitlines()
        out = run("một tay vợt trên sân quần vợt ban đêm")
        self.assertEqual(len(out), 6)
        ids = [l.split(" · ")[0].split(". ")[1] for l in out]
        self.assertEqual(len(set(ids)), 6)
        self.assertEqual(out, run("một tay vợt trên sân quần vợt ban đêm"))   # the same idea, the same six
        self.assertNotEqual(out, run("quảng cáo 30 giây cho thương hiệu cà phê của tôi"))
        named = run("chuyện một khu vườn đất nặn, kiểu aardman")
        self.assertTrue(named[0].startswith("named look: aardman"), "the name as the user said it")
        self.assertIn("brick-toy", " ".join(l for l in named if " · named · " in l))
        self.assertNotIn("a contrast", " ".join(named))   # a named look is never padded with unrelated styles
        plain = run("giới thiệu điện ảnh 40 giây: bát gốm làm tay")
        self.assertEqual(len(plain), 6)                    # a genre word is not a name
        self.assertNotIn("named", " ".join(plain))
        self.assertEqual(run("một phim phiêu lưu kiểu DreamWorks")[1:], [])   # a name without a recipe brings no filler

    def test_style_search_ranks_words_and_falls_back_to_the_family(self):
        run = lambda q: subprocess.run([sys.executable, ROOT / "scripts" / "styles.py", "list", "--q", q],
                                       capture_output=True, text=True).stdout.splitlines()
        out = run("Aardman gibi plastilin")
        self.assertIn('known name "aardman"', out[0])
        self.assertTrue(out[1].startswith("brick-toy ·"))
        self.assertEqual(out[-1], f"(1 of {len(json.loads((ROOT / "styles" / "index.json").read_text(encoding="utf-8"))["styles"])})")
        out = run("pixar gibi")
        self.assertIn("family pastel-storybook", out[0])
        self.assertTrue(all("· pastel-storybook ·" in l for l in out[1:-1]) and len(out) > 2)
        self.assertNotEqual(run("quảng cáo cà phê ấm áp")[-1], "(0 of 73)")

    def test_a_format_brings_the_language_and_never_the_old_film(self):
        fmt_root, src = self.root / "formats", self.root / "src"
        env = dict(os.environ, RUBYDAI_VIDEO_FORMATS=str(fmt_root), HOME=str(self.root))
        ran([sys.executable, ROOT / "scripts" / "init_film.py", str(src), "--quick"], env=env, capture_output=True)
        import re as _re
        old = (src / "film.html").read_text(encoding="utf-8")
        a = old.find("function score(ctx, out) {"); b = old.find("\n}\n", a)
        old = old[:a] + ("function score(ctx, out) {\n  // OLD FILM SCORE MARK\n  for (const h of grid('kick', 'X...x...X...x...')) "
                         "kick(ctx, out, h.t, 0.5);\n  pad(ctx, out, 0, 8, chord('Am7', 3), 0.05);") + old[b:]
        (src / "film.html").write_text(old, encoding="utf-8")
        subprocess.run([sys.executable, ROOT / "scripts" / "formats.py", "save", "miknatis", "--src", str(src), "--rhythm", "6 beats",
                        "--hook", "a magnet snaps into frame", "--ending", "the magnet lets go", "--keep", "the film ends on the same three-note motif"],
                       env=env, capture_output=True, check=True)
        text = (fmt_root / "miknatis" / "FORMAT.md").read_text(encoding="utf-8")
        for line in ("## The language", "Palette logic", "Sound language", "## Always new", "the music itself",
                     "## Kept on purpose", "- the film ends on the same three-note motif"):
            self.assertIn(line, text)
        new = self.root / "new"
        subprocess.run([sys.executable, ROOT / "scripts" / "init_film.py", str(new), "--quick", "--format", "miknatis"], env=env,
                       capture_output=True, check=True)
        self.assertNotIn("OLD FILM SCORE MARK", (new / "film.html").read_text(encoding="utf-8"))   # a fresh template
        self.assertIn("OLD FILM SCORE MARK", (new / "research" / "format-reference.html").read_text(encoding="utf-8"))
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        with patch.object(make, "PROJECT", new):
            mine = (new / "film.html").read_text(encoding="utf-8")
            a = mine.find("function score(ctx, out) {"); b = mine.find("\n}\n", a)
            (new / "film.html").write_text(mine[:a] + "function score(ctx, out) {\n  for (const h of grid('hat', 'x.x.x.x.x.x.x.x.', "
                                           "{ swing: 0.2 })) hat(ctx, out, h.t, 0.04);\n  bass(ctx, out, 0, 2, hz('E1'), 0.2);"
                                           + mine[b:], encoding="utf-8")
            self.assertEqual(make.format_copy_line(new / "film.html"), "")
            (new / "film.html").write_text((new / "research" / "format-reference.html").read_text(encoding="utf-8"), encoding="utf-8")
            self.assertIn("FORMAT COPY: the score", make.format_copy_line(new / "film.html"))

    def test_missing_format_leaves_no_folder(self):
        target = self.root / "new-film"
        r = subprocess.run([sys.executable, ROOT / "scripts" / "init_film.py", target, "--quick", "--format", "nope"],
                           capture_output=True, text=True, env=dict(os.environ, RUBYDAI_VIDEO_FORMATS=str(self.root / "fmts")))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no saved format named nope", r.stderr)
        self.assertFalse(target.exists())
        ran([sys.executable, ROOT / "scripts" / "init_film.py", target, "--quick"], capture_output=True)
        self.assertTrue((target / "notes").is_dir())

    def test_other_aspect_becomes_a_named_variant(self):
        state = self.root / "STATE.md"
        state.write_text("- **Format:** 8 s, 9:16, 1080x1920, 24 fps\n", encoding="utf-8")
        args = lambda size, variant=None: type("A", (), {"size": size, "variant": variant})()
        with patch.object(make, "PROJECT", self.root):
            self.assertEqual(make.variant_of(args(None), None), "")
            self.assertEqual(make.variant_of(args("720x1280"), (720, 1280)), "")
            self.assertEqual(make.variant_of(args("1080x1080"), (1080, 1080)), "1x1")
            self.assertEqual(make.variant_of(args("1920x1080"), (1920, 1080)), "16x9")
            self.assertEqual(make.variant_of(args(None, "story cut"), None), "story-cut")
            (self.root / "STATE.md").write_text("- **Format:** <length, aspect, size, fps>\n", encoding="utf-8")
            self.assertEqual(make.variant_of(args("240x240"), (240, 240), lambda: (1080, 1920)), "1x1")
            self.assertEqual(make.variant_of(args("540x960"), (540, 960), lambda: (1080, 1920)), "")

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_pop_and_loop_checks(self):
        clip, pop = self.root / "clip.mp4", self.root / "pop.mp4"
        src = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=2"]
        subprocess.run(src + ["-pix_fmt", "yuv420p", clip], check=True)
        subprocess.run(src + ["-vf", "drawbox=enable='eq(n,20)':x=0:y=0:w=iw:h=ih:color=white:t=fill",
                              "-pix_fmt", "yuv420p", pop], check=True)
        check = lambda kind, f: subprocess.run([sys.executable, ROOT / "scripts" / "scene_check.py", kind, f],
                                               capture_output=True, text=True)
        self.assertEqual(check("pops", clip).returncode, 0)
        p = check("pops", pop)
        self.assertEqual(p.returncode, 1)
        self.assertIn("frame 20 ", p.stdout)
        self.assertIn("JUMP", check("loop", clip).stdout)

    def test_key_file_opens_with_an_empty_line_and_stays_private(self):
        store = self.root / "keys.env"
        os.environ["RUBYDAI_VIDEO_KEYS"] = str(store)
        self.addCleanup(os.environ.pop, "RUBYDAI_VIDEO_KEYS", None)
        opened = []
        real = subprocess.Popen
        subprocess.Popen = lambda cmd, **kw: opened.append(cmd)
        try:
            with __import__("contextlib").redirect_stdout(__import__("io").StringIO()):
                keys.cmd_open(type("A", (), {"name": "gemini_api_key"})())
        finally:
            subprocess.Popen = real
        self.assertIn("GEMINI_API_KEY=\n", store.read_text(encoding="utf-8"))
        if os.name != "nt":                      # Windows keeps a user's files private by the profile's own rights
            self.assertEqual(oct(store.stat().st_mode)[-3:], "600")
        self.assertEqual(len(opened), 1)

    def test_font_search_follows_tone_and_leaves_out_house_defaults(self):
        vi = ["latin", "latin-ext", "vietnamese"]
        cat = {"kablammo": {"id": "kablammo", "family": "Kablammo", "category": "display", "license": "OFL-1.1",
                            "subsets": vi, "defSubset": "latin", "weights": [400], "variable": True},
               "inter": {"id": "inter", "family": "Inter", "category": "sans-serif", "license": "OFL-1.1",
                         "subsets": vi, "defSubset": "latin", "weights": [400, 700]},
               "noto-sans-avestan": {"id": "noto-sans-avestan", "family": "Noto Sans Avestan", "category": "sans-serif",
                                     "license": "OFL-1.1", "subsets": ["avestan"] + vi,
                                     "defSubset": "latin", "weights": [400]},
               "latin-only": {"id": "latin-only", "family": "Latin Only", "category": "display", "license": "OFL-1.1",
                              "subsets": ["latin"], "defSubset": "latin", "weights": [400]},
               "no-horn": {"id": "no-horn", "family": "No Horn", "category": "display", "license": "OFL-1.1",
                           "subsets": vi, "defSubset": "latin", "weights": [400]},
               "kana-face": {"id": "kana-face", "family": "Kana Face", "category": "display", "license": "OFL-1.1",
                             "subsets": ["japanese", "latin"], "defSubset": "latin", "weights": [400]}}
        tg = {"kablammo": {"/Expressive/Playful": 95}, "inter": {"/Expressive/Playful": 99},
              "noto sans avestan": {"/Expressive/Playful": 99}, "latin only": {"/Expressive/Playful": 99},
              "no horn": {"/Expressive/Playful": 97}, "kana face": {"/Expressive/Playful": 90}}
        out = io.StringIO()
        checked = lambda cands, lang="vi": {fid: fid != "no-horn" for fid, _ in cands}
        search = lambda tone, lang: fonts.cmd_search(type("A", (), {"tone": tone, "role": "display", "category": None, "n": 5,
                                                                    "latin_only": False, "allow_common": False, "lang": lang})())
        with patch.object(fonts, "catalogue", return_value=cat), patch.object(fonts, "tags", return_value=tg), \
                patch.object(fonts, "verify_letters", side_effect=checked), contextlib.redirect_stdout(out):
            search("hài hước hoạt hình", "vi")
        text = out.getvalue()
        self.assertIn("kablammo", text)
        listed = text.split("\n", 2)[2].split("(left out")[0]
        for absent in ("inter", "avestan", "latin-only", "no-horn", "kana-face"):
            self.assertNotIn(absent, listed)
        self.assertIn("missing Ơ Ư ầ ệ in the font itself: no-horn", text)
        out = io.StringIO()
        with patch.object(fonts, "catalogue", return_value=cat), patch.object(fonts, "tags", return_value=tg), \
                contextlib.redirect_stdout(out):
            search("コメディ", "ja")
        listed = out.getvalue().split("\n", 1)[1]
        self.assertIn("kana-face", listed, "a Japanese film is offered the faces with a japanese subset")
        self.assertNotIn("kablammo", listed)
        self.assertEqual(fonts.tone_tags("HÀI HƯỚC")[0], fonts.tone_tags("hài hước")[0])

    def test_an_even_rhythm_and_a_broken_tempo_promise_are_named(self):
        self.assertEqual(make.rhythm_line([0, 5, 9.5, 14.5, 19.5, 25], ""), "")         # five scenes of a short film
        even = [0] + [3.2 + 6.3 * i for i in range(19)]
        line = make.rhythm_line(even, "- **Director card:** **Tempo:** energetic · 120 BPM")
        self.assertIn("EVEN RHYTHM", line)
        self.assertIn("the card says about 4 s", line)
        self.assertEqual(make.rhythm_line([0, 1.5, 4, 9, 11, 18, 20, 26, 30], "Tempo: standart"), "")

    def test_a_delivered_draft_waits_for_the_users_notes(self):
        with patch.object(make, "PROJECT", self.root), patch.object(make, "LOGS", self.root / "logs"):
            (self.root / "logs").mkdir()
            self.assertEqual(make.draft_gate(), {})
            (self.root / "logs" / make.GATE).write_text('{"held": false, "delivered": {"version": 1, "file": "x.mp4", '
                                                       '"time": 1000}}', encoding="utf-8")
            self.assertEqual(make.draft_gate()["delivered"]["version"], 1)
            self.assertFalse(make.notes_since(1000))
            (self.root / "notes").mkdir()
            (self.root / "notes" / "round-1.md").write_text("- faster", encoding="utf-8")
            self.assertTrue(make.notes_since(1000))

    def test_a_still_or_repetitive_film_is_flagged(self):
        report = self.root / "r.txt"
        rows = "".join(f"     #{i} 00:{2*i:02d}.00-00:{2*i+2:02d}.00  residual 0.10  total 0.10  CHECK: nothing moves\n"
                       for i in range(1, 7)) + "".join(f"     #{i} 00:{2*i:02d}.00-00:{2*i+2:02d}.00  residual 3.0  total 3.0  ok\n"
                                                         for i in range(7, 11))
        report.write_text("== action per scene (camera move removed):\n" + rows +
                          "== repeated compositions (the same picture again, 6 s or more later; 32 px grey): 2 repeats, 4 s of 20\n"
                          "     00:12.00-00:14.00 repeats 00:02.00-00:04.00\n", encoding="utf-8")
        issues = make.report_lines(report, [0, 20])[2]
        self.assertTrue(any(i.startswith("TOO STILL: 6 of 10") for i in issues))
        self.assertTrue(any(i.startswith("TOO REPETITIVE: 4 of 20") for i in issues))
        self.assertTrue(any(i.startswith("repeated pictures 4 s: 00:12 = 00:02") for i in issues))

    def test_frozen_spans_read_across_lines_and_aspect_words_set_the_size(self):
        report = self.root / "r.txt"
        report.write_text("== frozen intervals (>= 1.5 s):\nlavfi.freezedetect.freeze_start: 2.5\n"
                          "lavfi.freezedetect.freeze_duration: 2\nlavfi.freezedetect.freeze_end: 4.5\n(grain hides)\n",
                          encoding="utf-8")
        self.assertIn("frozen 2.5–4.5 s", make.report_lines(report, [0, 8])[2])
        report.write_text("== black intervals:\nblack_start:20.0 black_end:23.5\nblack_start:58.2 black_end:60\n", encoding="utf-8")
        issues = make.report_lines(report, [0, 60])[2]
        self.assertTrue(any(i.startswith("LONG BLACK 20.0–23.5 s") for i in issues))
        self.assertFalse(any("58.2" in i for i in issues if i.startswith("LONG BLACK")))
        with patch.object(make, "PROJECT", self.root):
            for line, size in (("60 s, 16:9, 24 fps", (1920, 1080)), ("30 giây, dọc", (1080, 1920)),
                               ("vuông 15 giây", (1080, 1080)), ("30 s, 720x1280", (720, 1280))):
                (self.root / "STATE.md").write_text(f"- **Format source:** none\n- **Format:** {line}\n", encoding="utf-8")
                self.assertEqual(make.frame_size(None), size)

    def test_style_recipes_deal_type_through_their_family(self):
        import type_deal
        lib = json.loads((ROOT / "references" / "type-library.json").read_text(encoding="utf-8"))
        ids = [st["id"] for st in json.loads((ROOT / "styles" / "index.json").read_text(encoding="utf-8"))["styles"]]
        self.assertTrue(all(type_deal.look_families(lib, i) for i in ids))
        self.assertEqual(type_deal.mood_tags("TÀI LIỆU")[0], type_deal.mood_tags("tài liệu")[0])
        self.assertTrue(type_deal.mood_tags("tài liệu")[0], "a two-syllable Vietnamese tone is found")
        self.assertEqual(type_deal.mood_tags("KIDS")[0], type_deal.mood_tags("kids")[0])

    def test_a_film_at_the_root_is_shelved_and_never_nested(self):
        kit = [sys.executable, str(ROOT / "scripts" / "init_film.py")]
        shelf = self.root / "Phim"
        ran(kit + [str(shelf), "--quick"], capture_output=True)
        state = shelf / "STATE.md"
        state.write_text("# State: Chìa Khóa Mất (Quick mode)\n" + state.read_text(encoding="utf-8").split("\n", 1)[1],
                         encoding="utf-8")
        r = subprocess.run(kit + [str(shelf / "moi"), "--quick"], capture_output=True, text=True)
        self.assertIn("WHICH FOLDER", r.stderr)
        self.assertFalse((shelf / "moi").exists())
        ran(kit + [str(shelf), "--shelve"], capture_output=True)
        self.assertTrue((shelf / "chia-khoa-mat" / "film.html").is_file())
        self.assertFalse((shelf / "film.html").exists())
        ran(kit + [str(shelf / "moi"), "--quick"], capture_output=True)
        r = subprocess.run(kit + [str(shelf / "chia-khoa-mat" / "khac"), "--quick"], capture_output=True, text=True)
        self.assertIn("INSIDE A FILM", r.stderr)
        home = self.root / "home"
        (home / "Desktop").mkdir(parents=True)
        (home / "notes.txt").write_text("x", encoding="utf-8")
        out = subprocess.run(kit + ["meo", "--quick", "--films-folder", "Phim"], cwd=home, capture_output=True,
                             text=True, check=True).stdout
        self.assertTrue((home / "Phim" / "meo" / "film.html").is_file(), out)
        ran(kit + ["cho", "--quick"], cwd=home, capture_output=True)
        self.assertTrue((home / "cho" / "film.html").is_file(), "no films folder asked for: the folder given")
        self.assertFalse((home / "Phim" / "cho").exists(), "a films folder nearby is never picked on its own")
        ran(kit + ["vit", "--quick", "--films-folder", "Videos"], cwd=home, capture_output=True)
        self.assertTrue((home / "Videos" / "vit" / "film.html").is_file(), "the films folder the user named")
        self.assertFalse((home / "Phim" / "vit").exists(), "never another films folder instead of the named one")

    def test_handoff_opens_the_right_kind_of_new_chat(self):
        (self.root / "STATE.md").write_text("# State: X\n", encoding="utf-8")
        run = lambda entry, *extra: subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "handoff.py"), "--folder", str(self.root), "--dry-run", *extra],
            capture_output=True, text=True, env=dict(os.environ, CLAUDE_CODE_ENTRYPOINT=entry)).stdout
        if sys.platform == "darwin":
            self.assertIn("mcp__ccd_session__start_session", run("claude-desktop"))
            self.assertIn("mcp__ccd_session__start_session", run("local-agent"))
            self.assertIn("claude://code/new?folder=", run("claude-desktop", "--link"))
            self.assertIn("q=Ti%E1%BA%BFp+t%E1%BB%A5c+t%E1%BB%AB+STATE.md", run("local-agent", "--link"))
            self.assertIn("new Terminal window", run("cli"))
        self.assertIn("Continue from STATE.md", run("claude-vscode", "--lang", "en"))

    def test_a_throwaway_chat_folder_sends_films_home(self):
        import init_film
        home = self.root / "home"
        (home / "Filmler").mkdir(parents=True)
        with patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
            got = init_film.films_folder(str(self.root / "Claude" / "scratch-workspaces" / "x"), "Filmler")
        self.assertEqual(got, str(home / "Filmler"))
        chat = self.root / "Claude" / "scratch-workspaces" / "x"
        chat.mkdir(parents=True)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "init_film.py"), "road-trip", "--quick", "--films-folder",
                            "Filmler"], cwd=chat, env=dict(self.env, HOME=str(home), USERPROFILE=str(home)),
                           capture_output=True, text=True)
        self.assertTrue((home / "Filmler" / "road-trip" / "STATE.md").is_file(), r.stdout + r.stderr)
        self.assertIn("OUTSIDE THIS CHAT", r.stdout, "the chat moves into a film it cannot show files from")
        self.assertEqual(init_film.outside_chat(str(chat / "film"), str(chat)), "", "a film inside the chat's folder")

    def test_agents_md_keeps_the_users_own_lines(self):
        import init_film
        path = self.root / "AGENTS.md"
        init_film.write_agents(path, "# kit v1\n")
        path.write_text(path.read_text(encoding="utf-8") + "PROJECT RULE: keep the logo\n", encoding="utf-8")
        self.assertTrue(init_film.write_agents(path, "# kit v2\n"))
        text = path.read_text(encoding="utf-8")
        self.assertIn("# kit v2", text)
        self.assertNotIn("# kit v1", text)
        self.assertIn("PROJECT RULE: keep the logo", text)
        self.assertEqual(text.count(init_film.BEGIN), 1)
        path.write_text("an older pointer\nMY RULE\n", encoding="utf-8")
        init_film.write_agents(path, "# kit v3\n")
        self.assertTrue(path.read_text(encoding="utf-8").startswith(init_film.BEGIN))
        self.assertIn("MY RULE", path.read_text(encoding="utf-8"))

    def test_mix_plan_never_writes_into_the_users_music(self):
        (self.root / "audio").mkdir()
        (self.root / "film.html").write_text("const OWN_MUSIC = { file: 'audio/music.wav', gain: 0.8 };", encoding="utf-8")
        (self.root / "audio" / "mix.json").write_text(json.dumps({"layers": [{"file": "audio/music.wav", "bus": "music"}]}),
                                                       encoding="utf-8")
        with patch.object(make, "PROJECT", self.root):
            score, plan = make.sound_plan("film.html")
        self.assertEqual(score.name, "film.wav")
        self.assertEqual(plan["layers"][0]["file"], os.path.join("audio", "film.wav"))

    def test_a_bare_camera_line_on_the_second_shot_is_read(self):
        import validate_shots
        self.assertEqual(validate_shots.camera_move({"camera": "truck, 3 s, slow ease-in-out"})["type"], "move")
        self.assertEqual(validate_shots.camera_move({"camera": {"move": "locked, 2 s"}})["type"], "locked")
        self.assertEqual(validate_shots.camera_move({}), {})

    def test_words_check_stops_on_a_dash_and_flags_generated_lines(self):
        import words_check
        items = [("a", "Không chỉ là chiếc xe đạp — mà còn là một hành trình."), ("b", "Tiệm mở lúc 9 giờ, 1–3 người làm."),
                 ("c", "Đứa trẻ giật quả bóng, chạy mất."), ("d", "Gió thì thầm."), ("e", "Đừng bỏ lỡ!"),
                 ("f", "Hy vọng, can đảm và yêu thương."), ("g", "KIDS PLAY")]
        dashes, tells = words_check.check(items)
        self.assertEqual([w for w, _ in dashes], ["a"])
        flagged = {w for w, _, _ in tells}
        self.assertTrue({"a", "d", "e", "f"} <= flagged)
        self.assertFalse({"b", "c", "g"} & flagged)
        page = self.root / "film.html"
        page.write_text("// ============================== FILM ==============================\n"
                        "const TITLE = 'Xe đạp, ngoạn mục';  // a comment — with a dash\nconst F = 'audio/music.wav';\n"
                        "// ============================== HELPERS (picture) ==============================\n"
                        "const X = 'helper — text';\n", encoding="utf-8")
        self.assertEqual([s for _, s in words_check.film_words(str(page))], ["Xe đạp, ngoạn mục"])

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_sample_labels_an_octave_off_are_measured_and_corrected(self):
        import samples
        tone = self.root / "c5.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=523.25:d=0.6", tone], check=True)
        self.assertEqual(samples.octave_shift(str(tone), 60), 1)     # labelled C4, sounds C5
        self.assertEqual(samples.octave_shift(str(tone), 72), 0)

    def test_sample_takes_are_read_from_file_names_and_spread_over_the_range(self):
        import samples
        self.assertEqual(samples.parse("VlnEns_susVib_A#2_v1.wav")[:2], (46, 1))
        self.assertEqual(samples.parse("Player_vl2_rr1_A-1.wav"), (9, 2, 1))
        self.assertEqual(samples.parse("KSHarp_A2_mf.wav")[:2], (45, 5))
        self.assertEqual(samples.parse("Darbuka_1_hit_vl1_rr1.wav")[0], None)
        self.assertEqual(samples.parse("Cajon_hit1_f_rr2.wav")[0], None)
        self.assertEqual(samples.local_name("sax", "/c/Brett Tenor_F#3 x.flac"), "sax/Brett_Tenor_Fs3_x.flac")
        names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        notes = {f"X_{n}{o}_v{v}_rr{r}.wav": 1000 for n in names for o in (3, 4) for v in (1, 2, 3) for r in (1, 2)}
        takes = samples.choose(notes)
        midi = sorted(samples.parse(t)[0] for t in takes)
        self.assertLessEqual(len(takes), samples.MAX_NOTES)
        self.assertEqual((midi[0], midi[-1]), (48, 71))                  # two octaves: all of it, ends included
        self.assertTrue(all(b - a <= samples.MAX_GAP for a, b in zip(midi, midi[1:])))
        wide = samples.choose({f"X_{n}{o}_v1.wav": 1 for n in names for o in range(1, 8)})
        wm = sorted(samples.parse(t)[0] for t in wide)
        self.assertEqual(len(wm), samples.MAX_NOTES)                     # seven octaves: the middle, tightly spaced
        self.assertTrue(all(b - a <= samples.MAX_GAP for a, b in zip(wm, wm[1:])))
        self.assertTrue(wm[0] > 24 and wm[-1] < 107)
        hats = {f"HiHat_{k}_rr1_Mid.wav": 1 for k in ("Close", "HitC_v1", "HitC_v2", "HitO", "HitLoose")}
        self.assertEqual(sorted(samples.choose(hats, samples.CATALOG["hihat"][2])), ["HiHat_HitC_v1_rr1_Mid.wav", "HiHat_HitC_v2_rr1_Mid.wav"])
        self.assertEqual(samples.FULLER["vibraphone"], "vibes")
        self.assertTrue(all("_v2_rr1" in t for t in takes))              # the middle velocity, the first take
        hits = samples.choose({f"Drum_hit{k}_v{v}_rr{r}.wav": 1 for k in (1, 2) for v in range(1, 6) for r in (1, 2)})
        self.assertEqual(len(hits), samples.MAX_HITS)
        self.assertTrue(all("rr1" in h for h in hits))

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_music_candidates_are_previews_until_one_is_picked(self):
        track = self.root / "track.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=60", "-b:a", "128k", track], check=True)
        res = self.root / "results.json"
        res.write_text(json.dumps({"results": [{"n": 1, "source": "wikimedia", "id": "1", "title": "Big Band", "creator": "X",
                                                "licence": "pd", "page": "p", "file": str(track), "type": "music"}]}))
        run = lambda *extra: subprocess.run([sys.executable, str(ROOT / "scripts" / "asset_search.py"), "fetch", "--results",
                                             str(res), "--pick", "1", "--dest", str(self.root / "cand"),
                                             "--licenses", str(self.root / "L.csv"), *extra], capture_output=True, text=True)
        self.assertIn("first 30 s", run("--preview", "30").stdout)
        got = next((self.root / "cand").glob("*-preview.mp3"))
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", got],
                                   capture_output=True, text=True).stdout)
        self.assertAlmostEqual(dur, 30, delta=1)
        self.assertFalse((self.root / "L.csv").exists())

    def test_the_whole_narration_waits_for_an_audition(self):
        lines = self.root / "vo-lines.json"
        lines.write_text(json.dumps({"lines": [{"id": f"VO{i}", "text": "a line"} for i in range(6)]}), encoding="utf-8")
        run = lambda *extra: subprocess.run([sys.executable, str(ROOT / "scripts" / "tts.py"), "--lines", str(lines), "--out",
                                             str(self.root / "vo"), "--voice", "x", *extra], capture_output=True, text=True,
                                            cwd=self.root)
        self.assertIn("first --audition", run().stderr)                  # stops before any key is read
        sys.path.insert(0, str(ROOT / "scripts"))
        import tts
        self.assertFalse(tts.auditioned(str(self.root)))
        (self.root / "audio" / "audition").mkdir(parents=True)
        (self.root / "audio" / "audition" / "AUDITION.json").write_text("{}", encoding="utf-8")
        self.assertTrue(tts.auditioned(str(self.root)))

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_a_downloaded_effect_with_silence_first_is_named_late(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        sfx = self.root / "audio" / "sfx"
        sfx.mkdir(parents=True)
        tone = "sine=f=800:d=0.3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.25", "-f", "lavfi",
                        "-i", tone, "-filter_complex", "[1]aresample=48000[t];[0][t]concat=n=2:v=0:a=1", str(sfx / "late.wav")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", tone, "-ar", "48000", str(sfx / "tight.wav")], check=True)
        plan = {"layers": [{"file": "audio/sfx/late.wav", "at": 5.0, "bus": "sfx"},
                           {"file": "audio/sfx/tight.wav", "at": 7.0, "bus": "foley"},
                           {"file": "audio/sfx/late.wav", "at": 9.0, "bus": "sfx", "trim": [0.25, 0.5]}]}
        with patch.object(make, "PROJECT", self.root):
            line = make.sound_sync_line(plan)
        self.assertRegex(line, r"audio/sfx/late\.wav at 5\.00 s is heard at 5\.2\d s \(move 'at' to 4\.7\d")
        self.assertNotIn("tight.wav", line)
        self.assertNotIn("at 9.00", line)
        for name in ("impact-30.wav", "pad-30.wav"):                       # 30 ms of silence first
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.03", "-f",
                            "lavfi", "-i", tone, "-filter_complex", "[1]aresample=48000[t];[0][t]concat=n=2:v=0:a=1",
                            str(sfx / name)], check=True)
        plan = {"layers": [{"file": "audio/sfx/impact-30.wav", "at": 2.0, "bus": "sfx"},
                           {"file": "audio/sfx/pad-30.wav", "at": 3.0, "bus": "sfx"}]}
        with patch.object(make, "PROJECT", self.root):
            line = make.sound_sync_line(plan)
        self.assertIn("impact-30.wav", line)
        self.assertNotIn("pad-30.wav", line)

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_a_render_that_would_fill_the_disk_stops_first(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make, collections
        usage = collections.namedtuple("usage", "total used free")
        with patch.object(make, "PROJECT", self.root), patch.object(make.shutil, "disk_usage", return_value=usage(1, 1, 200e6)):
            self.assertIn("needs about", make.disk_short(60, "10M"))
        with patch.object(make, "PROJECT", self.root), patch.object(make.shutil, "disk_usage", return_value=usage(1, 1, 50e9)):
            self.assertEqual(make.disk_short(60, "10M"), "")

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_sound_and_picture_start_together(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        good, bad = self.root / "good.mp4", self.root / "bad.mp4"
        src = ["-f", "lavfi", "-i", "color=c=gray:s=64x36:d=1:r=24", "-f", "lavfi", "-i", "sine=f=440:d=1"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-shortest", "-pix_fmt", "yuv420p", str(good)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=64x36:d=1:r=24", "-itsoffset", "0.2",
                        "-f", "lavfi", "-i", "sine=f=440:d=1", "-pix_fmt", "yuv420p", str(bad)], check=True)
        self.assertEqual(make.av_start_line(good), "")
        self.assertIn("AV OFFSET", make.av_start_line(bad))

    def test_a_sample_that_does_not_match_its_pinned_commit_is_never_cached(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import samples
        good = b"RIFF....WAVEfmt the real sample"
        reply = lambda body: (lambda req, timeout=0: io.BytesIO(body))
        with patch.object(samples, "CACHE", str(self.root / "cache")), \
                patch.object(samples, "shas", return_value={"Piano/C4.wav": samples.blob_sha(good)}):
            with patch.object(samples.urllib.request, "urlopen", reply(good + b" altered")):
                with self.assertRaises(OSError):
                    samples.fetch("Piano/C4.wav")
            self.assertFalse((self.root / "cache" / "Piano" / "C4.wav").exists(), "a mismatch never enters the cache")
            with patch.object(samples.urllib.request, "urlopen", reply(good)):
                self.assertEqual(Path(samples.fetch("Piano/C4.wav")).read_bytes(), good)

    def test_a_sound_pack_is_cached_whole_or_not_at_all(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import sounds
        import zipfile as _zip
        page = b'<a href="https://kenney.nl/media/pages/assets/impact-sounds/x/pack.zip">Download</a>'
        good = io.BytesIO()
        with _zip.ZipFile(good, "w") as z:
            z.writestr("Audio/impactGlass_light_000.ogg", b"ogg")
            z.writestr("Audio/impactWood_heavy_000.ogg", b"WOODDATA")
            z.writestr("License.txt", b"CC0")
        bodies = []
        reply = lambda req, timeout=0: io.BytesIO(bodies.pop(0))
        with patch.object(sounds, "CACHE", self.root / "cache"), patch.object(sounds.urllib.request, "urlopen", reply):
            dest = self.root / "cache" / "kenney" / "impact-sounds"
            torn = good.getvalue().replace(b"WOODDATA", b"XXXXXXXX")       # the second sound fails its CRC mid-unpack
            bodies[:] = [page, torn]
            with self.assertRaises(Exception):
                sounds.download("impact")
            self.assertFalse(dest.exists(), "a broken download leaves no folder that library() would take as complete")
            self.assertEqual(list((self.root / "cache" / "kenney").iterdir()), [], "and no .part folder behind it")
            bodies[:] = [page, good.getvalue()]
            sounds.download("impact")
            self.assertEqual(sorted(f.name for f in dest.iterdir()),
                             ["License.txt", "SOURCE.txt", "impactGlass_light_000.ogg", "impactWood_heavy_000.ogg"])
            import hashlib as _h
            self.assertIn(f"sha256 {_h.sha256(good.getvalue()).hexdigest()}", (dest / "SOURCE.txt").read_text(encoding="utf-8"),
                          "the zip's checksum is kept beside the pack it made")

    @unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
    def test_ready_sounds_come_from_the_shared_cache_and_last_films_go_after_the_rest(self):
        cache, shown = self.root / "cache", self.root / "shown.json"
        for slug in ("impact-sounds", "interface-sounds", "ui-audio", "digital-audio", "rpg-audio", "casino-audio", "sci-fi-sounds"):
            (cache / "kenney" / slug).mkdir(parents=True)
        for name in ("impactGlass_light_000", "impactGlass_light_001", "impactWood_heavy_000"):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=900:d=0.2",
                            str(cache / "kenney" / "impact-sounds" / f"{name}.ogg")], check=True)
        env = dict(os.environ, RUBYDAI_VIDEO_SOUNDS_CACHE=str(cache), RUBYDAI_VIDEO_SHOWN_SOUNDS=str(shown))
        tool = [sys.executable, str(ROOT / "scripts" / "sounds.py")]
        film_a, film_b = self.root / "film-a", self.root / "film-b"
        film_a.mkdir(); film_b.mkdir()
        run = lambda cwd, *args: subprocess.run(tool + list(args), cwd=cwd, env=env, capture_output=True, text=True)
        first = run(film_a, "search", "kính nhẹ").stdout.splitlines()
        self.assertTrue(first[0].startswith("impact/impactGlass_light_000"))
        self.assertNotIn("impactWood", "\n".join(first[:2]))
        got = run(film_a, "get", "impact/impactGlass_light_000")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertTrue((film_a / "assets" / "sound" / "impact-impactGlass_light_000.wav").exists())
        self.assertIn("source=kenney", (film_a / "LICENSES.csv").read_text(encoding="utf-8"))
        later = run(film_b, "search", "glass light").stdout.splitlines()
        self.assertTrue(later[0].startswith("impact/impactGlass_light_001"))
        self.assertIn("impactGlass_light_000 · 0.2", "\n".join(later))
        self.assertIn("used in film-a", "\n".join(later))
        self.assertIn("are code", run(film_b, "search", "whoosh").stdout)
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        with patch.object(make, "PROJECT", film_a):
            make.credits_file("Kahve", "")
        self.assertIn("Sound effects: Kenney (kenney.nl), CC0", (film_a / "Kahve-credits.txt").read_text(encoding="utf-8"))

    def test_a_film_whose_every_effect_is_code_is_held(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        film = self.root / "film.html"
        film.write_text("const OWN_MUSIC = null;\n", encoding="utf-8")
        (self.root / "FORMAT.md").write_text("- **Sound language:** an open-licence electronic track around 120 BPM\n", encoding="utf-8")
        coded = {"layers": [{"bus": "music"}, {"bus": "dialogue"}]}
        ready = {"layers": [{"bus": "music"}, {"bus": "sfx", "file": "assets/sound/glass.wav"}]}
        (self.root / "LICENSES.csv").write_text("file,title\nassets/sound/glass.wav,impactGlass\n", encoding="utf-8")
        with patch.object(make, "PROJECT", self.root):
            line = make.sound_source_line(film, coded, "")
            self.assertIn("no ready or recorded effect", line)
            self.assertIn("the format's music is a recording", line)
            film.write_text("const OWN_MUSIC = { file: 'audio/music.wav', gain: 0.8 };\n", encoding="utf-8")
            self.assertEqual(make.sound_source_line(film, ready, ""), "")
            self.assertEqual(make.sound_source_line(film, coded, "look: 8-bit chiptune by choice"), "")

    def test_the_credits_go_beside_the_film_for_the_description(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        lic = self.root / "LICENSES.csv"
        lic.write_text("file,title,author,source_url,licence,licence_url,attribution_text,modifications,downloaded_at,used_in,notes\n"
                       "three.js,three.js,authors,,MIT,,three.js (MIT),none,,engine,software; loaded by import map\n"
                       "assets/a.jpg,Hives at dawn,Valley Archive,,CC BY 2.0,,\"\"\"Hives at dawn\"\" by Valley Archive, CC BY 2.0\",cropped,,s3,\n"
                       "audio/m.mp3,Meadow Song,Lena,,CC BY 4.0,,,none,,music,\n", encoding="utf-8")
        with patch.object(make, "PROJECT", self.root):
            line = make.credits_file("Kovan", "")
        self.assertIn("nothing goes on the picture", line)
        self.assertIn("IN CAPITALS", line)
        self.assertIn('"Hives at dawn" by Valley Archive, CC BY 2.0', line, "the lines travel in the message, not only the file")
        text = (self.root / "Kovan-credits.txt").read_text(encoding="utf-8")
        self.assertIn('"Hives at dawn" by Valley Archive, CC BY 2.0', text)
        self.assertIn('"Meadow Song" by Lena, CC BY 4.0', text)
        self.assertNotIn("three.js", text)

    def test_a_per_minute_limit_waits_and_a_daily_quota_stops(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import tts
        minute = RuntimeError('HTTP 429: {"error": {"status": "RESOURCE_EXHAUSTED", "details": [{"retryDelay": "21s"}]}}')
        day = RuntimeError('HTTP 429: {"error": {"message": "Quota exceeded for metric generate_requests_per_model_per_day"}}')
        calls, waits = [], []
        def flaky(*_):
            calls.append(1)
            if len(calls) < 3:
                raise minute
            return b"ok", "audio/wav"
        with patch.object(tts, "post", flaky):
            self.assertEqual(tts.post_patiently("u", {}, {}, wait=waits.append), (b"ok", "audio/wav"))
        self.assertEqual(waits, [23, 23])
        def spent(*_):
            raise day
        with patch.object(tts, "post", spent), self.assertRaises(tts.QuotaSpent):
            tts.post_patiently("u", {}, {}, wait=waits.append)
        self.assertEqual(len(waits), 2)

    def test_the_free_japanese_voice_asks_before_its_install(self):
        tts = [sys.executable, str(ROOT / "scripts" / "tts.py"), "--engine", "irodori", "--voice", "落ち着いた女性話者",
               "--text", "最初の行です。", "--out", str(self.root / "vo")]
        env = dict(os.environ, IRODORI_DIR=str(self.root / "no-irodori"))
        missing = subprocess.run(tts, capture_output=True, text=True, env=env)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("only if the user wants it: python3 tools/tts.py --install irodori", missing.stderr)
        self.assertFalse((self.root / "vo" / "VO1.wav").exists())
        dry = subprocess.run(tts + ["--dry-run"], capture_output=True, text=True, env=env)
        self.assertIn("VO1: irodori Aratako/Irodori-TTS-v4.1-Small voice=落ち着いた女性話者", dry.stdout)

    def test_a_voicevox_voice_writes_its_credit_and_terms(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import tts
        speakers = [{"name": "ずんだもん", "speaker_uuid": "u1", "styles": [{"name": "ノーマル", "id": 3, "type": "talk"}]}]
        info = {"policy": "「VOICEVOX:ずんだもん」とクレジットを記載すれば、商用・非商用で利用可能です。\nhttps://zunko.jp/con_ongen_kiyaku.html"}
        get = lambda path: speakers if path == "/speakers" else info
        film = self.root / "film"
        (film / "audio" / "vo").mkdir(parents=True)
        (film / "LICENSES.csv").write_text((ROOT / "templates" / "LICENSES.csv").read_text(encoding="utf-8"), encoding="utf-8")
        old = os.getcwd()
        os.chdir(film)
        try:
            with patch.object(tts, "voicevox_get", side_effect=get):
                self.assertEqual(tts.voicevox_voice("ずんだもん:ノーマル")[2], 3)
                self.assertEqual(tts.voicevox_voice("3")[0], "ずんだもん")
                with self.assertRaises(RuntimeError):
                    tts.voicevox_voice("存在しない")
                terms = tts.local_licence("voicevox", "ずんだもん", "audio/vo")
                tts.local_licence("voicevox", "ずんだもん", "audio/vo")          # a second run adds no second row
        finally:
            os.chdir(old)
        rows = (film / "LICENSES.csv").read_text(encoding="utf-8")
        self.assertEqual(rows.count("VOICEVOX:ずんだもん (ノーマル)"), 1)
        self.assertIn(",VOICEVOX:ずんだもん,", rows, "the credit the character's terms ask for goes into the credits")
        self.assertIn("https://zunko.jp/con_ongen_kiyaku.html", rows)
        self.assertIn("商用・非商用", (film / terms).read_text(encoding="utf-8"))

    def test_a_long_film_whose_narration_starts_late_is_named(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make
        film = self.root / "film.html"
        film.write_text("const VO = [\n  { id: 'VO1', at: 5.2, dur: 2.3 },\n];\n", encoding="utf-8")
        self.assertIn("NARRATION LATE", make.narration_line(film, 420))
        self.assertEqual(make.narration_line(film, 40), "")
        film.write_text("const VO = [{ id: 'VO1', at: 1.2, dur: 2.3 }];\n", encoding="utf-8")
        self.assertEqual(make.narration_line(film, 420), "")

    def test_a_large_sample_download_asks_the_user_first(self):
        import samples
        big = {"files": ([("Strings/X/a_C3_v1.wav", 48)], 40e6)}
        args = type("A", (), {"instruments": ["violins", "cellos"], "project": str(self.root), "yes": False})()
        with patch.object(samples, "plan", lambda n: big["files"]), patch.object(samples, "mg_catalogue", dict), \
                contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as stop:
            samples.cmd_get(args)
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("80 MB to download once", out.getvalue())
        self.assertFalse((self.root / "audio").exists())

    def test_a_question_box_in_another_language_is_stopped(self):
        transcript = self.root / "t.jsonl"
        transcript.write_text(json.dumps({"type": "user", "message": {"content": "làm cho tôi một phim hoạt hình ngắn"}})
                              + "\n", encoding="utf-8")
        box = lambda q, opts: {"questions": [{"question": q, "header": "x", "options": [{"label": l, "description": d}
                                                                                      for l, d in opts]}]}
        run = lambda inp: subprocess.run([sys.executable, str(GUARD), "tool"], input=json.dumps(
            {"transcript_path": str(transcript), "tool_name": "AskUserQuestion", "tool_input": inp, "cwd": str(self.root)}),
            capture_output=True, text=True)
        r = run(box("Which mode should we use for your film?", [("Quick mode", "one file and a few questions for you"),
                                                                 ("Film mode", "six steps with your approval")]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("Vietnamese", r.stderr)
        r = run(box("Mình bắt đầu bằng chế độ nào?", [("Chế độ nhanh", "một file, vài câu hỏi"), ("Chế độ Film", "sáu bước, có duyệt")]))
        self.assertEqual(r.returncode, 0)

    def test_cmap_reader_finds_the_letters_a_font_maps(self):
        def woff(groups):
            cmap = struct.pack(">HHHHI", 0, 1, 3, 10, 12) + struct.pack(">HHIII", 12, 0, 16 + 12 * len(groups), 0,
                                                                        len(groups))
            cmap += b"".join(struct.pack(">III", lo, hi, 1) for lo, hi in groups)
            packed = zlib.compress(cmap)
            head = b"wOFF" + struct.pack(">IIHH", 0x10000, 0, 1, 0) + b"\0" * 28
            return head + struct.pack(">4sIIII", b"cmap", 64, len(packed), len(cmap), 0) + packed
        want = fonts.VIETNAMESE["latin"]
        self.assertEqual(fonts.cmap_codes(woff([(0x20, 0xFF)]), want), set(want))
        self.assertEqual(fonts.cmap_codes(woff([(0xC0, 0xCF)]), want), {0xC2, 0xCA, 0xC3})
        self.assertIsNone(fonts.cmap_codes(b"wOF2....", (0x1A0,)))

    def test_vietnamese_letters_are_read_from_the_font_files_not_the_subset_label(self):
        def woff(groups):
            cmap = struct.pack(">HHHHI", 0, 1, 3, 10, 12) + struct.pack(">HHIII", 12, 0, 16 + 12 * len(groups), 0,
                                                                        len(groups))
            cmap += b"".join(struct.pack(">III", lo, hi, 1) for lo, hi in groups)
            packed = zlib.compress(cmap)
            head = b"wOFF" + struct.pack(">IIHH", 0x10000, 0, 1, 0) + b"\0" * 28
            return head + struct.pack(">4sIIII", b"cmap", 64, len(packed), len(cmap), 0) + packed
        want = fonts.VIETNAMESE["vietnamese"]
        full = woff([(0x102, 0x103), (0x110, 0x111), (0x128, 0x129), (0x168, 0x169), (0x1A0, 0x1A1), (0x1AF, 0x1B0),
                     (0x1EA0, 0x1EF9)])
        self.assertEqual(fonts.cmap_codes(full, want), set(want))
        no_d = woff([(0x102, 0x103), (0x128, 0x129), (0x168, 0x169), (0x1A0, 0x1A1), (0x1AF, 0x1B0), (0x1EA0, 0x1EF9)])
        self.assertNotIn(0x111, fonts.cmap_codes(no_d, want), "a vietnamese subset without đ is caught (Tilt Warp)")
        self.assertEqual(fonts.LETTERS["vi"]["role_subsets"], ["latin", "latin-ext", "vietnamese"])
        self.assertEqual(fonts.tone_tags("phim kinh dị")[0], fonts.tone_tags("horror")[0], "two-word Vietnamese tones match")
        self.assertEqual(fonts.tone_tags(__import__("unicodedata").normalize("NFD", "hài hước"))[0],
                         fonts.tone_tags("comedy")[0], "a decomposed (NFD) Vietnamese word matches too")

    def test_a_vietnamese_type_deal_keeps_only_pairings_with_vietnamese_letters(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import type_deal
        lib = type_deal.library()
        got, _ = type_deal.deal(lib, "s", 3, lang="vi")
        self.assertEqual(len(got), 3)
        for pid, _ in got:
            self.assertEqual(lib["_pairs"][pid]["vietnamese"], "verified", pid)
            for k in ("display", "text", "mono", "accent"):
                fid = lib["_pairs"][pid].get(k)
                if fid:
                    self.assertEqual(lib["_fonts"][fid]["vietnamese"]["status"], "verified", fid)
                    r = type_deal.role(lib, fid, "display" if k == "accent" else k, "vi")
                    if "pkg" in r and len(lib["_fonts"][fid]["load"]["subsets"]) > 1:
                        self.assertIn("vietnamese", r["subsets"], fid)
        self.assertEqual(lib["_fonts"]["tilt-warp"]["vietnamese"]["missing"], "đ")
        self.assertNotIn("subsets", type_deal.role(lib, "fraunces", "display", "en"), "a Latin-only film loads the default subsets")
        self.assertIn("vietnamese", type_deal.role(lib, "fraunces", "display")["subsets"], "Vietnamese is the default language")
        self.assertEqual(type_deal.mood_tags("tài liệu lịch sử")[0], type_deal.mood_tags("documentary")[0])

    def test_vietnamese_is_told_apart_from_japanese_and_english(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import guard
        for text in ("tôi muốn làm phim ngắn", "làm phim đi", "Bạn thích ý tưởng nào cho phim?",
                     "wait, check xem source code này có dùng được không",
                     __import__("unicodedata").normalize("NFD", "tôi muốn làm phim ngắn")):
            self.assertEqual(guard.language(text), "vi", text)
        self.assertEqual(guard.language("秋の京都の短編映画を作りたい"), "ja")
        self.assertEqual(guard.language("I want to make a short film about Đà Nẵng"), "en", "a place name stays a name")
        self.assertIsNone(guard.language("Hà Nội"))
        self.assertTrue(guard.IDEA_ASK.search("Bạn thích ý tưởng nào?"))
        self.assertTrue(guard.NOT_WANTED.search("đừng dùng bóng bay"))
        self.assertTrue(re.search(guard.HABIT_IMAGES["floating balloons"], "thêm bóng bay"))

    def test_vietnamese_words_slugs_and_casing(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import captions, init_film, words_check
        self.assertEqual(init_film.slug("Hà Nội mùa thu"), "ha-noi-mua-thu")
        self.assertEqual(init_film.slug("Đường về Huế"), "duong-ve-hue")
        self.assertEqual(init_film.slug("Café Ñandú"), "cafe-nandu")
        self.assertEqual(captions.stem("Im"), captions.stem("im"))
        self.assertEqual(captions.stem("ĐƯỜNG"), captions.stem("đường"))
        _, tells = words_check.check([("a", "Một hành trình khó quên."), ("b", "Không chỉ là cà phê, mà còn là ký ức."),
                                      ("c", "Mưa, gió và bão."), ("d", "Bà tôi pha cà phê lúc năm giờ sáng.")])
        labels = {(w, l.split(":")[0]) for w, _, l in tells}
        self.assertIn(("a", "cliché"), labels)
        self.assertIn(("b", "shape"), labels)
        self.assertIn(("c", "three-word list"), labels)
        self.assertFalse([t for t in tells if t[0] == "d"], "a plain concrete line passes")
        import handoff
        self.assertEqual(handoff.LINES["vi"], "Tiếp tục từ STATE.md")

    def test_vieneu_is_local_keyless_and_says_how_to_start_it(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import tts
        a = type("A", (), {"seed": 7, "stability": 0.45})()
        url, body, headers, key = tts.request_for("vieneu", "Xin chào", "", "Hải Đăng", "vieneu", a)
        self.assertEqual((url, key), ("http://127.0.0.1:8000/tts", None))
        self.assertEqual(body, {"text": "Xin chào", "format": "wav", "voice": "Hải Đăng"})
        self.assertNotIn("voice", tts.request_for("vieneu", "x", "", None, "vieneu", a)[1], "no preset: the server's own")
        down = __import__("urllib.error").error.URLError("Connection refused")
        with patch.dict(os.environ, {"VIENEU_URL": "http://127.0.0.1:9/"}), \
                patch.object(tts.urllib.request, "urlopen", side_effect=down):
            with self.assertRaises(RuntimeError) as e:
                tts.vieneu_voices()
        self.assertIn("http://127.0.0.1:9", str(e.exception))
        self.assertIn("start it", str(e.exception))
        quick = (ROOT / "references" / "quick-mode.md").read_text(encoding="utf-8")
        self.assertIn("never preselected and never the ★", quick, "VieNeu is offered every time, never the default")

    def test_taste_line_flags_defaults_and_stays_quiet_on_an_own_palette(self):
        house = {"palette": {"bg": "#f5f0e8", "ink": "#1d1a16", "accent": "#d97757"}, "lookPalette": {"bg": "#000000"},
                 "families": ["Inter", "Shrikhand"]}
        line = make.taste_line(house)
        self.assertIn("terracotta", line)
        self.assertIn("Inter", line)
        same = {"palette": {"bg": "#101418"}, "lookPalette": {"bg": "#101418"}, "families": []}
        self.assertIn("untouched default", make.taste_line(same))
        own = {"palette": {"bg": "#20140c", "ink": "#efe2c4", "accent": "#3fa7a1"}, "lookPalette": {"bg": "#000000"},
               "families": ["Shrikhand"]}
        self.assertEqual(make.taste_line(own), "")


if __name__ == "__main__":
    unittest.main()
