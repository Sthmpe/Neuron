import unittest

import wrap


class Tests(unittest.TestCase):
    def test_fits_on_one_line(self):
        self.assertEqual(wrap.wrap("hi there", 20), ["hi there"])

    def test_exact_width(self):
        self.assertEqual(wrap.wrap("abc def", 7), ["abc def"])

    def test_no_line_is_too_long(self):
        lines = wrap.wrap("the quick brown fox jumps over the lazy dog", 10)
        self.assertLessEqual(wrap.longest_line(lines), 10)

    def test_breaks(self):
        self.assertEqual(wrap.wrap("aaa bbb ccc", 7), ["aaa bbb", "ccc"])
        self.assertEqual(wrap.wrap("aaaa bbb", 7), ["aaaa", "bbb"])

    def test_long_word(self):
        self.assertEqual(wrap.wrap("a extraordinarily b", 5), ["a", "extraordinarily", "b"])

    def test_empty(self):
        self.assertEqual(wrap.wrap("", 5), [])
