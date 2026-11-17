import unittest

from clinic.billing.fees import bill, patient_pays, visit_fee
from tests.helpers import clinic


class FeeTests(unittest.TestCase):
    def setUp(self):
        self.d, self.p, self.book = clinic()

    def test_child_discount(self):
        self.assertEqual(visit_fee(self.d["D1"], self.p["P2"], 2026), 7500)
        self.assertEqual(visit_fee(self.d["D1"], self.p["P1"], 2026), 15000)
        self.assertTrue(self.p["P2"].is_child(2026))
        self.assertFalse(self.p["P2"].is_child(2031))       # 16 is not a child any more

    def test_insurance(self):
        self.assertEqual(patient_pays(self.d["D1"], self.p["P3"], 2026), 3000)
        self.assertEqual(patient_pays(self.d["D2"], self.p["P3"], 2026), 4000)

    def test_bill(self):
        a = self.book.book(self.p["P1"], self.d["D1"], "2026-12-01", "09:00")
        b = self.book.book(self.p["P1"], self.d["D1"], "2026-12-02", "09:00")
        c = self.book.book(self.p["P3"], self.d["D2"], "2026-12-01", "08:00")
        self.book.book(self.p["P2"], self.d["D2"], "2026-12-01", "09:00")
        self.book.mark(a.ref, "attended")
        self.book.mark(b.ref, "missed")
        self.book.mark(c.ref, "attended")
        self.assertEqual(bill(self.book, self.p, self.d, 2026), {"P1": 15000 + 7500, "P3": 4000})
