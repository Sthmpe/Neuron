"""Scheduler, planner, failure report, and the real two-process path over HTTP."""
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from neuron.brain import actions
from neuron.brain.planner import LlamaCppPlanner, RuleBasedPlanner
from neuron.brain.report import build_report
from tests.helpers import Rig


class SchedulerTests(unittest.TestCase):
    def test_task_starts_only_at_its_time(self):
        r = Rig(); self.addCleanup(r.close)
        tid = r.engine.submit("find leads", start_at=r.clock.t + 60)
        self.assertEqual(r.store.get_task(tid)["status"], "scheduled")
        r.clock.t += 59
        self.assertFalse(r.engine.tick())
        self.assertEqual(r.done(tid), [])
        r.restart()                                   # a restart must not lose or early-start it
        self.assertFalse(r.engine.tick())
        r.clock.t += 1
        r.run()
        self.assertGreater(len(r.done(tid)), 10)


class PlannerTests(unittest.TestCase):
    def test_find_leads_plan(self):
        plan = RuleBasedPlanner().plan("Find leads for me")
        self.assertEqual([s.no for s in plan], list(range(1, 21)))
        self.assertEqual([s.no for s in plan if s.needs_internet], [3, 4, 5, 8, 9, 14, 18, 19])
        self.assertEqual([s.no for s in plan if s.sensitive], [18])
        for s in plan:
            self.assertTrue(all(d < s.no for d in s.depends_on))

    def test_generic_plan_marks_online_and_sensitive(self):
        plan = RuleBasedPlanner().plan("tidy my notes then search the web for prices then send a message to Ada")
        self.assertEqual([(s.needs_internet, s.sensitive) for s in plan],
                         [(False, False), (True, False), (True, True)])

    def test_llama_planner_falls_back_when_no_server(self):
        plan = LlamaCppPlanner("http://127.0.0.1:9", timeout=1).plan("find leads")
        self.assertEqual(len(plan), 20)


class FailureTests(unittest.TestCase):
    def test_failed_step_is_reported_and_blocks_dependents(self):
        r = Rig(); self.addCleanup(r.close)
        original = actions.ACTIONS["verify_emails"]
        actions.ACTIONS["verify_emails"] = lambda c: 1 / 0
        self.addCleanup(actions.ACTIONS.__setitem__, "verify_emails", original)
        tid = r.engine.submit("find leads")
        r.run()
        rep = build_report(r.store, r.world, tid)
        self.assertEqual(rep["status"], "failed")
        self.assertEqual(rep["failed_steps"], [14])
        self.assertEqual(rep["blocked_steps"], [15, 16, 17, 18, 19, 20])
        self.assertEqual(rep["totals"]["done"], 13)
        self.assertIn("ZeroDivisionError", rep["steps"][13]["proof"]["summary"])


class HttpTests(unittest.TestCase):
    def test_host_and_brain_over_http(self):
        from neuron.brain.server import Brain, make_handler
        from neuron.host.client import HostClient
        d = tempfile.mkdtemp(prefix="neuron-http-")
        brain = Brain(d)
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(brain))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        threading.Thread(target=brain.run_engine, daemon=True).start()
        self.addCleanup(lambda: (brain.stop.set(), server.shutdown()))
        c = HostClient(f"http://127.0.0.1:{server.server_address[1]}")
        tid = c.send_task("find leads")["task"]["id"]
        end = time.time() + 20
        while not c.permissions("pending") and time.time() < end:
            time.sleep(0.02)
        perm = c.permissions("pending")[0]
        self.assertEqual(perm["step_no"], 18)
        c.decide(perm["id"], True)
        while c.task(tid)["task"]["status"] != "done" and time.time() < end:
            time.sleep(0.02)
        rep = c.report(tid)
        self.assertEqual(rep["totals"]["done"], 20)
        self.assertIn("NEURON REPORT", rep["text"])
        self.assertEqual(c._req("GET", "/tasks/nope")["error"], "no such task")

    def test_full_demo_with_real_kill(self):
        """Runs the real demo: separate brain process, kill -9, restart, resume."""
        from demo.run_demo import run_demo
        d = Path(tempfile.mkdtemp(prefix="neuron-demo-")) / "data"
        result = run_demo(d, step_delay=0.1, out=lambda *_: None)
        self.assertTrue(result["ok"], result["checks"])


if __name__ == "__main__":
    unittest.main()
