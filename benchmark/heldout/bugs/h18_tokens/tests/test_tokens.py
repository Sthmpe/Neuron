import unittest

import tokens


class Tests(unittest.TestCase):
    def test_with_brackets(self):
        self.assertEqual(tokens.tokenize("12+3*(4-1)"), ["12", "+", "3", "*", "(", "4", "-", "1", ")"])

    def test_spaces_are_ignored(self):
        self.assertEqual(tokens.tokenize(" 7 * ( 2 ) "), ["7", "*", "(", "2", ")"])

    def test_number_at_the_end(self):
        self.assertEqual(tokens.tokenize("1+25"), ["1", "+", "25"])

    def test_single_number(self):
        self.assertEqual(tokens.tokenize("3.14"), ["3.14"])

    def test_count_numbers(self):
        self.assertEqual(tokens.count_numbers("1+2+3"), 3)

    def test_bad_character(self):
        with self.assertRaises(ValueError):
            tokens.tokenize("2 $ 3")
