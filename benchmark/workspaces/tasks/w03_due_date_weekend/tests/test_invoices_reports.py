import os
import tempfile
import unittest

from shopkeeper.services import reports
from shopkeeper.services.invoices import days_overdue, due_date, invoice_lines, late_fee
from shopkeeper.services.pricing import price_order
from shopkeeper.storage.repository import NotFound, Repository
from tests.helpers import shop


class InvoiceTests(unittest.TestCase):
    def test_due_date(self):
        self.assertEqual(due_date("2026-11-02"), "2026-11-16")      # Monday + 14 = Monday
        self.assertEqual(due_date("2026-11-01"), "2026-11-16")      # lands on Sunday -> Monday

    def test_overdue_and_fee(self):
        self.assertEqual(days_overdue("2026-11-02", "2026-11-10"), 0)
        self.assertEqual(days_overdue("2026-11-02", "2026-11-30"), 14)
        self.assertEqual(late_fee(100000, 6), 0)
        self.assertEqual(late_fee(100000, 14), 2000)
        self.assertEqual(late_fee(100000, 200), 10000)

    def test_invoice_text(self):
        repo, inv, svc = shop()
        o = svc.place("C2", [("OIL1", 2)], "2026-11-02")
        text = "\n".join(invoice_lines(o, repo))
        self.assertIn("2 x Palm Oil 1L @ ₦2,400.00 = ₦4,800.00", text)
        self.assertIn("Loyalty discount -₦240.00", text)
        self.assertIn("Due 2026-11-16", text)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.inv, self.svc = shop()
        a = self.svc.place("C1", [("OIL1", 5), ("RICE5", 1)], "2026-01-05")
        b = self.svc.place("C2", [("SUG1", 5)], "2026-01-05")
        c = self.svc.place("C3", [("RICE5", 2)], "2026-01-06")
        self.svc.pay(a.number)
        self.svc.pay(c.number)
        self.svc.cancel(b.number)

    def test_best_sellers_ignore_cancelled(self):
        self.assertEqual(reports.best_sellers(self.repo), ["OIL1", "RICE5"])

    def test_revenue_by_day(self):
        rev = reports.revenue_by_day(self.repo, price_order)
        self.assertEqual(list(rev), ["2026-01-05", "2026-01-06"])
        self.assertEqual(rev["2026-01-06"], price_order(self.repo.order("ORD-00003"), self.repo.customer("C3"))["total"])

    def test_tiers(self):
        t = reports.customers_by_tier(self.repo)
        self.assertEqual(t["gold"], ["C3"])
        self.assertEqual(t["silver"], ["C2"])


class StorageTests(unittest.TestCase):
    def test_round_trip(self):
        repo, inv, svc = shop()
        svc.place("C1", [("RICE5", 2)], "2026-01-05")
        path = os.path.join(tempfile.mkdtemp(), "shop.json")
        repo.save(path)
        again = Repository.load(path)
        self.assertEqual(again.product("RICE5").stock, 8)
        self.assertEqual(again.order("ORD-00001").lines[0].quantity, 2)
        self.assertEqual(again.new_order_number(), "ORD-00002")

    def test_search_and_missing(self):
        repo, _, _ = shop()
        self.assertEqual([p.sku for p in repo.search_products("OIL")], ["OIL1"])
        self.assertEqual([p.sku for p in repo.search_products("k")], ["BOOK", "RICE5", "SUG1"])
        with self.assertRaises(NotFound):
            repo.product("NOPE")
