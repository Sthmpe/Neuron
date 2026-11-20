"""Paired Phase 3 experiment. All generated PDFs, job homes and databases are disposable."""
import argparse
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_answers import conditions, file_hash


def make_pdf(path, line):
    from reportlab.pdfgen.canvas import Canvas
    doc = Canvas(str(path), invariant=1)
    doc.setFont("Helvetica", 10)
    doc.drawString(35, 760, line)
    doc.save()


class FixedClaim:
    """Replay a specified claim at the model boundary, including any retries."""
    def __init__(self, claim):
        self.claim = claim

    def client(self, role):
        return self

    def model_for(self, role):
        return "controlled-claim"

    def chat(self, messages, **kwargs):
        return SimpleNamespace(text=json.dumps(self.claim), model="controlled-claim", completion_tokens=0, seconds=0)


def content_matches(value, answer):
    if value is None:
        return bool(re.search(r"not found|not (?:given|stated|specified|provided)|no (?:count|information)|unknown|does not|cannot", answer, re.I))
    return bool(re.search(r"(?<![\w.])" + re.escape(value) + r"(?!\w|\.\d)", answer, re.I))


def document(root, case, runner, sandbox, proposed=None):
    from neuron.agent.loop import Agent, Job
    from neuron.memory import Memory
    from neuron.memory.embed import HashEmbedder
    root.mkdir()
    pdf = root / (case["id"] + ".pdf")
    make_pdf(pdf, case["page"])
    memory = Memory(root / "memory/knowledge.db", embedder=HashEmbedder())
    ws = root / "jobs/development/workspace"
    if proposed is not None:
        runner = FixedClaim({"answer": proposed, "quote": case["page"], "doc": case["id"], "page": 1})
    try:
        job = Job(ws, runner, sandbox, memory=memory, log=lambda _: None)
        report = Agent(job).run(case["question"], [str(pdf)])
        saved = json.loads((ws / "answers.json").read_text())[0]
        notes = [dict(n) for n in memory.db.execute("SELECT text,source,status FROM notes")]
        recalled = [n["text"] for n in memory.search(case["question"]) if n["status"] == "verified"]
        correct = content_matches(case["value"], saved["answer"])
        should_verify = proposed == case["answer"] if proposed is not None else case["value"] is not None
        safe = not saved["verified"] and not recalled and all(n["status"] != "verified" for n in notes)
        passed = bool(saved["verified"] and correct and recalled) if should_verify else safe and (proposed is not None or correct)
        return {"id": case["id"], "proposed": proposed, "answer": saved, "verdict": report["verdict"], "notes": notes,
                "verified_recall": recalled, "correct_content": correct, "pass": passed, "usage": report["usage_all_sessions"]}
    finally:
        memory.db.close()


def sandbox_with_record():
    from neuron.brain.sandbox import Sandbox
    class RecordingSandbox(Sandbox):
        def __init__(self):
            super().__init__(timeout=60, mem_mb=512)
            self.runs = []

        def run(self, argv, work, **kwargs):
            r = super().run(argv, work, **kwargs)
            self.runs.append({"output": r.output[:2000], "exit": r.exit_code, "timeout": r.timed_out, "oom": r.oom_killed})
            return r
    return RecordingSandbox()


def calculation(root, case, runner):
    from neuron.agent.loop import Agent, Job
    sandbox = sandbox_with_record()
    job = Job(root, runner, sandbox, log=lambda _: None)
    report = Agent(job).run(case["question"])
    answer = job.state.task("answer").get("result", {}).get("answer", "")
    return {"id": case["id"], "answer": answer, "verdict": report["verdict"], "runs": sandbox.runs,
            "pass": content_matches(case["answer"], answer), "usage": report["usage_all_sessions"]}


def replay(case):
    from neuron.agent.thinking import solve
    messages = []
    def chat(msgs, n):
        if len(msgs) == 2 and messages:
            text = "Answer: " + case["review"]
        elif not messages and "code" in case:
            text = "```python\n" + case["code"] + "\n```" + ("\nAnswer: " + case["inline"] if "inline" in case else "")
        else:
            text = "Answer: " + case["draft"]
        messages.append(text)
        return SimpleNamespace(text=text, completion_tokens=0)
    sandbox = sandbox_with_record()
    result = solve(chat, sandbox, "Return the requested calculation.")
    return {"id": case["id"], "answer": result["answer"], "runs": sandbox.runs, "model_replies": messages,
            "pass": result["answer"] == case["expect"]}


def migration(home, cases):
    from neuron.memory import Memory
    from neuron.memory.embed import HashEmbedder
    embedder = HashEmbedder()
    path = home / "memory/knowledge.db"
    path.parent.mkdir(parents=True)
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE notes(id INTEGER PRIMARY KEY, kind TEXT, text TEXT, source TEXT, created REAL,
      version TEXT, status TEXT, tags TEXT, meta TEXT, vector TEXT, embedder TEXT, uses INTEGER DEFAULT 0,
      helped INTEGER DEFAULT 0, last_checked REAL);
    CREATE VIRTUAL TABLE notes_fts USING fts5(text,tags,content='notes',content_rowid='id');
    """)
    expected = {}
    def insert(kind, text, source, want, tag=""):
        vec = json.dumps(embedder.embed([text])[0])
        row = db.execute("INSERT INTO notes(kind,text,source,created,version,status,tags,meta,vector,embedder,last_checked)"
                         " VALUES(?,?,?,1,'','verified',?,'{}',?,?,1)", (kind,text,source,tag,vec,embedder.name)).lastrowid
        db.execute("INSERT INTO notes_fts(rowid,text,tags) VALUES(?,?,?)", (row,text,tag))
        expected[row] = (text, want)
    for c in cases:
        for claim in [a for a in (c["answer"],c["wrong"]) if a]:
            ws = home / "jobs" / str(len(expected)) / "workspace"
            index = ws / ".neuron/job/index.json"
            index.parent.mkdir(parents=True)
            index.write_text(json.dumps([{"doc": c["id"], "page":1, "text":c["page"]}]))
            a = {"question": c["question"], "answer":claim, "doc":c["id"], "page":1, "quote":c["page"], "verified":True}
            (ws/"answers.json").write_text(json.dumps([a]))
            insert("finding", f'{c["question"]} {claim} (quote: "{c["page"]}")', c["id"]+" page 1",claim==c["answer"],c["id"])
    insert("finding",'What is the pool depth? 90 m (quote: "The pool depth is 90 m.")',"lost page 4",False)
    insert("fix","A reversed range bound in the batch counter was corrected.","job range: batch.py",True)
    db.commit()
    db.close()
    snapshots = []
    for _ in range(2):
        memory = Memory(path, embedder=embedder)
        try:
            rows = []
            for nid,(text,want) in expected.items():
                row = memory.db.execute("SELECT status FROM notes WHERE id=?", (nid,)).fetchone()
                hits = {h["id"] for h in memory.search(text, k=50)}
                status = row["status"] if row else None
                rows.append({"id":nid,"text":text,"status":status,"recalled":nid in hits,"wanted":want,
                             "pass":bool(row) and (status=="verified" and nid in hits if want else status!="verified" and nid not in hits)})
            snapshots.append(rows)
        finally:
            memory.db.close()
    return {"opens":snapshots, "passes":sum(a["pass"] and b["pass"] for a,b in zip(*snapshots))}


def serve_child(args):
    from neuron.brain.models import ModelManager, ModelRunner
    from neuron.brain.sandbox import Sandbox
    from neuron.server.app import serve
    h = args.home
    runner = ModelRunner(ModelManager(h.parent/"models"), "2gb", threads=1, log_dir=h.parent)
    server = serve(h, "127.0.0.1", args.port, lambda:runner, lambda:Sandbox(), log=lambda _:None)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    boot = h.parent/"ready.json"
    tmp = boot.with_suffix(".tmp")
    tmp.write_text(json.dumps({"port":server.server_port,"code":server.neuron["pairing"].new_code()}))
    tmp.replace(boot)
    try:
        stop.wait()
    finally:
        jobs = server.neuron["jobs"]
        jobs.stopping = True
        jobs.wake.set()
        server.shutdown()
        server.server_close()
        thread.join()
        jobs.thread.join()
        runner.unload()


@contextmanager
def service(args, home, port=0):
    ready = home.parent/"ready.json"
    ready.unlink(missing_ok=True)
    proc = subprocess.Popen([sys.executable,__file__,"--source",str(args.source),"--home",str(home),"--port",str(port)])
    try:
        end = time.monotonic()+60
        while not ready.exists():
            if proc.poll() is not None or time.monotonic()>end:
                raise RuntimeError("phone server failed to start")
            time.sleep(.1)
        yield proc.pid,json.loads(ready.read_text())
    finally:
        proc.terminate()
        proc.wait(timeout=60)


def delayed(args, home, case):
    from benchmark.release.retest import Phone
    polls = []
    def call(method, path, body=None):
        status, data = phone.call(method,path,body)
        if not 200<=status<300:
            raise RuntimeError(f"phone call returned {status} for {path}")
        return data
    def wait(statuses):
        end = time.monotonic()+180
        while time.monotonic()<end:
            d = call("GET",url)
            if d["status"] in statuses:
                return d
            time.sleep(.2)
        raise TimeoutError("job did not reach requested state")
    def observe(seconds, pid):
        start = time.monotonic()
        while True:
            d = call("GET",url)
            ui = d.get("input_request") or {}
            polls.append({"pid":pid,"t":round(time.monotonic()-began,3),"job":d["id"],"prompt":ui.get("id"),
                          "status":d["status"],"tries":d["plan"][0]["tries"],"answer":d["answer"]})
            left = seconds - (time.monotonic()-start)
            if left<=0:
                return round(time.monotonic()-start,3)
            time.sleep(min(1,left))
    with service(args,home) as (first,auth):
        phone = Phone("http://127.0.0.1:"+str(auth["port"]))
        call("POST","/api/pair",{"code":auth["code"]})
        jid = call("POST","/api/jobs",{"goal":case["goal"]})["id"]
        url = "/api/jobs/"+jid
        call("POST",url+"/start")
        d = wait({"waiting_input","failed","done"})
        if d["status"]!="waiting_input":
            return {"id":jid,"status":d["status"],"answer":d["answer"],"pass":False}
        prompt = d["input_request"]
        began = time.monotonic()
        before = observe(case["wait_before_restart_s"],first)
    with service(args,home,auth["port"]) as (second,_):
        after = observe(case["wait_after_restart_s"],second)
        submitted = time.monotonic()-began
        call("POST",url+"/input",{"id":prompt["id"],"answer":case["owner"]})
        d = wait({"done","failed","partial","waiting_input"})
        passed = all(p["status"]=="waiting_input" and p["prompt"]==prompt["id"] and p["job"]==jid and not p["answer"]
                     and p["tries"]==0 for p in polls)
        passed = passed and d["id"]==jid and first!=second and d["status"]=="done" and content_matches(case["expect"],d["answer"].splitlines()[0])
        return {"pass":passed,"id":jid,"question":prompt["question"],"owner":case["owner"],"pids":[first,second],
                "observed_delays":[before,after],"reply_after_seconds":round(submitted,3),"polls":polls,
                "status":d["status"],"answer":d["answer"],"usage":d["report"]["usage_all_sessions"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path,required=True)
    ap.add_argument("--home",type=Path)
    ap.add_argument("--port",type=int,default=0)
    ap.add_argument("--model",type=Path)
    ap.add_argument("--label")
    ap.add_argument("--output",type=Path)
    args = ap.parse_args()
    sys.path.insert(0,str(args.source.resolve()))
    if args.home:
        return serve_child(args)
    from neuron.brain.models import ModelManager, ModelRunner
    from neuron.brain.sandbox import Sandbox
    group, env = conditions()
    os.environ["NEURON_MEMORY"]="on"
    fixture = Path(__file__).with_name("cases.json")
    cases = json.loads(fixture.read_text())
    f = json.loads((args.source/"model_manifests/frozen.json").read_text())["tiers"]["2gb"]
    if file_hash(args.model)!=f["sha256"]:
        raise ValueError("incorrect weights")
    result = {"label":args.label,"revision":(args.source/"REVISION").read_text().strip(),"environment":env,
              "model":f["id"],"model_sha256":f["sha256"],"binary_sha256":file_hash(Path(os.environ["NEURON_LLAMA_BIN"])),
              "fixture_sha256":file_hash(fixture),"driver_sha256":file_hash(Path(__file__)),"threads":1,"seed":71,"context":f["context_tokens"]}
    with args.output.open("x") as output,args.output.with_suffix(".jsonl").open("x") as journal,tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        def record(group_name, fn, *params):
            start = time.monotonic()
            row = fn(*params)
            row["seconds"] = round(time.monotonic()-start,3)
            result.setdefault(group_name,[]).append(row)
            journal.write(json.dumps({group_name:row})+"\n")
            journal.flush()
            os.fsync(journal.fileno())
            print(group_name,row.get("id",""),row.get("pass",row.get("passes")),row["seconds"],flush=True)
        mgr = ModelManager(root/"models")
        (mgr.store/f["file"]).symlink_to(args.model.resolve())
        mgr.install({**f,"request_extra":{**f["request_extra"],"seed":71}},verify=False)
        mgr.activate("2gb",f["id"])
        runner = ModelRunner(mgr,"2gb",threads=1,log_dir=root)
        start = time.monotonic()
        try:
            runner.client("builder")
            for c in cases["documents"]:
                record("documents",document,root/("natural-"+c["id"]),c,runner,Sandbox())
            for c in cases["calculations"]:
                record("calculations",calculation,root/c["id"],c,runner)
        finally:
            runner.unload()
        for c in cases["documents"]:
            for key in ("answer","wrong"):
                if c[key]:
                    record("claims",document,root/(key+"-"+c["id"]),c,None,Sandbox(),c[key])
        for c in cases["calculator_replays"]:
            record("calculator_replays",replay,c)
        record("migration",migration,root/"old",cases["documents"])
        record("delayed_phone",delayed,args,root/"phone",cases["delayed_phone"])
        result.update(seconds=round(time.monotonic()-start,3),peak_bytes=int((group/"memory.peak").read_text()),
                      memory_events=(group/"memory.events").read_text().splitlines())
        json.dump(result,output,indent=2)
        output.write("\n")
        print("Completed",args.label,result["seconds"],result["peak_bytes"],flush=True)


if __name__=="__main__":
    main()
