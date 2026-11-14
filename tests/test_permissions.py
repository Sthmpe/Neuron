"""Permissions: a sensitive step waits for the host, and obeys the answer."""
import unittest

from tests.helpers import Rig


def sends(r, tid):
    return [l for l in r.world.ledger(tid) if l["action"] == "send_message"]


class PermissionTests(unittest.TestCase):
    def setUp(self):
        self.r = Rig()
        self.addCleanup(self.r.close)
        self.tid = self.r.engine.submit("find leads")
        self.r.run()

    def test_sensitive_step_waits_for_host(self):
        r, tid = self.r, self.tid
        self.assertEqual(r.status(tid)[18], "waiting_approval")
        self.assertEqual(r.store.get_task(tid)["status"], "waiting_approval")
        pending = r.store.list_permissions("pending")
        self.assertEqual([(p["task_id"], p["step_no"]) for p in pending], [(tid, 18)])
        self.assertEqual(sends(r, tid), [])
        self.assertEqual(r.status(tid)[19], "done")        # unrelated work was not held up
        self.assertEqual(r.status(tid)[20], "pending")     # work that depends on it was
        r.clock.t += 3600
        for _ in range(10):
            self.assertFalse(r.engine.tick())              # waits as long as it takes
        self.assertEqual(sends(r, tid), [])

    def test_approved_step_runs_once(self):
        r, tid = self.r, self.tid
        r.approve_all(True)
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "done")
        self.assertEqual(len(sends(r, tid)), 1)
        self.assertEqual(r.done_runs(tid)[18], 1)

    def test_rejected_step_never_runs(self):
        r, tid = self.r, self.tid
        r.approve_all(False)
        r.run()
        self.assertEqual(r.status(tid)[18], "rejected")
        self.assertEqual(sends(r, tid), [])
        self.assertEqual(r.store.get_task(tid)["status"], "done")
        self.assertEqual(r.status(tid)[20], "done")
        from neuron.brain.report import build_report, report_text
        rep = build_report(r.store, r.world, tid)
        self.assertEqual((rep["totals"]["done"], rep["totals"]["rejected"], rep["totals"]["failed"]), (19, 1, 0))
        self.assertIn("rejected", report_text(rep))

    def test_pending_request_survives_restart(self):
        r, tid = self.r, self.tid
        r.restart()
        r.run()
        self.assertEqual(len(r.store.list_permissions()), 1)      # not asked twice
        self.assertEqual(r.status(tid)[18], "waiting_approval")
        self.assertEqual(sends(r, tid), [])
        r.approve_all(True)
        r.run()
        self.assertEqual(len(sends(r, tid)), 1)

    def test_decision_cannot_be_changed_afterwards(self):
        r = self.r
        p = r.store.list_permissions("pending")[0]
        r.store.decide_permission(p["id"], "rejected")
        self.assertEqual(r.store.decide_permission(p["id"], "approved")["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
