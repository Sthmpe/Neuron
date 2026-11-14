"""The engine: scheduler + executor + recovery + permissions in one loop.

`tick()` does at most one unit of work per task and returns True if anything
changed. The brain calls it in a loop; tests call it by hand.

Rules:
  * Steps run one at a time, lowest number first, once the steps they depend on are finished.
  * A step that needs internet is skipped while offline; offline steps that are ready still run.
  * When nothing more can be done offline the task is 'waiting_network' and the
    connection is re-checked on a schedule (retry with backoff).
  * A sensitive step never runs until the host has approved it.
  * A step whose status is 'done' is never run again - the status is read from SQLite.
"""
import hashlib
import json
import time
import traceback
from pathlib import Path

from .actions import ACTIONS, Ctx
from .network import NetworkDown

TERMINAL = ("done", "failed", "rejected", "blocked")


class Engine:
    def __init__(self, store, planner, monitor, world, artifacts_dir, clock=time.time,
                 step_delay=0.0, retry_base=1.0, retry_cap=30.0):
        self.store, self.planner, self.monitor, self.world = store, planner, monitor, world
        self.artifacts = Path(artifacts_dir)
        self.clock, self.step_delay = clock, step_delay
        self.retry_base, self.retry_cap = retry_base, retry_cap

    # ---- intake / restart ------------------------------------------------
    def submit(self, goal, start_at=None):
        plan = self.planner.plan(goal)
        return self.store.create_task(goal, plan, self.planner.name, start_at)

    def recover(self):
        """Call once at start-up. Returns the steps that were cut off mid-run."""
        return self.store.recover_interrupted()

    # ---- main loop -------------------------------------------------------
    def tick(self):
        now, worked = self.clock(), False
        for task in self.store.active_tasks():
            if task["status"] == "scheduled":
                if task["start_at"] > now:
                    continue
                self.store.set_task(task["id"], status="running",
                                    event=("schedule", "scheduled start time reached - starting"))
                task = self.store.get_task(task["id"])
                worked = True
            worked = self._advance(task, now) or worked
        return worked

    def _retry_delay(self, n):
        return min(self.retry_cap, self.retry_base * (2 ** min(n, 16)))

    def _network_for(self, task, now):
        """Is the network usable for this task right now? Handles the retry schedule."""
        tid = task["id"]
        if task["status"] != "waiting_network":
            return self.monitor.check()
        if now < (task["next_retry_at"] or 0):
            return False  # not time to retry yet
        n = task["retry_count"] + 1
        if self.monitor.check():
            self.store.set_task(tid, status="running", retry_count=0, next_retry_at=None,
                                event=("retry", f"retry #{n}: network is back - resuming"))
            return True
        delay = self._retry_delay(n)
        self.store.set_task(tid, retry_count=n, next_retry_at=now + delay,
                            event=("retry", f"retry #{n}: still offline - next retry in {delay:g}s"))
        return False

    def _advance(self, task, now):
        tid = task["id"]
        online = self._network_for(task, now)
        steps = self.store.steps(tid)
        status = {s["no"]: s["status"] for s in steps}
        changed = False
        for s in steps:
            no = s["no"]
            if s["status"] in TERMINAL:
                continue
            deps = [status.get(d) for d in s["depends_on"]]
            if any(d in ("failed", "blocked") for d in deps):
                self.store.set_step(tid, no, status="blocked",
                                    event=("step", f"step {no} blocked: a step it depends on failed"))
                status[no] = "blocked"
                changed = True
                continue
            if not all(d in ("done", "rejected") for d in deps):
                continue  # not ready yet
            if s["sensitive"]:
                perm = self.store.get_permission(tid, no)
                if perm is None:
                    self.store.request_permission(tid, no, s["title"])
                    return True
                if perm["status"] == "pending":
                    continue
                if perm["status"] == "rejected":
                    self.store.set_step(tid, no, status="rejected", finished_at=now,
                                        proof={"summary": "Not run: the host rejected this step",
                                               "permission_id": perm["id"]},
                                        event=("step", f"step {no} skipped: rejected by host"))
                    return True
            if s["needs_internet"] and not online:
                if s["status"] != "waiting_network":
                    self.store.set_step(tid, no, status="waiting_network",
                                        event=("step", f"step {no} needs internet - waiting"))
                    changed = True
                continue
            self._execute(task, s, steps)
            return True
        return self._settle(task, online, now) or changed

    def _settle(self, task, online, now):
        """Nothing could run this tick: work out what the task is waiting for."""
        tid = task["id"]
        steps = self.store.steps(tid)
        if all(s["status"] in TERMINAL for s in steps):
            bad = [s["no"] for s in steps if s["status"] in ("failed", "blocked")]
            self.store.set_task(tid, status="failed" if bad else "done", finished_at=now,
                                event=("task", f"task finished with problems in steps {bad}" if bad
                                       else "task finished: all steps accounted for"))
            return True
        net_wait = [s["no"] for s in steps if s["status"] == "waiting_network"]
        if net_wait and not online:
            if task["status"] == "waiting_network":
                return False
            self.store.mark_pending_as(tid, "waiting_dependency")
            delay = self._retry_delay(0)
            left = [s["no"] for s in steps if s["status"] not in TERMINAL]
            self.store.set_task(tid, status="waiting_network", retry_count=0, next_retry_at=now + delay,
                                event=("offline", f"offline: every possible offline step is done; steps {left} "
                                       f"are waiting (need internet: {net_wait}); first retry in {delay:g}s"))
            return True
        if any(s["status"] == "waiting_approval" for s in steps):
            if task["status"] == "waiting_approval":
                return False
            self.store.set_task(tid, status="waiting_approval",
                                event=("task", "waiting for the host to approve or reject"))
            return True
        if online:
            self.store.set_task(tid, status="failed", finished_at=now,
                                event=("task", "task is stuck: remaining steps can never become ready"))
            return True
        return False

    # ---- executor --------------------------------------------------------
    def _execute(self, task, step, steps):
        tid, no = task["id"], step["no"]
        if task["status"] == "waiting_approval":
            self.store.set_task(tid, status="running")
        attempt, exec_id = self.store.begin_execution(tid, no)
        started = self.clock()
        deps = {s["no"]: s["result"] for s in steps if s["no"] in step["depends_on"] and s["status"] == "done"}
        ctx = Ctx(task, step, deps, self.world, self.artifacts)
        try:
            if self.step_delay:
                time.sleep(self.step_delay)  # pretend the work takes time
            result, summary, evidence = ACTIONS[step["action"]](ctx)
        except NetworkDown as e:
            self.store.end_execution(exec_id, tid, no, "network_lost", detail=str(e), status="waiting_network",
                                     event=("step", f"step {no} lost the connection mid-step - waiting"))
            return
        except Exception as e:
            proof = {"summary": f"FAILED: {type(e).__name__}: {e}", "attempt": attempt,
                     "traceback": traceback.format_exc(limit=3)}
            self.store.end_execution(exec_id, tid, no, "failed", detail=str(e), status="failed",
                                     error=f"{type(e).__name__}: {e}", proof=proof,
                                     event=("step", f"step {no} FAILED: {e}"))
            return
        proof = {
            "summary": summary,
            "evidence": evidence,
            "attempt": attempt,
            "idempotency_key": ctx.key,
            "network_during_step": "online" if self.monitor.last else "offline",
            "started_at": started,
            "finished_at": self.clock(),
            "result_sha256": hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
        }
        self.store.end_execution(exec_id, tid, no, "done", status="done", result=result, proof=proof,
                                 event=("step", f"step {no} done: {summary}"))
