"""Core proof, category B: whole-codebase bugs. Each project has several modules; the bug is not in the file the failing
test imports first. The examiner restores the ORIGINAL tests, runs them, then runs HIDDEN tests (never shown to the agent).
'fix' is the reference change used only to validate the examiner. Written before any tuning."""

PY_TEST = ["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."]

BUGS = []

# B1: invoice totals: VAT rate typo in a different module from the totals the test checks
BUGS.append({"id": "B1_py_invoice", "lang": "python", "test_cmd": PY_TEST, "files": {
    "invoice/__init__.py": "",
    "invoice/models.py": '''from dataclasses import dataclass


@dataclass
class Line:
    """One line of an invoice. Amounts are in kobo."""
    description: str
    quantity: int
    unit_price: int

    def amount(self):
        return self.quantity * self.unit_price
''',
    "invoice/tax.py": '''VAT_RATE = 0.75          # Nigerian VAT: 7.5 percent


def vat(amount):
    """VAT on an amount in kobo, rounded to the nearest kobo."""
    return round(amount * VAT_RATE)
''',
    "invoice/totals.py": '''from .tax import vat


def subtotal(lines):
    return sum(line.amount() for line in lines)


def total(lines):
    s = subtotal(lines)
    return s + vat(s)
''',
    "invoice/fmt.py": '''def naira(kobo):
    """Format kobo as naira with two decimals, e.g. 2150000 -> 'NGN 21,500.00'."""
    return f"NGN {kobo / 100:,.2f}"
''',
    "tests/__init__.py": "",
    "tests/test_invoice.py": '''import unittest

from invoice.fmt import naira
from invoice.models import Line
from invoice.totals import subtotal, total


class InvoiceTests(unittest.TestCase):
    def test_subtotal(self):
        self.assertEqual(subtotal([Line("bag", 2, 10000), Line("tag", 1, 500)]), 20500)

    def test_total_includes_vat(self):
        self.assertEqual(total([Line("bag", 2, 1000000)]), 2150000)

    def test_format(self):
        self.assertEqual(naira(2150000), "NGN 21,500.00")
'''},
    "hidden": {"tests/test_hidden_b1.py": '''import unittest

from invoice.models import Line
from invoice.tax import vat
from invoice.totals import total


class Hidden(unittest.TestCase):
    def test_vat(self):
        self.assertEqual(vat(1000), 75)
        self.assertEqual(vat(333), 25)

    def test_total_many_lines(self):
        self.assertEqual(total([Line("a", 3, 2000), Line("b", 1, 4000)]), 10750)
'''},
    "fix": {"invoice/tax.py": ("VAT_RATE = 0.75", "VAT_RATE = 0.075")}})

# B2: reorder report: boundary comparison in the rules module, not the report the test calls
BUGS.append({"id": "B2_py_inventory", "lang": "python", "test_cmd": PY_TEST, "files": {
    "stock/__init__.py": "",
    "stock/items.py": '''from dataclasses import dataclass


@dataclass
class Item:
    name: str
    on_hand: int
    reorder_level: int
''',
    "stock/rules.py": '''def needs_reorder(item):
    """An item is reordered when what is left is at or below its reorder level."""
    return item.on_hand < item.reorder_level
''',
    "stock/report.py": '''from .rules import needs_reorder


def reorder_list(items):
    """Names of the items to reorder, in alphabetical order."""
    return sorted(i.name for i in items if needs_reorder(i))


def summary(items):
    names = reorder_list(items)
    return f"{len(names)} to reorder: " + ", ".join(names) if names else "nothing to reorder"
''',
    "tests/__init__.py": "",
    "tests/test_report.py": '''import unittest

from stock.items import Item
from stock.report import reorder_list, summary


class ReportTests(unittest.TestCase):
    def test_reorder_list(self):
        items = [Item("rice", 3, 5), Item("beans", 5, 5), Item("oil", 9, 4)]
        self.assertEqual(reorder_list(items), ["beans", "rice"])

    def test_summary(self):
        self.assertEqual(summary([Item("salt", 2, 2)]), "1 to reorder: salt")
'''},
    "hidden": {"tests/test_hidden_b2.py": '''import unittest

from stock.items import Item
from stock.rules import needs_reorder


class Hidden(unittest.TestCase):
    def test_boundaries(self):
        self.assertTrue(needs_reorder(Item("a", 0, 0)))
        self.assertTrue(needs_reorder(Item("b", 7, 7)))
        self.assertFalse(needs_reorder(Item("c", 8, 7)))
'''},
    "fix": {"stock/rules.py": ("item.on_hand < item.reorder_level", "item.on_hand <= item.reorder_level")}})

# B3: booking clashes: the time parser misreads hours from 10 upwards
BUGS.append({"id": "B3_py_schedule", "lang": "python", "test_cmd": PY_TEST, "files": {
    "schedule/__init__.py": "",
    "schedule/timeutil.py": '''def to_minutes(text):
    """'09:30' -> 570 minutes after midnight."""
    text = text.strip()
    return int(text[0]) * 60 + int(text[3:5])


def from_minutes(m):
    return f"{m // 60:02d}:{m % 60:02d}"
''',
    "schedule/bookings.py": '''from .timeutil import to_minutes


def overlaps(a, b):
    """a and b are (start, end) strings like ('10:00', '11:30'); touching ends do not overlap."""
    return to_minutes(a[0]) < to_minutes(b[1]) and to_minutes(b[0]) < to_minutes(a[1])


def clashes(bookings):
    """Pairs of booking names that overlap, in the order given."""
    out = []
    for i, (n1, t1) in enumerate(bookings):
        for n2, t2 in bookings[i + 1:]:
            if overlaps(t1, t2):
                out.append((n1, n2))
    return out
''',
    "tests/__init__.py": "",
    "tests/test_bookings.py": '''import unittest

from schedule.bookings import clashes, overlaps


class BookingTests(unittest.TestCase):
    def test_morning(self):
        self.assertTrue(overlaps(("08:00", "09:00"), ("08:30", "09:30")))
        self.assertFalse(overlaps(("08:00", "09:00"), ("09:00", "09:30")))

    def test_late_morning(self):
        self.assertTrue(overlaps(("10:00", "11:00"), ("10:30", "11:30")))
        self.assertFalse(overlaps(("09:00", "10:00"), ("10:00", "11:00")))

    def test_clashes(self):
        day = [("Ada", ("13:00", "14:00")), ("Bisi", ("13:30", "15:00")), ("Chi", ("15:00", "16:00"))]
        self.assertEqual(clashes(day), [("Ada", "Bisi")])
'''},
    "hidden": {"tests/test_hidden_b3.py": '''import unittest

from schedule.timeutil import from_minutes, to_minutes


class Hidden(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(to_minutes("00:05"), 5)
        self.assertEqual(to_minutes("12:45"), 765)
        self.assertEqual(to_minutes(" 23:59"), 1439)
        self.assertEqual(from_minutes(to_minutes("17:20")), "17:20")
'''},
    "fix": {"schedule/timeutil.py": ("int(text[0]) * 60 + int(text[3:5])", "int(text[:2]) * 60 + int(text[3:5])")}})

# B4: shopping cart: discount percent treated as a fraction in the pricing helper
BUGS.append({"id": "B4_js_cart", "lang": "javascript", "test_cmd": ["npm", "test", "--silent"], "files": {
    "package.json": '{\n  "name": "cart",\n  "version": "1.0.0",\n  "private": true,\n  "scripts": {"test": "node test/cart.test.js"}\n}\n',
    "cart/pricing.js": '''// Price after a percentage discount, rounded to whole naira. percent is like 10 for 10%.
function discounted(price, percent) {
  return Math.round(price - price * percent);
}
module.exports = { discounted };
''',
    "cart/cart.js": '''const { discounted } = require('./pricing');

// items: [{ name, price, qty }]; discountPercent applies to every item.
function total(items, discountPercent = 0) {
  return items.reduce((sum, it) => sum + discounted(it.price, discountPercent) * it.qty, 0);
}
function count(items) { return items.reduce((n, it) => n + it.qty, 0); }
module.exports = { total, count };
''',
    "test/cart.test.js": '''const assert = require('assert');
const { total, count } = require('../cart/cart');
const items = [{ name: 'rice', price: 42000, qty: 2 }, { name: 'oil', price: 9000, qty: 1 }];
assert.strictEqual(count(items), 3);
assert.strictEqual(total(items), 93000);
assert.strictEqual(total(items, 10), 83700);
console.log('cart tests passed');
'''},
    "hidden": {"test/hidden_b4.test.js": '''const assert = require('assert');
const { discounted } = require('../cart/pricing');
assert.strictEqual(discounted(1000, 25), 750);
assert.strictEqual(discounted(999, 0), 999);
assert.strictEqual(discounted(1500, 5), 1425);
console.log('hidden ok');
'''},
    "hidden_cmd": ["node", "test/hidden_b4.test.js"],
    "fix": {"cart/pricing.js": ("price - price * percent)", "price - price * percent / 100)")}})

# B5: CSV totals: commas inside quoted fields split a row in two
BUGS.append({"id": "B5_js_csv", "lang": "javascript", "test_cmd": ["npm", "test", "--silent"], "files": {
    "package.json": '{\n  "name": "csvtotals",\n  "version": "1.0.0",\n  "private": true,\n  "scripts": {"test": "node test/summary.test.js"}\n}\n',
    "lib/parse.js": '''// Split one CSV line into fields. Fields may be wrapped in double quotes.
function splitLine(line) {
  return line.split(',').map(f => f.trim().replace(/^"|"$/g, ''));
}
function parse(text) {
  const lines = text.trim().split(/\\r?\\n/);
  const header = splitLine(lines[0]);
  return lines.slice(1).map(l => Object.fromEntries(splitLine(l).map((v, i) => [header[i], v])));
}
module.exports = { splitLine, parse };
''',
    "lib/summary.js": '''const { parse } = require('./parse');

// Total of a numeric column for each value of a key column.
function totalBy(text, key, value) {
  const out = {};
  for (const row of parse(text)) out[row[key]] = (out[row[key]] || 0) + Number(row[value]);
  return out;
}
module.exports = { totalBy };
''',
    "test/summary.test.js": '''const assert = require('assert');
const { totalBy } = require('../lib/summary');
const csv = 'branch,amount\\n"Lagos, Ikeja",100\\nAbuja,50\\n"Lagos, Ikeja",25\\n';
assert.deepStrictEqual(totalBy(csv, 'branch', 'amount'), { 'Lagos, Ikeja': 125, Abuja: 50 });
console.log('summary tests passed');
'''},
    "hidden": {"test/hidden_b5.test.js": '''const assert = require('assert');
const { splitLine } = require('../lib/parse');
assert.deepStrictEqual(splitLine('a,"b, c",d'), ['a', 'b, c', 'd']);
assert.deepStrictEqual(splitLine('"x",y'), ['x', 'y']);
assert.deepStrictEqual(splitLine('1,2,3'), ['1', '2', '3']);
console.log('hidden ok');
'''},
    "hidden_cmd": ["node", "test/hidden_b5.test.js"],
    "fix_file": {"lib/parse.js": '''// Split one CSV line into fields. Fields may be wrapped in double quotes.
function splitLine(line) {
  const out = []; let cur = ''; let quoted = false;
  for (const ch of line) {
    if (ch === '"') { quoted = !quoted; continue; }
    if (ch === ',' && !quoted) { out.push(cur.trim()); cur = ''; continue; }
    cur += ch;
  }
  out.push(cur.trim());
  return out;
}
function parse(text) {
  const lines = text.trim().split(/\\r?\\n/);
  const header = splitLine(lines[0]);
  return lines.slice(1).map(l => Object.fromEntries(splitLine(l).map((v, i) => [header[i], v])));
}
module.exports = { splitLine, parse };
'''}})

# B6: payroll: overtime multiplier constant wrong in a different file from the gross pay function
BUGS.append({"id": "B6_go_payroll", "lang": "go", "test_cmd": ["go", "test", "./..."], "files": {
    "go.mod": "module example.com/payroll\n\ngo 1.21\n",
    "pay/rates.go": '''package pay

// Hours beyond the standard week are paid at time and a half.
const StandardWeek = 40.0
const OvertimeRate = 1.25
''',
    "pay/gross.go": '''package pay

import "math"

// Gross pay for a week, rounded to whole naira.
func Gross(hours, rate float64) float64 {
	regular := math.Min(hours, StandardWeek)
	over := math.Max(0, hours-StandardWeek)
	return math.Round(regular*rate + over*rate*OvertimeRate)
}
''',
    "pay/gross_test.go": '''package pay

import "testing"

func TestGross(t *testing.T) {
	if g := Gross(38, 1000); g != 38000 {
		t.Errorf("Gross(38, 1000) = %v, want 38000", g)
	}
	if g := Gross(44, 1000); g != 46000 {
		t.Errorf("Gross(44, 1000) = %v, want 46000", g)
	}
}
'''},
    "hidden": {"pay/hidden_b6_test.go": '''package pay

import "testing"

func TestHiddenOvertime(t *testing.T) {
	if g := Gross(50, 800); g != 44000 {
		t.Errorf("Gross(50, 800) = %v, want 44000", g)
	}
	if g := Gross(40, 1200); g != 48000 {
		t.Errorf("Gross(40, 1200) = %v, want 48000", g)
	}
}
'''},
    "fix": {"pay/rates.go": ("const OvertimeRate = 1.25", "const OvertimeRate = 1.5")}})

# B7: statistics: the median of an even-length list takes one middle value
BUGS.append({"id": "B7_go_stats", "lang": "go", "test_cmd": ["go", "test", "./..."], "files": {
    "go.mod": "module example.com/stats\n\ngo 1.21\n",
    "stats/median.go": '''package stats

import "sort"

// Median of the values (the input is not changed).
func Median(xs []float64) float64 {
	s := append([]float64(nil), xs...)
	sort.Float64s(s)
	n := len(s)
	if n == 0 {
		return 0
	}
	return s[n/2]
}
''',
    "stats/report.go": '''package stats

import "fmt"

// Summary line for a list of daily sales.
func Summary(xs []float64) string {
	total := 0.0
	for _, x := range xs {
		total += x
	}
	return fmt.Sprintf("days %d, total %.0f, median %.1f", len(xs), total, Median(xs))
}
''',
    "stats/report_test.go": '''package stats

import "testing"

func TestSummary(t *testing.T) {
	if s := Summary([]float64{40, 10, 30, 20}); s != "days 4, total 100, median 25.0" {
		t.Errorf("got %q", s)
	}
	if s := Summary([]float64{5, 1, 3}); s != "days 3, total 9, median 3.0" {
		t.Errorf("got %q", s)
	}
}
'''},
    "hidden": {"stats/hidden_b7_test.go": '''package stats

import "testing"

func TestHiddenMedian(t *testing.T) {
	cases := map[float64][]float64{2.5: {1, 2, 3, 4}, 7: {7}, 0: {}, 4: {9, 1, 4}}
	for want, xs := range cases {
		if got := Median(xs); got != want {
			t.Errorf("Median(%v) = %v, want %v", xs, got, want)
		}
	}
}
'''},
    "fix_file": {"stats/median.go": '''package stats

import "sort"

// Median of the values (the input is not changed).
func Median(xs []float64) float64 {
	s := append([]float64(nil), xs...)
	sort.Float64s(s)
	n := len(s)
	if n == 0 {
		return 0
	}
	if n%2 == 0 {
		return (s[n/2-1] + s[n/2]) / 2
	}
	return s[n/2]
}
'''}})

# B8: bank account: the withdrawal fee is charged twice, once in each of two files
BUGS.append({"id": "B8_cpp_bank", "lang": "c++", "test_cmd": ["make", "-s", "test"], "files": {
    "Makefile": "test: tests/run\n\t./tests/run\ntests/run: src/account.cpp src/account.h src/ledger.cpp src/ledger.h tests/test.cpp\n\tg++ -std=c++17 -O1 -Isrc -o tests/run src/account.cpp src/ledger.cpp tests/test.cpp\n",
    "src/account.h": '''#pragma once
// A savings account. Amounts in naira. Every withdrawal costs a fixed fee.
class Account {
public:
    explicit Account(long opening) : balance_(opening) {}
    long balance() const { return balance_; }
    static long fee() { return 50; }
    bool withdraw(long amount);           // false (and no change) if the balance cannot cover amount + fee
    void charge(long amount) { balance_ -= amount; }
    void deposit(long amount) { balance_ += amount; }
private:
    long balance_;
};
''',
    "src/account.cpp": '''#include "account.h"

bool Account::withdraw(long amount) {
    if (amount + fee() > balance_) return false;
    balance_ -= amount + fee();
    return true;
}
''',
    "src/ledger.h": '''#pragma once
#include <string>
#include <vector>
#include "account.h"
// Records every operation on an account.
struct Ledger {
    std::vector<std::string> lines;
    bool withdraw(Account& a, long amount);
    void deposit(Account& a, long amount);
};
''',
    "src/ledger.cpp": '''#include "ledger.h"

bool Ledger::withdraw(Account& a, long amount) {
    if (!a.withdraw(amount)) { lines.push_back("refused " + std::to_string(amount)); return false; }
    a.charge(Account::fee());
    lines.push_back("withdrew " + std::to_string(amount));
    return true;
}

void Ledger::deposit(Account& a, long amount) {
    a.deposit(amount);
    lines.push_back("deposited " + std::to_string(amount));
}
''',
    "tests/test.cpp": '''#include <iostream>
#include "account.h"
#include "ledger.h"
static int failures = 0;
#define CHECK(c) do { if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\\n"; } } while (0)
int main() {
    Account a(10000); Ledger l;
    CHECK(l.withdraw(a, 1000));
    CHECK(a.balance() == 8950);
    l.deposit(a, 50);
    CHECK(a.balance() == 9000);
    CHECK(!l.withdraw(a, 9000));
    CHECK(l.lines.size() == 3);
    if (!failures) std::cout << "all tests passed\\n";
    return failures;
}
'''},
    "hidden": {"tests/hidden_b8.cpp": '''#include <iostream>
#include "account.h"
#include "ledger.h"
int main() {
    Account a(200); Ledger l; int bad = 0;
    if (!l.withdraw(a, 150)) bad++;
    if (a.balance() != 0) bad++;
    Account b(500);
    if (l.withdraw(b, 451)) bad++;
    if (b.balance() != 500) bad++;
    std::cout << (bad ? "hidden failed" : "hidden ok") << "\\n";
    return bad;
}
'''},
    "hidden_cmd": ["sh", "-c", "g++ -std=c++17 -Isrc -o /tmp/hb8 src/account.cpp src/ledger.cpp tests/hidden_b8.cpp && /tmp/hb8"],
    "fix": {"src/ledger.cpp": ("    a.charge(Account::fee());\n", "")}})

for b in BUGS:
    b["category"] = "bug"
    b["budget_s"] = 600
    b["request"] = ("The tests of this project fail. Find the bug in the source code and fix it so the tests pass. "
                    "Do not change the tests.")
    b.setdefault("hidden_cmd", PY_TEST if b["lang"] == "python" else b["test_cmd"])
