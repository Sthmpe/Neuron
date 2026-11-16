import unittest

import paging


class Tests(unittest.TestCase):
    def test_exact_pages(self):
        self.assertEqual(paging.total_pages(20, 5), 4)

    def test_partial_last_page(self):
        self.assertEqual(paging.total_pages(21, 5), 5)
        self.assertEqual(paging.total_pages(1, 10), 1)

    def test_no_items(self):
        self.assertEqual(paging.total_pages(0, 10), 0)

    def test_page(self):
        self.assertEqual(paging.page(list(range(1, 8)), 2, 3), [4, 5, 6])

    def test_has_next(self):
        self.assertTrue(paging.has_next(7, 2, 3))
        self.assertFalse(paging.has_next(7, 3, 3))
