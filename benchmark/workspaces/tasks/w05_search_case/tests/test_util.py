import unittest

from shopkeeper.util.dates import add_days, days_between, is_weekend, next_working_day
from shopkeeper.util.money import format_naira, percent_of, split_evenly, to_kobo


class MoneyTests(unittest.TestCase):
    def test_to_kobo(self):
        self.assertEqual(to_kobo("1,250.50"), 125050)
        self.assertEqual(to_kobo(19.99), 1999)
        self.assertEqual(to_kobo("₦ 3"), 300)

    def test_format(self):
        self.assertEqual(format_naira(125050), "₦1,250.50")
        self.assertEqual(format_naira(5), "₦0.05")
        self.assertEqual(format_naira(-1500), "-₦15.00")

    def test_percent_of(self):
        self.assertEqual(percent_of(10000, 10), 1000)
        self.assertEqual(percent_of(1050, 10), 105)
        self.assertEqual(percent_of(1005, 10), 101)       # 100.5 rounds up

    def test_split(self):
        self.assertEqual(split_evenly(1000, 3), [334, 333, 333])
        self.assertEqual(sum(split_evenly(99999, 7)), 99999)


class DateTests(unittest.TestCase):
    def test_add_and_between(self):
        self.assertEqual(add_days("2026-01-30", 3), "2026-02-02")
        self.assertEqual(days_between("2026-01-01", "2026-03-01"), 59)
        self.assertEqual(days_between("2026-03-01", "2026-01-01"), -59)

    def test_weekends(self):
        self.assertTrue(is_weekend("2026-11-14"))       # Saturday
        self.assertFalse(is_weekend("2026-11-16"))      # Monday
        self.assertEqual(next_working_day("2026-11-14"), "2026-11-16")
        self.assertEqual(next_working_day("2026-11-15"), "2026-11-16")
        self.assertEqual(next_working_day("2026-11-17"), "2026-11-17")
