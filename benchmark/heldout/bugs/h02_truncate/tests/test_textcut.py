import unittest

import textcut


class Tests(unittest.TestCase):
    def test_short_text_is_unchanged(self):
        self.assertEqual(textcut.truncate("hello", 10), "hello")

    def test_exact_fit(self):
        self.assertEqual(textcut.truncate("hello", 5), "hello")

    def test_long_text_is_cut_to_the_limit(self):
        out = textcut.truncate("abcdefghijklmnop", 10)
        self.assertEqual(len(out), 10)
        self.assertEqual(out, "abcdefg...")

    def test_small_limit(self):
        self.assertEqual(textcut.truncate("abcdef", 3), "...")

    def test_initials(self):
        self.assertEqual(textcut.initials("ada lovelace"), "AL")

    def test_title_case(self):
        self.assertEqual(textcut.title_case("the quick fox"), "The Quick Fox")
