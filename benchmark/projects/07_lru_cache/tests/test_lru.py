import unittest

from lru import LRUCache


class LRUTests(unittest.TestCase):
    def test_put_and_get(self):
        c = LRUCache(2)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("zzz"))

    def test_evicts_oldest(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        self.assertIsNone(c.get("a"))
        self.assertEqual(len(c), 2)

    def test_reading_keeps_an_entry_alive(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")
        c.put("c", 3)
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("b"))

    def test_order_after_reads(self):
        c = LRUCache(3)
        for k in "abc":
            c.put(k, k.upper())
        c.get("a")
        self.assertEqual(c.keys(), ["b", "c", "a"])

    def test_overwrite_refreshes(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("a", 10)
        c.put("c", 3)
        self.assertEqual(c.get("a"), 10)
        self.assertIsNone(c.get("b"))
