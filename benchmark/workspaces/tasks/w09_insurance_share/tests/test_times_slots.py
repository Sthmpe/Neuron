import unittest

from clinic.core.times import overlaps, to_minutes, to_text
from clinic.scheduling.slots import day_slots, first_free, free_slots
from tests.helpers import clinic


class TimeTests(unittest.TestCase):
    def test_conversion(self):
        self.assertEqual(to_minutes("09:30"), 570)
        self.assertEqual(to_text(570), "09:30")
        with self.assertRaises(ValueError):
            to_minutes("24:00")

    def test_overlaps(self):
        self.assertTrue(overlaps(0, 30, 15, 45))
        self.assertFalse(overlaps(0, 30, 30, 60))
        self.assertTrue(overlaps(0, 60, 10, 20))


class SlotTests(unittest.TestCase):
    def setUp(self):
        self.d, self.p, self.book = clinic()

    def test_day_slots_skip_lunch(self):
        s = day_slots(self.d["D1"])
        self.assertEqual(len(s), 14)
        self.assertIn("12:30", s)
        self.assertNotIn("13:00", s)
        self.assertNotIn("13:30", s)
        self.assertIn("14:00", s)
        self.assertEqual(s[-1], "16:30")

    def test_short_day(self):
        self.assertEqual(day_slots(self.d["D2"]), ["08:00", "08:30", "09:00", "09:30", "10:30", "11:00", "11:30"])

    def test_free_slots(self):
        free = free_slots(self.d["D2"], [("08:30", 60)])
        self.assertEqual(free, ["08:00", "09:30", "10:30", "11:00", "11:30"])

    def test_first_free(self):
        self.assertEqual(first_free(self.d["D2"], [("08:00", 30)], after="08:00"), "08:30")
        self.assertEqual(first_free(self.d["D2"], [], after="10:00"), "10:30")
        self.assertIsNone(first_free(self.d["D2"], [], after="11:45"))
