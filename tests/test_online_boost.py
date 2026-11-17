"""Online boost: off by default, used only for chosen roles when online, falls back to local on any problem."""
import http.server
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from neuron.agent.loop import Agent, Job
from neuron.brain.sandbox import Sandbox
from neuron.online.boost import BoostedRunner, OnlineBoost
from tests.fakes import ScriptedLLM


class Local:
    def __init__(self, replies):
        self.llm, self.loaded = ScriptedLLM(replies), "local"

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "local-model"

    def unload(self):
        pass


class Remote(http.server.BaseHTTPRequestHandler):
    seen, fail = [], {"on": False}

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Remote.seen.append({"auth": self.headers.get("Authorization"), "body": body})
        if Remote.fail["on"]:
            self.send_response(500); self.end_headers(); return
        out = json.dumps({"choices": [{"message": {"content": "Plan from the online model."}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)


class BoostTests(unittest.TestCase):
    def setUp(self):
        Remote.seen.clear(); Remote.fail["on"] = False
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Remote)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.shutdown)
        old = {k: os.environ.pop(k) for k in list(os.environ) if "proxy" in k.lower()}
        self.addCleanup(os.environ.update, old)
        self.cfg = {"enabled": True, "provider": "test", "base_url": f"http://127.0.0.1:{self.httpd.server_address[1]}/v1",
                    "model": "big", "api_key": "sk-secret-123", "roles": ["planner"]}
        self.logs = []

    def test_off_without_settings(self):
        home = Path(tempfile.mkdtemp())
        b = OnlineBoost.from_home(home)
        self.assertFalse(b.configured())
        self.assertEqual(b.status()["on"], False)
        (home / "online.json").write_text(json.dumps(self.cfg))
        os.chmod(home / "online.json", 0o644)
        self.assertFalse(OnlineBoost.from_home(home, log=self.logs.append).configured())    # readable by others: refused
        os.chmod(home / "online.json", 0o600)
        self.assertTrue(OnlineBoost.from_home(home).configured())

    def test_only_chosen_roles_and_only_when_online(self):
        online = {"up": True}
        r = BoostedRunner(Local(["local answer"] * 5), OnlineBoost(self.cfg, online_check=lambda: online["up"]))
        msg = [{"role": "user", "content": "plan this"}]
        self.assertTrue(r.client("planner").chat(msg).model.startswith("online:test/big"))
        self.assertEqual(r.client("builder").chat(msg).text, "local answer")        # builder stays local
        online["up"] = False
        self.assertEqual(r.client("planner").chat(msg).text, "local answer")        # offline: local
        self.assertEqual(Remote.seen[0]["auth"], "Bearer sk-secret-123")
        self.assertEqual(len(Remote.seen), 1)

    def test_failure_falls_back_and_rests_without_leaking_the_key(self):
        Remote.fail["on"] = True
        b = OnlineBoost(self.cfg, log=self.logs.append)
        r = BoostedRunner(Local(["local answer"] * 5), b)
        msg = [{"role": "user", "content": "plan"}]
        self.assertEqual(r.client("planner").chat(msg).text, "local answer")
        self.assertEqual(r.client("planner").chat(msg).text, "local answer")
        self.assertEqual(len(Remote.seen), 1)                                       # resting after the failure
        self.assertTrue(b.status()["resting"])
        self.assertNotIn("sk-secret-123", " ".join(self.logs) + json.dumps(b.status()))

    def test_job_report_counts_online_calls(self):
        ws = Path(tempfile.mkdtemp())
        cfg = dict(self.cfg, roles=["builder", "planner", "reviewer"])
        r = BoostedRunner(Local([]), OnlineBoost(cfg))
        rep = Agent(Job(ws, r, Sandbox(timeout=30), log=lambda *_: None)).run("Why is the sky blue?")
        self.assertGreaterEqual(rep["online_calls"], 1)
        self.assertEqual(rep["online_calls"], rep["model_calls"])
        self.assertIn("online model", (ws / "answer.md").read_text())
        self.assertNotIn("sk-secret-123", "".join(p.read_text(errors="ignore") for p in ws.rglob("*") if p.is_file()))


if __name__ == "__main__":
    unittest.main()
