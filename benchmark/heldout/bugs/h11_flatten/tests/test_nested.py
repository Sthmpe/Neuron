import unittest

import nested


class Tests(unittest.TestCase):
    def test_already_flat(self):
        self.assertEqual(nested.flatten([1, 2, 3]), [1, 2, 3])

    def test_one_level(self):
        self.assertEqual(nested.flatten([1, [2, 3], 4]), [1, 2, 3, 4])

    def test_deep(self):
        self.assertEqual(nested.flatten([1, [2, [3, [4]]], 5]), [1, 2, 3, 4, 5])

    def test_depth(self):
        self.assertEqual(nested.depth([1, [2, [3]]]), 3)

    def test_count_leaves(self):
        self.assertEqual(nested.count_leaves([[1, 2], [3, [4, 5]]]), 5)

    def test_empty(self):
        self.assertEqual(nested.flatten([]), [])
