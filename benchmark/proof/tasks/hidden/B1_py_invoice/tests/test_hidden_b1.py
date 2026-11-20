import unittest

from invoice.models import Line
from invoice.tax import vat
from invoice.totals import total


class Hidden(unittest.TestCase):
    def test_vat(self):
        self.assertEqual(vat(1000), 75)
        self.assertEqual(vat(333), 25)

    def test_total_many_lines(self):
        self.assertEqual(total([Line("a", 3, 2000), Line("b", 1, 4000)]), 10750)
