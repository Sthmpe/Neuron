import unittest

from account import InsufficientFunds
from bank import Bank


class BankTests(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.open("ada", 100)
        self.bank.open("ben", 20)

    def test_transfer_moves_money(self):
        self.bank.transfer("ada", "ben", 30)
        self.assertEqual(self.bank.accounts["ada"].balance, 70)
        self.assertEqual(self.bank.accounts["ben"].balance, 50)

    def test_transfer_is_logged(self):
        self.bank.transfer("ada", "ben", 30)
        self.assertEqual(self.bank.log, [("ada", "ben", 30)])

    def test_failed_transfer_changes_nothing(self):
        with self.assertRaises(InsufficientFunds):
            self.bank.transfer("ben", "ada", 500)
        self.assertEqual(self.bank.accounts["ada"].balance, 100)
        self.assertEqual(self.bank.accounts["ben"].balance, 20)
        self.assertEqual(self.bank.log, [])

    def test_money_is_never_created(self):
        try:
            self.bank.transfer("ben", "ada", 500)
        except InsufficientFunds:
            pass
        self.assertEqual(self.bank.total_money(), 120)

    def test_duplicate_account(self):
        with self.assertRaises(ValueError):
            self.bank.open("ada")
