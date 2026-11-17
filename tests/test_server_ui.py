"""Drive the phone web page in a real browser (phone-sized screen): pair, goal + file, finish, download, status."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from neuron.agent.capability import default_registry
from neuron.brain.sandbox import Sandbox
from neuron.server.app import serve
from tests.test_server import P5, Runner

HERE = Path(__file__).resolve().parent
HAS_BROWSER = bool(shutil.which("node")) and subprocess.run(["node", "-e", "require('playwright')"], capture_output=True).returncode == 0


@unittest.skipUnless(HAS_BROWSER, "needs node with playwright")
class PhoneJourney(unittest.TestCase):
    def test_phone_journey(self):
        home = Path(tempfile.mkdtemp(prefix="neuron-ui-"))
        plan = {"group_by": "category", "measures": [{"label": "Total", "op": "sum", "columns": ["amount"]}], "total_row": True, "share_of": ""}
        httpd = serve(home, "127.0.0.1", 0, lambda: Runner([json.dumps(plan)]), lambda: Sandbox(timeout=60, mem_mb=512), default_registry(),
                      models_status=lambda: {"tier": "4gb", "builder": "scripted"}, log=lambda *_: None)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        shots = os.environ.get("NEURON_UI_SHOTS")
        env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
        p = subprocess.run(["node", str(HERE / "ui_journey.js"), f"http://127.0.0.1:{httpd.server_address[1]}", httpd.neuron["pairing"].new_code(),
                            str(P5 / "sources" / "dev_expenses.csv"), shots or ""], capture_output=True, text=True, timeout=400, env=env)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        print("\n".join(out["steps"]))
        self.assertEqual(out["problems"], [], "\n".join(out["steps"]))


if __name__ == "__main__":
    unittest.main()
