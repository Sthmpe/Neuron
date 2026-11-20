import unittest

from stock.items import Item
from stock.rules import needs_reorder


class Hidden(unittest.TestCase):
    def test_boundaries(self):
        self.assertTrue(needs_reorder(Item("a", 0, 0)))
        self.assertTrue(needs_reorder(Item("b", 7, 7)))
        self.assertFalse(needs_reorder(Item("c", 8, 7)))
