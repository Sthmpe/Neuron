import unittest

from search import contains, index_of, insert_position


class SearchTests(unittest.TestCase):
    def test_finds_middle(self):
        self.assertEqual(index_of([1, 3, 5, 7, 9], 5), 2)

    def test_finds_first_and_last(self):
        data = [2, 4, 6, 8, 10, 12]
        self.assertEqual(index_of(data, 2), 0)
        self.assertEqual(index_of(data, 12), 5)

    def test_single_element(self):
        self.assertEqual(index_of([42], 42), 0)
        self.assertTrue(contains([42], 42))

    def test_every_element_is_found(self):
        data = list(range(0, 40, 3))
        for i, value in enumerate(data):
            self.assertEqual(index_of(data, value), i)

    def test_missing(self):
        self.assertEqual(index_of([1, 3, 5], 4), -1)
        self.assertEqual(index_of([], 1), -1)

    def test_insert_position(self):
        self.assertEqual(insert_position([1, 3, 5], 4), 2)
        self.assertEqual(insert_position([1, 3, 5], 9), 3)
