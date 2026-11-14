import unittest

import textstats


class TextStatsTests(unittest.TestCase):
    def test_simple_sentence(self):
        self.assertEqual(textstats.word_count("The quick brown fox."), 4)

    def test_multiple_lines(self):
        text = "one two\nthree four\nfive"
        self.assertEqual(textstats.word_count(text), 5)

    def test_tabs_and_newlines(self):
        self.assertEqual(textstats.words("red\tgreen\nblue"), ["red", "green", "blue"])

    def test_most_common(self):
        text = "b a b c a b"
        self.assertEqual(textstats.most_common(text, 2), [("b", 3), ("a", 2)])

    def test_average_word_length(self):
        self.assertEqual(textstats.average_word_length("aa bbbb"), 3.0)

    def test_empty(self):
        self.assertEqual(textstats.word_count(""), 0)
        self.assertEqual(textstats.average_word_length(""), 0.0)
