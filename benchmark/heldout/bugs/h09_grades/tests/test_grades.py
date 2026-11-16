import unittest

import grades


class Tests(unittest.TestCase):
    def test_middle_of_bands(self):
        self.assertEqual(grades.letter(95), "A")
        self.assertEqual(grades.letter(75), "C")
        self.assertEqual(grades.letter(12), "F")

    def test_boundaries(self):
        self.assertEqual(grades.letter(90), "A")
        self.assertEqual(grades.letter(80), "B")
        self.assertEqual(grades.letter(60), "D")

    def test_just_below(self):
        self.assertEqual(grades.letter(89), "B")
        self.assertEqual(grades.letter(59), "F")

    def test_summary(self):
        self.assertEqual(grades.summary([90, 91, 70]), {"A": 2, "C": 1})

    def test_passed(self):
        self.assertTrue(grades.passed(60))
        self.assertFalse(grades.passed(59))
