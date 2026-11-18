"""Phase-5 evaluation runner: NEURON's general agent on the dev or the LOCKED tasks, offline, inside a RAM tier.

  python3 -m benchmark.phase5.run --set dev --tier 4gb [--only D02_excel_expenses] [--tag try1]
  python3 -m benchmark.phase5.run --set locked --tier 8gb        # refuses unless LOCK.json still matches

For every task:
  * a fresh job folder gets the task's inputs (and, for workspace tasks, a copy of the project)
  * the agent runs as its own process (python3 -m neuron.agent ...) with the network cut and the whole
    run counted against the tier's memory limit; tasks marked kill_and_resume are killed with SIGKILL
    once about half their work is done, then the same command is run again and must resume
  * an independent examiner checks only the delivered files or the running app; what the agent says
    about its own work is recorded separately, so false claims show up
Reported per task: solved (every examiner check passed), checks passed/total, time, peak memory of
everything, model calls and tokens (all sessions), human help needed, recovery after the kill,
who made the result (model, template, plain code) and the agent's own verdict.
Results: benchmark/results/phase5/<set>-<tier>[-tag].json. Re-running skips tasks already recorded.
"""
import argparse
import ast
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.phase5.examine import examine                 # noqa: E402
from benchmark.run_benchmark import cut_network               # noqa: E402
from neuron.brain.tiers import Tier                           # noqa: E402

MB = 2 ** 20
TASK_SECONDS = {"web_app": 5400, "long_task": 5400}           # everything else: DEFAULT_SECONDS
DEFAULT_SECONDS = 2400
BUG_REQUEST = ("The tests of this project fail. Find the bug in the source code and fix it so the tests pass. "
               "Do not change the tests.")                    # fixed before any locked run; the same for every bug task


def load_tasks(which):
    if which == "locked":
        r = subprocess.run([sys.executable, str(HERE / "verify_lock.py")], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("REFUSED: the locked tasks or examiners changed since they were locked:\n" + r.stdout + r.stderr)
    return json.loads((HERE / which / "tasks.json").read_text()), HERE / which


def goal_of(task, base):
    if task["kind"] == "web_app" and task.get("reuse"):
        return json.loads((HERE / task["reuse"]).resolve().read_text())["request"]
    if task["kind"] == "workspace_bug":
        return BUG_REQUEST
    text = task["request"]
    if task.get("questions"):
        text += "\n" + "\n".join(f"{i}. {q['q']}" for i, q in enumerate(task["questions"], 1))
    return text


def prepare(task, base, job):
    shutil.rmtree(job, ignore_errors=True)
    job.mkdir(parents=True)
    attach = [str(HERE / rel) for rel in task.get("inputs", [])]
    if task["kind"] == "workspace_bug":
        src = HERE / "workspace_tasks" / f"{task['workspace']}_bug{task['bug']}"
        shutil.copytree(src, job, dirs_exist_ok=True)
    elif task.get("workspace"):
        shutil.copytree((HERE / task["workspace"]).resolve(), job, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".neuron"))
    return attach


def undocumented(folder):
    """How many functions in non-test Python files have no docstring (one-line defs excluded, as the tool skips them)."""
    n = 0
    for f in Path(folder).rglob("*.py"):
        rel = f.relative_to(folder)
        if rel.parts[0] in ("tests", "test", ".neuron") or rel.name.startswith("test_"):
            continue
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not ast.get_docstring(node) and node.body[0].lineno != node.lineno:
                n += 1
    return n


def half_done(task, job, total_docs):
    """True once about half the task's work is saved (the moment a kill_and_resume task is killed)."""
    if task["kind"] == "web_app":
        f = job / "app" / ".neuron" / "tasks.json"
        try:
            ts = json.loads(f.read_text())
            return len(ts) >= 2 and sum(t["status"] == "done" for t in ts) >= len(ts) / 2
        except (OSError, ValueError, KeyError, TypeError):
            return False
    if task["kind"] == "long_task":
        f = job / ".neuron" / "job" / "documented.json"
        try:
            return total_docs > 0 and len(json.loads(f.read_text())) >= total_docs / 2
        except (OSError, ValueError):
            return False
    return False


def run_agent(goal, job, attach, tier_name, seconds, log_file, kill_when=None):
    cmd = [sys.executable, "-m", "neuron.agent", goal, "--workspace", str(job), "--tier", tier_name, "--max-seconds", str(seconds),
           "--report", str(job / ".neuron" / "final_report.json")]
    if attach:
        cmd += ["--attach"] + attach
    with open(log_file, "a") as log:
        log.write(f"\n===== session started {time.strftime('%H:%M:%S')} =====\n")
        log.flush()
        env = dict(os.environ, NEURON_MEMORY="off")      # evaluations never read or write knowledge memory
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        t0 = time.time()
        while proc.poll() is None:
            if time.time() - t0 > seconds + 900 or (kill_when and kill_when()):
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                log.write(f"\n===== KILLED (SIGKILL) at {time.strftime('%H:%M:%S')} =====\n")
                return "killed", time.time() - t0
            time.sleep(1)
    return "exited", time.time() - t0


def answers_for(job):
    try:
        data = json.loads((job / "answers.json").read_text())
    except (OSError, ValueError):
        return []
    return [f"{a.get('answer', '')} ({str(a.get('doc', '')).replace('_', ' ')}, page {a.get('page', '?')})" for a in data]


def delivered_folder(task, job):
    return job / "app" if task["kind"] == "web_app" else job


def examine_task(task, base, job, shots):
    if task["kind"] == "web_app" and task.get("reuse"):        # dev app task: the step-3 examiner of that build
        from benchmark.examine import examine as build_examine
        from neuron.brain.sandbox import Sandbox
        r = build_examine((HERE / task["reuse"]).resolve(), job / "app", Sandbox(timeout=60, mem_mb=256), shots)
        checks = r["checks"]
        return {"checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks)}
    return examine(task, delivered_folder(task, job), answers=answers_for(job), out_dir=shots)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["dev", "locked"])
    ap.add_argument("--tier", required=True, choices=["2gb", "4gb", "8gb"])
    ap.add_argument("--only")
    ap.add_argument("--tag", default="")
    ap.add_argument("--examine-existing", help="record a row for this task from the folder the agent already delivered, "
                    "without running the agent again (used after an examiner crash)")
    a = ap.parse_args(argv)
    tasks, base = load_tasks(a.set)
    label = f"{a.set}-{a.tier}" + (f"-{a.tag}" if a.tag else "")
    out_file = ROOT / "benchmark" / "results" / "phase5" / f"{label}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(out_file.read_text()) if out_file.exists() else {"rows": []}
    net = cut_network()
    if net["internet_reachable"]:
        sys.exit("The network could not be cut off; refusing to run.")
    scratch = ROOT / "benchmark" / "run" / "phase5" / label
    scratch.mkdir(parents=True, exist_ok=True)
    tier = Tier(a.tier).enter()
    from neuron.brain.models import ModelManager
    mgr = ModelManager()
    results.update(set=a.set, tier=a.tier, tier_limit_mb=round(tier.limit / MB), network=net["method"],
                   model={r: mgr.active(a.tier, r) for r in ("planner", "reviewer", "builder")},
                   bug_request=BUG_REQUEST, started=results.get("started") or time.strftime("%Y-%m-%d %H:%M:%S"),
                   code_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    done = {r["task"] for r in results["rows"]}
    only = set(a.only.split(",")) if a.only else None
    try:
        for task in tasks:
            if task["id"] in done or (only and task["id"] not in only):
                continue
            job = scratch / task["id"]
            if a.examine_existing:
                if task["id"] != a.examine_existing:
                    continue
                rep = json.loads((job / ".neuron" / "final_report.json").read_text()) if (job / ".neuron" / "final_report.json").exists() else {}
                exam = examine_task(task, base, job, scratch / f"{task['id']}__shots")
                usage = rep.get("usage_all_sessions") or {}
                row = {"task": task["id"], "kind": task["kind"], "solved": exam["total"] > 0 and exam["passed"] == exam["total"],
                       "checks_passed": exam["passed"], "checks_total": exam["total"],
                       "failed_checks": [c["id"] + (": " + str(c.get("detail"))[:160] if c.get("detail") else "") for c in exam["checks"] if not c["pass"]],
                       "seconds": rep.get("seconds"), "peak_mb": None, "sessions": "see the task log", "model_calls": usage.get("model_calls"),
                       "tokens": usage.get("tokens"), "model_seconds": usage.get("model_seconds"), "online_calls": usage.get("online_calls", 0),
                       "human_help": {"approvals_asked": len(rep.get("waiting_approval") or []), "manual_steps": 0}, "recovery": None,
                       "made_by": rep.get("made_by"), "agent_verdict": rep.get("verdict", "no report"),
                       "false_claim": rep.get("verdict") == "VERIFIED" and not (exam["total"] > 0 and exam["passed"] == exam["total"]),
                       "note": "examined from the delivered folder after an examiner crash (lock amendment 3); agent not rerun; peak memory not measured"}
                results["rows"].append(row)
                out_file.write_text(json.dumps(results, indent=1))
                print(f"{label} {task['id']}: examined existing delivery: {row['checks_passed']}/{row['checks_total']} | agent says {row['agent_verdict']}", flush=True)
                continue
            attach = prepare(task, base, job)
            goal = goal_of(task, base)
            total_docs = undocumented(job) if task["kind"] == "long_task" else 0
            seconds = TASK_SECONDS.get(task["kind"], DEFAULT_SECONDS)
            log_file = scratch / f"{task['id']}.log"
            tier.reset_peak()
            t0 = time.time()
            sessions = []
            kill = (lambda: half_done(task, job, total_docs)) if task.get("kill_and_resume") else None
            how, took = run_agent(goal, job, attach, a.tier, seconds, log_file, kill_when=kill)
            sessions.append({"ended": how, "seconds": round(took, 1)})
            if how == "killed" and kill:
                left = max(300, seconds - took)
                how, took = run_agent(goal, job, attach, a.tier, left, log_file)
                sessions.append({"ended": how, "seconds": round(took, 1), "resumed": True})
            wall = time.time() - t0
            peak = round(tier.peak_bytes() / MB)
            try:
                rep = json.loads((job / ".neuron" / "final_report.json").read_text())
            except (OSError, ValueError):
                rep = {}
            exam = examine_task(task, base, job, scratch / f"{task['id']}__shots")
            journal = (job / ".neuron" / "job" / "journal.jsonl")
            resumed_msgs = [l for l in journal.read_text().splitlines() if "resum" in l.lower()] if journal.exists() else []
            usage = rep.get("usage_all_sessions") or {}
            row = {"task": task["id"], "kind": task["kind"], "solved": exam["total"] > 0 and exam["passed"] == exam["total"],
                   "checks_passed": exam["passed"], "checks_total": exam["total"],
                   "failed_checks": [c["id"] + (": " + str(c.get("detail"))[:160] if c.get("detail") else "") for c in exam["checks"] if not c["pass"]],
                   "seconds": round(wall, 1), "peak_mb": peak, "sessions": sessions,
                   "model_calls": usage.get("model_calls"), "tokens": usage.get("tokens"), "model_seconds": usage.get("model_seconds"),
                   "online_calls": usage.get("online_calls", 0),
                   "human_help": {"approvals_asked": len(rep.get("waiting_approval") or []), "manual_steps": 0},
                   "recovery": ({"killed_halfway": sessions[0]["ended"] == "killed", "resumed_and_finished": len(sessions) > 1 and sessions[-1]["ended"] == "exited",
                                 "resume_notes": resumed_msgs[-3:]} if task.get("kill_and_resume") else None),
                   "made_by": rep.get("made_by"), "agent_verdict": rep.get("verdict", "no report (crashed or killed)"),
                   "false_claim": rep.get("verdict") == "VERIFIED" and not (exam["total"] > 0 and exam["passed"] == exam["total"])}
            results["rows"].append(row)
            results["tier_limit_hits"], results["oom_kills"] = tier.limit_hits(), tier.oom_kills()
            out_file.write_text(json.dumps(results, indent=1))
            print(f"{label} {task['id']}: {'SOLVED' if row['solved'] else 'not solved'} | {row['checks_passed']}/{row['checks_total']} checks | "
                  f"{row['seconds']}s | peak {peak} MB | calls {row['model_calls']} | agent says {row['agent_verdict']}", flush=True)
    finally:
        tier.leave()
    print("PHASE5-DONE", label, flush=True)


if __name__ == "__main__":
    main()
