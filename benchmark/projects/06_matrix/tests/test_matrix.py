import unittest

import matrix


class MatrixTests(unittest.TestCase):
    def test_transpose(self):
        self.assertEqual(matrix.transpose([[1, 2, 3], [4, 5, 6]]), [[1, 4], [2, 5], [3, 6]])

    def test_square_product(self):
        a = [[1, 2], [3, 4]]
        self.assertEqual(matrix.multiply(a, matrix.identity(2)), a)

    def test_wide_times_tall(self):
        a = [[1, 2, 3]]
        b = [[4], [5], [6]]
        self.assertEqual(matrix.multiply(a, b), [[32]])

    def test_tall_times_wide(self):
        a = [[1], [2]]
        b = [[3, 4, 5]]
        self.assertEqual(matrix.multiply(a, b), [[3, 4, 5], [6, 8, 10]])

    def test_shape_mismatch(self):
        with self.assertRaises(ValueError):
            matrix.multiply([[1, 2]], [[1, 2]])
