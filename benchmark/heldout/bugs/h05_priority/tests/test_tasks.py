import unittest

from tasks import TaskQueue


class Tests(unittest.TestCase):
    def test_single(self):
        q = TaskQueue()
        q.add("a")
        self.assertEqual(q.next(), "a")
        self.assertEqual(len(q), 0)

    def test_most_urgent_first(self):
        q = TaskQueue()
        q.add("low", 9)
        q.add("urgent", 1)
        q.add("normal", 5)
        self.assertEqual(q.next(), "urgent")
        self.assertEqual(q.next(), "normal")

    def test_ties_keep_arrival_order(self):
        q = TaskQueue()
        q.add("first", 3)
        q.add("second", 3)
        self.assertEqual(q.next(), "first")

    def test_names(self):
        q = TaskQueue()
        q.add("b", 2)
        q.add("a", 1)
        self.assertEqual(q.names(), ["a", "b"])

    def test_empty(self):
        with self.assertRaises(IndexError):
            TaskQueue().next()
