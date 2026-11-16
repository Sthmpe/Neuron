"""Project state on disk - independent of any model.

Everything the builder knows about a project lives in <project>/.neuron/ as plain JSON:

  spec.json          the request in the owner's words + the structured specification
  acceptance.json    acceptance tests (declarative steps, or "run the project's test suite")
  tasks.json         the task list: status, attempts, result of each
  map.json           project map: every file's purpose and interfaces (functions, routes, tables)
  decisions.jsonl    decisions and diagnoses, in order, with the reason
  test_results.jsonl every test run: which task, which attempt, pass/fail, output
  journal.jsonl      sessions: when work started/resumed, with which model

Nothing here mentions a model's internals. A different model, or a brand-new session, loads
this folder and carries on. For each task the model is shown only a slice (see `slice_for`).
"""
import json
import os
import time
from pathlib import Path

from . import pmap

DONE = ("done", "failed")


def _write(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    os.replace(tmp, path)


class ProjectState:
    def __init__(self, project_dir):
        self.root = Path(project_dir)
        self.dir = self.root / ".neuron"

    # ---- lifecycle -------------------------------------------------------
    def exists(self):
        return (self.dir / "tasks.json").exists()

    def create(self, request, kind, spec, tasks, acceptance, purposes=None):
        self.dir.mkdir(parents=True, exist_ok=True)
        _write(self.dir / "spec.json", {"request": request, "kind": kind, "spec": spec, "created_at": time.time()})
        _write(self.dir / "acceptance.json", acceptance)
        for t in tasks:
            t.setdefault("status", "pending")
            t.setdefault("attempts", [])
        _write(self.dir / "tasks.json", tasks)
        self.refresh_map(purposes)
        self.journal("created", kind=kind, tasks=len(tasks))

    def resume(self):
        """Call when a session starts on an existing project. A task that was in progress when the
        previous session died goes back to pending; finished tasks are never redone."""
        tasks = self.tasks()
        interrupted = [t["id"] for t in tasks if t["status"] == "in_progress"]
        for t in tasks:
            if t["status"] == "in_progress":
                t["status"] = "pending"
        _write(self.dir / "tasks.json", tasks)
        self.journal("resumed", interrupted=interrupted,
                     done=[t["id"] for t in tasks if t["status"] == "done"])
        return interrupted

    # ---- reading ---------------------------------------------------------
    def _read(self, name, default=None):
        p = self.dir / name
        return json.loads(p.read_text()) if p.exists() else default

    def spec(self):
        return self._read("spec.json")

    def acceptance(self):
        return self._read("acceptance.json", [])

    def tasks(self):
        return self._read("tasks.json", [])

    def task(self, task_id):
        return next(t for t in self.tasks() if t["id"] == task_id)

    def map(self):
        return self._read("map.json", {})

    def next_task(self):
        return next((t for t in self.tasks() if t["status"] not in DONE), None)

    def finished(self):
        return all(t["status"] in DONE for t in self.tasks())

    def lines(self, name):
        p = self.dir / name
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    # ---- writing ---------------------------------------------------------
    def update_task(self, task_id, **fields):
        tasks = self.tasks()
        for t in tasks:
            if t["id"] == task_id:
                t.update(fields)
        _write(self.dir / "tasks.json", tasks)

    def add_attempt(self, task_id, attempt):
        tasks = self.tasks()
        for t in tasks:
            if t["id"] == task_id:
                t["attempts"].append(attempt)
        _write(self.dir / "tasks.json", tasks)

    def _append(self, name, obj):
        with open(self.dir / name, "a") as f:
            f.write(json.dumps({"at": time.time(), **obj}) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def decide(self, task_id, kind, text):
        self._append("decisions.jsonl", {"task": task_id, "kind": kind, "text": text})

    def record_test(self, task_id, attempt, passed, summary, output=""):
        self._append("test_results.jsonl", {"task": task_id, "attempt": attempt, "passed": passed,
                                            "summary": summary, "output_tail": output[-2000:]})

    def journal(self, event, **fields):
        self._append("journal.jsonl", {"event": event, **fields})

    def refresh_map(self, purposes=None):
        old = self.map()
        known = {f: v.get("purpose", "") for f, v in old.items()}
        known.update(purposes or {})
        _write(self.dir / "map.json", pmap.build_map(self.root, known))

    # ---- the slice a model gets for one task ------------------------------
    def slice_for(self, task, budget=6000):
        """Only what this task needs: its contract, the interfaces of the files it depends on,
        the file it edits (if any), and what the last attempt got wrong."""
        m = self.map()
        parts = {"task": task["title"], "contract": task.get("contract", ""), "file": task.get("file", "")}
        needs = [f for f in task.get("needs", []) if f in m]
        parts["interfaces"] = pmap.interfaces_text(m, needs)
        target = self.root / task["file"] if task.get("file") else None
        parts["current_file"] = target.read_text()[:budget] if target and target.exists() else ""
        fails = [a for a in task.get("attempts", []) if not a.get("passed")]
        if fails:
            last = fails[-1]
            parts["last_failure"] = (last.get("failure") or "")[-1500:]
            parts["advice"] = last.get("advice") or ""
            parts["previous_code"] = (last.get("code") or "")[:budget]
        return parts
