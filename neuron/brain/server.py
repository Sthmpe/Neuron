"""The brain program: local HTTP + JSON API in front of the engine.

Run:  python3 -m neuron.brain.server --port 8765 --data data

API
  GET  /health
  POST /tasks                 {"goal": "...", "delay_seconds": 0 | "start_at": epoch}
  GET  /tasks                 all tasks
  GET  /tasks/<id>            task + its steps
  GET  /tasks/<id>/events?after=<event id>
  GET  /tasks/<id>/report     final report (JSON, plus a plain-text version)
  GET  /permissions?status=pending
  POST /permissions/<id>      {"decision": "approve" | "reject"}
  GET  /tools                 every registered tool (name, description, inputs, needs internet, sensitive)
  GET  /network               state of the SIMULATED network switch
  POST /network               {"online": true|false}   (test switch, not a real network control)
"""
import argparse
import json
import os
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import Engine
from .llm import LlamaClient
from .sandbox import Sandbox
from .tools import default_registry
from .network import NetworkMonitor, SimulatedSwitch
from .planner import LlamaCppPlanner, RuleBasedPlanner
from .report import build_report, report_text
from .store import Store
from .world import FakeWorld


class Brain:
    def __init__(self, data_dir, step_delay=0.0, retry_base=1.0, retry_cap=30.0, planner=None,
                 llama_url=None, tools_dirs=None):
        data = Path(data_dir)
        data.mkdir(parents=True, exist_ok=True)
        self.store = Store(data / "brain.db")
        self.switch = SimulatedSwitch(data / "network.json")
        self.world = FakeWorld(data / "world.db", self.switch)
        self.monitor = NetworkMonitor(self.switch.is_online, self._network_changed)
        self.tools = default_registry(tools_dirs)
        self.llm = LlamaClient(llama_url) if llama_url else None
        if planner is None:
            planner = LlamaCppPlanner(registry=self.tools, client=self.llm) if self.llm else RuleBasedPlanner()
        self.engine = Engine(self.store, planner, self.monitor, self.world,
                             data / "artifacts", step_delay=step_delay,
                             retry_base=retry_base, retry_cap=retry_cap, tools=self.tools,
                             services={"llm": self.llm, "sandbox": Sandbox()})
        self.stop = threading.Event()

    def _network_changed(self, online, previous):
        if previous is None:
            msg = f"network monitor started: connection is {'UP' if online else 'DOWN'}"
        else:
            msg = "network monitor: connection RESTORED" if online else "network monitor: connection LOST"
        self.store.add_event(None, "network", msg)

    def run_engine(self):
        interrupted = self.engine.recover()
        self.store.add_event(None, "brain", f"brain started (pid {os.getpid()}); "
                             f"{len(self.store.active_tasks())} unfinished task(s) found in storage; "
                             f"{len(interrupted)} step(s) had been cut off mid-run")
        while not self.stop.is_set():
            try:
                worked = self.engine.tick()
            except Exception as e:  # keep the device alive
                self.store.add_event(None, "brain", f"engine error: {type(e).__name__}: {e}")
                worked = False
            if not worked:
                self.stop.wait(0.05)


def make_handler(brain):
    store = brain.store

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            path = url.path.rstrip("/")
            if path == "/health":
                return self._send(200, {"ok": True, "pid": os.getpid()})
            if path == "/network":
                return self._send(200, {"online": brain.switch.is_online(), "simulated": True})
            if path == "/tasks":
                return self._send(200, {"tasks": store.list_tasks()})
            if path == "/tools":
                return self._send(200, {"tools": brain.tools.specs(planner_only=False)})
            if path == "/permissions":
                return self._send(200, {"permissions": store.list_permissions(q.get("status", [None])[0])})
            m = re.fullmatch(r"/tasks/(\w+)(/events|/report)?", path)
            if m:
                task = store.get_task(m.group(1))
                if not task:
                    return self._send(404, {"error": "no such task"})
                if m.group(2) == "/events":
                    after = int(q.get("after", ["0"])[0])
                    return self._send(200, {"events": store.events(task["id"], after)})
                if m.group(2) == "/report":
                    r = build_report(store, brain.world, task["id"])
                    r["text"] = report_text(r)
                    return self._send(200, r)
                return self._send(200, {"task": task, "steps": store.steps(task["id"]),
                                        "executions": store.executions(task["id"])})
            self._send(404, {"error": "unknown path"})

        def do_POST(self):
            path = urlparse(self.path).path.rstrip("/")
            try:
                body = self._body()
            except ValueError:
                return self._send(400, {"error": "body must be JSON"})
            if path == "/tasks":
                goal = str(body.get("goal") or "").strip()
                if not goal:
                    return self._send(400, {"error": "goal is required"})
                start_at = body.get("start_at")
                if body.get("delay_seconds"):
                    start_at = time.time() + float(body["delay_seconds"])
                task_id = brain.engine.submit(goal, start_at)
                return self._send(201, {"task": store.get_task(task_id), "steps": store.steps(task_id)})
            if path == "/network":
                brain.switch.set(bool(body.get("online")))
                return self._send(200, {"online": brain.switch.is_online(), "simulated": True})
            m = re.fullmatch(r"/permissions/(\d+)", path)
            if m:
                decision = {"approve": "approved", "reject": "rejected"}.get(body.get("decision"))
                if not decision:
                    return self._send(400, {"error": "decision must be approve or reject"})
                perm = store.decide_permission(int(m.group(1)), decision)
                return self._send(200, {"permission": perm}) if perm else self._send(404, {"error": "no such permission"})
            self._send(404, {"error": "unknown path"})

    return Handler


def main():
    ap = argparse.ArgumentParser(description="NEURON brain")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--data", default="data")
    ap.add_argument("--step-delay", type=float, default=0.0, help="pretend each step takes this long")
    ap.add_argument("--retry-base", type=float, default=1.0)
    ap.add_argument("--retry-cap", type=float, default=30.0)
    ap.add_argument("--llama-url", help="address of a running llama.cpp server, e.g. http://127.0.0.1:8080")
    ap.add_argument("--tools-dir", action="append", help="extra folder with plug-in tools (repeatable)")
    a = ap.parse_args()
    brain = Brain(a.data, a.step_delay, a.retry_base, a.retry_cap, llama_url=a.llama_url,
                  tools_dirs=a.tools_dir)
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(brain))
    threading.Thread(target=brain.run_engine, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    print(f"NEURON brain listening on http://127.0.0.1:{a.port} (data: {a.data}, pid {os.getpid()})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    brain.stop.set()


if __name__ == "__main__":
    main()
