import unittest

from shopkeeper.services.inventory import OutOfStock
from tests.helpers import shop


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.inv, _ = shop()

    def test_receive(self):
        self.inv.receive("RICE5", 5)
        self.assertEqual(self.repo.product("RICE5").stock, 15)
        with self.assertRaises(ValueError):
            self.inv.receive("RICE5", 0)

    def test_reserve_exact_stock(self):
        self.inv.reserve("BOOK", 3)
        self.assertEqual(self.repo.product("BOOK").stock, 0)

    def test_reserve_too_much_changes_nothing(self):
        with self.assertRaises(OutOfStock):
            self.inv.reserve("BOOK", 4)
        self.assertEqual(self.repo.product("BOOK").stock, 3)

    def test_reorder_list(self):
        self.assertEqual(self.inv.reorder_list(), ["BOOK"])
        self.inv.reserve("SUG1", 2)
        self.assertEqual(self.inv.reorder_list(), ["BOOK", "SUG1"])

    def test_total_value(self):
        self.assertEqual(self.inv.total_value(), 10 * 850000 + 40 * 240000 + 3 * 50000 + 6 * 190000)
