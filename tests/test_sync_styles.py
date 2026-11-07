import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHA = "a" * 40


def style(up, sid, essence, demo_link=True):
    d = up / "styles" / sid
    d.mkdir(parents=True)
    (d / "style.json").write_text(json.dumps({"en": sid.title(), "category_en": "Games", "uses": ["Tests"]}), encoding="utf-8")
    link = "\n\nHow our demo was made: [DEMO.md](DEMO.md#build-notes). Code: `f(t)`.\n" if demo_link else "\n"
    (d / "STYLE.md").write_text(f"# {sid}\n\n> {essence}\n{link}", encoding="utf-8")
    (d / "poster.jpg").write_bytes(b"jpg")


class SyncStyles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.up, self.kit = t / "up", t / "kit"
        (self.kit / "styles").mkdir(parents=True)
        (self.kit / "styles" / "old.md").write_text("old text", encoding="utf-8")
        (self.kit / "styles" / "mine.md").write_text("the kit's own", encoding="utf-8")
        own = {"id": "mine", "name": "Mine", "category": "Games", "base": "anime-cel", "essence": "x", "uses": [],
               "poster": None, "demo": None, "source": "rubydai-make-video-skill"}
        old = dict(own, id="old", name="Old", base="handmade-ink")
        del old["source"]
        (self.kit / "styles" / "index.json").write_text(json.dumps({"commit": "b" * 40, "styles": [old, own]}),
                                                        encoding="utf-8")
        style(self.up, "old", "Old, now updated upstream.")
        style(self.up, "fresh", "A brand new style.")
        (self.up / "styles" / "_template").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_sync(self, *extra):
        return subprocess.run([sys.executable, ROOT / "scripts" / "sync_styles.py", "--src", self.up, "--commit", SHA,
                               "--kit", self.kit, *extra], capture_output=True, text=True)

    def index(self):
        return json.loads((self.kit / "styles" / "index.json").read_text(encoding="utf-8"))

    def test_a_new_style_without_a_base_family_writes_nothing(self):
        r = self.run_sync()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NEW STYLES NEED A BASE FAMILY", r.stderr)
        self.assertIn("fresh", r.stderr)
        self.assertEqual(self.index()["commit"], "b" * 40)
        self.assertEqual((self.kit / "styles" / "old.md").read_text(encoding="utf-8"), "old text")
        self.assertNotEqual(self.run_sync("--base", "fresh=not-a-family").returncode, 0)

    def test_sync_pins_links_keeps_the_kits_fields_and_its_own_styles(self):
        r = self.run_sync("--base", "fresh=claymation")
        self.assertEqual(r.returncode, 0, r.stderr)
        idx = self.index()
        self.assertEqual(idx["commit"], SHA)
        by = {s["id"]: s for s in idx["styles"]}
        self.assertEqual([s["id"] for s in idx["styles"]], ["fresh", "old", "mine"])
        self.assertEqual(by["old"]["base"], "handmade-ink", "the kit's base family is kept")
        self.assertEqual(by["old"]["essence"], "Old, now updated upstream.")
        self.assertEqual(by["fresh"]["base"], "claymation")
        self.assertIn(SHA, by["fresh"]["poster"])
        self.assertEqual(by["mine"]["source"], "rubydai-make-video-skill")
        md = (self.kit / "styles" / "old.md").read_text(encoding="utf-8")
        self.assertIn(f"](https://github.com/lemomo-ai/lemo-opuscar/blob/{SHA}/styles/old/DEMO.md#build-notes)", md)
        self.assertIn("`f(t)`", md)
        self.assertEqual((self.kit / "styles" / "mine.md").read_text(encoding="utf-8"), "the kit's own")
        self.assertIn("aliases.json", r.stdout)

    def test_a_relative_link_the_kit_cannot_follow_stops_the_sync(self):
        (self.up / "styles" / "old" / "STYLE.md").write_text("# old\n\n> e\n\nSee [the engine](demo/engine.js).\n",
                                                             encoding="utf-8")
        r = self.run_sync("--base", "fresh=claymation")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("relative link", r.stderr)
        self.assertEqual(self.index()["commit"], "b" * 40)


if __name__ == "__main__":
    unittest.main()
