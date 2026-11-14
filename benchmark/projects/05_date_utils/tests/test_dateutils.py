import unittest

import dateutils


class DateTests(unittest.TestCase):
    def test_ordinary_years(self):
        self.assertTrue(dateutils.is_leap_year(2024))
        self.assertFalse(dateutils.is_leap_year(2023))

    def test_century_years(self):
        self.assertFalse(dateutils.is_leap_year(1900))
        self.assertTrue(dateutils.is_leap_year(2000))

    def test_february(self):
        self.assertEqual(dateutils.days_in_month(2023, 2), 28)
        self.assertEqual(dateutils.days_in_month(2000, 2), 29)

    def test_day_of_year(self):
        self.assertEqual(dateutils.day_of_year(2023, 3, 1), 60)
        self.assertEqual(dateutils.day_of_year(2000, 12, 31), 366)

    def test_days_in_year(self):
        self.assertEqual(dateutils.days_in_year(2400), 366)
        self.assertEqual(dateutils.days_in_year(2100), 365)

    def test_bad_day(self):
        with self.assertRaises(ValueError):
            dateutils.day_of_year(2023, 2, 29)
