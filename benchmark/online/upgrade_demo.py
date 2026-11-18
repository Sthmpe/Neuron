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


def make_npm_project():
    """ms 2.0.0 -> newer keeps working; uuid 3.4.0 -> newest removed require('uuid/v4'), which the test uses."""
    p = Path(tempfile.mkdtemp(prefix="upgrade-demo-npm-")) / "shop_ids"
    p.mkdir(parents=True)
    (p / "package.json").write_text(json.dumps({"name": "shop-ids", "version": "1.0.0", "private": True,
                                                "scripts": {"test": "node test.js"},
                                                "dependencies": {"ms": "2.0.0", "uuid": "3.4.0"}}, indent=2))
    (p / "test.js").write_text("const assert = require('assert');\nconst ms = require('ms');\nconst v4 = require('uuid/v4');\n"
                               "assert.strictEqual(ms('2h'), 7200000);\nassert.match(v4(), /^[0-9a-f-]{36}$/);\nconsole.log('ok');\n")
    return p


def run_npm():
    p = make_npm_project()
    t0 = time.time()
    rep = packages.upgrade(p, Sandbox(timeout=300, mem_mb=1024, toolchains=True), detect_test_command(p),
                           effects=Effects(p / ".neuron" / "e.jsonl"))
    rep["seconds"] = round(time.time() - t0, 1)
    rep["package_json_after"] = json.loads((p / "package.json").read_text())["dependencies"]
    rep["expected"] = "ms upgraded; uuid kept back (newer versions removed require('uuid/v4'))"
    rep["as_expected"] = [u["name"] for u in rep["upgraded"]] == ["ms"] and [k["name"] for k in rep["kept_back"]] == ["uuid"]
    shutil.rmtree(p.parent, ignore_errors=True)
    return rep


def main():
    import sys
    if "--npm" in sys.argv:
        rep = run_npm()
        (ROOT / "benchmark" / "results" / "online_upgrade_demo_npm.json").write_text(json.dumps(rep, indent=1))
        print(json.dumps({k: rep[k] for k in ("summary", "upgraded", "kept_back", "seconds", "as_expected")}, indent=1)[:3000])
        return
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
