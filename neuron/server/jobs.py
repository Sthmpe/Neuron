"""Jobs on the NEURON machine: one at a time (one model in memory), saved on disk, resumed after a restart."""
import json
import shutil
import threading
import time
import uuid
import zipfile
from collections import deque
from pathlib import Path

from ..agent.loop import Agent, Job
from ..agent.state import JobState


def short_title(goal, limit=70):
    line = goal.strip().split("\n")[0]
    if len(line) <= limit:
        return line
    cut = line[:limit].rsplit(" ", 1)[0].rstrip(",.;:")
    return cut + "..."


class JobManager:
    def __init__(self, home, runner_factory, sandbox_factory, registry=None, log=print):
        self.dir = Path(home) / "jobs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.runner_factory, self.sandbox_factory, self.registry, self.log = runner_factory, sandbox_factory, registry, log
        self.runner = None
        self.queue, self.lock, self.wake = deque(), threading.Lock(), threading.Event()
        self.meta_lock = threading.Lock()
        self.current, self.current_job, self.stopping = None, None, False
        for meta in sorted(self.all(), key=lambda m: m["created"]):
            replied = meta["status"] == "waiting_input" and any(
                t["status"] == "pending" and t.get("owner_inputs") for t in JobState(self._path(meta["id"]) / "workspace").plan())
            if meta["status"] in ("queued", "running") or replied:
                self.queue.append(meta["id"])
                self._meta(meta["id"], status="queued", note="resumed after a restart")
        self.memory = None                              # created on the first job (default: <home>/memory/knowledge.db)
        from . import sysinfo
        self.online_check = sysinfo.online              # replaceable in tests
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    # ---- records ---------------------------------------------------------------------------------------
    def _path(self, jid):
        p = (self.dir / jid).resolve()
        if p.parent != self.dir.resolve() or not p.exists():
            raise KeyError(jid)
        return p

    def _meta(self, jid, **fields):
        f = self._path(jid) / "meta.json"
        with self.meta_lock:
            m = json.loads(f.read_text())
            m.update(fields, updated=time.time())
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps(m, indent=1))
            tmp.replace(f)
        return m

    def meta(self, jid):
        directory = self._path(jid)
        meta = json.loads((directory / "meta.json").read_text())
        report = meta.get("report") or {}
        # Older reports promoted a delivered answer even when the saved step explicitly said unverified.
        if report.get("kind") == "answer" and report.get("verdict") == "VERIFIED":
            plan = JobState(directory / "workspace").plan()
            if any(t.get("verification") == "unverified" for t in plan):
                report["verdict"] = "UNVERIFIED"
        return meta

    def all(self):
        out = []
        for d in self.dir.iterdir():
            if (d / "meta.json").exists():
                try:
                    out.append(self.meta(d.name))
                except ValueError:
                    pass
        return sorted(out, key=lambda m: -m["created"])

    # ---- lifecycle ---------------------------------------------------------------------------------------
    def create(self, goal):
        jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        ws = self.dir / jid
        (ws / "workspace").mkdir(parents=True)
        (ws / "meta.json").write_text(json.dumps({"id": jid, "goal": goal, "title": short_title(goal), "status": "draft",
                                                  "created": time.time(), "updated": time.time(), "files": []}))
        return jid

    def follow_up(self, jid, text):
        """A follow-up in the same conversation: a new job that starts with the earlier job's files and knows
        what was asked before. The earlier job is left as it was."""
        try:
            old = self.meta(jid)
        except OSError:
            raise KeyError(jid) from None
        thread = self.conversation(jid)
        before = "\n".join(f"- {j['goal'][:400]}" for j in thread)
        goal = f"{text.strip()}\n\nEarlier requests in this conversation (their files are in this folder):\n{before}"
        new = self.create(goal)
        src, dst = self._path(jid) / "workspace", self._path(new) / "workspace"
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".neuron", "__pycache__", "data.db*"))
        self._meta(new, title=short_title(text), parent=jid, thread=old.get("thread") or jid, request=text.strip())
        return new

    def conversation(self, jid):
        """Every job in the same conversation as jid, oldest first."""
        root = self.meta(jid).get("thread") or jid
        return sorted((m for m in self.all() if m["id"] == root or m.get("thread") == root), key=lambda m: m["created"])

    def add_file(self, jid, name, data, max_bytes=200 * 1024 * 1024):
        name = Path(name).name
        if not name or len(data) > max_bytes:
            raise ValueError("bad file")
        ws = self._path(jid) / "workspace"
        if name.lower().endswith(".zip"):                           # a project: unpack it as the workspace
            tmp = self._path(jid) / name
            tmp.write_bytes(data)
            with zipfile.ZipFile(tmp) as z:
                members = z.namelist()
                root = members[0].split("/")[0] + "/" if members and all(m.startswith(members[0].split("/")[0] + "/") for m in members) else ""
                for m in members:
                    rel = m[len(root):]
                    target = (ws / rel).resolve()
                    if not rel or not str(target).startswith(str(ws.resolve()) + "/"):
                        continue                                    # no escaping the workspace
                    if m.endswith("/"):
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(z.read(m))
            tmp.unlink()
            kind = "project"
        else:
            (ws / "inputs").mkdir(exist_ok=True)
            (ws / "inputs" / name).write_bytes(data)
            kind = "file"
        m = self.meta(jid)
        self._meta(jid, files=m["files"] + [{"name": name, "kind": kind, "bytes": len(data)}])

    def start(self, jid):
        with self.lock:
            status = self.meta(jid)["status"]
            if status == "waiting_input" or (self.current == jid and status in ("running", "queued")):
                return
            self._enqueue(jid)

    def _enqueue(self, jid):
        """Called under the queue lock, including when the previous run is just leaving the worker."""
        if jid not in self.queue:
            self.queue.append(jid)
        self._meta(jid, status="queued")
        self.wake.set()

    def submit_input(self, jid, prompt_id, answer):
        if not isinstance(prompt_id, str) or not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 1200:
            raise ValueError("Enter a reply of 1 to 1200 characters.")
        with self.lock:
            st = JobState(self._path(jid) / "workspace")
            waiting = self.meta(jid)["status"] == "waiting_input"
            if st.answer_input(prompt_id, answer.strip(), accept_new=waiting):
                self._enqueue(jid)

    def stop(self, jid):
        with self.lock:
            if self.meta(jid)["status"] == "waiting_input":
                return
            if self.current == jid and self.current_job is not None:
                self.current_job.stop_requested = True
            if jid in self.queue:
                self.queue.remove(jid)
            self._meta(jid, status="paused", note="stopped by the owner")

    def approve(self, jid, task, action, yes):
        st = JobState(self._path(jid) / "workspace")
        st.answer_approval(task, action, yes)
        st.update_task(task, status="pending")
        self.start(jid)

    def _work(self):
        while not self.stopping:
            with self.lock:
                jid = self.queue.popleft() if self.queue else None
                self.current = jid
            if jid is None:
                self._resume_waiting()
                self._maintain()
                self.wake.wait(1.0)
                self.wake.clear()
                continue
            try:
                self._run(jid)
            except Exception as e:                                  # a job's failure must not stop the machine
                self._meta(jid, status="failed", error=f"{type(e).__name__}: {e}"[:400])
            finally:
                with self.lock:
                    self.current, self.current_job = None, None

    def _resume_waiting(self, every=30):
        """Jobs that stopped only because they needed the internet start again by themselves once it is back."""
        if time.time() - getattr(self, "_net_checked", 0) < every:
            return
        self._net_checked = time.time()
        waiting = [m["id"] for m in self.all() if m.get("status") == "waiting_network"
                   and (m.get("report") or {}).get("retry_at", 0) <= time.time()]          # a service asked us to wait: respect it
        if waiting and self.online_check():
            for jid in waiting:
                self.log(f"[{jid}] the internet is back: resuming")
                self.start(jid)

    def _run(self, jid):
        m = self._meta(jid, status="running", started=time.time())
        ws = self._path(jid) / "workspace"
        attachments = [str(p) for p in sorted((ws / "inputs").glob("*"))] if (ws / "inputs").exists() else []
        if self.runner is None:
            self.runner = self.runner_factory()
        if hasattr(self.runner, "boost"):
            self.runner.boost.new_job()
        self._open_memory()
        job = Job(ws, self.runner, self.sandbox_factory(), registry=self.registry, log=lambda msg: self.log(f"[{jid}] {msg}"),
                  memory=self.memory or None)
        job.online = self.online_check()
        self.current_job = job
        rep = Agent(job).run(m["goal"], attachments)
        status = "waiting_approval" if rep.get("waiting_approval") else ("paused" if getattr(job, "stop_requested", False)
                  else "waiting_network" if rep.get("waiting_network")
                  else {"VERIFIED": "done", "UNVERIFIED": "done", "WAITING_INPUT": "waiting_input",
                        "PARTIAL": "partial", "FAILED": "failed"}[rep["verdict"]])
        self._meta(jid, status=status, report=rep, finished=time.time())

    def _open_memory(self):
        if self.memory is None:
            from ..memory import Memory, memory_enabled
            try:
                self.memory = Memory(self.dir.parent / "memory" / "knowledge.db") if memory_enabled() else False
            except Exception as e:                       # noqa: BLE001  NEURON works without memory
                self.log(f"knowledge memory unavailable: {e}")
                self.memory = False

    def _maintain(self, every=86400):
        """Once a day, when idle and online: recheck old memory notes, and keep finished projects' packages current
        (isolated copy, the project's tests, swap in only what passes, backup kept). Results go into the job's record."""
        if not hasattr(self, "_maintained"):
            self._maintained = time.time() - every + 600                # first pass ten minutes after NEURON starts
        if self.queue or self.current or time.time() - self._maintained < every:
            return
        self._maintained = time.time()
        if not self.online_check():
            self._maintained = time.time() - every + 1800           # offline: try again in half an hour
            return
        self._open_memory()
        if self.memory:
            from ..memory.recheck import recheck
            r = recheck(self.memory, log=self.log)
            if r["checked"]:
                self.log(f"memory recheck: {r}")
        from ..online import packages
        from ..agent.capabilities.workspace import detect_test_command
        from ..agent.effects import Effects
        for meta in self.all():
            if self.queue or self.stopping:                         # the owner asked for something: that comes first
                return
            ws = self._path(meta["id"]) / "workspace"
            if meta.get("status") not in ("done", "partial") or not packages.pins(ws):
                continue
            try:
                rep = packages.upgrade(ws, self.sandbox_factory(), detect_test_command(ws),
                                       effects=Effects(ws / ".neuron" / "job" / "effects.jsonl"), log=self.log)
                self._meta(meta["id"], maintenance={"at": time.time(), "summary": rep["summary"],
                                                    "upgraded": rep["upgraded"], "kept_back": rep["kept_back"]})
                if self.memory:
                    for n in packages.memory_notes(rep):
                        self.memory.add(n["kind"], n["text"], n["source"], version=n["version"], verified=True, tags=n["tags"])
            except Exception as e:                                  # noqa: BLE001  maintenance never breaks NEURON
                self.log(f"[{meta['id']}] package check failed: {type(e).__name__}: {e}")

    # ---- views for the phone -----------------------------------------------------------------------------
    def detail(self, jid):
        m = self.meta(jid)
        st = JobState(self._path(jid) / "workspace")
        tasks = st.plan()
        prompt = next((t["input_request"] for t in tasks if t["status"] == "waiting_input"), None)
        asking = m["status"] == "waiting_input" and prompt is not None
        history = [{"question": turn["question"], "answer": turn["answer"]} for t in tasks for turn in t.get("owner_inputs", [])]
        hide_answer = any(t.get("capability") == "answer_question" and t["status"] != "done" for t in tasks)
        plan = [{"id": t["id"], "title": t["title"], "status": t["status"], "summary": t.get("summary", ""), "made_by": t.get("made_by"),
                 "verification": t.get("verification"), "tries": len(t.get("attempts", [])), "gaps": t.get("gaps", []),
                 "last_failure": (t["attempts"][-1].get("failure") if t.get("attempts") and not t["attempts"][-1].get("passed") else "")}
                for t in tasks]
        evidence = st.lines("evidence.jsonl")[-12:] if st.exists() else []
        progress = st.progress() if st.exists() else {}
        if (m.get("report") or {}).get("verdict") == "UNVERIFIED":
            progress["verdict"] = "UNVERIFIED"
        return {**m, "kind": st.goal().get("kind") if st.exists() else None, "plan": plan, "progress": progress,
                "input_request": {k: prompt[k] for k in ("id", "question")} if asking else None, "owner_inputs": history,
                "approvals": [a for a in st.approvals() if a["status"] == "pending"] if st.exists() else [],
                "evidence": [{"task": e["task"], "passed": e["passed"], "how": e["how"],
                              "checks": [{"id": c["id"], "pass": c["pass"], "detail": str(c["detail"])[:160]} for c in e["checks"][:12]]} for e in evidence],
                "outputs": [o for o in self.outputs(jid) if not hide_answer or o["path"] not in ("answer.md", "answers.md")],
                "answer": "" if hide_answer else self._answer(jid),
                "thread": [{"id": t["id"], "said": t.get("request") or t["goal"], "status": t["status"],
                            "verdict": (t.get("report") or {}).get("verdict")} for t in self.conversation(jid)]}

    def _answer(self, jid):
        """A written answer (questions, document questions) is shown on the phone directly, like a chat reply."""
        for name in ("answer.md", "answers.md"):
            f = self._path(jid) / "workspace" / name
            if f.exists():
                return f.read_text(errors="replace")[:8000]
        return ""

    def events(self, jid, after=0):
        st = JobState(self._path(jid) / "workspace")
        ev = []
        for name, kind in (("journal.jsonl", "session"), ("decisions.jsonl", "decision"), ("evidence.jsonl", "check")):
            for e in st.lines(name):
                text = e.get("text") or e.get("event", "")
                if kind == "check":
                    label = "answer delivered" if e.get("how") == "unverified" else "verified"
                    text = f"{e.get('task')}: {label if e.get('passed') else 'check failed'} ({e.get('how')})"
                ev.append({"at": e["at"], "kind": kind, "text": str(text)[:300]})
        ev.sort(key=lambda e: e["at"])
        return [dict(e, seq=i) for i, e in enumerate(ev, 1) if i > after]

    def outputs(self, jid):
        ws = self._path(jid) / "workspace"
        out = []
        for p in sorted(ws.rglob("*")):
            rel = p.relative_to(ws)
            if p.is_file() and rel.parts[0] != "inputs" and ".neuron" not in rel.parts and "kit" not in rel.parts and "__pycache__" not in rel.parts \
                    and not rel.name.startswith("data.db") and p.stat().st_size < 50 * 1024 * 1024:
                out.append({"path": str(rel), "bytes": p.stat().st_size})
        return out[:200]

    def file(self, jid, rel):
        ws = (self._path(jid) / "workspace").resolve()
        p = (ws / rel).resolve()
        if not str(p).startswith(str(ws) + "/") or not p.is_file():
            raise KeyError(rel)
        return p
