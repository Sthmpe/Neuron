import unittest

from shopkeeper.models import Customer, Order, OrderLine, Product


class ModelTests(unittest.TestCase):
    def test_reorder(self):
        self.assertTrue(Product("A", "a", 100, stock=5).needs_reorder())
        self.assertFalse(Product("A", "a", 100, stock=6).needs_reorder())

    def test_tiers(self):
        self.assertEqual(Customer("x", "x").tier(), "bronze")
        self.assertEqual(Customer("x", "x", lifetime_spend=100_000_00).tier(), "silver")
        self.assertEqual(Customer("x", "x", lifetime_spend=500_000_00).tier(), "gold")
        self.assertEqual(Customer("x", "x", lifetime_spend=499_999_99).discount_percent(), 5)

    def test_new_customers_do_not_share_tags(self):
        a, b = Customer("a", "A"), Customer("b", "B")
        a.tags.append("vip")
        self.assertEqual(b.tags, [])

    def test_order_merges_same_line(self):
        o = Order("1", "C1", "2026-01-01")
        o.add(OrderLine("A", 2, 100))
        o.add(OrderLine("A", 3, 100))
        o.add(OrderLine("A", 1, 120))
        self.assertEqual(len(o.lines), 2)
        self.assertEqual(o.item_count(), 6)
        self.assertEqual(o.subtotal(), 620)
