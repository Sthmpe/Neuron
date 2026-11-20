"""Adding a feature to an existing project, and the routing fixes found by the core proof. Real files and a real
sandbox; only the model's words are scripted. The projects here are invented for these tests (not from the locked set)."""
import json
import tempfile
import unittest
from pathlib import Path

from neuron.agent.router import is_simple, rule_guess
from tests.test_agent import run

TESTS_PY = '''import unittest
from shop.prices import with_tax


class PriceTests(unittest.TestCase):
    def test_tax(self):
        self.assertEqual(with_tax(1000), 1075)


if __name__ == "__main__":
    unittest.main()
'''
PRICES_PY = '''def with_tax(amount):
    return round(amount * 1.075)
'''
REQUEST = ("Add gift cards to this shop. Create shop/cards.py with balance_after(balance, spend): it returns the balance "
           "minus the spend, or 0 if the spend is larger than the balance.")
CARDS_PY = '''def balance_after(balance, spend):
    return max(0, balance - spend)
'''
FEATURE_TEST = '''import unittest
from shop.cards import balance_after


class CardTests(unittest.TestCase):
    def test_spend(self):
        self.assertEqual(balance_after(5000, 1200), 3800)

    def test_overspend(self):
        self.assertEqual(balance_after(1000, 1500), 0)


if __name__ == "__main__":
    unittest.main()
'''


def project():
    ws = Path(tempfile.mkdtemp(prefix="neuron-feat-"))
    (ws / "shop").mkdir()
    (ws / "shop" / "__init__.py").write_text("")
    (ws / "shop" / "prices.py").write_text(PRICES_PY)
    (ws / "tests").mkdir()
    (ws / "tests" / "__init__.py").write_text("")
    (ws / "tests" / "test_prices.py").write_text(TESTS_PY)
    return ws


def plan(*paths):
    return json.dumps({"files": [{"path": p, "action": "create", "what": "as asked"} for p in paths]})


class RoutingFixTests(unittest.TestCase):
    def test_fix_in_a_website_request_with_an_empty_folder_is_not_a_bug_fix(self):
        empty = Path(tempfile.mkdtemp(prefix="neuron-empty-"))
        r = ("Make a website for Quick Mend, a shoe repair stall. We fix heels from 2,000 naira and replace soles from "
             "5,000 naira. Add a form for call-back requests.")
        self.assertEqual(rule_guess(r, [], empty)[0], "web_app")

    def test_feature_request_on_a_project_goes_to_add_feature(self):
        self.assertEqual(rule_guess(REQUEST, [], project())[0], "add_feature")

    def test_bug_request_on_a_project_still_goes_to_the_bug_fixer(self):
        self.assertEqual(rule_guess("The tests fail. Fix the bug.", [], project())[0], "fix_bug")

    def test_make_without_a_project_is_not_a_feature_and_stays_on_the_fast_path(self):
        self.assertNotIn("add_feature", rule_guess("Make a haiku about rain", [], None)[1])
        self.assertTrue(is_simple("Make a haiku about rain"))


class AddFeatureTests(unittest.TestCase):
    def test_writes_the_feature_and_its_own_passing_test(self):
        ws = project()
        rep, job, llm = run(REQUEST, [plan("shop/cards.py"), f"```python\n{CARDS_PY}```", f"```python\n{FEATURE_TEST}```"], workspace=ws)
        self.assertEqual(rep["kind"], "add_feature")
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertTrue((ws / "shop" / "cards.py").exists())
        self.assertTrue((ws / "tests" / "test_neuron_feature.py").exists())
        self.assertEqual((ws / "shop" / "prices.py").read_text(), PRICES_PY)

    def test_wrong_code_is_not_verified_and_its_failing_test_is_removed(self):
        ws = project()
        wrong = "```python\ndef balance_after(balance, spend):\n    return balance - spend\n```"
        blame = json.dumps({"wrong": "code", "file": "shop/cards.py", "why": "overspend must give 0"})
        replies = [plan("shop/cards.py"), wrong, f"```python\n{FEATURE_TEST}```"] + [blame, wrong] * 3
        rep, job, llm = run(REQUEST, replies, workspace=ws)
        self.assertNotEqual(rep["verdict"], "VERIFIED", rep)
        self.assertFalse((ws / "tests" / "test_neuron_feature.py").exists())

    def test_a_rewrite_that_drops_an_existing_function_is_refused(self):
        ws = project()
        req = "Add a discount to this shop: change shop/prices.py so it also has with_discount(amount, percent)."
        dropped = "```python\ndef with_discount(amount, percent):\n    return round(amount * (100 - percent) / 100)\n```"
        kept = "```python\n" + PRICES_PY + "\n\ndef with_discount(amount, percent):\n    return round(amount * (100 - percent) / 100)\n```"
        test = ("```python\nimport unittest\nfrom shop.prices import with_discount\n\n\nclass T(unittest.TestCase):\n"
                "    def test_d(self):\n        self.assertEqual(with_discount(2000, 10), 1800)\n\n\nif __name__ == '__main__':\n    unittest.main()\n```")
        rep, job, llm = run(req, [json.dumps({"files": [{"path": "shop/prices.py", "action": "change", "what": "add with_discount"}]}),
                                  dropped, kept, test], workspace=ws)
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertIn("def with_tax", (ws / "shop" / "prices.py").read_text())

    def test_a_bug_request_whose_tests_already_pass_is_not_verified(self):
        ws = project()
        rep, job, llm = run("The tests of this project fail. Find the bug and fix it.", ["unused"] * 6, workspace=ws)
        self.assertNotEqual(rep["verdict"], "VERIFIED", rep)


if __name__ == "__main__":
    unittest.main()
