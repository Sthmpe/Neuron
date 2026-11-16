import unittest

import listtools


class Tests(unittest.TestCase):
    def test_dedupe_keeps_order(self):
        self.assertEqual(listtools.dedupe(["pear", "apple", "pear", "fig", "apple"]), ["pear", "apple", "fig"])

    def test_dedupe_numbers(self):
        self.assertEqual(listtools.dedupe([30, 10, 30, 20, 10, 99, 5]), [30, 10, 20, 99, 5])

    def test_dedupe_empty(self):
        self.assertEqual(listtools.dedupe([]), [])

    def test_chunk(self):
        self.assertEqual(listtools.chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_most_common_tie_goes_to_first_seen(self):
        self.assertEqual(listtools.most_common(["zebra", "ant", "ant", "zebra"]), "zebra")
