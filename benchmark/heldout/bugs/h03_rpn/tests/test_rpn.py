import unittest

import rpn


class Tests(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(rpn.evaluate("3 4 +"), 7)

    def test_multiplication(self):
        self.assertEqual(rpn.evaluate("3 4 *"), 12)

    def test_subtraction(self):
        self.assertEqual(rpn.evaluate("10 4 -"), 6)

    def test_division(self):
        self.assertEqual(rpn.evaluate("8 2 /"), 4)

    def test_longer_expression(self):
        self.assertEqual(rpn.evaluate("5 1 2 + 4 * + 3 -"), 14)

    def test_malformed(self):
        with self.assertRaises(ValueError):
            rpn.evaluate("1 +")
