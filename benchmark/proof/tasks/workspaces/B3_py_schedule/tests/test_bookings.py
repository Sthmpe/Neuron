import unittest

from schedule.bookings import clashes, overlaps


class BookingTests(unittest.TestCase):
    def test_morning(self):
        self.assertTrue(overlaps(("08:00", "09:00"), ("08:30", "09:30")))
        self.assertFalse(overlaps(("08:00", "09:00"), ("09:00", "09:30")))

    def test_late_morning(self):
        self.assertTrue(overlaps(("10:00", "11:00"), ("10:30", "11:30")))
        self.assertFalse(overlaps(("09:00", "10:00"), ("10:00", "11:00")))

    def test_clashes(self):
        day = [("Ada", ("13:00", "14:00")), ("Bisi", ("13:30", "15:00")), ("Chi", ("15:00", "16:00"))]
        self.assertEqual(clashes(day), [("Ada", "Bisi")])
