"""The shared loop: understand, investigate, plan, execute, observe, verify, revise, continue.

The same loop runs every kind of job. What differs per kind is the workflow (which capabilities, in what
order) and the verification each capability performs. The model is used for the small decisions it can
get right (classify, outline, diagnose, write one piece) and never to judge its own success.
"""
import json
import time
from pathlib import Path

from ..brain.llm import LLMUnavailable
from . import router
from .capability import Missing, Outcome, Verdict, default_registry
from .state import JobState

MAX_TRIES = 3          # per task, across strategies
MAX_REWORK = 2         # how often a check may send an earlier task back

# General workflows per kind of job: (task id, capability, title). Inputs are filled from the goal.
WORKFLOWS = {
    "excel": [("inputs", "read_tables", "Read the attached data"), ("design", "plan_workbook", "Decide the sheets, columns and formulas"),
              ("write", "write_workbook", "Write the workbook with real formulas"), ("check", "check_workbook", "Recalculate it in a spreadsheet application and check the numbers")],
    "word": [("outline", "plan_document", "Outline the document from the request"), ("write", "write_document", "Write each section and assemble the document"),
             ("check", "check_document", "Check structure, length, tables and wording")],
    "pptx": [("outline", "plan_deck", "Plan the slides"), ("build", "build_deck", "Build the deck with the design system"),
             ("check", "check_deck", "Render the deck and check it")],
    "pdf_qa": [("index", "index_documents", "Read and index the documents page by page"), ("answer", "answer_from_documents", "Answer each question with a cited page")],
    "fix_bug": [("inspect", "inspect_workspace", "Look at the project: languages, build and test commands"),
                ("fix", "fix_bug", "Find the faulty code, change it, run the tests")],
    "document_code": [("inspect", "inspect_workspace", "Look at the project"), ("document", "document_functions", "Write a docstring for every undocumented function"),
                      ("check", "run_tests", "Run the tests to prove behaviour is unchanged")],
    "build_program": [("design", "plan_program", "Decide the files and what each must do"), ("write", "write_program", "Write the files, build them, test them against examples")],
    "web_app": [("build", "build_web_app", "Plan, build and test the web app")],
    "answer": [("answer", "answer_question", "Answer with the local model")],
}


class Job:
    """One goal in one workspace: the state on disk, the models (one in memory at a time), the sandbox."""

    def __init__(self, workspace, runner, sandbox, registry=None, log=print, design=True):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state = JobState(self.workspace)
        self.runner, self.sandbox, self.log = runner, sandbox, log
        self.registry = registry or default_registry()
        self.design = design
        self.calls, self.model_seconds, self.tokens, self.online_calls = 0, 0.0, 0, 0

    # ---- model access (roles share one loaded model unless configured otherwise) -------------------
    def chat(self, role, messages, **kw):
        reply = self.runner.client(role).chat(messages, **kw)
        self.calls += 1
        self.online_calls += str(reply.model).startswith("online:")
        self.model_seconds += reply.seconds
        self.tokens += reply.completion_tokens
        return reply

    def ask_text(self, role, system, user, max_tokens=800, temperature=0.2):
        try:
            return self.chat(role, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                             max_tokens=max_tokens, temperature=temperature).text.strip()
        except LLMUnavailable:
            return ""

    def ask_json(self, role, system, user, schema, max_tokens=800, tries=2):
        messages = [{"role": "system", "content": system + " Reply with JSON only."}, {"role": "user", "content": user}]
        for _ in range(tries):
            try:
                reply = self.chat(role, messages, max_tokens=max_tokens, temperature=0.1, json_schema=schema)
            except LLMUnavailable:
                return None
            t = reply.text
            try:
                return json.loads(t[t.index("{"): t.rindex("}") + 1])
            except ValueError:
                messages += [{"role": "assistant", "content": t}, {"role": "user", "content": "That was not valid JSON. Send it again."}]
        return None


class Agent:
    def __init__(self, job):
        self.job = job
        self.s = job.state

    # ---- the loop ------------------------------------------------------------------------------------
    def run(self, request, attachments=(), max_seconds=None):
        t0, job, s = time.time(), self.job, self.s
        if s.exists():
            cut = s.resume()
            job.log(f"resuming: interrupted {cut}, done {[t['id'] for t in s.plan() if t['status'] == 'done']}")
        else:
            s.create(request, attachments)
        s.journal("session", models={r: job.runner.model_for(r) for r in ("planner", "reviewer", "builder")})
        g = s.goal()
        if not g.get("kind"):                                            # understand
            kind, how = router.understand(job, request, attachments)
            s.update_goal(kind=kind, kind_reason=how)
            s.decide("understand", "kind", f"{kind} ({how})")
            job.log(f"understood as: {kind} ({how})")
        if not s.plan():                                                 # investigate + plan
            self.plan(s.goal())
        while True:                                                      # execute, observe, verify, revise, continue
            if max_seconds and time.time() - t0 > max_seconds:
                s.set_progress(state="stopped", reason="time limit")
                break
            if getattr(job, "stop_requested", False):
                s.set_progress(state="stopped", reason="stopped by the owner")
                break
            task = s.ready_task()
            if task is None:
                break
            self.step(task)
        return self.report(time.time() - t0)

    def plan(self, goal):
        kind = goal["kind"]
        steps = WORKFLOWS.get(kind, WORKFLOWS["answer"])
        tasks, prev = [], None
        for tid, cap, title in steps:
            tasks.append({"id": tid, "capability": cap, "title": title, "params": {}, "depends": [prev] if prev else []})
            prev = tid
        missing = {t["capability"]: self.job.registry.get(t["capability"]).missing() for t in tasks if self.job.registry.has(t["capability"])}
        unknown = [t["capability"] for t in tasks if not self.job.registry.has(t["capability"])]
        self.s.set_plan(tasks)
        self.s.decide("plan", "workflow", f"{kind}: " + " -> ".join(t["capability"] for t in tasks))
        for cap, miss in missing.items():
            if miss:
                self.s.decide("plan", "missing", f"{cap} needs {', '.join(miss)}, which is not installed")
        if unknown:
            self.s.decide("plan", "missing", f"no capability yet for: {', '.join(unknown)}")

    def step(self, task):
        job, s = self.job, self.s
        tid = task["id"]
        if not job.registry.has(task["capability"]):
            s.update_task(tid, status="failed", summary=f"NEURON has no '{task['capability']}' capability yet")
            return
        cap = job.registry.get(task["capability"])
        if cap.missing():
            s.update_task(tid, status="failed", summary="not installed: " + ", ".join(cap.missing()))
            return
        if "send_message" in cap.permissions or getattr(cap, "sensitive", False):     # the owner decides, not NEURON
            answer = next((a for a in s.approvals() if a["task"] == tid and a["action"] == cap.name), None)
            if answer is None:
                s.ask_approval(tid, cap.name)
                s.update_task(tid, status="waiting_approval", summary=f"waiting for the owner to approve: {task['title']}")
                s.set_progress(state="waiting_approval", task=tid)
                return
            if answer["status"] == "pending":
                s.update_task(tid, status="waiting_approval")
                return
            if answer["status"] == "rejected":
                s.update_task(tid, status="skipped", summary="the owner rejected this action")
                return
        if cap.needs_internet and not getattr(job, "online", False):
            s.update_task(tid, status="pending", summary="waiting for the internet")
            s.set_progress(state="waiting_network", task=tid)
            return
        s.update_task(tid, status="in_progress")
        s.set_progress(state="working", task=tid, title=task["title"])
        task = s.task(tid)
        while len(task["attempts"]) < MAX_TRIES:
            n = len(task["attempts"]) + 1
            params = dict(task.get("params") or {})
            if task["attempts"] and not task["attempts"][-1].get("passed"):   # revise: change strategy, never repeat
                params.update(self.choose_strategy(task, cap))
            t0 = time.time()
            try:
                out = cap.run(job, params)
            except Missing as e:
                out = Outcome(False, f"not installed: {e}")
            except LLMUnavailable as e:
                out = Outcome(False, f"the local model could not be used: {e}")
            verdict = cap.verify(job, params, out) if out.ok else Verdict(False, [{"id": "ran", "pass": False, "detail": out.summary}], "the step itself failed")
            s.record_evidence(tid, verdict)
            attempt = {"n": n, "passed": verdict.passed, "summary": out.summary, "files": out.files, "made_by": out.made_by,
                       "strategy": params.get("strategy"), "seconds": round(time.time() - t0, 1),
                       "failure": "; ".join(f"{c['id']}: {c['detail']}" for c in verdict.failures)[:1500]}
            s.add_attempt(tid, attempt)
            job.log(f"  {tid} try {n}: {'verified' if verdict.passed else 'failed - ' + attempt['failure'][:140]}")
            if verdict.passed:
                s.update_task(tid, status="done", summary=out.summary, result=out.result, files=out.files, made_by=out.made_by,
                              verification=verdict.how)
                return
            if verdict.rework and self._rework(task, verdict, attempt["failure"]):
                return
            task = s.task(tid)
            if out.evidence.get("no_retry"):
                break
        s.update_task(tid, status="failed", summary=task["attempts"][-1]["summary"] if task["attempts"] else "no attempt")

    def _rework(self, task, verdict, failure):
        """A check found a problem an earlier step must fix: send that step back with the findings."""
        back = verdict.rework
        try:
            earlier = self.s.task(back)
        except StopIteration:
            return False
        if task.get("reworks", 0) >= MAX_REWORK:
            return False
        params = dict(earlier.get("params") or {})
        params.update(feedback=failure, strategy=f"rework requested by '{task['id']}'")
        self.s.update_task(back, status="pending", params=params)
        self.s.update_task(task["id"], status="pending", reworks=task.get("reworks", 0) + 1, attempts=task["attempts"][:-1])
        self.s.decide(task["id"], "rework", f"sent '{back}' back: {failure[:300]}")
        self.job.log(f"  {task['id']}: sent '{back}' back to be redone")
        return True

    def choose_strategy(self, task, cap):
        tried = [a.get("strategy") for a in task["attempts"]]
        options = [x for x in getattr(cap, "strategies", ()) if x not in tried]
        feedback = task["attempts"][-1].get("failure", "")
        if not options:
            return {"feedback": feedback, "strategy": f"retry {len(tried) + 1} with the failure as feedback"}
        choice = options[0]
        if len(options) > 1:
            data = self.job.ask_json("reviewer", "A step failed. Pick the strategy most likely to work next.",
                                     f"Step: {task['title']}\nWhat failed: {feedback[:1200]}\nStrategies not tried yet: {', '.join(options)}",
                                     {"type": "object", "required": ["strategy", "reason"],
                                      "properties": {"strategy": {"type": "string", "enum": options}, "reason": {"type": "string"}}},
                                     max_tokens=200)
            if data and data.get("strategy") in options:
                choice = data["strategy"]
                self.s.decide(task["id"], "strategy", f"{choice}: {data.get('reason', '')[:200]}")
        self.s.update_task(task["id"], strategies_tried=tried + [choice])
        return {"feedback": feedback, "strategy": choice}

    # ---- the report: only verified work counts as done -----------------------------------------------
    def report(self, seconds):
        plan = self.s.plan()
        done = [t for t in plan if t["status"] == "done"]
        failed = [t for t in plan if t["status"] in ("failed", "skipped")]
        made = {}
        for t in done:
            made[t.get("made_by", "deterministic")] = made.get(t.get("made_by", "deterministic"), 0) + 1
        verdict = "VERIFIED" if plan and len(done) == len(plan) else "PARTIAL" if done else "FAILED"
        files = sorted({f for t in done for f in t.get("files", [])})
        rep = {"verdict": verdict, "kind": self.s.goal().get("kind"), "tasks": {t["id"]: t["status"] for t in plan},
               "failed": {t["id"]: t.get("summary", "") for t in failed}, "files": files, "made_by": made,
               "model_calls": self.job.calls, "online_calls": self.job.online_calls, "model_seconds": round(self.job.model_seconds, 1), "tokens": self.job.tokens,
               "seconds": round(seconds, 1), "pending": [t["id"] for t in plan if t["status"] in ("pending", "waiting_approval")],
               "waiting_approval": [t["id"] for t in plan if t["status"] == "waiting_approval"]}
        self.s.set_progress(state="finished" if not rep["pending"] else "paused", verdict=verdict)
        (self.s.dir / "report.json").write_text(json.dumps(rep, indent=1))
        return rep
