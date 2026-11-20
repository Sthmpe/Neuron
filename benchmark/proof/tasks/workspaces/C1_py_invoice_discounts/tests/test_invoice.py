import unittest

from invoice.fmt import naira
from invoice.models import Line
from invoice.totals import subtotal, total


class InvoiceTests(unittest.TestCase):
    def test_subtotal(self):
        self.assertEqual(subtotal([Line("bag", 2, 10000), Line("tag", 1, 500)]), 20500)

    def test_total_includes_vat(self):
        self.assertEqual(total([Line("bag", 2, 1000000)]), 2150000)

    def test_format(self):
        self.assertEqual(naira(2150000), "NGN 21,500.00")
