"""Core proof, category C: multi-file features on existing, working projects. The examiner runs the project's ORIGINAL
tests (restored) and HIDDEN tests for the new feature. 'reference' holds files of a correct implementation, used only to
validate the examiner. Written before any tuning."""
import copy

from .defs_bugs import BUGS, PY_TEST


def fixed(bug_id):
    """A bug project with its reference fix applied: the working project a feature is added to."""
    b = next(x for x in BUGS if x["id"] == bug_id)
    files = copy.deepcopy(b["files"])
    for path, (old, new) in b.get("fix", {}).items():
        files[path] = files[path].replace(old, new)
    for path, text in b.get("fix_file", {}).items():
        files[path] = text
    return files


FEATURES = []

FEATURES.append({"id": "C1_py_invoice_discounts", "lang": "python", "test_cmd": PY_TEST, "files": fixed("B1_py_invoice"),
    "request": "Add discount codes to this invoice project. Create invoice/discounts.py with apply_code(subtotal, code): SAVE10 "
               "takes 10 percent off, FLAT500 takes 500 naira (50000 kobo) off but never below zero, and an unknown code raises "
               "ValueError. Then change invoice.totals.total(lines, code=None) so a code is applied to the subtotal before VAT. "
               "Keep the existing behaviour when no code is given and keep the existing tests passing.",
    "hidden": {"tests/test_hidden_c1.py": '''import unittest

from invoice.discounts import apply_code
from invoice.models import Line
from invoice.totals import total


class Hidden(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(apply_code(20000, "SAVE10"), 18000)
        self.assertEqual(apply_code(100000, "FLAT500"), 50000)
        self.assertEqual(apply_code(30000, "FLAT500"), 0)
        with self.assertRaises(ValueError):
            apply_code(1000, "FREE")

    def test_total_with_code(self):
        self.assertEqual(total([Line("bag", 2, 10000)], "SAVE10"), 19350)
        self.assertEqual(total([Line("bag", 1, 100000)], code="FLAT500"), 53750)
        self.assertEqual(total([Line("bag", 2, 10000)]), 21500)
'''},
    "reference": {"invoice/discounts.py": '''def apply_code(subtotal, code):
    if code == "SAVE10":
        return round(subtotal * 0.9)
    if code == "FLAT500":
        return max(0, subtotal - 50000)
    raise ValueError(f"unknown discount code: {code}")
''', "invoice/totals.py": '''from .discounts import apply_code
from .tax import vat


def subtotal(lines):
    return sum(line.amount() for line in lines)


def total(lines, code=None):
    s = subtotal(lines)
    if code is not None:
        s = apply_code(s, code)
    return s + vat(s)
'''}})

FEATURES.append({"id": "C2_py_inventory_export", "lang": "python", "test_cmd": PY_TEST, "files": fixed("B2_py_inventory"),
    "request": "Add a CSV export to this stock project. Create stock/export.py with to_csv(items) that returns text: the header "
               "line name,on_hand,reorder_level,reorder and then one line per item in alphabetical order of name, where reorder is "
               "yes or no according to the existing reorder rule. Also make python3 -m stock.export FILE work: FILE is a JSON list "
               "of objects with name, on_hand and reorder_level, and the command prints the CSV.",
    "hidden": {"tests/test_hidden_c2.py": '''import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from stock.export import to_csv
from stock.items import Item


class Hidden(unittest.TestCase):
    def test_to_csv(self):
        text = to_csv([Item("rice", 3, 5), Item("beans", 9, 5)])
        self.assertEqual(text.strip().splitlines(), ["name,on_hand,reorder_level,reorder", "beans,9,5,no", "rice,3,5,yes"])

    def test_command(self):
        f = Path(tempfile.mkdtemp()) / "items.json"
        f.write_text(json.dumps([{"name": "salt", "on_hand": 2, "reorder_level": 2}]))
        out = subprocess.run([sys.executable, "-m", "stock.export", str(f)], capture_output=True, text=True).stdout
        self.assertEqual(out.strip().splitlines(), ["name,on_hand,reorder_level,reorder", "salt,2,2,yes"])
'''},
    "reference": {"stock/export.py": '''import json
import sys

from .items import Item
from .rules import needs_reorder


def to_csv(items):
    lines = ["name,on_hand,reorder_level,reorder"]
    for i in sorted(items, key=lambda i: i.name):
        lines.append(f"{i.name},{i.on_hand},{i.reorder_level},{'yes' if needs_reorder(i) else 'no'}")
    return "\\n".join(lines) + "\\n"


if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    print(to_csv([Item(d["name"], d["on_hand"], d["reorder_level"]) for d in data]), end="")
'''}})

FEATURES.append({"id": "C3_js_cart_delivery", "lang": "javascript", "test_cmd": ["npm", "test", "--silent"], "files": fixed("B4_js_cart"),
    "request": "Add delivery to this cart. Create cart/delivery.js exporting deliveryFee(subtotal): 1500 naira, or 0 when the "
               "subtotal is 20000 or more. Then change total(items, discountPercent) in cart/cart.js to add the delivery fee, "
               "worked out on the discounted subtotal, and keep count working. Update the existing test's expected totals for "
               "the new delivery rule if they change.",
    "hidden": {"test/hidden_c3.test.js": '''const assert = require('assert');
const { deliveryFee } = require('../cart/delivery');
const { total } = require('../cart/cart');
assert.strictEqual(deliveryFee(19999), 1500);
assert.strictEqual(deliveryFee(20000), 0);
assert.strictEqual(total([{ name: 'soap', price: 500, qty: 3 }]), 3000);
assert.strictEqual(total([{ name: 'rice', price: 42000, qty: 2 }, { name: 'oil', price: 9000, qty: 1 }], 10), 83700);
assert.strictEqual(total([{ name: 'tea', price: 21000, qty: 1 }], 10), 18900 + 1500);
console.log('hidden ok');
'''},
    "hidden_cmd": ["node", "test/hidden_c3.test.js"],
    "original_tests_may_change": True,
    "reference": {"cart/delivery.js": '''// Delivery costs 1500 naira, free from 20000.
function deliveryFee(subtotal) { return subtotal >= 20000 ? 0 : 1500; }
module.exports = { deliveryFee };
''', "cart/cart.js": '''const { discounted } = require('./pricing');
const { deliveryFee } = require('./delivery');

// items: [{ name, price, qty }]; discountPercent applies to every item; delivery is added on the discounted subtotal.
function total(items, discountPercent = 0) {
  const sub = items.reduce((sum, it) => sum + discounted(it.price, discountPercent) * it.qty, 0);
  return sub + deliveryFee(sub);
}
function count(items) { return items.reduce((n, it) => n + it.qty, 0); }
module.exports = { total, count };
'''}})

FEATURES.append({"id": "C4_go_payroll_payslip", "lang": "go", "test_cmd": ["go", "test", "./..."], "files": fixed("B6_go_payroll"),
    "request": "Add a payslip to package pay. Create pay/tax.go with Tax(gross float64) float64: 10 percent of the part of the "
               "gross above 30000, nothing below that, rounded to whole naira. Then add Payslip(name string, hours, rate "
               "float64) string in a new file pay/payslip.go returning exactly \"NAME: gross G, tax T, net N\" with whole-naira "
               "numbers, using the existing Gross function.",
    "hidden": {"pay/hidden_c4_test.go": '''package pay

import "testing"

func TestHiddenPayslip(t *testing.T) {
	if v := Tax(25000); v != 0 {
		t.Errorf("Tax(25000) = %v", v)
	}
	if v := Tax(46000); v != 1600 {
		t.Errorf("Tax(46000) = %v", v)
	}
	if s := Payslip("Ada", 44, 1000); s != "Ada: gross 46000, tax 1600, net 44400" {
		t.Errorf("got %q", s)
	}
	if s := Payslip("Bo", 20, 1000); s != "Bo: gross 20000, tax 0, net 20000" {
		t.Errorf("got %q", s)
	}
}
'''},
    "reference": {"pay/tax.go": '''package pay

import "math"

// Tax is 10 percent of the gross above 30000.
func Tax(gross float64) float64 {
	return math.Round(math.Max(0, gross-30000) * 0.1)
}
''', "pay/payslip.go": '''package pay

import "fmt"

// Payslip for one week.
func Payslip(name string, hours, rate float64) string {
	g := Gross(hours, rate)
	t := Tax(g)
	return fmt.Sprintf("%s: gross %.0f, tax %.0f, net %.0f", name, g, t, g-t)
}
'''}})

FEATURES.append({"id": "C5_py_notes_search", "lang": "python", "test_cmd": PY_TEST, "files": {
    "notes/__init__.py": "",
    "notes/store.py": '''import json
from pathlib import Path


def load(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else []


def save(path, notes):
    Path(path).write_text(json.dumps(notes, indent=1))


def add(path, title, body):
    notes = load(path)
    notes.append({"title": title, "body": body})
    save(path, notes)
''',
    "notes/cli.py": '''import os
import sys

from . import store

FILE = os.environ.get("NOTES_FILE", "notes.json")


def main(argv):
    if argv[:1] == ["add"] and len(argv) == 3:
        store.add(FILE, argv[1], argv[2])
        print("added")
    elif argv[:1] == ["list"]:
        for n in store.load(FILE):
            print(n["title"])
    else:
        print("usage: add TITLE BODY | list")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
''',
    "tests/__init__.py": "",
    "tests/test_cli.py": '''import os
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "notes.cli", *args], capture_output=True, text=True, env=self.env).stdout

    def setUp(self):
        self.env = dict(os.environ, NOTES_FILE=os.path.join(tempfile.mkdtemp(), "n.json"))

    def test_add_and_list(self):
        self.assertEqual(self.run_cli("add", "Shopping", "rice and oil").strip(), "added")
        self.run_cli("add", "Calls", "ring the landlord")
        self.assertEqual(self.run_cli("list").split(), ["Shopping", "Calls"])
'''},
    "request": "Add a search command to this notes tool: python3 -m notes.cli search WORD prints the titles of the notes whose "
               "title or body contains WORD, ignoring upper and lower case, one per line in the order they were added, and prints "
               "no notes found if none match. Put the matching logic in a new module notes/search.py as find(notes, word) "
               "returning the matching notes, and keep add and list working.",
    "hidden": {"tests/test_hidden_c5.py": '''import os
import subprocess
import sys
import tempfile
import unittest

from notes.search import find


class Hidden(unittest.TestCase):
    def test_find(self):
        notes = [{"title": "Shopping", "body": "Rice and OIL"}, {"title": "Oil change", "body": "car"}, {"title": "Calls", "body": "x"}]
        self.assertEqual([n["title"] for n in find(notes, "oil")], ["Shopping", "Oil change"])
        self.assertEqual(find(notes, "zzz"), [])

    def test_command(self):
        env = dict(os.environ, NOTES_FILE=os.path.join(tempfile.mkdtemp(), "n.json"))
        run = lambda *a: subprocess.run([sys.executable, "-m", "notes.cli", *a], capture_output=True, text=True, env=env).stdout
        run("add", "Market", "buy TOMATOES")
        run("add", "Rent", "pay on Friday")
        self.assertEqual(run("search", "tomatoes").strip(), "Market")
        self.assertEqual(run("search", "bicycle").strip(), "no notes found")
'''},
    "reference": {"notes/search.py": '''def find(notes, word):
    w = word.lower()
    return [n for n in notes if w in n["title"].lower() or w in n["body"].lower()]
''', "notes/cli.py": '''import os
import sys

from . import store
from .search import find

FILE = os.environ.get("NOTES_FILE", "notes.json")


def main(argv):
    if argv[:1] == ["add"] and len(argv) == 3:
        store.add(FILE, argv[1], argv[2])
        print("added")
    elif argv[:1] == ["list"]:
        for n in store.load(FILE):
            print(n["title"])
    elif argv[:1] == ["search"] and len(argv) == 2:
        hits = find(store.load(FILE), argv[1])
        print("\\n".join(n["title"] for n in hits) if hits else "no notes found")
    else:
        print("usage: add TITLE BODY | list | search WORD")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''}})

FEATURES.append({"id": "C6_js_todo_overdue", "lang": "javascript", "test_cmd": ["npm", "test", "--silent"], "files": {
    "package.json": '{\n  "name": "todo",\n  "version": "1.0.0",\n  "private": true,\n  "scripts": {"test": "node test/todo.test.js"}\n}\n',
    "todo/store.js": '''// A small to-do list kept in memory.
function create() { return []; }
function add(list, title) { list.push({ title, done: false }); return list; }
function finish(list, title) { const it = list.find(i => i.title === title); if (it) it.done = true; return list; }
function open(list) { return list.filter(i => !i.done).map(i => i.title); }
module.exports = { create, add, finish, open };
''',
    "test/todo.test.js": '''const assert = require('assert');
const t = require('../todo/store');
const l = t.create();
t.add(l, 'pay rent'); t.add(l, 'buy bread'); t.finish(l, 'pay rent');
assert.deepStrictEqual(t.open(l), ['buy bread']);
console.log('todo tests passed');
'''},
    "request": "Add due dates to this to-do list. add(list, title, due) takes an optional due date written as YYYY-MM-DD and "
               "stores it on the item. Create todo/overdue.js exporting overdue(list, today) that returns the titles of the "
               "unfinished items whose due date is before today (also YYYY-MM-DD), earliest due date first. Items without a due "
               "date are never overdue. Keep the existing functions and test working.",
    "hidden": {"test/hidden_c6.test.js": '''const assert = require('assert');
const t = require('../todo/store');
const { overdue } = require('../todo/overdue');
const l = t.create();
t.add(l, 'tax', '2026-03-10'); t.add(l, 'rent', '2026-02-28'); t.add(l, 'bread'); t.add(l, 'gas', '2026-04-01'); t.add(l, 'fees', '2026-01-15');
t.finish(l, 'fees');
assert.deepStrictEqual(overdue(l, '2026-03-15'), ['rent', 'tax']);
assert.deepStrictEqual(overdue(l, '2026-01-01'), []);
console.log('hidden ok');
'''},
    "hidden_cmd": ["node", "test/hidden_c6.test.js"],
    "reference": {"todo/store.js": '''// A small to-do list kept in memory.
function create() { return []; }
function add(list, title, due) { list.push({ title, done: false, due: due || null }); return list; }
function finish(list, title) { const it = list.find(i => i.title === title); if (it) it.done = true; return list; }
function open(list) { return list.filter(i => !i.done).map(i => i.title); }
module.exports = { create, add, finish, open };
''', "todo/overdue.js": '''function overdue(list, today) {
  return list.filter(i => !i.done && i.due && i.due < today).sort((a, b) => a.due.localeCompare(b.due)).map(i => i.title);
}
module.exports = { overdue };
'''}})

FEATURES.append({"id": "C7_cpp_shapes_triangle", "lang": "c++", "test_cmd": ["make", "-s", "test"], "files": {
    "Makefile": "test: tests/run\n\t./tests/run\ntests/run: src/shapes.cpp src/shapes.h tests/test.cpp\n\tg++ -std=c++17 -O1 -Isrc -o tests/run src/shapes.cpp tests/test.cpp\n",
    "src/shapes.h": '''#pragma once
#include <memory>
#include <vector>

struct Shape {
    virtual ~Shape() = default;
    virtual double area() const = 0;
    virtual double perimeter() const = 0;
};

struct Rectangle : Shape {
    double w, h;
    Rectangle(double w, double h) : w(w), h(h) {}
    double area() const override;
    double perimeter() const override;
};

struct Circle : Shape {
    double r;
    explicit Circle(double r) : r(r) {}
    double area() const override;
    double perimeter() const override;
};

double total_area(const std::vector<std::unique_ptr<Shape>>& shapes);
''',
    "src/shapes.cpp": '''#include "shapes.h"
#include <cmath>

double Rectangle::area() const { return w * h; }
double Rectangle::perimeter() const { return 2 * (w + h); }
double Circle::area() const { return M_PI * r * r; }
double Circle::perimeter() const { return 2 * M_PI * r; }

double total_area(const std::vector<std::unique_ptr<Shape>>& shapes) {
    double t = 0;
    for (const auto& s : shapes) t += s->area();
    return t;
}
''',
    "tests/test.cpp": '''#include <cmath>
#include <iostream>
#include "shapes.h"
static int failures = 0;
#define CHECK(c) do { if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\\n"; } } while (0)
int main() {
    std::vector<std::unique_ptr<Shape>> v;
    v.push_back(std::make_unique<Rectangle>(3, 4));
    v.push_back(std::make_unique<Circle>(1));
    CHECK(std::fabs(total_area(v) - (12 + M_PI)) < 1e-9);
    CHECK(Rectangle(3, 4).perimeter() == 14);
    if (!failures) std::cout << "all tests passed\\n";
    return failures;
}
'''},
    "request": "Add a Triangle shape to this C++ project: struct Triangle in src/shapes.h constructed from three side lengths "
               "(a, b, c), with area() by Heron's formula and perimeter(), implemented in src/shapes.cpp. The constructor must "
               "throw std::invalid_argument when the sides cannot form a triangle (any side zero or negative, or one side at "
               "least the sum of the other two). total_area must work with triangles too. Keep the existing tests passing.",
    "hidden": {"tests/hidden_c7.cpp": '''#include <cmath>
#include <iostream>
#include <stdexcept>
#include "shapes.h"
int main() {
    int bad = 0;
    Triangle t(3, 4, 5);
    if (std::fabs(t.area() - 6) > 1e-9) bad++;
    if (t.perimeter() != 12) bad++;
    std::vector<std::unique_ptr<Shape>> v;
    v.push_back(std::make_unique<Triangle>(3, 4, 5));
    v.push_back(std::make_unique<Rectangle>(2, 2));
    if (std::fabs(total_area(v) - 10) > 1e-9) bad++;
    try { Triangle x(1, 2, 3); bad++; } catch (const std::invalid_argument&) {}
    try { Triangle x(0, 2, 2); bad++; } catch (const std::invalid_argument&) {}
    std::cout << (bad ? "hidden failed" : "hidden ok") << "\\n";
    return bad;
}
'''},
    "hidden_cmd": ["sh", "-c", "g++ -std=c++17 -Isrc -o /tmp/hc7 src/shapes.cpp tests/hidden_c7.cpp && /tmp/hc7"],
    "reference": {"src/shapes.h": '''#pragma once
#include <memory>
#include <vector>

struct Shape {
    virtual ~Shape() = default;
    virtual double area() const = 0;
    virtual double perimeter() const = 0;
};

struct Rectangle : Shape {
    double w, h;
    Rectangle(double w, double h) : w(w), h(h) {}
    double area() const override;
    double perimeter() const override;
};

struct Circle : Shape {
    double r;
    explicit Circle(double r) : r(r) {}
    double area() const override;
    double perimeter() const override;
};

struct Triangle : Shape {
    double a, b, c;
    Triangle(double a, double b, double c);
    double area() const override;
    double perimeter() const override;
};

double total_area(const std::vector<std::unique_ptr<Shape>>& shapes);
''', "src/shapes.cpp": '''#include "shapes.h"
#include <cmath>
#include <stdexcept>

double Rectangle::area() const { return w * h; }
double Rectangle::perimeter() const { return 2 * (w + h); }
double Circle::area() const { return M_PI * r * r; }
double Circle::perimeter() const { return 2 * M_PI * r; }

Triangle::Triangle(double a, double b, double c) : a(a), b(b), c(c) {
    if (a <= 0 || b <= 0 || c <= 0 || a >= b + c || b >= a + c || c >= a + b)
        throw std::invalid_argument("not a triangle");
}
double Triangle::perimeter() const { return a + b + c; }
double Triangle::area() const { double s = perimeter() / 2; return std::sqrt(s * (s - a) * (s - b) * (s - c)); }

double total_area(const std::vector<std::unique_ptr<Shape>>& shapes) {
    double t = 0;
    for (const auto& s : shapes) t += s->area();
    return t;
}
'''}})

FEATURES.append({"id": "C8_py_units_temperature", "lang": "python", "test_cmd": PY_TEST, "files": {
    "units/__init__.py": '''from .length import FACTORS as LENGTH, convert_length


def convert(value, from_unit, to_unit):
    """Convert value between units of the same kind."""
    if from_unit in LENGTH and to_unit in LENGTH:
        return convert_length(value, from_unit, to_unit)
    raise ValueError(f"cannot convert {from_unit} to {to_unit}")
''',
    "units/length.py": '''FACTORS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0}


def convert_length(value, from_unit, to_unit):
    return value * FACTORS[from_unit] / FACTORS[to_unit]
''',
    "tests/__init__.py": "",
    "tests/test_units.py": '''import unittest

from units import convert


class UnitTests(unittest.TestCase):
    def test_length(self):
        self.assertAlmostEqual(convert(2.4, "km", "m"), 2400)
        self.assertAlmostEqual(convert(150, "cm", "m"), 1.5)

    def test_unknown(self):
        with self.assertRaises(ValueError):
            convert(1, "km", "kg")
'''},
    "request": "Add temperature conversion to this units package: create units/temperature.py and make units.convert(value, "
               "from_unit, to_unit) also convert between C, F and K (Celsius, Fahrenheit, Kelvin). Converting between a length "
               "and a temperature, or using an unknown unit, must still raise ValueError. Keep the length conversions working.",
    "hidden": {"tests/test_hidden_c8.py": '''import unittest

from units import convert


class Hidden(unittest.TestCase):
    def test_temperature(self):
        self.assertAlmostEqual(convert(100, "C", "F"), 212)
        self.assertAlmostEqual(convert(32, "F", "C"), 0)
        self.assertAlmostEqual(convert(0, "C", "K"), 273.15)
        self.assertAlmostEqual(convert(300, "K", "F"), 80.33, places=2)
        self.assertAlmostEqual(convert(20, "C", "C"), 20)

    def test_mixed_and_unknown(self):
        for args in [(1, "C", "m"), (1, "km", "F"), (1, "C", "R")]:
            with self.assertRaises(ValueError):
                convert(*args)
'''},
    "reference": {"units/temperature.py": '''UNITS = {"C", "F", "K"}


def convert_temperature(value, from_unit, to_unit):
    c = {"C": value, "F": (value - 32) * 5 / 9, "K": value - 273.15}[from_unit]
    return {"C": c, "F": c * 9 / 5 + 32, "K": c + 273.15}[to_unit]
''', "units/__init__.py": '''from .length import FACTORS as LENGTH, convert_length
from .temperature import UNITS as TEMPERATURE, convert_temperature


def convert(value, from_unit, to_unit):
    """Convert value between units of the same kind."""
    if from_unit in LENGTH and to_unit in LENGTH:
        return convert_length(value, from_unit, to_unit)
    if from_unit in TEMPERATURE and to_unit in TEMPERATURE:
        return convert_temperature(value, from_unit, to_unit)
    raise ValueError(f"cannot convert {from_unit} to {to_unit}")
'''}})

for f in FEATURES:
    f["category"] = "feature"
    f["budget_s"] = 720
    f.setdefault("hidden_cmd", PY_TEST if f["lang"] == "python" else f["test_cmd"])
