import unittest

import roman


class Tests(unittest.TestCase):
    def test_to_roman(self):
        self.assertEqual(roman.to_roman(1994), "MCMXCIV")

    def test_simple_from_roman(self):
        self.assertEqual(roman.from_roman("VIII"), 8)
        self.assertEqual(roman.from_roman("MDC"), 1600)

    def test_subtractive_from_roman(self):
        self.assertEqual(roman.from_roman("IV"), 4)
        self.assertEqual(roman.from_roman("XIV"), 14)

    def test_round_trip(self):
        for n in (1, 9, 40, 90, 400, 944, 1994, 3999):
            self.assertEqual(roman.from_roman(roman.to_roman(n)), n)

    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            roman.to_roman(0)
