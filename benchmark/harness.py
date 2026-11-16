"""Benchmark harness for step 3: runs a task set at one RAM tier in one condition.

    python3 -m benchmark.harness --set dev|heldout --tier 2gb|4gb|8gb --condition base|full
                                 [--model ID | --models planner=ID,reviewer=ID,builder=ID]
                                 [--kind bugs|builds|all] [--only name,name] [--tag TEXT]

  * network: the whole run happens in an empty network namespace (loopback only), verified first
  * memory : the whole run - model server, builder, sandboxes, dev server, browser - is inside
             one memory cgroup with the tier's limit (swap included)
  * verdict: bugs  -> the project's ORIGINAL tests are run again, independently, on the result
             builds -> the app is started and examined with a real browser (see benchmark/examiner)
  * results: benchmark/results/<set>/<tier>-<condition>[-tag].json, written after every task;
             finished tasks are skipped when the command is run again
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from benchmark.examine import examine                                          # noqa: E402
from benchmark.run_benchmark import cut_network, tree_hash                     # noqa: E402
from neuron.brain.actions import Ctx                                            # noqa: E402
from neuron.brain.models import ModelManager, ModelRunner                       # noqa: E402
from neuron.brain.sandbox import Sandbox                                        # noqa: E402
from neuron.brain.tiers import Tier                                             # noqa: E402
from neuron.brain.tools import ToolFailure                                      # noqa: E402
from neuron.brain.tools.fix_code import FixCodeTool, default_test_command, tests_passed  # noqa: E402
from neuron.builder.bugfix import fix_project                                   # noqa: E402

BUG_DIRS = {"dev": ROOT / "benchmark" / "projects", "heldout": ROOT / "benchmark" / "heldout" / "bugs"}
BUILD_DIRS = {"dev": ROOT / "benchmark" / "builds" / "dev", "heldout": ROOT / "benchmark" / "builds" / "heldout"}
BUG_SECONDS = 15 * 60
BUILD_SECONDS = 45 * 60
MB = 2 ** 20


def run_bug(project, scratch, condition, runner, sandbox, tier):
    name = project.name
    target = scratch / name
    for leftover in scratch.glob(name + "*"):
        shutil.rmtree(leftover, ignore_errors=True)
    shutil.copytree(project, target)
    tier.reset_peak()
    t0 = time.time()
    info = {}
    try:
        if condition == "full":
            r = fix_project(target, runner, sandbox, log=lambda *_: None, max_seconds=BUG_SECONDS)
            info = {"claimed": r.get("claimed"), "attempts": r.get("attempts"), "llm": r.get("llm"),
                    "what_happened": [(f"{a.get('function')}: " + ("tests passed" if a.get("passed") else (a.get("failure") or "")[:80]))
                                      for a in r.get("history") or []]}
        else:
            ctx = Ctx({"id": name}, {"no": 1, "params": {"project": str(target)}}, {}, None, scratch / "artifacts",
                      {"llm": runner.client("builder"), "sandbox": sandbox})
            try:
                out = FixCodeTool().run(ctx)
                ev, claimed = out.evidence, bool(out.result.get("fixed"))
            except ToolFailure as e:
                ev, claimed = e.evidence, False
            attempts = ev.get("attempts") or []
            info = {"claimed": claimed, "attempts": len(attempts),
                    "llm": {"calls": len([a for a in attempts if "llm" in a]),
                            "seconds": round(sum(a.get("llm", {}).get("seconds", 0) for a in attempts), 1),
                            "tokens": sum(a.get("llm", {}).get("completion_tokens", 0) for a in attempts)},
                    "what_happened": [("rejected: " + a["error"][:70]) if a.get("error") else
                                      ("tests passed" if a.get("passed") else "tests still failing") for a in attempts]}
    except Exception as e:      # the harness must survive anything a run does
        info = {"claimed": False, "attempts": None, "error": f"{type(e).__name__}: {e}"[:300]}
    seconds = time.time() - t0
    check = scratch / (name + "__check")
    shutil.rmtree(check, ignore_errors=True)
    shutil.copytree(target, check, ignore=shutil.ignore_patterns(".neuron", "__pycache__"))
    shutil.rmtree(check / "tests")
    shutil.copytree(project / "tests", check / "tests")
    res = sandbox.run(default_test_command(check), check)
    ok = tests_passed(res, True)
    return {"task": name, "type": "bug", "solved": ok, "score": 1.0 if ok else 0.0, **info,
            "tests_untouched": tree_hash(target, True) == tree_hash(project, True),
            "seconds": round(seconds, 1), "peak_mb": round(tier.peak_bytes() / MB)}


def _builder_cmd(project, request_file, tier, condition, models, summary):
    cmd = [sys.executable, "-m", "neuron.builder", "build", "--project", str(project), "--request-file", str(request_file),
           "--tier", tier, "--condition", condition, "--max-seconds", str(BUILD_SECONDS), "--summary", str(summary)]
    for role, model in models.items():
        cmd += ["--role-model", f"{role}={model}"]
    return cmd


def _run_builder(cmd, log_file, kill_when=None):
    """Run the builder as its own process group. If kill_when() becomes true, kill -9 the whole group."""
    with open(log_file, "a") as log:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        t0 = time.time()
        while proc.poll() is None:
            if time.time() - t0 > BUILD_SECONDS + 600 or (kill_when and kill_when(time.time() - t0)):
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                return "killed", time.time() - t0
            time.sleep(0.5)
    return "exited", time.time() - t0


def run_build(task_file, scratch, condition, models, tier_name, sandbox, tier, shots_dir):
    task = json.loads(task_file.read_text())
    name = task["name"]
    for leftover in scratch.glob(name + "*"):
        shutil.rmtree(leftover, ignore_errors=True) if leftover.is_dir() else leftover.unlink()
    project, request_file = scratch / name, scratch / (name + ".request.txt")
    summary_file, log_file = scratch / (name + ".summary.json"), scratch / (name + ".builder.log")
    request_file.write_text(task["request"])
    cmd = _builder_cmd(project, request_file, tier_name, condition, models, summary_file)
    tier.reset_peak()
    row = {"task": name, "type": "build", "sessions": 1}
    t0 = time.time()
    if task.get("kill_and_resume"):
        tasks_file = project / ".neuron" / "tasks.json"

        def half_done(elapsed):
            if condition == "base":
                return elapsed > 75          # nothing is saved in this condition; kill it mid-generation
            try:
                tasks = json.loads(tasks_file.read_text())
            except (OSError, ValueError):
                return False
            done = sum(t["status"] == "done" for t in tasks)
            if done * 2 >= len(tasks) and done < len(tasks):
                half_done.seen = getattr(half_done, "seen", None) or time.time()
                return time.time() - half_done.seen > 4      # a few seconds into the next task
            return False

        how, first = _run_builder(cmd, log_file, kill_when=half_done)
        before = {}
        if tasks_file.exists():
            before = {t["id"]: (t["status"], len(t["attempts"])) for t in json.loads(tasks_file.read_text())}
        row.update(killed=how == "killed", killed_after_seconds=round(first, 1), state_at_kill=before, sessions=2)
        subprocess.run(["pkill", "-9", "-f", "llama-server"], capture_output=True)
        time.sleep(1)
        _run_builder(cmd, log_file)
        if tasks_file.exists():
            after = {t["id"]: (t["status"], len(t["attempts"])) for t in json.loads(tasks_file.read_text())}
            done_before = [k for k, v in before.items() if v[0] == "done"]
            row["finished_work_redone_after_resume"] = any(after.get(k) != before[k] for k in done_before)
            row["tasks_done_before_kill"] = done_before
    else:
        _run_builder(cmd, log_file)
    row["build_seconds"] = round(time.time() - t0, 1)
    try:
        row["builder"] = json.loads(summary_file.read_text())
    except (OSError, ValueError):
        row["builder"] = {"ok": False, "error": "the builder did not finish (no summary)"}
    row["peak_mb_build"] = round(tier.peak_bytes() / MB)
    tier.reset_peak()
    t1 = time.time()
    result = examine(task_file, project, sandbox, shots_dir / name)
    row.update(examiner=result["checks"], passed=result["passed"], total=result["total"],
               score=round(result["passed"] / result["total"], 3), solved=result["verified"],
               screenshots=result["screenshots"], examine_seconds=round(time.time() - t1, 1),
               peak_mb_examine=round(tier.peak_bytes() / MB),
               seconds=round(time.time() - t0, 1))
    row["peak_mb"] = max(row["peak_mb_build"], row["peak_mb_examine"])
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["dev", "heldout"])
    ap.add_argument("--tier", required=True)
    ap.add_argument("--condition", required=True, choices=["base", "full"])
    ap.add_argument("--model")
    ap.add_argument("--models")
    ap.add_argument("--kind", default="all", choices=["bugs", "builds", "all"])
    ap.add_argument("--only")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    manager = ModelManager()
    roles = ("planner", "reviewer", "builder")
    models = {r: a.model for r in roles} if a.model else dict(x.split("=") for x in a.models.split(",")) if a.models \
        else {r: manager.active(a.tier, r) for r in roles}
    for m in set(models.values()):
        if not manager.fits(m, a.tier):
            sys.exit(f"REFUSED: {m} does not fit the {a.tier} tier")
    label = f"{a.tier}-{a.condition}" + (f"-{a.tag}" if a.tag else "")
    out_file = ROOT / "benchmark" / "results" / a.set / f"{label}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(out_file.read_text()) if out_file.exists() else {"rows": []}
    net = cut_network()
    if net["internet_reachable"]:
        sys.exit("The network could not be cut off - refusing to run.")
    scratch = ROOT / "benchmark" / "run" / f"{a.set}-{label}"
    scratch.mkdir(parents=True, exist_ok=True)
    tier = Tier(a.tier).enter()
    sandbox = Sandbox(timeout=60, mem_mb=256)
    runner = ModelRunner(manager, a.tier, overrides=models, log_dir=scratch)
    results.update(set=a.set, tier=a.tier, tier_limit_mb=round(tier.limit / MB), condition=a.condition, models=models,
                   network=net["method"], started=results.get("started") or time.strftime("%Y-%m-%d %H:%M:%S"))
    only = set(a.only.split(",")) if a.only else None
    done = {r["task"] for r in results["rows"]}

    def save(row):
        results["rows"].append(row)
        results["tier_limit_hits"] = tier.limit_hits()
        results["oom_kills"] = tier.oom_kills()
        out_file.write_text(json.dumps(results, indent=1))
        extra = f"{row.get('passed')}/{row.get('total')} checks" if row["type"] == "build" else f"attempts {row.get('attempts')}"
        print(f"{label} {row['task']}: {'SOLVED' if row['solved'] else 'not solved'} | {extra} | {row['seconds']}s | peak {row['peak_mb']} MB", flush=True)

    try:
        if a.kind in ("bugs", "all"):
            for project in sorted(p for p in BUG_DIRS[a.set].iterdir() if p.is_dir()):
                if project.name not in done and (not only or project.name in only):
                    save(run_bug(project, scratch, a.condition, runner, sandbox, tier))
        runner.unload()
        if a.kind in ("builds", "all"):
            for task_file in sorted(BUILD_DIRS[a.set].glob("*.json")):
                if task_file.stem not in done and (not only or task_file.stem in only):
                    save(run_build(task_file, scratch, a.condition, models, a.tier, sandbox, tier,
                                   ROOT / "benchmark" / "results" / a.set / "screenshots" / label))
    finally:
        runner.unload()
        tier.leave()
    rows = results["rows"]
    print(f"{label}: solved {sum(r['solved'] for r in rows)}/{len(rows)}; mean score {sum(r['score'] for r in rows) / max(1, len(rows)):.2f}")


if __name__ == "__main__":
    main()
