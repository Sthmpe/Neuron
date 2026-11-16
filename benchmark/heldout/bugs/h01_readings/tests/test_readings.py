import unittest

import readings


class Tests(unittest.TestCase):
    def test_whole_number_average(self):
        self.assertEqual(readings.average([2, 4, 6]), 4)

    def test_fractional_average(self):
        self.assertEqual(readings.average([1, 2]), 1.5)

    def test_empty(self):
        self.assertEqual(readings.average([]), 0.0)

    def test_spread(self):
        self.assertEqual(readings.spread([3, 9, 4]), 6)

    def test_above_average(self):
        self.assertEqual(readings.above_average([1, 2, 2]), [2, 2])
