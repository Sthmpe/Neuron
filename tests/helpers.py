import shutil
import tempfile
from pathlib import Path

from neuron.brain.engine import Engine
from neuron.brain.network import NetworkMonitor, SimulatedSwitch
from neuron.brain.planner import RuleBasedPlanner
from neuron.brain.store import Store
from neuron.brain.world import FakeWorld


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Rig:
    """A brain without HTTP, on a temp folder, with a clock the test controls.
    `restart()` throws the engine away and builds a new one on the same files,
    which is exactly what a process restart does."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="neuron-test-"))
        self.clock = Clock()
        self.boot()

    def boot(self):
        self.store = Store(self.dir / "brain.db", self.clock)
        self.switch = SimulatedSwitch(self.dir / "network.json")
        self.world = FakeWorld(self.dir / "world.db", self.switch, self.clock)
        self.engine = Engine(self.store, RuleBasedPlanner(), NetworkMonitor(self.switch.is_online),
                             self.world, self.dir / "artifacts", clock=self.clock,
                             retry_base=1.0, retry_cap=4.0)

    def restart(self):
        self.store.db.close()
        self.world.db.close()
        self.boot()
        return self.engine.recover()

    def close(self):
        self.store.db.close()
        self.world.db.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    # ---- driving ---------------------------------------------------------
    def run(self, until=None, limit=500):
        """Tick until nothing more happens (or until `until()` is true)."""
        for _ in range(limit):
            if until and until():
                return
            if not self.engine.tick():
                return
        raise AssertionError("engine did not settle")

    def status(self, tid):
        return {s["no"]: s["status"] for s in self.store.steps(tid)}

    def done(self, tid):
        return [n for n, st in self.status(tid).items() if st == "done"]

    def done_runs(self, tid):
        counts = {}
        for e in self.store.executions(tid):
            if e["outcome"] == "done":
                counts[e["step_no"]] = counts.get(e["step_no"], 0) + 1
        return counts

    def approve_all(self, approve=True):
        for p in self.store.list_permissions("pending"):
            self.store.decide_permission(p["id"], "approved" if approve else "rejected")

    def run_to_step8_then_cut(self):
        tid = self.engine.submit("find leads")
        self.run(until=lambda: self.status(tid)[8] == "done")
        self.switch.set(False)
        self.run()
        return tid
