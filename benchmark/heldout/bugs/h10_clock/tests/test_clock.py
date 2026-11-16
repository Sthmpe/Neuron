import unittest

import clock


class Tests(unittest.TestCase):
    def test_morning(self):
        self.assertEqual(clock.to_minutes("7:30 am"), 450)

    def test_afternoon(self):
        self.assertEqual(clock.to_minutes("3:05 pm"), 905)

    def test_noon(self):
        self.assertEqual(clock.to_minutes("12:00 pm"), 720)

    def test_just_after_midnight(self):
        self.assertEqual(clock.to_minutes("12:15 am"), 15)

    def test_duration(self):
        self.assertEqual(clock.duration("9:00 am", "5:30 pm"), 510)
        self.assertEqual(clock.duration("11:00 am", "12:30 pm"), 90)

    def test_bad_time(self):
        with self.assertRaises(ValueError):
            clock.to_minutes("13:00 pm")
