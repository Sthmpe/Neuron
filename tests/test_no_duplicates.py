"""No duplicates: a finished step is never run again, whatever happens."""
import unittest

from tests.helpers import Rig


class Crash(BaseException):
    """Stands in for the process dying at the worst possible moment."""


class NoDuplicateTests(unittest.TestCase):
    def setUp(self):
        self.r = Rig()
        self.addCleanup(self.r.close)

    def assert_exactly_once(self, tid):
        r = self.r
        self.assertEqual(r.done_runs(tid), {n: 1 for n in range(1, 21)})
        ledger = r.world.ledger(tid)
        self.assertEqual(len(ledger), 8)                               # 8 online steps, 8 outside actions
        self.assertEqual(len({l["key"] for l in ledger}), 8)
        self.assertEqual([l["action"] for l in ledger].count("send_message"), 1)

    def test_cut_restart_restore_runs_each_step_once(self):
        r = self.r
        tid = r.run_to_step8_then_cut()
        r.restart()
        r.switch.set(True)
        r.clock.t += 10
        r.run()
        r.approve_all()
        r.run()
        self.assert_exactly_once(tid)
        self.assertEqual(sum(l["duplicates_blocked"] for l in r.world.ledger(tid)), 0)

    def test_restart_after_every_single_step(self):
        r = self.r
        tid = r.engine.submit("find leads")
        for _ in range(200):
            r.approve_all()
            if not r.engine.tick() and r.store.get_task(tid)["status"] == "done":
                break
            r.restart()
        self.assertEqual(r.store.get_task(tid)["status"], "done")
        self.assert_exactly_once(tid)
        self.assertEqual(sum(l["duplicates_blocked"] for l in r.world.ledger(tid)), 0)

    def test_finished_task_is_never_touched_again(self):
        r = self.r
        tid = r.engine.submit("find leads")
        r.run(); r.approve_all(); r.run()
        n = len(r.store.executions(tid))
        r.restart()
        r.clock.t += 1000
        for _ in range(20):
            self.assertFalse(r.engine.tick())
        self.assertEqual(len(r.store.executions(tid)), n)
        self.assert_exactly_once(tid)

    def test_crash_after_the_action_but_before_the_checkpoint(self):
        """Worst case: the message really went out, then the brain died before saving that fact.
        On restart the step runs again with the same idempotency key, and the outside world
        refuses to do it twice."""
        r = self.r
        tid = r.engine.submit("find leads")
        r.run(); r.approve_all()
        real = r.store.end_execution

        def dying(exec_id, task_id, no, outcome, **kw):
            if no == 18:
                raise Crash()
            return real(exec_id, task_id, no, outcome, **kw)

        r.store.end_execution = dying
        with self.assertRaises(Crash):
            r.run()
        sends = [l for l in r.world.ledger(tid) if l["action"] == "send_message"]
        self.assertEqual(len(sends), 1)                       # it did go out
        self.assertEqual(r.status(tid)[18], "running")        # but the brain never recorded it

        self.assertEqual(r.restart(), [(tid, 18)])            # restart notices the cut-off step
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "done")
        sends = [l for l in r.world.ledger(tid) if l["action"] == "send_message"]
        self.assertEqual(len(sends), 1)                       # still only ONE message sent
        self.assertEqual(sends[0]["duplicates_blocked"], 1)   # the second try was blocked
        self.assertEqual(r.done_runs(tid)[18], 1)
        proof = [s for s in r.store.steps(tid) if s["no"] == 18][0]["proof"]
        self.assertTrue(proof["evidence"]["receipt"]["replayed"])


if __name__ == "__main__":
    unittest.main()
