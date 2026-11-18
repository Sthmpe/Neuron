"""Real package upgrade on a small project, against the real PyPI, with real installs and the real sandbox.

  python3 -m benchmark.online.upgrade_demo
The project pins six==1.15.0 (newer versions keep working) and packaging==21.3 (version 22 removed LegacyVersion, which
the project's test uses). Expected: six upgraded, packaging kept back, real project untouched by the failing upgrade.
"""
import json
import shutil
import tempfile
import time
from pathlib import Path

from neuron.agent.capabilities.workspace import detect_test_command
from neuron.agent.effects import Effects
from neuron.brain.sandbox import Sandbox
from neuron.online import packages

ROOT = Path(__file__).resolve().parents[2]


def make_project():
    p = Path(tempfile.mkdtemp(prefix="upgrade-demo-")) / "shop_tools"
    (p / "tests").mkdir(parents=True)
    (p / "requirements.txt").write_text("six==1.15.0\npackaging==21.3\n")
    (p / "tools.py").write_text("import six\nfrom packaging.version import LegacyVersion, Version\n\n\n"
                                "def label(v):\n    return six.text_type(Version(v) if v[0].isdigit() else LegacyVersion(v))\n")
    (p / "tests" / "test_tools.py").write_text("import unittest\nfrom tools import label\n\n\n"
                                               "class T(unittest.TestCase):\n    def test_label(self):\n"
                                               "        self.assertEqual(label('1.2'), '1.2')\n        self.assertEqual(label('build-7'), 'build-7')\n")
    return p


def main():
    p = make_project()
    t0 = time.time()
    rep = packages.upgrade(p, Sandbox(timeout=300, mem_mb=1024), detect_test_command(p), effects=Effects(p / ".neuron" / "e.jsonl"))
    rep["seconds"] = round(time.time() - t0, 1)
    rep["requirements_after"] = (p / "requirements.txt").read_text()
    rep["expected"] = "six upgraded; packaging kept back (22+ removed LegacyVersion)"
    rep["as_expected"] = [u["name"] for u in rep["upgraded"]] == ["six"] and [k["name"] for k in rep["kept_back"]] == ["packaging"]
    out = ROOT / "benchmark" / "results" / "online_upgrade_demo.json"
    out.write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: rep[k] for k in ("summary", "upgraded", "kept_back", "seconds", "as_expected")}, indent=1)[:3000])
    shutil.rmtree(p.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
