import unittest

from stock.items import Item
from stock.report import reorder_list, summary


class ReportTests(unittest.TestCase):
    def test_reorder_list(self):
        items = [Item("rice", 3, 5), Item("beans", 5, 5), Item("oil", 9, 4)]
        self.assertEqual(reorder_list(items), ["beans", "rice"])

    def test_summary(self):
        self.assertEqual(summary([Item("salt", 2, 2)]), "1 to reorder: salt")
