import unittest

from units import convert


class UnitTests(unittest.TestCase):
    def test_length(self):
        self.assertAlmostEqual(convert(2.4, "km", "m"), 2400)
        self.assertAlmostEqual(convert(150, "cm", "m"), 1.5)

    def test_unknown(self):
        with self.assertRaises(ValueError):
            convert(1, "km", "kg")
