"""Wider standard repair changes, tried before the model (core proof 2 GB run 1: NEURON fixed 0 of 8 planted bugs).
Invented projects, not the locked ones; the scripted model gives only useless replies, so only the search can fix them."""
import tempfile
import unittest
from pathlib import Path

from neuron.agent.repair_search import mutants
from tests.test_agent import run

REQUEST = "The tests of this project fail. Find the bug in the source code and fix it so the tests pass. Do not change the tests."
CASES = {
    "constant written ten times too big": ("DISCOUNT = 1.5\n\n\ndef discounted(price):\n    return round(price * (1 - DISCOUNT))\n",
                                           "self.assertEqual(discounted(1000), 850)"),
    "index that should be a slice": ("def initials(name):\n    return name[0].upper()\n", "self.assertEqual(initials('ng'), 'NG')"),
    "stray division by a constant": ("def kobo_to_total(kobo):\n    return kobo / 100\n", "self.assertEqual(kobo_to_total(500), 500)"),
    "statement done twice": ("def charge(balance, fee):\n    balance -= fee\n    balance -= fee\n    return balance\n",
                             "self.assertEqual(charge(1000, 50), 950)"),
}


def project(src, check):
    ws = Path(tempfile.mkdtemp(prefix="neuron-rep-"))
    (ws / "lib").mkdir()
    (ws / "lib" / "__init__.py").write_text("")
    (ws / "lib" / "core.py").write_text(src)
    (ws / "tests").mkdir()
    (ws / "tests" / "__init__.py").write_text("")
    name = check.split("(")[1].split("(")[0].split(")")[0].split(",")[0]
    func = check.split("assertEqual(")[1].split("(")[0]
    (ws / "tests" / "test_core.py").write_text(f"import unittest\nfrom lib.core import {func}\n\n\nclass T(unittest.TestCase):\n"
                                              f"    def test_it(self):\n        {check}\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    return ws


class WiderRepair(unittest.TestCase):
    def test_each_bug_is_fixed_by_the_search_without_the_model(self):
        for what, (src, check) in CASES.items():
            with self.subTest(what):
                ws = project(src, check)
                rep, job, llm = run(REQUEST, ["no idea"] * 30, workspace=ws)
                self.assertEqual(rep["verdict"], "VERIFIED", (what, rep.get("failed")))
                self.assertEqual(rep["made_by"], {"deterministic": 1, "search": 1}, what)

    def test_comments_and_strings_are_never_changed(self):
        src = "def f(x):\n    # rate 0.75 / 100\n    s = 'a[0]'\n    return x\n"
        self.assertFalse([m for m in mutants(src, 1, 4) if m[0] in (2, 3) and m[3].split(":")[0] in ("scale", "drop", "slice")])


class EditMatching(unittest.TestCase):
    """Core proof B4, 4 GB run 1: the model's diagnosis was right but its edit 'could not be applied'."""
    FN = "function share(total, pct) {\n  return total - total * pct;\n}"
    FILE = "// split\n" + FN + "\nmodule.exports = { share };\n"

    def test_spacing_and_semicolon_do_not_stop_an_edit(self):
        from neuron.builder.bugfix import apply_edit
        r = apply_edit(self.FILE, self.FN, "```js\nreturn total-total*pct\n```\n```js\nreturn total - total * pct / 100;\n```")
        self.assertIn("total * pct / 100;", r)

    def test_a_one_line_fragment_is_replaced_where_it_occurs_once(self):
        from neuron.builder.bugfix import apply_edit
        r = apply_edit(self.FILE, self.FN, "```\ntotal * pct\n```\n```\ntotal * pct / 100\n```")
        self.assertIn("return total - total * pct / 100;", r)

    def test_percentage_used_as_a_fraction_is_a_candidate_change(self):
        self.assertTrue(any("/ 100" in m[2] for m in mutants(self.FILE, 2, 4)))


if __name__ == "__main__":
    unittest.main()
