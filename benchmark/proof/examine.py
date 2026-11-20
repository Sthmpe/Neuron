"""Core-proof examiners. Only the delivered folder and the running app count; what the agent says is recorded elsewhere.

  examine(task, delivered_folder, out_dir) -> {"checks": [...], "passed": n, "total": n, "solved": bool}
Apps: started from an empty database (data.db removed) in the sandbox and used in a real browser like a person
(app_exam.js), then restarted to check the data survived. Code: the ORIGINAL tests are put back over whatever the agent
did to them, then the project's tests and the HIDDEN tests run in the sandbox. Documents: eval2's examiner functions.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks"
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark" / "eval2" / "examiners"))
import docs as eval2_docs        # noqa: E402  (eval2's locked examiner functions, imported, never modified)


def _result(checks):
    passed = sum(bool(c["pass"]) for c in checks)
    return {"checks": checks, "passed": passed, "total": len(checks), "solved": bool(checks) and passed == len(checks)}


def _sandbox(**kw):
    from neuron.brain.sandbox import Sandbox
    return Sandbox(**kw)


# ---- apps -------------------------------------------------------------------------------------------------------
def examine_app(task, delivered, out_dir):
    d = Path(delivered)
    app = d / "app" if (d / "app" / "app.py").exists() else d
    if not (app / "app.py").exists():
        return _result([{"id": "app_delivered", "pass": False, "detail": "no app.py"}])
    work = Path(tempfile.mkdtemp(prefix="proof-app-")) / "app"
    shutil.copytree(app, work, ignore=shutil.ignore_patterns(".neuron", "__pycache__", "data.db*", "node_modules"))
    spec_file = TASKS / task["spec"]
    spec = json.loads(spec_file.read_text())
    sbx = _sandbox(timeout=1200, mem_mb=256)
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    checks = []
    for phase in ("1", "2"):
        if phase == "2" and not spec.get("after_restart"):
            break
        srv = sbx.start(["python3", "app.py"], work)
        if not srv.wait_ready("/"):
            srv.stop()
            checks.append({"id": f"app_runs_phase_{phase}", "pass": False, "detail": "the app did not answer on port 8000"})
            continue
        try:
            out = subprocess.run(["node", str(HERE / "app_exam.js"), srv.url, phase, str(out_dir), str(spec_file)],
                                 capture_output=True, text=True, env=env, timeout=900).stdout
            checks += json.loads(out.strip().splitlines()[-1])["checks"]
        except Exception as e:      # noqa: BLE001
            checks.append({"id": f"examiner_phase_{phase}", "pass": False, "detail": type(e).__name__})
        srv.stop()
    shutil.rmtree(work.parent, ignore_errors=True)
    return _result(checks)


# ---- code -------------------------------------------------------------------------------------------------------
def examine_code(task, delivered):
    d = Path(delivered)
    if not d.exists():
        return _result([{"id": "project_delivered", "pass": False, "detail": "nothing delivered"}])
    work = Path(tempfile.mkdtemp(prefix="proof-code-")) / "p"
    shutil.copytree(d, work, ignore=shutil.ignore_patterns(".neuron", "__pycache__", "node_modules", "tests/run"))
    original = TASKS / task["workspace"]
    for rel in task["original_tests"]:                    # the agent's own edits to the tests never count
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(original / rel, work / rel)
    for f in (TASKS / task["hidden"]).rglob("*"):
        if f.is_file():
            dest = work / f.relative_to(TASKS / task["hidden"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, dest)
    sbx = _sandbox(timeout=600, mem_mb=1024, toolchains=True)
    r1 = sbx.run(task["test_cmd"], work, timeout=600)
    r2 = sbx.run(task["hidden_cmd"], work, timeout=600)
    shutil.rmtree(work.parent, ignore_errors=True)
    return _result([{"id": "original_tests_pass", "pass": r1.ok and not r1.timed_out, "detail": r1.output[-300:]},
                    {"id": "hidden_tests_pass", "pass": r2.ok and not r2.timed_out, "detail": r2.output[-300:]}])


# ---- documents --------------------------------------------------------------------------------------------------
def answers_from(folder, n):
    f = Path(folder)
    if (f / "answers.json").exists():
        try:
            data = json.loads((f / "answers.json").read_text())
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return [f"{a.get('answer', '')} ({a.get('doc', '')}, page {a.get('page', '')})" for a in data]
        except ValueError:
            pass
    text = (f / "answers.md").read_text(errors="replace") if (f / "answers.md").exists() else ""
    items = re.split(r"(?m)^\s*(?:\*\*)?(\d+)[.)]\s*", text)
    out = {}
    for i in range(1, len(items) - 1, 2):
        out.setdefault(int(items[i]), " ".join(items[i + 1].split()))
    return [out.get(k, "") for k in range(1, n + 1)]


def examine_document(task, delivered):
    d = Path(delivered)
    if task["kind"] == "pdf_qa":
        t = {"inputs": task["inputs"], "questions": task["questions"]}
        return _result(eval2_docs.pdf_qa(answers_from(d, len(task["questions"])), t, TASKS / "sources")["checks"])
    path = d / task["output"]
    if task["kind"] == "excel_products":
        r = eval2_docs.excel_products(path, TASKS / task["inputs"][0], *task["args"])
    elif task["kind"] == "excel_simple":
        r = eval2_docs.excel_simple(path, TASKS / task["inputs"][0], *task["args"])
    elif task["kind"] == "word":
        w = task["word"]
        r = eval2_docs.word(path, w["headings"], table=w["table"], words=tuple(w["words"]))
    else:
        p = task["pptx"]
        r = eval2_docs.pptx(path, p["slides"], must_contain=p["must_contain"], max_bullets=p["max_bullets"])
    return _result(r["checks"])


def examine(task, delivered, out_dir=None):
    out_dir = out_dir or Path(tempfile.mkdtemp(prefix="proof-shots-"))
    if task["category"] == "app":
        return examine_app(task, delivered, out_dir)
    if task["category"] in ("bug", "feature"):
        return examine_code(task, delivered)
    return examine_document(task, delivered)
