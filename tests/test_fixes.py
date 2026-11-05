"""Small behaviours: an empty one-line score, deal history outside the kit, credits for used files only, the edge engine."""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import make  # noqa: E402
import tts  # noqa: E402


class Fixes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_one_line_empty_score_is_no_music(self):
        src = "function score(ctx, out) {}\nfunction other() {\n  pad(ctx, out, 0, 1, [220], 0.2);\n}\n"
        self.assertEqual(make.function_body(src, src.find("function score(")).strip(), "")
        (self.root / "film.html").write_text(src, encoding="utf-8")
        with patch.object(make, "PROJECT", self.root):
            self.assertEqual(make.music_choice_line(self.root / "film.html", None, "- **Music:** none (user)\n"), "")

    def test_a_score_with_code_is_still_music(self):
        src = "function score(ctx, out) {\n  if (x) { pad(ctx, out, 0, 1, [220], 0.2); }\n}\n"
        self.assertIn("pad(", make.function_body(src, 0))

    def test_deal_run_in_the_kit_writes_no_file_there(self):
        kit = self.root / "kit"
        (kit / "scripts").mkdir(parents=True)
        (kit / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        home = self.root / "deals"
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "deal.py"), "deal", "sound", "--project", str(kit)],
                             capture_output=True, text=True, env={**os.environ, "RUBYDAI_VIDEO_DEALS": str(home)})
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse((kit / "history.json").exists())
        self.assertTrue((home / "kit" / "history.json").exists())

    def test_credits_leave_out_unused_candidates_and_placeholder_lines(self):
        (self.root / "audio").mkdir()
        (self.root / "film.html").write_text("const PHOTOS = { a: 'assets/a.jpg' };", encoding="utf-8")
        (self.root / "audio" / "mix.json").write_text(json.dumps({"layers": [{"file": "audio/b.wav", "bus": "sfx"}]}))
        head = "file,title,author,source_url,licence,licence_url,attribution_text,modifications,downloaded_at,used_in,notes\n"
        (self.root / "LICENSES.csv").write_text(head +
            "assets/a.jpg,A,Ann,,CC BY,,A by Ann,,,,\n"                 # named by the page
            "assets/sound/c.mp3,C,Cy,,CC BY,,C by Cy,,,film,\n"         # used through a processed file: used_in filled
            "assets/sound/d.mp3,D,Di,,CC BY,,D by Di,,,,\n"             # a candidate never used
            "assets/ai/e.jpg,E,gen,,AI,,none needed,,,film.html,\n", encoding="utf-8")   # no credit owed
        with patch.object(make, "PROJECT", self.root):
            line = make.credits_file("Film", "")
        text = (self.root / "Film-credits.txt").read_text(encoding="utf-8")
        self.assertIn("A by Ann", text)
        self.assertIn("C by Cy", text)
        self.assertNotIn("D by Di", text)
        self.assertNotIn("none needed", text)
        self.assertIn("LEFT OUT", line)
        self.assertIn("assets/sound/d.mp3", line)

    def test_credits_take_the_page_title(self):
        (self.root / "film.html").write_text("const TITLE = 'New title';\n", encoding="utf-8")
        (self.root / "STATE.md").write_text("# State: Old title (Quick mode)\n", encoding="utf-8")
        with patch.object(make, "PROJECT", self.root):
            self.assertEqual(make.page_title(), "New title")

    def test_edge_request_shape(self):
        a = argparse.Namespace(speed=1.0)
        url, body, headers, key = tts.request_for("edge", "Hello.", "", "en-US-EmmaNeural", "edge", a)
        self.assertTrue(url.endswith("/tts/free/base64"))
        self.assertEqual(body["voiceId"], "en-US-EmmaNeural")
        self.assertIsNone(key)
        with contextlib.redirect_stdout(io.StringIO()):
            body = tts.edge_request("Hi", "warm and close", "en-US-EmmaNeural", a)
        self.assertNotIn("style", body)                       # free-text styles are not sent
        self.assertEqual(tts.edge_request("Hi", "cheerful", None, a)["style"], "cheerful")


if __name__ == "__main__":
    unittest.main()
