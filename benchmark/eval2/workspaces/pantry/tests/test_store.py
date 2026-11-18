import unittest
from datetime import date

from pantry.store import Pantry


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.p = Pantry()
        self.p.add("rice", 5, date(2026, 3, 10), minimum=2)
        self.p.add("milk", 1, date(2026, 3, 3), minimum=2)
        self.p.add("eggs", 12, date(2026, 3, 6), minimum=6)

    def test_add_more_of_the_same(self):
        self.p.add("rice", 3, date(2026, 3, 10))
        self.assertEqual(self.p.items["rice"].quantity, 8)

    def test_use_refuses_too_much(self):
        with self.assertRaises(ValueError):
            self.p.use("milk", 2)

    def test_expiring_within_includes_the_last_day(self):
        self.assertEqual(self.p.expiring_within(3, date(2026, 3, 3)), ["eggs", "milk"])

    def test_low_stock(self):
        self.assertEqual(self.p.low_stock(), ["milk"])
