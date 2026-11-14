"""Resume: after a network loss and a restart, carry on from the exact step."""
import unittest
from pathlib import Path

from tests.helpers import Rig


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.r = Rig()
        self.addCleanup(self.r.close)

    def test_offline_does_offline_steps_and_waits(self):
        r = self.r
        tid = r.run_to_step8_then_cut()
        self.assertEqual(r.done(tid), [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 13])
        st = r.status(tid)
        self.assertEqual(st[9], "waiting_network")
        for no in (11, 14, 15, 16, 17, 18, 19, 20):
            self.assertEqual(st[no], "waiting_dependency")
        self.assertEqual(r.store.get_task(tid)["status"], "waiting_network")

    def test_resume_from_step_9_after_restart(self):
        r = self.r
        tid = r.run_to_step8_then_cut()
        before = r.done(tid)
        n_execs = len(r.store.executions(tid))

        self.assertEqual(r.restart(), [])          # brain process "dies" and comes back
        r.clock.t += 10
        r.run()                                    # still offline: only a retry happens
        self.assertEqual(r.done(tid), before)
        self.assertEqual(len(r.store.executions(tid)), n_execs)
        self.assertEqual(r.store.get_task(tid)["status"], "waiting_network")

        r.switch.set(True)                         # network back
        r.clock.t += 10
        r.run()
        self.assertEqual(r.store.executions(tid)[n_execs]["step_no"], 9)   # exact resume point
        r.approve_all()
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "done")
        self.assertEqual(r.done(tid), list(range(1, 21)))

    def test_retry_schedule(self):
        r = self.r
        tid = r.run_to_step8_then_cut()
        t0 = r.clock.t
        self.assertEqual(r.store.get_task(tid)["next_retry_at"], t0 + 1)
        delays = []
        for _ in range(4):                         # backoff 2, 4, then capped at 4
            r.clock.t = r.store.get_task(tid)["next_retry_at"]
            r.run()
            delays.append(r.store.get_task(tid)["next_retry_at"] - r.clock.t)
        self.assertEqual(delays, [2, 4, 4, 4])
        r.switch.set(True)                         # network is back but it is not retry time yet
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "waiting_network")
        r.clock.t = r.store.get_task(tid)["next_retry_at"]
        r.run()
        self.assertIn(9, r.done(tid))
        retries = [e["message"] for e in r.store.events(tid) if e["kind"] == "retry"]
        self.assertEqual(len(retries), 5)
        self.assertIn("network is back", retries[-1])

    def test_connection_lost_in_the_middle_of_a_step(self):
        r = self.r
        tid = r.engine.submit("find leads")
        r.run(until=lambda: r.status(tid)[2] == "done")
        r.engine.monitor.check()                   # monitor believes we are online...
        r.engine.monitor.probe = lambda: True      # ...and keeps believing it
        r.switch.set(False)                        # but the cable is really out
        r.engine.tick()                            # step 3 starts and hits the dead connection
        self.assertEqual(r.status(tid)[3], "waiting_network")
        self.assertEqual(r.world.ledger(tid), [])  # nothing reached the outside world
        self.assertEqual(r.store.executions(tid)[-1]["outcome"], "network_lost")

    def test_every_change_is_on_disk_immediately(self):
        r = self.r
        tid = r.engine.submit("find leads")
        r.engine.tick()
        from neuron.brain.store import Store       # a second, independent reader of the file
        other = Store(r.dir / "brain.db")
        self.addCleanup(other.db.close)
        self.assertEqual(other.steps(tid)[0]["status"], "done")
        self.assertTrue(other.steps(tid)[0]["proof"]["evidence"]["sha256"])
        self.assertTrue(Path(other.steps(tid)[0]["proof"]["evidence"]["file"]).exists())


if __name__ == "__main__":
    unittest.main()
