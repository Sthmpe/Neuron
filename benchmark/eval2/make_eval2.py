"""Builds the second locked evaluation (eval2): sources, projects, buggy copies and tasks. Deterministic.

  python3 -m benchmark.eval2.make_eval2

Written on 2026-11-18 before any tuning on it. Every source, project and fact here is invented for this evaluation.
The clean projects in workspaces/ are the reference solutions; the agent only ever sees the buggy copies in
workspace_tasks/ (or, for the docstring task, the clean project without docstrings).
"""
import csv
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# ---- sources ----------------------------------------------------------------------------------------------
PDF_PAGES = [
    ("Harbour Street Market: 2026 report",
     ["Harbour Street Market in Port Elara opened in 2019 on the old fish quay.",
      "In 2026 the market had 142 stalls, up from 118 stalls in 2024.",
      "The market is open from Tuesday to Sunday, 7am to 6pm. It is closed on Mondays for cleaning.",
      "The market committee has nine members, elected every two years by the stall holders."]),
    ("Fees and visitors",
     ["The daily stall fee is 2,500 naira for a food stall and 1,800 naira for a dry goods stall.",
      "An annual permit costs 45,000 naira and replaces the daily fee.",
      "On an average Saturday the market receives 6,400 visitors. The weekday average is 2,150 visitors.",
      "Card payments were accepted at 61 stalls by the end of 2026."]),
    ("Plans and complaints",
     ["A new cold room with a capacity of 12 tonnes will open in March 2027.",
      "The committee aims to recycle 60 percent of market waste by 2028.",
      "The market received 37 complaints in 2025, most of them about parking near the north gate.",
      "A second entrance on Cable Road is planned for 2028, subject to council approval."]),
]
PDF_QUESTIONS = [
    {"q": "How many stalls did Harbour Street Market have in 2026?", "expect": ["142"], "doc": "harbour_market_report_2026", "page": 1},
    {"q": "What is the daily stall fee for a food stall?", "expect": ["2500"], "doc": "harbour_market_report_2026", "page": 2},
    {"q": "How many visitors come on an average Saturday?", "expect": ["6400"], "doc": "harbour_market_report_2026", "page": 2},
    {"q": "On which day of the week is the market closed?", "expect": ["monday"], "doc": "harbour_market_report_2026", "page": 1},
    {"q": "What capacity will the new cold room have?", "expect": ["12tonnes"], "doc": "harbour_market_report_2026", "page": 3},
    {"q": "How many complaints did the market receive in 2025?", "expect": ["37"], "doc": "harbour_market_report_2026", "page": 3},
]
CLINIC_ROWS = [
    ("2026-02-02", "Dental", 14, 7500), ("2026-02-02", "Eye", 9, 6000), ("2026-02-03", "General", 31, 3500),
    ("2026-02-03", "Children", 22, 3000), ("2026-02-04", "Dental", 11, 7500), ("2026-02-04", "General", 27, 3500),
    ("2026-02-05", "Eye", 12, 6000), ("2026-02-05", "Children", 18, 3000), ("2026-02-06", "Dental", 9, 7500),
    ("2026-02-06", "General", 35, 3500), ("2026-02-07", "Eye", 7, 6000), ("2026-02-07", "Children", 25, 3000),
]


def make_sources():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    out = HERE / "sources" / "harbour_market_report_2026.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=A4, invariant=1)
    for title, lines in PDF_PAGES:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(60, 780, title)
        c.setFont("Helvetica", 11)
        y = 740
        for line in lines:
            c.drawString(60, y, line)
            y -= 24
        c.showPage()
    c.save()
    with open(HERE / "sources" / "clinic_visits_2026.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "department", "visits", "fee_per_visit"])
        w.writerows(CLINIC_ROWS)


# ---- projects (clean versions = reference solutions) ------------------------------------------------------
PANTRY = {
    "pantry/__init__.py": "",
    "pantry/items.py": '''from dataclasses import dataclass
from datetime import date


@dataclass
class Item:
    name: str
    quantity: int
    expires: date
    minimum: int = 1

    def is_low(self):
        return self.quantity < self.minimum
''',
    "pantry/store.py": '''from datetime import date, timedelta

from .items import Item


class Pantry:
    def __init__(self):
        self.items = {}

    def add(self, name, quantity, expires, minimum=1):
        if name in self.items:
            self.items[name].quantity += quantity
        else:
            self.items[name] = Item(name, quantity, expires, minimum)
        return self.items[name]

    def use(self, name, quantity):
        item = self.items[name]
        if quantity > item.quantity:
            raise ValueError(f"only {item.quantity} {name} left")
        item.quantity -= quantity
        return item.quantity

    def expiring_within(self, days, today):
        limit = today + timedelta(days=days)
        return sorted(i.name for i in self.items.values() if i.expires <= limit)

    def low_stock(self):
        return sorted(i.name for i in self.items.values() if i.is_low())
''',
    "pantry/report.py": '''def shopping_list(pantry):
    lines = []
    for name in pantry.low_stock():
        item = pantry.items[name]
        lines.append(f"{name}: buy {item.minimum - item.quantity}")
    return lines


def summary(pantry, today):
    soon = pantry.expiring_within(3, today)
    return {"items": len(pantry.items), "low": len(pantry.low_stock()), "expiring_soon": soon}
''',
    "tests/__init__.py": "",
    "tests/test_store.py": '''import unittest
from datetime import date

from pantry.store import Pantry


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.p = Pantry()
        self.p.add("rice", 5, date(2026, 3, 10), minimum=2)
        self.p.add("milk", 1, date(2026, 3, 3), minimum=2)
        self.p.add("eggs", 12, date(2026, 3, 6), minimum=6)

    def test_add_more_of_the_same(self):
        self.p.add("rice", 3, date(2026, 3, 10))
        self.assertEqual(self.p.items["rice"].quantity, 8)

    def test_use_refuses_too_much(self):
        with self.assertRaises(ValueError):
            self.p.use("milk", 2)

    def test_expiring_within_includes_the_last_day(self):
        self.assertEqual(self.p.expiring_within(3, date(2026, 3, 3)), ["eggs", "milk"])

    def test_low_stock(self):
        self.assertEqual(self.p.low_stock(), ["milk"])
''',
    "tests/test_report.py": '''import unittest
from datetime import date

from pantry.report import shopping_list, summary
from pantry.store import Pantry


class ReportTests(unittest.TestCase):
    def test_shopping_list_and_summary(self):
        p = Pantry()
        p.add("oil", 1, date(2026, 4, 1), minimum=3)
        p.add("salt", 4, date(2026, 9, 1))
        self.assertEqual(shopping_list(p), ["oil: buy 2"])
        self.assertEqual(summary(p, date(2026, 3, 29)), {"items": 2, "low": 1, "expiring_soon": ["oil"]})
''',
}
PANTRY_BUG = ("pantry/store.py", "if i.expires <= limit", "if i.expires < limit")

INVOICE = {
    "package.json": '{\n  "name": "invoice-js",\n  "version": "1.0.0",\n  "private": true,\n  "scripts": {"test": "node --test"}\n}\n',
    "src/invoice.js": '''// Invoice arithmetic in kobo-free naira amounts with 2 decimals. VAT is 7.5% on the subtotal.
const VAT_RATE = 0.075;

function round2(x) {
  return Math.round(x * 100) / 100;
}

function lineTotal(line) {
  return round2(line.quantity * line.price);
}

function subtotal(lines) {
  return round2(lines.reduce((sum, l) => sum + lineTotal(l), 0));
}

function vat(amount) {
  return round2(amount * VAT_RATE);
}

function total(lines) {
  const s = subtotal(lines);
  return round2(s + vat(s));
}

module.exports = { lineTotal, subtotal, vat, total, VAT_RATE };
''',
    "test/invoice.test.js": '''const test = require('node:test');
const assert = require('node:assert');
const { lineTotal, subtotal, vat, total } = require('../src/invoice.js');

const lines = [{ quantity: 3, price: 1250.5 }, { quantity: 2, price: 799.96 }];

test('line totals', () => { assert.strictEqual(lineTotal(lines[0]), 3751.5); });
test('subtotal', () => { assert.strictEqual(subtotal(lines), 5351.42); });
test('vat rounds to the nearest kobo', () => { assert.strictEqual(vat(5351.42), 401.36); });
test('total is subtotal plus vat', () => { assert.strictEqual(total(lines), 5752.78); });
''',
}
INVOICE_BUG = ("src/invoice.js", "  return round2(amount * VAT_RATE);", "  return Math.floor(amount * VAT_RATE * 100) / 100;")

SHIFTS = {
    "go.mod": "module example.com/shifts\n\ngo 1.21\n",
    "shifts/pay.go": '''package shifts

// Weekly pay: hours up to 40 at the base rate, hours above 40 at 1.5 times the base rate. Amounts in naira.

const StandardHours = 40.0

func Overtime(hours float64) float64 {
	if hours <= StandardHours {
		return 0
	}
	return hours - StandardHours
}

func WeeklyPay(hours, rate float64) float64 {
	ot := Overtime(hours)
	return (hours-ot)*rate + ot*rate*1.5
}

func TeamPay(hours []float64, rate float64) float64 {
	total := 0.0
	for _, h := range hours {
		total += WeeklyPay(h, rate)
	}
	return total
}
''',
    "shifts/pay_test.go": '''package shifts

import "testing"

func TestOvertime(t *testing.T) {
	if got := Overtime(46); got != 6 {
		t.Fatalf("Overtime(46)=%v want 6", got)
	}
	if got := Overtime(38); got != 0 {
		t.Fatalf("Overtime(38)=%v want 0", got)
	}
}

func TestWeeklyPay(t *testing.T) {
	if got := WeeklyPay(46, 1000); got != 49000 {
		t.Fatalf("WeeklyPay(46,1000)=%v want 49000", got)
	}
	if got := WeeklyPay(30, 1000); got != 30000 {
		t.Fatalf("WeeklyPay(30,1000)=%v want 30000", got)
	}
}

func TestTeamPay(t *testing.T) {
	if got := TeamPay([]float64{40, 44}, 500); got != 43000 {
		t.Fatalf("TeamPay=%v want 43000", got)
	}
}
''',
}
SHIFTS_BUG = ("shifts/pay.go", "\treturn (hours-ot)*rate + ot*rate*1.5", "\treturn hours*rate + ot*rate*1.5")

TEMPS = {
    "Cargo.toml": '[package]\nname = "temps"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n',
    "src/lib.rs": '''//! Temperature statistics for a weather station (degrees Celsius).

pub fn mean(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().sum::<f64>() / values.len() as f64
}

pub fn median(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut v = values.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = v.len();
    if n % 2 == 1 {
        v[n / 2]
    } else {
        (v[n / 2 - 1] + v[n / 2]) / 2.0
    }
}

pub fn longest_streak_above(values: &[f64], threshold: f64) -> usize {
    let mut best = 0;
    let mut run = 0;
    for &x in values {
        if x > threshold {
            run += 1;
            if run > best {
                best = run;
            }
        } else {
            run = 0;
        }
    }
    best
}
''',
    "tests/stats.rs": '''use temps::{longest_streak_above, mean, median};

#[test]
fn mean_of_values() {
    assert_eq!(mean(&[20.0, 22.0, 24.0]), 22.0);
}

#[test]
fn median_odd_and_even() {
    assert_eq!(median(&[31.0, 25.0, 28.0]), 28.0);
    assert_eq!(median(&[30.0, 24.0, 26.0, 28.0]), 27.0);
}

#[test]
fn streak_above() {
    assert_eq!(longest_streak_above(&[30.0, 33.0, 34.0, 29.0, 35.0, 36.0, 37.0], 32.0), 3);
}
''',
}
TEMPS_BUG = ("src/lib.rs", "        (v[n / 2 - 1] + v[n / 2]) / 2.0", "        v[n / 2]")

PROJECTS = {"pantry": (PANTRY, PANTRY_BUG, "python"), "invoice_js": (INVOICE, INVOICE_BUG, "javascript"),
            "go_shifts": (SHIFTS, SHIFTS_BUG, "go"), "rust_temps": (TEMPS, TEMPS_BUG, "rust")}


def make_projects():
    for name, (files, (rel, good, bad), lang) in PROJECTS.items():
        clean = HERE / "workspaces" / name
        if clean.exists():
            shutil.rmtree(clean)
        for f, text in files.items():
            write(clean / f, text)
        task = HERE / "workspace_tasks" / f"{name}_bug"
        if task.exists():
            shutil.rmtree(task)
        shutil.copytree(clean, task)
        src = (task / rel).read_text()
        assert good in src, (name, good)
        (task / rel).write_text(src.replace(good, bad, 1))
    # the docstring task: the clean pantry project with every docstring it has (none) left to write
    doc = HERE / "workspaces" / "pantry_docs"
    if doc.exists():
        shutil.rmtree(doc)
    shutil.copytree(HERE / "workspaces" / "pantry", doc)


BUG_REQUEST_NOTE = "same fixed request as phase 5 (benchmark/phase5/run.py BUG_REQUEST)"
TASKS = [
    {"id": "E01_pdf_market", "kind": "pdf_qa", "inputs": ["sources/harbour_market_report_2026.pdf"],
     "request": "Answer from the attached report, with the page number for each answer.", "questions": PDF_QUESTIONS},
    {"id": "E02_excel_clinic", "kind": "excel", "inputs": ["sources/clinic_visits_2026.csv"],
     "request": "Make clinic_summary.xlsx: put the rows on a sheet named Data; on a sheet named Summary show, for each department, "
                "the total visits and the total fees (visits times fee per visit), and a Total row. Use formulas."},
    {"id": "E03_word_notice", "kind": "word", "inputs": [],
     "request": "Write tenancy_notice.docx: a notice from Harbourview Apartments to its tenants about the 2027 rent review, with the "
                "headings Purpose, Details and Next steps, 200 to 400 words, and a table with the columns Item and Amount (NGN) with "
                "the rows Rent 450000, Service charge 60000 and Caution deposit 100000, followed by a Total row."},
    {"id": "E04_pptx_training", "kind": "pptx", "inputs": [],
     "request": "Make food_safety.pptx: a 5-slide training deck for kitchen staff at Mama Put Kitchens: a title slide, then handwashing, "
                "safe cooking temperatures (cook chicken to 75 degrees Celsius), storage, and cleaning. At most 5 bullets per slide."},
    {"id": "E05_python_bug", "kind": "workspace_bug", "lang": "python", "workspace": "pantry"},
    {"id": "E06_js_bug", "kind": "workspace_bug", "lang": "javascript", "workspace": "invoice_js"},
    {"id": "E07_go_bug", "kind": "workspace_bug", "lang": "go", "workspace": "go_shifts"},
    {"id": "E08_rust_bug", "kind": "workspace_bug", "lang": "rust", "workspace": "rust_temps"},
    {"id": "E09_cpp_csvsum", "kind": "cpp_build", "inputs": [],
     "request": "Write a C++17 command-line program called csvsum. It reads the CSV file given as its first argument (the first line is "
                "the header) and, for every column whose values are all numbers, prints a line 'name: total' with the total to 2 "
                "decimal places, in column order. Put the sources in src/ and write a Makefile that builds ./csvsum."},
    {"id": "E10_repair_app", "kind": "web_app", "kill_and_resume": True,
     "request": "Build an app for my phone repair shop, Tunde Fixes, with login (user tunde, password spanner9). Keep customers with "
                "their name and phone. Keep repairs with the customer, the device, the parts cost and the labour cost; the repairs "
                "list must show each repair's total (parts plus labour). The dashboard shows the number of customers, the number "
                "of repairs, and the total billed (all repair totals added together)."},
    {"id": "E11_long_docstrings", "kind": "long_task", "kill_and_resume": True, "workspace": "workspaces/pantry_docs",
     "request": "Add a clear docstring to every function and method in this project's source code (not the tests) that does not "
                "already have one, explaining what it does, its inputs and what it returns. Do not change any behaviour: every "
                "existing test must still pass."},
    {"id": "E12_computed_answer", "kind": "answer", "inputs": [],
     "request": "A caterer buys 18 kg of rice at 1,250 naira per kg and 7 litres of oil at 2,900 naira per litre, and pays 7.5% VAT "
                "on the whole amount. How much does she pay in total, in naira?", "expect_number": 46010},
]


def main():
    make_sources()
    make_projects()
    write(HERE / "locked" / "tasks.json", json.dumps(TASKS, indent=1) + "\n")
    print("eval2 written:", [t["id"] for t in TASKS])


if __name__ == "__main__":
    main()
