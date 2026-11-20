import unittest

from units import convert


class Hidden(unittest.TestCase):
    def test_temperature(self):
        self.assertAlmostEqual(convert(100, "C", "F"), 212)
        self.assertAlmostEqual(convert(32, "F", "C"), 0)
        self.assertAlmostEqual(convert(0, "C", "K"), 273.15)
        self.assertAlmostEqual(convert(300, "K", "F"), 80.33, places=2)
        self.assertAlmostEqual(convert(20, "C", "C"), 20)

    def test_mixed_and_unknown(self):
        for args in [(1, "C", "m"), (1, "km", "F"), (1, "C", "R")]:
            with self.assertRaises(ValueError):
                convert(*args)
