"""Linked records and rules (a sale picks a product and lowers its stock), on a dev-only example.

Developed on a shop example written for this test; the locked phase-5 tasks were not used."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from neuron.builder import relations, templates
from neuron.builder.build import prepare_project
from neuron.builder.checks import CheckRunner
from neuron.builder.spec import SPEC_SCHEMA, normalise

RAW = {"app_name": "Corner Shop", "kind": "app", "login_required": False, "username": "", "password": "",
       "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [], "dashboard": [],
       "entities": [{"name": "product", "search_field": "name",
                     "fields": [{"name": "name", "type": "text"}, {"name": "stock", "type": "number"}, {"name": "price", "type": "number"}]},
                    {"name": "sale", "search_field": "customer",
                     "fields": [{"name": "product", "type": "link", "to": "product"}, {"name": "quantity", "type": "number"},
                                {"name": "customer", "type": "text"}]}],
       "rules": [{"on_add": "sale", "link_field": "product", "target_field": "stock", "amount_field": "quantity",
                  "change": "subtract", "block_if_negative": True}]}


def spec_of(raw):
    s, problems = normalise(raw)
    relations.apply(raw, s, problems)
    return s, problems


def free_port():
    with socket.socket() as k:
        k.bind(("127.0.0.1", 0))
        return k.getsockname()[1]


class Running:
    def __init__(self, project):
        self.project, self.proc = project, None

    def start(self):
        self.port = free_port()
        env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
        env["PORT"] = str(self.port)
        self.proc = subprocess.Popen([sys.executable, "app.py"], cwd=self.project, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), 0.2).close()
                return f"http://127.0.0.1:{self.port}"
            except OSError:
                time.sleep(0.05)
        raise RuntimeError(self.proc.stderr.read().decode()[-500:] if self.proc.poll() is not None else "app did not start")

    def restart(self):
        self.stop()
        return self.start()

    def stop(self):
        if self.proc:
            self.proc.kill()
            self.proc.wait()


class RelationsTests(unittest.TestCase):
    def test_schema_offers_links_and_rules(self):
        s = relations.extend_schema(SPEC_SCHEMA)
        self.assertIn("link", s["properties"]["entities"]["items"]["properties"]["fields"]["items"]["properties"]["type"]["enum"])
        self.assertIn("rules", s["properties"])
        self.assertNotIn("link", SPEC_SCHEMA["properties"]["entities"]["items"]["properties"]["fields"]["items"]["properties"]["type"]["enum"])

    def test_spec_gets_links_and_rules(self):
        s, problems = spec_of(RAW)
        self.assertEqual(problems, [])
        sale = s["entities"][1]
        self.assertEqual(sale["fields"][0], {"name": "product", "label": "Product", "type": "link", "to": "product"})
        self.assertEqual(s["rules"][0]["target"], "product")
        self.assertEqual(s["rules"][0]["target_key"], "name")

    def test_bad_rules_are_explained(self):
        import copy
        raw = copy.deepcopy(RAW)
        raw["rules"] = [{"on_add": "sale", "link_field": "customer", "target_field": "stock", "amount_field": "quantity",
                         "change": "subtract", "block_if_negative": True},
                        {"on_add": "sale", "link_field": "product", "target_field": "price_x", "amount_field": "quantity",
                         "change": "subtract", "block_if_negative": True}]
        raw["entities"][1]["fields"].append({"name": "shelf", "type": "link", "to": "warehouse"})
        s, problems = spec_of(raw)
        self.assertEqual(s["rules"], [])
        self.assertEqual(len(problems), 3, problems)
        self.assertTrue(any("not a link field" in p for p in problems))
        self.assertTrue(any("not a number field" in p for p in problems))
        self.assertTrue(any("unknown entity 'warehouse'" in p for p in problems))

    def test_template_app_passes_its_rule_and_page_checks(self):
        s, _ = spec_of(RAW)
        project = Path(tempfile.mkdtemp(prefix="rel-"))
        prepare_project(project, s["app_name"], design=True)
        (project / "schema.py").write_text(templates.schema_py(s))
        for e in s["entities"]:
            (project / "pages" / f"{e['name']}.py").write_text(templates.entity_py(s, e))
        run = Running(project)
        base = run.start()
        self.addCleanup(run.stop)
        checks = relations.rule_checks(s, [])
        sale = s["entities"][1]
        page_check = {"name": "sale page with a linked product", "steps": relations.setup_steps(s, sale) + [
            {"post": "/sale", "form": relations.sample(s, sale, 0)}, {"post": "/sale", "form": relations.sample(s, sale, 1)},
            {"get": "/sale", "expect_text": ["Zed Alpha", "Kay Omega", "Product"]}]}
        runner = CheckRunner(base, restart=run.restart)              # follows the app across restarts
        for check in checks + [page_check]:
            ok, why = runner.run(check)
            self.assertTrue(ok, f"{check['name']}: {why}")
        self.assertIn("lowers the product's stock", checks[0]["name"])
        page = CheckRunner(run.restart()).run({"name": "drop-down", "steps": [{"get": "/sale", "expect_text": ["Zed Alpha"]}]})
        self.assertTrue(page[0])

    def test_rule_check_catches_an_app_that_ignores_the_rule(self):
        s, _ = spec_of(RAW)
        project = Path(tempfile.mkdtemp(prefix="rel-"))
        prepare_project(project, s["app_name"], design=True)
        (project / "schema.py").write_text(templates.schema_py(s))
        plain = dict(s, rules=[])                                         # pages written without the rule
        for e in s["entities"]:
            (project / "pages" / f"{e['name']}.py").write_text(templates.entity_py(plain, e))
        run = Running(project)
        base = run.start()
        self.addCleanup(run.stop)
        ok, why = CheckRunner(base, restart=run.restart).run(relations.rule_checks(s, [])[0])
        self.assertFalse(ok)
        self.assertIn("42", why)

    def test_contract_tells_the_model_exactly_what_to_do(self):
        s, _ = spec_of(RAW)
        text = "\n".join(relations.contract_lines(s, s["entities"][1]))
        self.assertIn('ui.select("Product", "product"', text)
        self.assertIn("UPDATE product SET stock = ? WHERE name = ?", text)
        self.assertIn("Not enough stock", text)
        self.assertEqual(relations.contract_lines(s, s["entities"][0]), [])


if __name__ == "__main__":
    unittest.main()
