import unittest

from shopkeeper.services.inventory import OutOfStock
from shopkeeper.services.orders import OrderError
from shopkeeper.services.pricing import price_order, vat_for
from tests.helpers import shop


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.inv, self.svc = shop()

    def test_vat(self):
        self.assertEqual(vat_for(100000), 7500)
        self.assertEqual(vat_for(10), 1)          # 0.75 kobo rounds to 1

    def test_bronze_customer(self):
        o = self.svc.place("C1", [("RICE5", 1)], "2026-01-05")
        bill = price_order(o, self.repo.customer("C1"))
        self.assertEqual(bill, {"subtotal": 850000, "discount": 0, "vat": 63750, "total": 913750})

    def test_silver_discount_comes_before_vat(self):
        o = self.svc.place("C2", [("OIL1", 10)], "2026-01-05")
        bill = price_order(o, self.repo.customer("C2"))
        self.assertEqual(bill["discount"], 120000)
        self.assertEqual(bill["vat"], 171000)
        self.assertEqual(bill["total"], 2400000 - 120000 + 171000)

    def test_vat_exempt_lines(self):
        o = self.svc.place("C3", [("BOOK", 2), ("SUG1", 1)], "2026-01-05")
        bill = price_order(o, self.repo.customer("C3"))
        self.assertEqual(bill["discount"], 10000 + 19000)
        self.assertEqual(bill["vat"], vat_for(190000 - 19000))


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.inv, self.svc = shop()

    def test_place_takes_stock(self):
        o = self.svc.place("C1", [("RICE5", 2), ("OIL1", 1)], "2026-01-05")
        self.assertEqual(o.number, "ORD-00001")
        self.assertEqual(self.repo.product("RICE5").stock, 8)

    def test_failed_order_changes_nothing(self):
        with self.assertRaises(OutOfStock):
            self.svc.place("C1", [("RICE5", 2), ("BOOK", 9)], "2026-01-05")
        self.assertEqual(self.repo.product("RICE5").stock, 10)
        self.assertEqual(self.repo.product("BOOK").stock, 3)
        self.assertEqual(self.repo.orders, {})

    def test_pay_adds_lifetime_spend(self):
        o = self.svc.place("C1", [("RICE5", 1)], "2026-01-05")
        bill = self.svc.pay(o.number)
        self.assertEqual(self.repo.customer("C1").lifetime_spend, bill["total"])
        with self.assertRaises(OrderError):
            self.svc.pay(o.number)

    def test_cancel_paid_order_restores_everything(self):
        o = self.svc.place("C2", [("RICE5", 3)], "2026-01-05")
        self.svc.pay(o.number)
        self.svc.cancel(o.number)
        self.assertEqual(self.repo.product("RICE5").stock, 10)
        self.assertEqual(self.repo.customer("C2").lifetime_spend, 150_000_00)
        self.assertEqual(o.status, "cancelled")

    def test_deliver_only_paid(self):
        o = self.svc.place("C1", [("OIL1", 1)], "2026-01-05")
        with self.assertRaises(OrderError):
            self.svc.deliver(o.number)
        self.svc.pay(o.number)
        self.svc.deliver(o.number)
        self.assertEqual(o.status, "delivered")
