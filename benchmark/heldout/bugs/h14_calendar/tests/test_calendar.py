import unittest

from calendar_book import Calendar, Clash


class Tests(unittest.TestCase):
    def setUp(self):
        self.cal = Calendar()
        self.cal.book("standup", 9, 10)

    def test_separate_events(self):
        self.cal.book("lunch", 12, 13)
        self.assertEqual(self.cal.busy_hours(), 2)

    def test_overlap_is_refused(self):
        with self.assertRaises(Clash):
            self.cal.book("call", 9, 11)

    def test_event_inside_another_is_refused(self):
        self.cal.book("workshop", 13, 17)
        with self.assertRaises(Clash):
            self.cal.book("coffee", 14, 15)

    def test_back_to_back_is_allowed(self):
        self.cal.book("review", 10, 11)
        self.cal.book("prep", 8, 9)
        self.assertEqual(len(self.cal.events), 3)

    def test_bad_event(self):
        with self.assertRaises(ValueError):
            self.cal.book("nothing", 5, 5)
