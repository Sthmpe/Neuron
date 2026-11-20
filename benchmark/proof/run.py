"""Core-proof runner: the bare model vs full NEURON on the 32 locked tasks. Same model, tier, sandbox tools and time
budget; network cut; knowledge memory off; the same seed for both conditions in a run.

  python3 -m benchmark.proof.run --tier 2gb --run 1            (refuses unless the lock is intact)
  python3 -m benchmark.proof.run --tier 2gb --run 1 --only B1_py_invoice --conditions bare --tag smoke

For every task, in alternating order (bare first on even task positions of odd runs, NEURON first otherwise):
  * a fresh job folder: for code tasks a copy of the project; inputs are attached
  * the condition runs as its own process inside the tier (model server included), with the task's time budget;
    it is killed (SIGKILL) at budget + 60 s
  * the independent examiner checks only the delivered files or the running app
Recorded per task and condition: solved, checks, wall time, peak memory of the tier (everything in it), model calls,
tokens, what the condition claimed (NEURON's verdict, the bare model's DONE) and whether that claim was false.
Results: benchmark/results/proof/<tier>-run<k>[-tag].json. Running again skips rows already recorded.
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
TASKS = HERE / "tasks"
MB = 2 ** 20
GRACE = 60


# Attempts that ran but whose result was not recorded, so the condition ran again (see LOCKED.md, runner amendment R1)
NOTES = {("2gb-run1", "D2_excel_staff_costs", "bare"): "second attempt: the first attempt's examination crashed (BadZipFile on "
         "a text file named .xlsx) before runner amendment R1, so no row was recorded and the condition ran again",
         ("4gb-run1", "A1_pharmacy", "bare"): "second attempt: the first was stopped after about 4 minutes, unrecorded, "
         "to apply runner amendment R1",
         ("4gb-run2", "A5_library_loans", "bare"): "second attempt: during the first, the tier's memory limit killed the runner "
         "itself (runner amendment R2), so no row was recorded",
         ("2gb-run3", "A1_pharmacy", "bare"): "second attempt: the first ran beside an orphaned process from the killed 4 GB "
         "runner (same machine, same model port) and was stopped, unrecorded (runner amendment R2)"}


def verify_lock():
    r = subprocess.run([sys.executable, str(HERE / "verify_lock.py")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("REFUSED: the locked tasks or examiners changed since they were locked:\n" + r.stdout + r.stderr)


def prepare(task, job):
    shutil.rmtree(job, ignore_errors=True)
    if task.get("workspace"):
        shutil.copytree(TASKS / task["workspace"], job, ignore=shutil.ignore_patterns("__pycache__"))
    job.mkdir(parents=True, exist_ok=True)
    return [str(TASKS / rel) for rel in task.get("inputs", [])]


def command(cond, task, job, attach, tier, report):
    if cond == "neuron":
        cmd = [sys.executable, "-m", "neuron.agent", task["request"], "--workspace", str(job), "--tier", tier,
               "--max-seconds", str(task["budget_s"]), "--report", str(report)]
    else:
        cmd = [sys.executable, "-m", "benchmark.proof.bare", "--task", task["id"], "--workspace", str(job), "--tier", tier,
               "--max-seconds", str(task["budget_s"]), "--report", str(report)]
    return cmd + (["--attach"] + attach if attach else [])


TIMING = re.compile(r"print_timing: .*?prompt eval time = +[\d.]+ ms / +(\d+) tokens")
EVAL = re.compile(r"print_timing: .*?\| +eval time = +[\d.]+ ms / +(\d+) tokens")


def server_usage(job):
    """Model calls and tokens counted from the model server's own logs (the same way for both conditions; the
    conditions' self-reports are kept too, but NEURON's misses calls made inside some inner loops)."""
    calls = prompt = generated = 0
    for log in list(job.glob(".neuron/llama-*.log")) + list(job.glob(".bare/llama-*.log")):
        text = log.read_text(errors="replace")
        found = TIMING.findall(text)
        calls += len(found)
        prompt += sum(map(int, found))
        generated += sum(map(int, EVAL.findall(text)))
    return {"calls": calls, "prompt_tokens_processed": prompt, "generated_tokens": generated}


def _child_setup():
    """Runner amendment R2: every measured process (and all it starts) gets the same raised out-of-memory priority, so
    when the tier's limit is hit the kernel picks among the measured processes exactly as before, never the runner
    (lowering the runner's own priority is not permitted in this container); and it dies if the runner dies, so no
    orphan keeps running beside the next condition."""
    import ctypes
    with open("/proc/self/oom_score_adj", "w") as f:
        f.write("500")
    ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGKILL)     # PR_SET_PDEATHSIG


def _clear_strays():
    """Nothing from an earlier condition may run beside this one (R2: after the runner was killed, its orphaned bare
    loop and model server kept running beside the next pass)."""
    for pattern in ("benchmark.proof.bare", "neuron.agent", "llama-server"):
        subprocess.run(["pkill", "-9", "-f", pattern], capture_output=True)
    time.sleep(1)


def run_one(cmd, log_file, seconds, seed):
    env = dict(os.environ, NEURON_MEMORY="off", NEURON_SEED=str(seed))
    _clear_strays()
    with open(log_file, "a") as log:
        log.write(f"\n===== started {time.strftime('%H:%M:%S')} =====\n")
        log.flush()
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env,
                                preexec_fn=_child_setup)
        t0 = time.time()
        while proc.poll() is None:
            if time.time() - t0 > seconds + GRACE:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                log.write(f"\n===== KILLED at the time limit {time.strftime('%H:%M:%S')} =====\n")
                return "killed at the time limit", time.time() - t0
            time.sleep(0.5)
    return "exited", time.time() - t0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True, choices=["2gb", "4gb"])
    ap.add_argument("--run", type=int, required=True, choices=[1, 2, 3])
    ap.add_argument("--only")
    ap.add_argument("--conditions", default="bare,neuron")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    verify_lock()
    from benchmark.proof.examine import examine
    from benchmark.run_benchmark import cut_network
    from neuron.brain.models import ModelManager
    from neuron.brain.tiers import Tier
    tasks = json.loads((TASKS / "tasks.json").read_text())
    label = f"{a.tier}-run{a.run}" + (f"-{a.tag}" if a.tag else "")
    out_file = ROOT / "benchmark" / "results" / "proof" / f"{label}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(out_file.read_text()) if out_file.exists() else {"rows": []}
    net = cut_network()
    if net["internet_reachable"]:
        sys.exit("The network could not be cut off; refusing to run.")
    scratch = ROOT / "benchmark" / "run" / "proof" / label
    scratch.mkdir(parents=True, exist_ok=True)
    tier = Tier(a.tier).enter()
    mgr = ModelManager()
    lock = json.loads((HERE / "LOCK.json").read_text())
    results.update(tier=a.tier, run=a.run, seed=a.run, tier_limit_mb=round(tier.limit / MB), network=net["method"],
                   model={r: mgr.active(a.tier, r) for r in ("planner", "reviewer", "builder")}, lock=lock["whole"],
                   grace_s=GRACE, started=results.get("started") or time.strftime("%Y-%m-%d %H:%M:%S"),
                   code_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    done = {(r["task"], r["condition"]) for r in results["rows"]}
    only = set(a.only.split(",")) if a.only else None
    conds = a.conditions.split(",")
    try:
        for i, task in enumerate(tasks):
            if only and task["id"] not in only:
                continue
            order = ["bare", "neuron"] if (i + a.run) % 2 == 1 else ["neuron", "bare"]
            for cond in [c for c in order if c in conds]:
                if (task["id"], cond) in done:
                    continue
                job = scratch / cond / task["id"]
                attach = prepare(task, job)
                report = scratch / cond / f"{task['id']}.report.json"
                report.unlink(missing_ok=True)
                tier.reset_peak()
                how, took = run_one(command(cond, task, job, attach, a.tier, report), scratch / cond / f"{task['id']}.log",
                                    task["budget_s"], a.run)
                peak = round(tier.peak_bytes() / MB)
                try:
                    rep = json.loads(report.read_text())
                except (OSError, ValueError):
                    rep = {}
                try:
                    exam = examine(task, job, scratch / cond / f"{task['id']}__shots")
                    examiner_error = None
                except Exception as e:      # noqa: BLE001  runner amendment R1: a crash on a delivery fails it, never stops the pass
                    examiner_error = f"{type(e).__name__}: {e}"[:300]
                    exam = {"checks": [{"id": "examiner_could_not_read_the_delivery", "pass": False, "detail": examiner_error}],
                            "passed": 0, "total": 1, "solved": False}
                usage_srv = server_usage(job)
                solved = exam["solved"]
                if cond == "neuron":
                    usage = rep.get("usage_all_sessions") or {}
                    calls, tokens, claim = usage.get("model_calls"), usage.get("tokens"), rep.get("verdict", "no report")
                    claimed_success = claim == "VERIFIED"
                else:
                    calls, tokens = rep.get("model_calls"), rep.get("tokens")
                    claim = "DONE" if rep.get("claimed_done") else f"stopped: {rep.get('ended') or 'no report'}"
                    claimed_success = bool(rep.get("claimed_done"))
                row = {"task": task["id"], "category": task["category"], "condition": cond, "solved": solved,
                       "checks_passed": exam["passed"], "checks_total": exam["total"],
                       "failed_checks": [c["id"] + (": " + str(c.get("detail"))[:160] if c.get("detail") else "")
                                         for c in exam["checks"] if not c["pass"]],
                       "seconds": round(took, 1), "budget_s": task["budget_s"], "ended": how, "peak_mb": peak,
                       "model_calls": usage_srv["calls"], "generated_tokens": usage_srv["generated_tokens"],
                       "prompt_tokens_processed": usage_srv["prompt_tokens_processed"],
                       "self_reported": {"model_calls": calls, "tokens": tokens}, "claim": claim,
                       "false_claim": claimed_success and not solved,
                       "made_by": rep.get("made_by") if cond == "neuron" else "model", "examiner_error": examiner_error,
                       "note": NOTES.get((label, task["id"], cond)),
                       "bare_detail": {k: rep.get(k) for k in ("turns", "writes", "runs", "reads", "ended", "errors")} if cond == "bare" else None}
                results["rows"].append(row)
                results["tier_limit_hits"], results["oom_kills"] = tier.limit_hits(), tier.oom_kills()
                out_file.write_text(json.dumps(results, indent=1))
                print(f"{label} {task['id']} {cond}: {'SOLVED' if solved else 'not solved'} | {exam['passed']}/{exam['total']} | "
                      f"{row['seconds']}s | peak {peak} MB | calls {row['model_calls']} | claims {claim}", flush=True)
    finally:
        tier.leave()
    print("PROOF-DONE", label, flush=True)


if __name__ == "__main__":
    main()
