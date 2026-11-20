"""Everything about a job, on disk, independent of any model. <workspace>/.neuron/job/

  goal.json        the owner's words, domain, deliverables, acceptance criteria
  plan.json        the task graph: capability, inputs, dependencies, status, attempts, evidence
  knowledge.jsonl  facts learned, each with its source
  decisions.jsonl  why things were done, diagnoses, strategy changes
  evidence.jsonl   every verification, with its checks
  approvals.jsonl  sensitive actions asked for, and the owner's answers
  journal.jsonl    sessions: started, resumed, which model, interruptions
  progress.json    where the job is and the next action
"""
import json
import os
import time
import uuid
from pathlib import Path

TERMINAL = ("done", "partial", "failed", "skipped")     # partial: delivered with stated gaps


def _write(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    os.replace(tmp, path)


class JobState:
    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.dir = self.workspace / ".neuron" / "job"

    def exists(self):
        return (self.dir / "goal.json").exists()

    def _read(self, name, default):
        p = self.dir / name
        return json.loads(p.read_text()) if p.exists() else default

    def _append(self, name, obj):
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / name, "a") as f:
            f.write(json.dumps({"at": time.time(), **obj}) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def lines(self, name):
        p = self.dir / name
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    # goal ------------------------------------------------------------------------------------------
    def create(self, request, attachments=()):
        self.dir.mkdir(parents=True, exist_ok=True)
        _write(self.dir / "goal.json", {"request": request, "attachments": list(attachments), "created_at": time.time(),
                                        "domain": None, "deliverables": [], "criteria": []})
        _write(self.dir / "plan.json", [])
        self.journal("created")

    def goal(self):
        return self._read("goal.json", {})

    def update_goal(self, **fields):
        g = self.goal()
        g.update(fields)
        _write(self.dir / "goal.json", g)

    # plan ------------------------------------------------------------------------------------------
    def plan(self):
        return self._read("plan.json", [])

    def set_plan(self, tasks):
        for t in tasks:
            t.setdefault("status", "pending")
            t.setdefault("attempts", [])
            t.setdefault("depends", [])
            t.setdefault("strategies_tried", [])
        _write(self.dir / "plan.json", tasks)

    def task(self, tid):
        return next(t for t in self.plan() if t["id"] == tid)

    def update_task(self, tid, **fields):
        plan = self.plan()
        for t in plan:
            if t["id"] == tid:
                t.update(fields)
        _write(self.dir / "plan.json", plan)

    def add_attempt(self, tid, attempt):
        plan = self.plan()
        for t in plan:
            if t["id"] == tid:
                t["attempts"].append(attempt)
        _write(self.dir / "plan.json", plan)

    def request_input(self, tid, question, context=None):
        """A step needs a fact only the owner has (from Astra's research/astra branch)."""
        prompt = {"id": uuid.uuid4().hex, "question": question, "context": context}
        self.update_task(tid, status="waiting_input", input_request=prompt, summary="Waiting for the owner's reply")

    def answer_input(self, prompt_id, answer, accept_new):
        """Commit the reply and make the step runnable in the same plan revision. Re-sending the same reply is harmless."""
        for task in self.plan():
            history = task.get("owner_inputs", [])
            for old in history:
                if old["id"] == prompt_id:
                    if old["answer"] == answer:
                        return False
                    raise ValueError("This question already has a different reply.")
            prompt = task.get("input_request")
            if accept_new and task["status"] == "waiting_input" and prompt and prompt["id"] == prompt_id:
                self.update_task(task["id"], status="pending", input_request=None,
                                 owner_inputs=[*history, {**prompt, "answer": answer}], summary="Owner replied")
                return True
        raise ValueError("This question is no longer waiting for a reply.")

    def add_tasks(self, tasks, after=None):
        plan = self.plan()
        for t in tasks:
            t.setdefault("status", "pending")
            t.setdefault("attempts", [])
            t.setdefault("depends", [after] if after else [])
            t.setdefault("strategies_tried", [])
        _write(self.dir / "plan.json", plan + tasks)

    def ready_task(self):
        plan = self.plan()
        done = {t["id"] for t in plan if t["status"] in ("done", "partial")}
        blocked = {t["id"] for t in plan if t["status"] in ("failed", "skipped")}
        for t in plan:
            if t["status"] in ("pending", "in_progress"):
                if any(d in blocked for d in t["depends"]):
                    self.update_task(t["id"], status="skipped", reason="a task it depends on did not succeed")
                    return self.ready_task()
                if all(d in done for d in t["depends"]):
                    return t
        return None

    def finished(self):
        return all(t["status"] in TERMINAL for t in self.plan())

    # records ---------------------------------------------------------------------------------------
    def learn(self, fact, source):
        self._append("knowledge.jsonl", {"fact": fact, "source": source})

    def decide(self, task, kind, text):
        self._append("decisions.jsonl", {"task": task, "kind": kind, "text": text})

    def record_evidence(self, task, verdict):
        self._append("evidence.jsonl", {"task": task, "passed": verdict.passed, "how": verdict.how, "checks": verdict.checks})

    def ask_approval(self, task, action, question=""):
        self._append("approvals.jsonl", {"task": task, "action": action, "status": "pending", "question": question})

    def approvals(self):
        latest = {}
        for a in self.lines("approvals.jsonl"):
            latest[(a["task"], a["action"])] = a
        return list(latest.values())

    def answer_approval(self, task, action, approved):
        self._append("approvals.jsonl", {"task": task, "action": action, "status": "approved" if approved else "rejected"})

    def journal(self, event, **fields):
        self._append("journal.jsonl", {"event": event, **fields})

    def set_progress(self, **fields):
        _write(self.dir / "progress.json", {"at": time.time(), **fields})

    def progress(self):
        return self._read("progress.json", {})

    def resume(self):
        """A task left in progress by a dead session goes back to pending. Finished work is never redone."""
        plan = self.plan()
        cut = [t["id"] for t in plan if t["status"] == "in_progress"]
        for t in plan:
            if t["status"] == "in_progress":
                t["status"] = "pending"
        _write(self.dir / "plan.json", plan)
        self.journal("resumed", interrupted=cut, done=[t["id"] for t in plan if t["status"] == "done"])
        return cut
