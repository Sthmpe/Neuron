"""The builder with the design system switched on: design chosen at plan time, saved with its reason,
kept on resume, reviewed in a real browser. A scripted stand-in plays the model."""
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("NEURON_DESIGN_HISTORY", os.path.join(tempfile.mkdtemp(prefix="neuron-hist-"), "h.json"))
from neuron.brain.sandbox import Sandbox                        # noqa: E402
from neuron.builder.build import build_full                    # noqa: E402
from neuron.builder.spec import normalise                      # noqa: E402
from tests.fakes import ScriptedLLM                            # noqa: E402
from tests.reference_builder import REFERENCE_SPECS, reference_files  # noqa: E402

SBX = Sandbox(timeout=60, mem_mb=256)
HAS_BROWSER = shutil.which("node") and Path("/opt/node-tools/node_modules/playwright").exists()


class Runner:
    def __init__(self, llm):
        self.llm, self.loads = llm, 1

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


def scripted(name):
    spec, _ = normalise(REFERENCE_SPECS[name])
    files = reference_files(spec)

    def reply(messages):
        prompt = messages[-1]["content"]
        if messages[0]["content"].startswith("You turn a plain-language request"):
            return json.dumps(REFERENCE_SPECS[name])
        if "check a web page against" in messages[0]["content"]:
            return '{"ok": true, "missing": []}'
        m = re.search(r"# Your task: (\S+)", prompt)
        return "```python\n" + files[m.group(1)] + "```" if m else "ok"
    return ScriptedLLM([reply] * 40)


@unittest.skipUnless(SBX.available() and HAS_BROWSER, "needs bubblewrap and the browser")
class DesignBuilderTests(unittest.TestCase):
    def test_site_build_saves_design_reviews_it_and_keeps_it_on_resume(self):
        project = Path(tempfile.mkdtemp(prefix="neuron-dsite-")) / "site"
        request = json.load(open(Path(__file__).resolve().parents[1] / "benchmark/builds/heldout/b1_bakery_landing.json"))["request"]
        r = build_full(project, request, Runner(scripted("b1_bakery_landing")), SBX, log=lambda *_: None, design=True)
        self.assertTrue(r["ok"], r)
        self.assertIsNotNone(r["design"])
        self.assertEqual(r["design"]["fails"], 0, r["design"])
        theme = json.loads((project / "theme.json").read_text())
        saved = json.loads((project / ".neuron" / "design.json").read_text())
        self.assertEqual(saved["choice"]["tokens"], theme["tokens"])
        self.assertEqual(theme["mood"], "warmth")
        self.assertIn("bakery", saved["choice"]["reason"])
        decisions = (project / ".neuron" / "decisions.jsonl").read_text()
        self.assertIn('"kind": "choice"', decisions)
        self.assertTrue((project / "kit" / "static" / "fonts").exists())
        # a resumed session keeps the same look
        before = (project / "theme.json").read_text()
        r2 = build_full(project, request, Runner(scripted("b1_bakery_landing")), SBX, log=lambda *_: None, design=True)
        self.assertEqual((project / "theme.json").read_text(), before)
        self.assertTrue(r2["ok"])


if __name__ == "__main__":
    unittest.main()
