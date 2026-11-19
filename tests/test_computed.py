"""Computed values (a total on each record, sums on the dashboard): plan, checks and templates agree, end to end."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from neuron.builder import computed, prompts, templates
from neuron.builder.spec import normalise, unsupported_features
from tests.fakes import ScriptedLLM

CATERING = {"app_name": "Ada Catering", "kind": "app", "login_required": True, "username": "ada", "password": "jollof5",
            "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
            "entities": [{"name": "dishes", "search_field": "name", "fields": [{"name": "name", "type": "text"}, {"name": "price", "type": "number"}]},
                         {"name": "orders", "search_field": "client", "fields": [
                             {"name": "client", "type": "text"}, {"name": "dish", "type": "link", "to": "dishes"},
                             {"name": "plates", "type": "number"}, {"name": "delivery", "type": "number"},
                             {"name": "total", "type": "computed", "formula": "plates * dish.price + delivery"}]}],
            "dashboard": [{"label": "Orders", "entity": "orders", "kind": "count"},
                          {"label": "Total sales", "entity": "orders", "kind": "sum", "field": "total"}]}


class Scripted:
    def __init__(self, llm):
        self.llm, self.loads = llm, 1

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


class ComputedSpecTests(unittest.TestCase):
    def test_formula_compiles_with_lookups_and_bad_ones_are_dropped(self):
        s, problems = normalise(CATERING)
        self.assertEqual(problems, [])
        orders = s["entities"][1]
        self.assertEqual([f["name"] for f in orders["fields"]], ["client", "dish", "plates", "delivery"])   # total is not stored
        self.assertIn("SELECT price FROM dishes WHERE name = orders.dish", orders["computed"][0]["sql"])
        self.assertEqual(s["dashboard"][1]["kind"], "sum")
        bad = copy.deepcopy(CATERING)
        bad["entities"][1]["fields"][-1]["formula"] = "plates * colour"
        s2, p2 = normalise(bad)
        self.assertEqual(p2, [])
        self.assertTrue(any("not a number field" in d for d in s2["dropped"]))
        self.assertEqual(s2["entities"][1]["computed"], [])

    def test_evaluate_matches_the_formula(self):
        s, _ = normalise(CATERING)
        c = s["entities"][1]["computed"][0]
        v = computed.evaluate(c["parts"], {"plates": "3", "delivery": "500", "dish": "Jollof"}, lambda t, k, val, f: 2500.0)
        self.assertEqual(v, 8000.0)
        self.assertEqual(computed.fmt(8000.0), "8000")
        self.assertEqual(computed.fmt(1234567.5), "1234567.50")

    def test_gaps_are_not_reported_when_the_plan_covers_them(self):
        s, _ = normalise(CATERING)
        req = "Show each order's total and the total sales on the dashboard."
        self.assertEqual(unsupported_features(req, s), [])
        self.assertEqual(len(unsupported_features(req, None)), 2)


@unittest.skipUnless(__import__("neuron.brain.sandbox", fromlist=["Sandbox"]).Sandbox().available(), "needs bubblewrap")
class ComputedBuildTests(unittest.TestCase):
    def build(self, raw, write_pages):
        from neuron.brain.sandbox import Sandbox
        from neuron.builder.build import build_full
        s, _ = normalise(raw)
        files = templates.reference_files(s)

        def reply(messages):
            if messages[0]["content"].startswith("You turn a plain-language request"):
                return json.dumps(raw)
            m = re.search(r"# Your task: (\S+)", messages[-1]["content"])
            if m and write_pages:
                return "```python\n" + files[m.group(1)] + "```"
            return "Not sure."
        project = Path(tempfile.mkdtemp(prefix="comp-")) / "app"
        return build_full(project, "catering app with order totals and total sales", Scripted(ScriptedLLM([reply] * 80)),
                          Sandbox(timeout=60, mem_mb=256), log=lambda *_: None, design=False, templates_allowed=True)

    def test_templates_pass_the_computed_and_sum_checks(self):
        r = self.build(CATERING, False)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["not_built"], [])

    def test_tool_hire_example_builds(self):
        r = self.build(prompts.PLANNER_RULE_SPEC, True)
        self.assertTrue(r["ok"], r)

    def test_a_page_with_a_wrong_total_fails_its_check(self):
        from neuron.builder.spec import expand
        s, _ = normalise(CATERING)
        tasks, checks, _ = expand(s)
        comp = [c for c in checks if "computed" in c["name"]]
        self.assertEqual(len(comp), 1)
        wants = [x for st in comp[0]["steps"] for x in st.get("expect_text", [])]
        self.assertTrue(any(re.fullmatch(r"\d+", w) for w in wants), wants)    # real numbers are expected, not just labels


if __name__ == "__main__":
    unittest.main()


class OwnerWordsTests(unittest.TestCase):
    def test_generic_count_field_gets_the_owners_word(self):
        from neuron.builder.spec import owner_labels
        spec = {"entities": [{"name": "dishes", "fields": [{"name": "name", "label": "Name", "type": "text"},
                                                           {"name": "price", "label": "Price", "type": "number"}]},
                             {"name": "orders", "fields": [{"name": "dish", "label": "Dish", "type": "link", "to": "dishes"},
                                                           {"name": "quantity", "label": "Quantity", "type": "number"}]}]}
        req = "Keep my dishes with their price. Keep orders: which dish and the number of plates."
        self.assertEqual(len(owner_labels(spec, req)), 1)
        self.assertEqual(spec["entities"][1]["fields"][1]["label"], "Plates")
        self.assertEqual(spec["entities"][1]["fields"][1]["name"], "quantity")       # the column keeps its name
        self.assertEqual(owner_labels(spec, req), [])                                # nothing more to change
