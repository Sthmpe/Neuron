import unittest

from clinic.scheduling.book import Clash
from clinic.scheduling.reminders import reminders_for
from tests.helpers import clinic


class BookTests(unittest.TestCase):
    def setUp(self):
        self.d, self.p, self.book = clinic()

    def test_book_and_refs(self):
        a = self.book.book(self.p["P1"], self.d["D1"], "2026-12-01", "09:00")
        b = self.book.book(self.p["P2"], self.d["D1"], "2026-12-01", "09:30")
        self.assertEqual((a.ref, b.ref), ("A0001", "A0002"))

    def test_doctor_clash(self):
        self.book.book(self.p["P1"], self.d["D1"], "2026-12-01", "09:00", minutes=60)
        with self.assertRaises(Clash):
            self.book.book(self.p["P2"], self.d["D1"], "2026-12-01", "09:30")

    def test_back_to_back_is_fine(self):
        self.book.book(self.p["P1"], self.d["D1"], "2026-12-01", "09:00")
        self.book.book(self.p["P2"], self.d["D1"], "2026-12-01", "09:30")
        self.assertEqual(len(self.book.for_doctor("D1", "2026-12-01")), 2)

    def test_cancelled_slot_can_be_rebooked(self):
        a = self.book.book(self.p["P1"], self.d["D1"], "2026-12-01", "10:00")
        self.book.cancel(a.ref)
        self.book.book(self.p["P2"], self.d["D1"], "2026-12-01", "10:00")
        self.assertEqual(len(self.book.for_doctor("D1", "2026-12-01")), 1)

    def test_patient_cannot_be_in_two_places(self):
        self.book.book(self.p["P1"], self.d["D1"], "2026-12-01", "09:00")
        with self.assertRaises(Clash):
            self.book.book(self.p["P1"], self.d["D2"], "2026-12-01", "09:00")

    def test_not_a_slot(self):
        with self.assertRaises(ValueError):
            self.book.book(self.p["P1"], self.d["D1"], "2026-12-01", "13:00")

    def test_reminders(self):
        self.book.book(self.p["P2"], self.d["D2"], "2026-12-02", "11:00")
        self.book.book(self.p["P1"], self.d["D1"], "2026-12-02", "09:00")
        c = self.book.book(self.p["P3"], self.d["D1"], "2026-12-02", "15:00")
        self.book.cancel(c.ref)
        self.book.book(self.p["P3"], self.d["D1"], "2026-12-03", "15:00")
        msgs = reminders_for(self.book, self.p, self.d, "2026-12-01")
        self.assertEqual([m[0] for m in msgs], ["0801", "0802"])
        self.assertIn("Hello Ngozi, a reminder of your appointment with Dr Bello tomorrow at 09:00.", msgs[0][1])
