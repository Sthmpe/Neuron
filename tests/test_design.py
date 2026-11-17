"""The design engine and the new kit: colour maths, mood, roles, tokens, contrast, variety, copy rules."""
import itertools
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["NEURON_DESIGN_HISTORY"] = os.path.join(tempfile.mkdtemp(prefix="neuron-hist-"), "h.json")
from neuron.design import color as C                                   # noqa: E402
from neuron.design import engine                                       # noqa: E402
from neuron.design.mood import MOODS, detect                           # noqa: E402
from neuron.design.names import find_colours                           # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "neuron"))
from kit_next import copy as kcopy                                      # noqa: E402
from kit_next import theme as ktheme                                    # noqa: E402

USER_SETS = ["navy and gold", "terracotta and cream colours", "brand colour #0E7C66 with a coral accent", "I like sage green",
             "black with bright orange", "dark green and pale pink", "colours: yellow", "lime and charcoal", "#ffffff and #000000",
             "use red, white and blue", "lavender colour", "brand colours #ff00ff #00ffff #ffff00 #123456", "light blue theme",
             "colour: beige", "colour: maroon"]


class ColourTests(unittest.TestCase):
    def test_round_trip(self):
        for h in ["#1b2a4a", "#f4c430", "#c2603e", "#2563c9", "#7f8c8d", "#000000", "#ffffff"]:
            self.assertEqual(C.oklch_to_hex(C.hex_to_oklch(h)), h)

    def test_contrast_known_values(self):
        self.assertAlmostEqual(C.contrast("#000000", "#ffffff"), 21, places=3)
        self.assertAlmostEqual(C.contrast("#777777", "#ffffff"), 4.48, places=2)

    def test_contrast_fix_changes_lightness_not_hue(self):
        for fg, bg in [("#f4c430", "#ffffff"), ("#ff8217", "#fafafa"), ("#7fd1ae", "#ffffff"), ("#2563c9", "#101010")]:
            fixed = C.ensure_contrast(fg, bg, 4.5)
            self.assertGreaterEqual(C.contrast(fixed, bg), 4.5)
            self.assertLess(C.hue_distance(C.hex_to_oklch(fg)[2], C.hex_to_oklch(fixed)[2]), 4, (fg, fixed))

    def test_buttons_always_readable_and_keep_hue(self):
        for h in ["#f4c430", "#e5533d", "#2f8f4e", "#b9f227", "#c9a227", "#7f8c8d", "#ff00ff", "#00ffff", "#b08d57", "#808080"]:
            b, t = C.button_pair(h, "#ffffff", "#151b25")
            self.assertGreaterEqual(C.contrast(b, t), 4.5)
            if C.hex_to_oklch(h)[1] > 0.03:
                self.assertLess(C.hue_distance(C.hex_to_oklch(h)[2], C.hex_to_oklch(b)[2]), 5)

    def test_tonal_scale(self):
        for h in ["#c2603e", "#1b2a4a", "#f4c430"]:
            s = C.tonal_scale(h)
            ls = [C.hex_to_oklch(s[k])[0] for k in sorted(s)]
            self.assertEqual(ls, sorted(ls, reverse=True))
            self.assertIn(h, s.values())         # the brand colour itself is in its scale


class WordsAndMoodTests(unittest.TestCase):
    def test_colour_words(self):
        f = lambda r: [c["word"] for c in find_colours(r)]
        self.assertEqual(f("Please use navy and gold for my law firm."), ["navy", "gold"])
        self.assertEqual(f("We sell fresh lemon cake and olive oil"), [])
        self.assertEqual(f("We bake chocolate cake and sell gold jewellery"), [])
        self.assertEqual(f("Our gym: black with bright orange"), ["black", "bright orange"])
        self.assertEqual(f("Make it dark green and pale pink"), ["dark green", "pale pink"])
        self.assertEqual(find_colours("brand #0E7C66")[0]["hex"], "#0e7c66")

    def test_moods(self):
        cases = {"law firm in Abuja": "trust", "my bakery": "warmth", "payments app": "clarity", "yoga studio": "calm",
                 "boxing gym": "energy", "bridal boutique": "elegance", "kids party planner": "playful",
                 "organic farm shop": "natural", "plumbing company": "dependable", "maths tutoring": "bright", "my business": "modern"}
        for request, mood in cases.items():
            self.assertEqual(detect(request)[0], mood, request)


class EngineTests(unittest.TestCase):
    def test_every_design_passes_contrast(self):
        failures = []
        for mood, seed in itertools.product(MOODS, range(6)):
            d = engine.choose(f"a website", seed=seed, mood=mood, avoid_history=False)
            failures += [(mood, seed, r) for r in d["contrast"] if not r["ok"]]
        for i, words in enumerate(USER_SETS):
            for mood in ("trust", "warmth", "elegance", "energy"):
                d = engine.choose(f"site for us, {words}", seed=i, mood=mood, avoid_history=False)
                failures += [(words, mood, r) for r in d["contrast"] if not r["ok"]]
        self.assertEqual(failures, [])

    def test_user_colours_are_used_and_explained(self):
        d = engine.choose("Law firm site. Please use navy and gold.", seed=1, avoid_history=False)
        self.assertEqual(d["palette"]["source"], "user")
        self.assertEqual(d["palette"]["roles"]["accent"], "#c9a227")          # the vivid one gets the actions
        self.assertEqual(d["tokens"]["color-strong"], "#1b2a4a")              # navy carries the bands
        self.assertIn("gold is kept for buttons", d["reason"])
        one = engine.choose("bakery, colour: cream", seed=1, avoid_history=False)
        self.assertIn("light colour", one["reason"])

    def test_same_seed_same_design(self):
        a = engine.choose("my bakery", seed=99, avoid_history=False)
        b = engine.choose("my bakery", seed=99, avoid_history=False)
        self.assertEqual(a["tokens"], b["tokens"])
        self.assertEqual(a["variants"], b["variants"])

    def test_two_sites_never_share_a_template(self):
        prints = [engine.choose("my bakery in Lagos", seed=s)["fingerprint"] for s in range(12)]
        for x, y in itertools.combinations(prints, 2):
            self.assertLess(sum(a == b for a, b in zip(x, y)), 5, (x, y))

    def test_tokens_cover_everything_the_stylesheet_uses(self):
        d = engine.choose("a website", seed=3, avoid_history=False)
        used = set(re.findall(r"var\(--([a-z0-9-]+)\)", ktheme.COMPONENTS))
        have = set(d["tokens"]) | {f"fs-{k}" for k in ktheme._sizes(1.25)}
        self.assertEqual(used - have, set())

    def test_reason_is_plain_english_without_dashes(self):
        for mood in MOODS:
            d = engine.choose("site", seed=2, mood=mood, avoid_history=False)
            self.assertGreater(len(d["reason"]), 200)
            self.assertFalse(kcopy.has_dash(d["reason"]))


class StylesheetAndCopyTests(unittest.TestCase):
    def test_components_use_tokens_only(self):
        css = ktheme.COMPONENTS
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,6}\b", css), [])
        self.assertEqual(re.findall(r"\brgba?\(|\bhsla?\(", css), [])
        self.assertEqual(re.findall(r"font-family:\s*['\"A-Z]", css), [])

    def test_no_border_lines(self):
        for decl in re.findall(r"border(?:-(?:top|right|bottom|left|width|style|color))?:([^;}]+)", ktheme.COMPONENTS):
            self.assertIn(decl.strip().split()[0], ("0", "none"), decl)

    def test_em_dashes_removed(self):
        self.assertEqual(kcopy.clean("Fresh bread — baked daily"), "Fresh bread, baked daily")
        self.assertEqual(kcopy.clean("— Welcome —"), "Welcome")
        self.assertEqual(kcopy.clean("Open 7am–7pm"), "Open 7am–7pm")        # a range keeps its en dash
        self.assertEqual(kcopy.clean("Unlock seamless banking"), "Get simple banking")

    def test_catalogue_fits_a_small_context_window(self):
        text = (Path(__file__).resolve().parents[1] / "neuron" / "kit_next" / "CATALOGUE.md").read_text()
        self.assertLess(len(text.split()), 400)          # roughly 600 tokens
        self.assertFalse(kcopy.has_dash(text))

    def test_fonts_and_icons_are_bundled(self):
        root = Path(__file__).resolve().parents[1] / "neuron" / "kit_next" / "static"
        for f in engine.FONTS:
            self.assertTrue((root / "fonts" / f"{f}.woff2").exists(), f)
        self.assertGreater((root / "icons.json").stat().st_size, 10000)
        self.assertTrue((root / "fonts" / "LICENSES.txt").exists())


if __name__ == "__main__":
    unittest.main()
