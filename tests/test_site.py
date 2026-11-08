import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Site(unittest.TestCase):
    def test_the_site_lists_every_style_with_its_links(self):
        index = json.loads((ROOT / "styles" / "index.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as out:
            r = subprocess.run([sys.executable, ROOT / "site" / "build.py", out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            page = (Path(out) / "index.html").read_text(encoding="utf-8")
            self.assertTrue((Path(out) / "logo.png").exists())
            copied = {p.name for p in (Path(out) / "posters").glob("*.jpg")}
        self.assertNotIn("/*STYLE_DATA*/null", page)
        start = page.index("const DATA = ") + len("const DATA = ")
        data, _ = json.JSONDecoder().raw_decode(page[start:])
        self.assertEqual([s["id"] for s in data["styles"]], [s["id"] for s in index["styles"]])
        self.assertEqual(data["commit"], index["commit"])
        for s in data["styles"]:
            self.assertTrue(s["recipe"].endswith(f"/styles/{s['id']}.md"))
            self.assertTrue((ROOT / "styles" / f"{s['id']}.md").exists(), s["id"])
            if not s["own"]:                          # LemoLab's styles show their poster and demo film
                self.assertIn(index["commit"], s["poster"])
                self.assertTrue(s["film"].endswith(f"/films/{s['id']}.mp4"))
            else:                                     # the kit's own: a poster drawn in code, copied next to the page
                self.assertEqual(s["poster"], f"posters/{s['id']}.jpg", s["id"])
                self.assertIn(f"{s['id']}.jpg", copied)

    def test_every_kit_style_has_a_drawn_poster(self):
        index = json.loads((ROOT / "styles" / "index.json").read_text(encoding="utf-8"))
        page = (ROOT / "site" / "posters" / "posters.html").read_text(encoding="utf-8")
        film = (ROOT / "templates" / "quick" / "film.html").read_text(encoding="utf-8")
        sys.path.insert(0, str(ROOT / "site" / "posters"))
        import render
        self.assertLess(film.index(render.RIG_START), film.index(render.RIG_END))   # the rig the posters inject
        self.assertIn("function stickman(", render.rig())
        self.assertIn("/*RIG*/", page)
        for s in index["styles"]:
            if s.get("source"):
                self.assertIn(f"'{s['id']}'() {{", page, s["id"])
                self.assertTrue((ROOT / "styles" / "posters" / f"{s['id']}.jpg").is_file(), s["id"])


if __name__ == "__main__":
    unittest.main()
