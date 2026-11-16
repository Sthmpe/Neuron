import unittest

import bill


class Tests(unittest.TestCase):
    def test_even_split(self):
        self.assertEqual(bill.split(900, 3), [300, 300, 300])

    def test_shares_add_up(self):
        self.assertEqual(sum(bill.split(1000, 3)), 1000)

    def test_extra_cents_go_to_the_first_people(self):
        self.assertEqual(bill.split(1000, 3), [334, 333, 333])
        self.assertEqual(bill.split(101, 4), [26, 25, 25, 25])

    def test_one_person(self):
        self.assertEqual(bill.split(455, 1), [455])

    def test_tip(self):
        self.assertEqual(bill.with_tip(2000, 10), 2200)

    def test_format(self):
        self.assertEqual(bill.format_cents(1205), "12.05")
