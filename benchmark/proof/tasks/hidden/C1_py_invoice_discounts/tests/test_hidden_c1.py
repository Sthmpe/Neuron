import unittest

from invoice.discounts import apply_code
from invoice.models import Line
from invoice.totals import total


class Hidden(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(apply_code(20000, "SAVE10"), 18000)
        self.assertEqual(apply_code(100000, "FLAT500"), 50000)
        self.assertEqual(apply_code(30000, "FLAT500"), 0)
        with self.assertRaises(ValueError):
            apply_code(1000, "FREE")

    def test_total_with_code(self):
        self.assertEqual(total([Line("bag", 2, 10000)], "SAVE10"), 19350)
        self.assertEqual(total([Line("bag", 1, 100000)], code="FLAT500"), 53750)
        self.assertEqual(total([Line("bag", 2, 10000)]), 21500)
