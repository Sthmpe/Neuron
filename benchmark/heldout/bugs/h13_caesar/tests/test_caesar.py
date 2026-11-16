import unittest

import caesar


class Tests(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(caesar.encrypt("abc", 1), "bcd")

    def test_wraps_around(self):
        self.assertEqual(caesar.encrypt("xyz", 3), "abc")

    def test_uppercase(self):
        self.assertEqual(caesar.encrypt("ABC", 1), "BCD")
        self.assertEqual(caesar.encrypt("Hello, World!", 3), "Khoor, Zruog!")

    def test_other_characters_unchanged(self):
        self.assertEqual(caesar.encrypt("a-b c!", 1), "b-c d!")

    def test_round_trip(self):
        msg = "Meet Me At Noon"
        self.assertEqual(caesar.decrypt(caesar.encrypt(msg, 7), 7), msg)
