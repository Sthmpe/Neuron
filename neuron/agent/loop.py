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
from .effects import Effects, Uncertain
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
    "upgrade_packages": [("inspect", "inspect_workspace", "Look at the project: packages and test command"),
                         ("upgrade", "upgrade_packages", "Check for newer packages, upgrade in an isolated copy, test, keep only what passes")],
    "answer": [("answer", "answer_question", "Answer with the local model")],
}


class Job:
    """One goal in one workspace: the state on disk, the models (one in memory at a time), the sandbox."""

    def __init__(self, workspace, runner, sandbox, registry=None, log=print, design=True, memory=None):
        self.memory = memory               # knowledge memory (neuron.memory.Memory) or None
        self.memory_notes = []
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state = JobState(self.workspace)
        self.effects = Effects(self.workspace / ".neuron" / "job" / "effects.jsonl")    # outside actions, each at most once
        self.online = False                # set by whoever starts the job (sysinfo.online()); steps needing the internet wait
        self.runner, self.sandbox, self.log = runner, sandbox, log
        self.registry = registry or default_registry()
        self.design = design
        self.calls, self.model_seconds, self.tokens, self.online_calls = 0, 0.0, 0, 0
        self.usage_file = Path(workspace) / ".neuron" / "job" / "usage.json"     # totals over every session of this job
        try:
            self.prior = json.loads(self.usage_file.read_text())
        except (OSError, ValueError):
            self.prior = {}

    def memory_context(self, kinds=None):
        """Remembered notes relevant to this job, as a prompt block to be checked before use ('' if none)."""
        from ..memory import context_text
        notes = [n for n in self.memory_notes if not kinds or n["kind"] in kinds]
        return context_text(notes)

    # ---- model access (roles share one loaded model unless configured otherwise) -------------------
    def chat(self, role, messages, **kw):
        reply = self.runner.client(role).chat(messages, **kw)
        self.count(1, reply.completion_tokens, reply.seconds, str(reply.model).startswith("online:"))
        return reply

    def count(self, calls, tokens, seconds, online=0):
        """Add model use (also used by tools that call the model through their own loop, like the app builder)."""
        self.calls += calls
        self.tokens += tokens
        self.model_seconds += seconds
        self.online_calls += online
        try:
            self.usage_file.parent.mkdir(parents=True, exist_ok=True)
            self.usage_file.write_text(json.dumps(self.usage_total()))
        except OSError:
            pass

    def usage_total(self):
        p = self.prior
        return {"model_calls": p.get("model_calls", 0) + self.calls, "tokens": p.get("tokens", 0) + self.tokens,
                "model_seconds": round(p.get("model_seconds", 0) + self.model_seconds, 1),
                "online_calls": p.get("online_calls", 0) + self.online_calls, "sessions": p.get("sessions", 0) + 1}

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
        if getattr(job, "online", False):                                # back online: steps that waited for it run now
            for t in s.plan():
                if t["status"] == "waiting_network" and t.get("not_before", 0) <= time.time():
                    s.update_task(t["id"], status="pending", summary="the internet is back")
        if job.memory is not None:                                       # memory first, before any reasoning
            try:
                job.memory_notes = job.memory.search(s.goal()["request"], k=4)
            except Exception as e:                                       # noqa: BLE001  memory problems never stop a job
                job.memory_notes = []
                job.log(f"memory search failed: {e}")
            s.journal("memory", found=[{"id": n["id"], "kind": n["kind"], "status": n["status"], "score": n["score"]} for n in job.memory_notes])
            for n in job.memory_notes:
                job.memory.mark(n["id"], used=True)
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

    def _remember(self, tid, out):
        """Save what a verified step learned (its capability lists the notes), and credit remembered notes that helped."""
        job = self.job
        if job.memory is None:
            return
        for note in (out.result or {}).get("memory_notes", []) if isinstance(out.result, dict) else []:
            try:
                nid = job.memory.add(note["kind"], note["text"], note.get("source", f"job {job.workspace.name}"),
                                     version=note.get("version", ""), verified=note.get("verified", False), tags=note.get("tags", ()),
                                     meta=note.get("meta"))
                self.s.journal("memory_saved", id=nid, kind=note["kind"], task=tid)
            except Exception as e:                                       # noqa: BLE001
                job.log(f"memory save failed: {e}")
        for nid in (out.result or {}).get("memory_helped", []) if isinstance(out.result, dict) else []:
            job.memory.mark(nid, helped=True)

    def _follow_ups(self, tid, out):
        """A step can add work it found to be needed, such as fetching photos for 'Image needed' placeholders."""
        extra = (out.result or {}).get("add_tasks", []) if isinstance(out.result, dict) else []
        have = {t["id"] for t in self.s.plan()}
        new = [dict(t, depends=[tid]) for t in extra if t["id"] not in have]
        if new:
            self.s.add_tasks(new)
            self.s.decide(tid, "follow_up", "added: " + ", ".join(t["title"] for t in new))

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
        for a in s.approvals():                # the owner answered about an interrupted outside action
            if a["task"] == tid and a["action"].startswith("repeat:") and a["status"] != "pending":
                job.effects.resolve(a["action"][len("repeat:"):], happened=a["status"] == "rejected")
        if cap.needs_internet and not getattr(job, "online", False):
            # not 'pending': the loop would pick it again at once. It waits; the job resumes it when the internet is back.
            s.update_task(tid, status="waiting_network", summary="waiting for the internet")
            s.set_progress(state="waiting_network", task=tid)
            job.log(f"  {tid}: needs the internet; it will run when the connection is back")
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
            except Uncertain as e:
                # NEURON stopped in the middle of an outside action last time. Repeating it could do it twice: ask.
                action = f"repeat:{e.key}"
                if not any(a["task"] == tid and a["action"] == action and a["status"] == "pending" for a in s.approvals()):
                    s.ask_approval(tid, action, question=f"NEURON stopped in the middle of: {e.what}. It may already have "
                                                         "happened. Approve to do it again, or reject if it already happened.")
                s.update_task(tid, status="waiting_approval", summary=f"may already have happened, asking the owner: {e.what}")
                s.set_progress(state="waiting_approval", task=tid)
                return
            except Missing as e:
                out = Outcome(False, f"not installed: {e}")
            except LLMUnavailable as e:
                out = Outcome(False, f"the local model could not be used: {e}")
            if out.evidence.get("retry_later"):
                # an outside service asked NEURON to wait: stop asking, keep what was done, try again later by itself
                waits = task.get("waits", 0) + 1
                delay = max(out.evidence["retry_later"], min(600 * 3 ** (waits - 1), 6 * 3600))   # 10 min, 30 min, 1.5 h ... 6 h
                s.update_task(tid, status="waiting_network", waits=waits, not_before=time.time() + delay,
                              summary=f"{out.evidence.get('why', 'the service asked NEURON to wait')}; tries again by itself in "
                                      f"{round(delay / 60)} minutes ({out.summary})")
                s.set_progress(state="waiting_network", task=tid)
                job.log(f"  {tid}: asked to wait; tries again in {round(delay / 60)} minutes")
                return
            verdict = cap.verify(job, params, out) if out.ok else Verdict(False, [{"id": "ran", "pass": False, "detail": out.summary}], "the step itself failed")
            s.record_evidence(tid, verdict)
            attempt = {"n": n, "passed": verdict.passed, "summary": out.summary, "files": out.files, "made_by": out.made_by,
                       "strategy": params.get("strategy"), "seconds": round(time.time() - t0, 1),
                       "failure": "; ".join(f"{c['id']}: {c['detail']}" for c in verdict.failures)[:1500]}
            s.add_attempt(tid, attempt)
            job.log(f"  {tid} try {n}: {'verified' if verdict.passed else 'failed - ' + attempt['failure'][:140]}")
            if verdict.passed:
                s.update_task(tid, status="done", summary=out.summary, result=out.result, files=out.files, made_by=out.made_by,
                              verification=verdict.how, unverified=verdict.unverified)
                self._remember(tid, out)
                self._follow_ups(tid, out)
                return
            if out.ok and verdict.failures and all(c.get("gap") for c in verdict.failures):
                # what was built passes its checks; the rest cannot be built yet: deliver it and say so, retrying cannot help
                s.update_task(tid, status="partial", summary=out.summary, result=out.result, files=out.files, made_by=out.made_by,
                              verification=verdict.how, gaps=[c["detail"] for c in verdict.failures])
                self._follow_ups(tid, out)
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
        partial = [t for t in plan if t["status"] == "partial"]
        failed = [t for t in plan if t["status"] in ("failed", "skipped")]
        made = {}
        for t in done:
            made[t.get("made_by", "deterministic")] = made.get(t.get("made_by", "deterministic"), 0) + 1
        verdict = "VERIFIED" if plan and len(done) == len(plan) else "PARTIAL" if done or partial else "FAILED"
        unchecked = [t["id"] for t in done if t.get("unverified")]
        if verdict == "VERIFIED" and unchecked:       # everything ran, but part of it nothing independent could check
            verdict = "UNVERIFIED"
        files = sorted({f for t in done + partial for f in t.get("files", [])})
        rep = {"verdict": verdict, "kind": self.s.goal().get("kind"), "tasks": {t["id"]: t["status"] for t in plan},
               "failed": {t["id"]: t.get("summary", "") for t in failed}, "files": files, "made_by": made,
               "not_done": {**{t["id"]: t.get("gaps", []) for t in partial},
                            **{t["id"]: [t.get("summary") if t.get("not_before") else f"{t['title']}: waiting for the internet, resumes by itself"]
                               for t in plan if t["status"] == "waiting_network"}},
               "model_calls": self.job.calls, "online_calls": self.job.online_calls, "model_seconds": round(self.job.model_seconds, 1), "tokens": self.job.tokens,
               "usage_all_sessions": self.job.usage_total(),
               "seconds": round(seconds, 1), "pending": [t["id"] for t in plan if t["status"] in ("pending", "waiting_approval", "waiting_network")],
               "waiting_network": [t["id"] for t in plan if t["status"] == "waiting_network"],
               "retry_at": min([t.get("not_before", 0) for t in plan if t["status"] == "waiting_network"] or [0]),
               "outside_actions": self.job.effects.summary(),
               "waiting_approval": [t["id"] for t in plan if t["status"] == "waiting_approval"],
               "unverified": unchecked}
        self.s.set_progress(state="finished" if not rep["pending"] else "paused", verdict=verdict)
        (self.s.dir / "report.json").write_text(json.dumps(rep, indent=1))
        return rep
