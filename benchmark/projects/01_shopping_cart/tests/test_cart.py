import unittest

from cart import Cart


class CartTests(unittest.TestCase):
    def setUp(self):
        self.cart = Cart()
        self.cart.add("pen", 2.50, 4)
        self.cart.add("book", 10.00)

    def test_subtotal(self):
        self.assertEqual(self.cart.subtotal(), 20.00)

    def test_total_without_discount(self):
        self.assertEqual(self.cart.total(), 20.00)

    def test_total_with_discount(self):
        self.cart.set_discount(25)
        self.assertEqual(self.cart.total(), 15.00)

    def test_full_discount(self):
        self.cart.set_discount(100)
        self.assertEqual(self.cart.total(), 0)

    def test_bad_discount(self):
        with self.assertRaises(ValueError):
            self.cart.set_discount(120)
