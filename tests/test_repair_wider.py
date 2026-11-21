"""Wider standard repair changes, tried before the model (core proof 2 GB run 1: NEURON fixed 0 of 8 planted bugs).
Invented projects, not the locked ones; the scripted model gives only useless replies, so only the search can fix them."""
import json
import tempfile
import unittest
from pathlib import Path

from neuron.agent.repair_search import mutants
from tests.test_agent import run

REQUEST = "The tests of this project fail. Find the bug in the source code and fix it so the tests pass. Do not change the tests."
CASES = {
    "constant written ten times too big": ("DISCOUNT = 1.5\n\n\ndef discounted(price):\n    return round(price * (1 - DISCOUNT))\n",
                                           "self.assertEqual(discounted(1000), 850)"),
    # 'ngozi' rather than 'ng': for 'ng' both [:2] and [0:] pass, which is genuinely ambiguous (see AmbiguousSmallChanges)
    "index that should be a slice": ("def initials(name):\n    return name[0].upper()\n", "self.assertEqual(initials('ngozi'), 'NG')"),
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


class ConstantOutsideAFunction(unittest.TestCase):
    """Core proof B6, 4 GB run 1: the wrong value was a package-level constant, which was never searched. Invented project."""

    def test_go_constant_is_found_by_the_search(self):
        import shutil
        if not shutil.which("go"):
            self.skipTest("go not installed")
        ws = Path(tempfile.mkdtemp(prefix="neuron-go-"))
        (ws / "go.mod").write_text("module ship\n\ngo 1.21\n")
        (ws / "ship").mkdir()
        (ws / "ship" / "rates.go").write_text("package ship\n\n// Price per kilogram, in naira hundreds.\nconst PerKg = 2.5\n")
        (ws / "ship" / "cost.go").write_text("package ship\n\n// Cost of sending a parcel.\nfunc Cost(kg float64) float64 {\n\treturn kg * PerKg\n}\n")
        (ws / "ship" / "cost_test.go").write_text('package ship\n\nimport "testing"\n\nfunc TestCost(t *testing.T) {\n'
                                                 '\tif c := Cost(3); c != 6 {\n\t\tt.Errorf("Cost(3) = %v, want 6", c)\n\t}\n}\n')
        rep, job, llm = run(REQUEST, ["no idea"] * 30, workspace=ws)
        self.assertEqual(rep["verdict"], "VERIFIED", rep.get("failed"))
        self.assertIn("PerKg = 2.0", (ws / "ship" / "rates.go").read_text())


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


class WholeFileRewrite(unittest.TestCase):
    """The plain-loop approach as NEURON's second strategy, with its guards (core proof 4 GB run 1). Invented project."""

    def _job(self, replies):
        from neuron.agent.loop import Job
        from tests.fakes import ScriptedLLM
        from tests.test_agent import SBX, Runner
        ws = project("def area(w, h):\n    return w + h\n", "self.assertEqual(area(3, 4), 12)")
        return ws, Job(ws, Runner(ScriptedLLM(replies)), SBX, log=lambda *_: None)

    def test_rewrites_the_source_file_and_never_the_tests(self):
        from neuron.agent.capabilities.code import FixBug
        test_edit = "FILE: tests/test_core.py\n```python\nimport unittest\n```\n"
        good = "FILE: lib/core.py\n```python\ndef area(w, h):\n    return w * h\n```\n"
        ws, job = self._job(["I am not sure.", test_edit, good])
        before = (ws / "tests" / "test_core.py").read_text()
        out = FixBug()._rewrite_files(job, {})
        self.assertTrue(out.ok, out.summary)
        self.assertEqual((ws / "tests" / "test_core.py").read_text(), before)
        self.assertIn("w * h", (ws / "lib" / "core.py").read_text())

    def test_a_failed_rewrite_is_undone(self):
        from neuron.agent.capabilities.code import FixBug
        wrong = "FILE: lib/core.py\n```python\ndef area(w, h):\n    return w - h\n```\n"
        ws, job = self._job([wrong] * 3)
        out = FixBug()._rewrite_files(job, {})
        self.assertFalse(out.ok)
        self.assertIn("w + h", (ws / "lib" / "core.py").read_text())


class AmbiguousSmallChanges(unittest.TestCase):
    """After-fixes rerun try 1 (B3, 2 GB): text[0] -> text[1] passed the visible tests but was wrong. When several
    different changes pass, the model must choose; with no valid choice nothing is claimed. Invented project."""
    SRC = "def to_minutes(text):\n    return int(text[0]) * 60 + int(text[3:5])\n"
    CHECK = "self.assertEqual(to_minutes('09:30') - to_minutes('08:00'), 90)"      # text[1] and text[:2] both pass

    def _pick(self, want):
        def reply(messages):
            opts = [l[2:] for l in messages[-1]["content"].splitlines() if l.startswith("- ")]
            pick = next((o for o in opts if want in o), None)
            return json.dumps({"change": pick or "none of them", "why": "two digits for the hour"})
        return reply

    def test_the_models_choice_among_passing_changes_is_applied(self):
        ws = project(self.SRC, self.CHECK)
        rep, job, llm = run(REQUEST, [self._pick("[:2]")] + ["no idea"] * 30, workspace=ws)
        self.assertIn("text[:2]", (ws / "lib" / "core.py").read_text())
        self.assertIn("chose", (job.state.dir / "decisions.jsonl").read_text())

    def test_without_a_valid_choice_the_search_claims_nothing(self):
        ws = project(self.SRC, self.CHECK)
        rep, job, llm = run(REQUEST, [self._pick("no such change")] + ["no idea"] * 30, workspace=ws)
        decisions = (job.state.dir / "decisions.jsonl").read_text()
        self.assertNotIn('"kind": "small change"', decisions)
