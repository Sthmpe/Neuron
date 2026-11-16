import unittest

from chain import Chain


class Tests(unittest.TestCase):
    def make(self, *values):
        c = Chain()
        for v in values:
            c.append(v)
        return c

    def test_append(self):
        self.assertEqual(self.make(1, 2, 3).to_list(), [1, 2, 3])

    def test_remove_middle(self):
        c = self.make(1, 2, 3)
        self.assertTrue(c.remove(2))
        self.assertEqual(c.to_list(), [1, 3])

    def test_remove_last(self):
        c = self.make(1, 2, 3)
        c.remove(3)
        self.assertEqual(c.to_list(), [1, 2])

    def test_remove_first(self):
        c = self.make(1, 2, 3)
        self.assertTrue(c.remove(1))
        self.assertEqual(c.to_list(), [2, 3])

    def test_remove_only_item(self):
        c = self.make(7)
        c.remove(7)
        self.assertEqual(c.to_list(), [])

    def test_remove_missing(self):
        self.assertFalse(self.make(1).remove(9))
