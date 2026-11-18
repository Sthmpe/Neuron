import unittest
from datetime import date

from pantry.report import shopping_list, summary
from pantry.store import Pantry


class ReportTests(unittest.TestCase):
    def test_shopping_list_and_summary(self):
        p = Pantry()
        p.add("oil", 1, date(2026, 4, 1), minimum=3)
        p.add("salt", 4, date(2026, 9, 1))
        self.assertEqual(shopping_list(p), ["oil: buy 2"])
        self.assertEqual(summary(p, date(2026, 3, 29)), {"items": 2, "low": 1, "expiring_soon": ["oil"]})
