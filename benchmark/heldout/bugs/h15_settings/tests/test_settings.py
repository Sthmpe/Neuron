import unittest

import settings


class Tests(unittest.TestCase):
    DEFAULTS = {"volume": 5, "screen": {"width": 800, "height": 600, "colors": {"bg": "white", "fg": "black"}}}

    def test_top_level_override(self):
        self.assertEqual(settings.merge(self.DEFAULTS, {"volume": 9})["volume"], 9)

    def test_new_key(self):
        self.assertEqual(settings.merge(self.DEFAULTS, {"lang": "en"})["lang"], "en")

    def test_nested_override_keeps_siblings(self):
        out = settings.merge(self.DEFAULTS, {"screen": {"width": 1024}})
        self.assertEqual(out["screen"]["width"], 1024)
        self.assertEqual(out["screen"]["height"], 600)

    def test_deeply_nested(self):
        out = settings.merge(self.DEFAULTS, {"screen": {"colors": {"bg": "navy"}}})
        self.assertEqual(settings.get_path(out, "screen.colors.bg"), "navy")
        self.assertEqual(settings.get_path(out, "screen.colors.fg"), "black")

    def test_defaults_are_not_changed(self):
        settings.merge(self.DEFAULTS, {"volume": 1})
        self.assertEqual(self.DEFAULTS["volume"], 5)

    def test_get_path_default(self):
        self.assertEqual(settings.get_path(self.DEFAULTS, "screen.depth", 24), 24)
