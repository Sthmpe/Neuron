import unittest

import intervals


class IntervalTests(unittest.TestCase):
    def test_no_overlap(self):
        self.assertEqual(intervals.merge([(5, 6), (1, 2)]), [(1, 2), (5, 6)])

    def test_simple_overlap(self):
        self.assertEqual(intervals.merge([(1, 4), (3, 8)]), [(1, 8)])

    def test_touching(self):
        self.assertEqual(intervals.merge([(1, 2), (2, 3)]), [(1, 3)])

    def test_interval_inside_another(self):
        self.assertEqual(intervals.merge([(1, 10), (2, 3)]), [(1, 10)])

    def test_total_length(self):
        self.assertEqual(intervals.total_length([(0, 10), (2, 4), (20, 25)]), 15)

    def test_covers(self):
        self.assertTrue(intervals.covers([(1, 10), (3, 4)], 7))
        self.assertFalse(intervals.covers([(1, 2), (5, 6)], 3))

    def test_gaps(self):
        self.assertEqual(intervals.gaps([(1, 2), (5, 6), (9, 12)]), [(2, 5), (6, 9)])
