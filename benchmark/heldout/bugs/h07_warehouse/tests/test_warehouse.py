import unittest

from warehouse import OutOfStock, Warehouse


class Tests(unittest.TestCase):
    def setUp(self):
        self.w = Warehouse()
        self.w.add_shelf("A", 100)
        self.w.store("A", 30)

    def test_store(self):
        self.assertEqual(self.w.total_stock(), 30)

    def test_take(self):
        self.w.take("A", 10)
        self.assertEqual(self.w.shelves["A"].stock, 20)

    def test_cannot_take_more_than_is_there(self):
        with self.assertRaises(OutOfStock):
            self.w.take("A", 50)

    def test_stock_never_goes_negative(self):
        try:
            self.w.take("A", 31)
        except OutOfStock:
            pass
        self.assertGreaterEqual(self.w.shelves["A"].stock, 0)

    def test_no_space(self):
        with self.assertRaises(ValueError):
            self.w.store("A", 71)
