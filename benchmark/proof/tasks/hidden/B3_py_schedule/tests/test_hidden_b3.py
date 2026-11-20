import unittest

from schedule.timeutil import from_minutes, to_minutes


class Hidden(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(to_minutes("00:05"), 5)
        self.assertEqual(to_minutes("12:45"), 765)
        self.assertEqual(to_minutes(" 23:59"), 1439)
        self.assertEqual(from_minutes(to_minutes("17:20")), "17:20")
