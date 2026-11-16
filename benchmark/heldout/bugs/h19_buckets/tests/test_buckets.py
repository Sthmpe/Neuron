import unittest

import buckets


class Tests(unittest.TestCase):
    def test_low_values(self):
        self.assertEqual(buckets.bucket_start(3, 10), 0)
        self.assertEqual(buckets.bucket_start(12, 10), 10)

    def test_upper_part_of_a_bucket(self):
        self.assertEqual(buckets.bucket_start(7, 10), 0)
        self.assertEqual(buckets.bucket_start(19, 10), 10)

    def test_boundary(self):
        self.assertEqual(buckets.bucket_start(20, 10), 20)

    def test_histogram(self):
        self.assertEqual(buckets.histogram([1, 5, 9, 11, 25, 29], 10), {0: 3, 10: 1, 20: 2})

    def test_fullest(self):
        self.assertEqual(buckets.fullest([1, 2, 16, 17, 18, 40], 10), 10)
