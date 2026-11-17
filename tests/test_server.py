"""The NEURON server: pairing, security, jobs from the phone, approvals, restart. Scripted stand-in model."""
import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from neuron.agent.capability import Capability, Outcome, default_registry
from neuron.brain.sandbox import Sandbox
from neuron.server.app import serve
from tests.fakes import ScriptedLLM

P5 = Path(__file__).resolve().parents[1] / "benchmark" / "phase5"


class Runner:
    def __init__(self, replies):
        self.llm, self.loaded = ScriptedLLM(replies), "scripted"

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


class SendText(Capability):
    name = "answer_question"           # stands in for a sensitive action in the test
    purpose = "send a text message"
    permissions = ("send_message",)

    def run(self, job, params):
        (job.workspace / "sent.txt").write_text("sent")
        return Outcome(True, "message sent", files=["sent.txt"])


class Client:
    def __init__(self, base):
        self.base, self.cookie = base, None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, method, path, body=None, raw=None, headers=None):
        h = {"X-Neuron": "1", **(headers or {})}
        if self.cookie:
            h["Cookie"] = self.cookie
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            r = self.opener.open(req, timeout=20)
        except urllib.error.HTTPError as e:
            r = e
        if r.headers.get("Set-Cookie"):
            self.cookie = r.headers["Set-Cookie"].split(";")[0]
        payload = r.read()
        try:
            return r.status, json.loads(payload)
        except ValueError:
            return r.status, payload


def start(home, replies, registry=None):
    httpd = serve(home, "127.0.0.1", 0, lambda: Runner(replies), lambda: Sandbox(timeout=60, mem_mb=512), registry or default_registry(),
                  log=lambda *_: None)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def wait_for(c, jid, statuses, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        s, d = c.call("GET", f"/api/jobs/{jid}")
        if d.get("status") in statuses:
            return d
        time.sleep(0.3)
    raise AssertionError(f"job did not reach {statuses}: {d.get('status')}")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="neuron-home-"))

    def test_nothing_works_before_pairing_and_wrong_codes_lock_out(self):
        httpd, base = start(self.home, [])
        self.addCleanup(httpd.shutdown)
        c = Client(base)
        self.assertEqual(c.call("GET", "/api/jobs")[0], 401)
        self.assertEqual(c.call("POST", "/api/jobs", {"goal": "x"})[0], 401)
        code = httpd.neuron["pairing"].new_code()
        for _ in range(5):
            self.assertEqual(c.call("POST", "/api/pair", {"code": "000000" if code != "000000" else "111111"})[0], 403)
        self.assertEqual(c.call("POST", "/api/pair", {"code": code})[0], 403)        # locked out after 5 wrong codes
        httpd.neuron["pairing"].fail_window = 0                                      # window passes
        code = httpd.neuron["pairing"].new_code()
        self.assertEqual(c.call("POST", "/api/pair", {"code": code})[0], 200)
        self.assertEqual(c.call("GET", "/api/jobs")[0], 200)
        self.assertEqual(Client(base).call("POST", "/api/pair", {"code": code})[0], 403)   # single use
        stored = (self.home / "devices.json").read_text()
        self.assertNotIn(c.cookie.split("=", 1)[1], stored)                          # tokens are stored hashed

    def test_cross_site_posts_and_path_tricks_are_refused(self):
        httpd, base = start(self.home, [])
        self.addCleanup(httpd.shutdown)
        c = Client(base)
        c.call("POST", "/api/pair", {"code": httpd.neuron["pairing"].new_code()})
        self.assertEqual(c.call("POST", "/api/jobs", {"goal": "x"}, headers={"X-Neuron": "0"})[0], 403)
        s, d = c.call("POST", "/api/jobs", {"goal": "zip test"})
        jid = d["id"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("proj/main.py", "print(1)\n")
            z.writestr("proj/../../evil.txt", "x")
        self.assertEqual(c.call("POST", f"/api/jobs/{jid}/upload?name=proj.zip", raw=buf.getvalue())[0], 200)
        ws = self.home / "jobs" / jid / "workspace"
        self.assertTrue((ws / "main.py").exists())
        self.assertFalse(any(p.name == "evil.txt" for p in self.home.rglob("evil.txt")))
        self.assertEqual(c.call("GET", f"/api/jobs/{jid}/file?path=../meta.json")[0], 404)
        self.assertEqual(c.call("GET", "/api/jobs/..%2F..%2Fdevices")[0], 404)

    def test_phone_job_end_to_end_with_files(self):
        plan = {"group_by": "category", "measures": [{"label": "Total", "op": "sum", "columns": ["amount"]}], "total_row": True, "share_of": ""}
        httpd, base = start(self.home, [json.dumps(plan)])
        self.addCleanup(httpd.shutdown)
        c = Client(base)
        c.call("POST", "/api/pair", {"code": httpd.neuron["pairing"].new_code()})
        s, d = c.call("POST", "/api/jobs", {"goal": "Make expenses.xlsx: rows on a sheet Data; a sheet Summary with the total per category and a Total row, using formulas."})
        jid = d["id"]
        c.call("POST", f"/api/jobs/{jid}/upload?name=dev_expenses.csv", raw=(P5 / "sources" / "dev_expenses.csv").read_bytes())
        c.call("POST", f"/api/jobs/{jid}/start")
        d = wait_for(c, jid, ("done", "failed", "partial"))
        self.assertEqual(d["status"], "done", d)
        self.assertIn("expenses.xlsx", [o["path"] for o in d["outputs"]])
        s, data = c.call("GET", f"/api/jobs/{jid}/file?path=expenses.xlsx")
        self.assertEqual(s, 200)
        self.assertEqual(data[:2], b"PK")
        s, ev = c.call("GET", f"/api/jobs/{jid}/events")
        self.assertTrue(any("check" == e["kind"] for e in ev["events"]))

    def test_sensitive_action_waits_for_approval(self):
        reg = default_registry()
        reg.add(SendText())
        httpd, base = start(self.home, [], registry=reg)
        self.addCleanup(httpd.shutdown)
        c = Client(base)
        c.call("POST", "/api/pair", {"code": httpd.neuron["pairing"].new_code()})
        s, d = c.call("POST", "/api/jobs", {"goal": "Why is the sky blue?"})
        jid = d["id"]
        c.call("POST", f"/api/jobs/{jid}/start")
        d = wait_for(c, jid, ("waiting_approval",))
        self.assertFalse((self.home / "jobs" / jid / "workspace" / "sent.txt").exists())
        a = d["approvals"][0]
        c.call("POST", f"/api/jobs/{jid}/approve", {"task": a["task"], "action": a["action"], "approve": True})
        d = wait_for(c, jid, ("done",))
        self.assertTrue((self.home / "jobs" / jid / "workspace" / "sent.txt").exists())

    def test_queued_job_resumes_after_a_server_restart(self):
        httpd, base = start(self.home, [])
        c = Client(base)
        c.call("POST", "/api/pair", {"code": httpd.neuron["pairing"].new_code()})
        s, d = c.call("POST", "/api/jobs", {"goal": "Why is the sky blue?"})
        jid = d["id"]
        meta = self.home / "jobs" / jid / "meta.json"
        m = json.loads(meta.read_text())
        m["status"] = "running"                                   # as if the machine died mid-job
        meta.write_text(json.dumps(m))
        httpd.shutdown()
        httpd.neuron["jobs"].stopping = True
        httpd2, base2 = start(self.home, ["The sky scatters blue light most."])
        self.addCleanup(httpd2.shutdown)
        c.base = base2
        d = wait_for(c, jid, ("done",))
        self.assertIn("answer.md", [o["path"] for o in d["outputs"]])
        self.assertIn("scatters blue light", d["answer"])            # shown on the phone directly


if __name__ == "__main__":
    unittest.main()


class PreviewTests(unittest.TestCase):
    def test_preview_needs_its_token_and_hides_neuron_cookies(self):
        home = Path(tempfile.mkdtemp(prefix="neuron-home-"))
        httpd, base = start(home, [])
        self.addCleanup(httpd.shutdown)
        self.addCleanup(httpd.neuron["previews"].close_all)
        c = Client(base)
        c.call("POST", "/api/pair", {"code": httpd.neuron["pairing"].new_code()})
        s, d = c.call("POST", "/api/jobs", {"goal": "preview test"})
        jid = d["id"]
        app = home / "jobs" / jid / "workspace" / "app"
        app.mkdir(parents=True)
        (app / "app.py").write_text(
            "import http.server, os\n"
            "class H(http.server.BaseHTTPRequestHandler):\n"
            "    def do_GET(self):\n"
            "        b = ('cookies:' + (self.headers.get('Cookie') or '')).encode()\n"
            "        self.send_response(200); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)\n"
            "http.server.HTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8000))), H).serve_forever()\n")
        s, r = c.call("POST", f"/api/jobs/{jid}/preview")
        self.assertEqual(s, 200, r)
        port, query = r["url"][1:].split("/", 1)
        p = Client(f"http://127.0.0.1:{port}")
        self.assertEqual(p.call("GET", "/")[0], 403)                       # no token, no app
        p.cookie = c.cookie                                                 # the phone's NEURON cookie is sent too
        s, body = p.call("GET", "/" + query)
        self.assertEqual(s, 200)
        self.assertNotIn(b"neuron_token", body)
        self.assertNotIn(b"neuron_preview", body)


class FollowUpTests(unittest.TestCase):
    def test_follow_up_keeps_the_conversation_and_the_files(self):
        home = Path(tempfile.mkdtemp(prefix="neuron-home-"))
        httpd, base = start(home, ["The sky scatters blue light most.", "Sunsets look red because light travels further."])
        self.addCleanup(httpd.shutdown)
        c = Client(base)
        c.call("POST", "/api/pair", {"code": httpd.neuron["pairing"].new_code()})
        s, d = c.call("POST", "/api/jobs", {"goal": "Why is the sky blue?"})
        first = d["id"]
        c.call("POST", f"/api/jobs/{first}/start")
        wait_for(c, first, ("done",))
        self.assertEqual(c.call("POST", f"/api/jobs/{first}/followup", {"text": ""})[0], 400)
        s, d = c.call("POST", f"/api/jobs/{first}/followup", {"text": "And why are sunsets red?"})
        self.assertEqual(s, 201)
        second = d["id"]
        d = wait_for(c, second, ("done",))
        self.assertEqual([t["id"] for t in d["thread"]], [first, second])
        self.assertEqual(d["thread"][1]["said"], "And why are sunsets red?")
        self.assertEqual(d["title"], "And why are sunsets red?")
        meta = json.loads((home / "jobs" / second / "meta.json").read_text())
        self.assertIn("Why is the sky blue?", meta["goal"])                   # the new job knows what came before
        self.assertIn("sunsets look red", d["answer"].lower())
        old = json.loads((home / "jobs" / first / "meta.json").read_text())
        self.assertEqual(old["status"], "done")                                # the earlier job is untouched
        self.assertEqual(c.call("POST", "/api/jobs/nope-123/followup", {"text": "x"})[0], 404)
