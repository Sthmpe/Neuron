"""The builder must not reject its own correct app when a stock rule refuses one of its sample records (core proof
validation, A5: with "how many have fewer than 1" on the dashboard, a sample record's stock was set to 0, the sample
loan of it was refused, and the dashboard check still expected every post to be saved). Invented app, not the locked one."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from neuron.brain.sandbox import Sandbox
from neuron.builder import templates
from neuron.builder.build import build_full
from tests.fakes import ScriptedLLM

PLAN = {"app_name": "Tool Shed", "kind": "app", "login_required": True, "username": "keeper", "password": "hammer9",
        "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
        "entities": [{"name": "tools", "fields": [{"name": "name", "type": "text"}, {"name": "units", "type": "number"}],
                      "search_field": "name"},
                     {"name": "lends", "fields": [{"name": "tool", "type": "link", "to": "tools"}, {"name": "neighbour", "type": "text"},
                                                  {"name": "units_out", "type": "number"}], "search_field": "neighbour"}],
        "dashboard": [{"label": "Lends", "entity": "lends", "kind": "count"},
                      {"label": "Tools with fewer than 1 unit", "entity": "tools", "kind": "count_below", "field": "units", "below": 1}],
        "rules": [{"on_add": "lends", "link_field": "tool", "target_field": "units", "amount_field": "units_out",
                   "change": "subtract", "block_if_negative": True}]}
REQUEST = ("Make a tool lending app with a login (user keeper, password hammer9). Keep tools with name and units on the "
           "shelf. Keep lends: which tool, the neighbour and how many units; lending lowers the tool's units and is refused "
           "if there are not enough. The dashboard shows the number of lends and how many tools have fewer than 1 unit.")


class Runner:
    loads = 1

    def __init__(self, llm):
        self.llm = llm

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


class DashboardWithStockRule(unittest.TestCase):
    def test_correct_template_app_passes_its_own_checks(self):
        project = Path(tempfile.mkdtemp(prefix="neuron-dash-")) / "app"

        def reply(messages):
            sys_, last = messages[0]["content"], messages[-1]["content"]
            if sys_.startswith("You turn a plain-language request"):
                return json.dumps(PLAN)
            if "check a web page against" in sys_:
                return '{"ok": true, "missing": []}'
            m = re.search(r"# Your task: (\S+)", last)
            st = json.loads((project / ".neuron" / "spec.json").read_text())["spec"]
            return "```python\n" + templates.reference_files(st)[m.group(1)] + "```" if m else "ok"

        r = build_full(project, REQUEST, Runner(ScriptedLLM([reply] * 80)), Sandbox(timeout=60, mem_mb=256), log=lambda *_: None, design=True)
        self.assertTrue(r.get("ok"), r.get("error"))


if __name__ == "__main__":
    unittest.main()
