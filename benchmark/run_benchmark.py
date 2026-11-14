"""Run fix_code on the 10 buggy projects with the real local model and NO network.

    python3 -m benchmark.run_benchmark

What it does
  * Moves itself into a new, empty network namespace (only loopback exists), then checks
    that the internet really is unreachable. The brain's own simulated switch is also set OFF.
  * Starts llama.cpp's server with the local model file found in models/ (or $NEURON_MODEL).
    If there is no model file it stops. It never substitutes anything for the model.
  * For each project: copies it to a scratch folder, hands the brain the task
    "Fix the failing tests in <folder>", lets the engine run it (model plans -> fix_code ->
    model reviews), then INDEPENDENTLY re-runs the project's original tests in the sandbox
    against the fixed project. Only that independent run decides "solved".
  * Records per project: solved or not, attempts, time, peak RAM. Writes benchmark/results.json
    and benchmark/results.md.

The reference fixes in benchmark/solutions/ are never copied anywhere the model can read.
"""
import ctypes
import fcntl
import hashlib
import json
import os
import platform
import resource
import shutil
import socket
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from neuron.brain.engine import Engine                                    # noqa: E402
from neuron.brain.llama_server import DEFAULT_BIN, LlamaServer, find_model  # noqa: E402
from neuron.brain.network import NetworkMonitor, SimulatedSwitch          # noqa: E402
from neuron.brain.planner import LlamaCppPlanner                          # noqa: E402
from neuron.brain.report import build_report, report_text                 # noqa: E402
from neuron.brain.sandbox import Sandbox                                  # noqa: E402
from neuron.brain.store import Store                                      # noqa: E402
from neuron.brain.tools import default_registry                           # noqa: E402
from neuron.brain.tools.fix_code import default_test_command, tests_passed  # noqa: E402
from neuron.brain.world import FakeWorld                                  # noqa: E402

PROJECTS = ROOT / "benchmark" / "projects"
TASK_TIMEOUT = 30 * 60


def cut_network():
    """Enter an empty network namespace with only loopback. Returns a description of what was verified."""
    info = {"method": "none", "internet_reachable": None}
    try:
        os.unshare(os.CLONE_NEWNET)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifr = struct.pack("16sH", b"lo", 0)
        flags = struct.unpack("16sH", fcntl.ioctl(s, 0x8913, ifr))[1]          # SIOCGIFFLAGS
        fcntl.ioctl(s, 0x8914, struct.pack("16sH", b"lo", flags | 1))          # SIOCSIFFLAGS, IFF_UP
        s.close()
        info["method"] = "new empty network namespace (loopback only)"
    except (AttributeError, OSError) as e:
        info["method"] = f"could not isolate the network: {e}"
    for var in list(os.environ):
        if var.lower() in ("http_proxy", "https_proxy", "all_proxy"):
            del os.environ[var]
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=3).close()
        info["internet_reachable"] = True
    except OSError as e:
        info["internet_reachable"] = False
        info["probe_error"] = str(e)
    info["interfaces"] = sorted(os.listdir("/sys/class/net")) if info["method"].startswith("could") else ["lo"]
    return info


def tree_hash(folder, only_tests=False):
    h = hashlib.sha256()
    for p in sorted(Path(folder).rglob("*.py")):
        rel = p.relative_to(folder)
        if only_tests and "tests" not in rel.parts:
            continue
        h.update(str(rel).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def run_project(engine, store, sandbox, project, scratch, server=None, timeout=TASK_TIMEOUT, log=print):
    """Run one project through the engine. Returns the result row."""
    name = project.name
    target = scratch / name
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(project, target)
    if server:
        server.reset_peak()
    start = time.time()
    tid = engine.submit(f"Fix the failing tests in {target}")
    while store.get_task(tid)["status"] not in ("done", "failed"):
        if time.time() - start > timeout:
            break
        if not engine.tick():
            time.sleep(0.05)
    seconds = time.time() - start
    task = store.get_task(tid)
    steps = store.steps(tid)
    fix_steps = [s for s in steps if s["action"] == "fix_code"]
    ev = ((fix_steps[-1]["proof"] or {}).get("evidence") or {}) if fix_steps else {}
    attempts = ev.get("attempts") or []
    # independent check: original tests + whatever is now in the project folder
    check_dir = scratch / (name + "__check")
    shutil.rmtree(check_dir, ignore_errors=True)
    shutil.copytree(target, check_dir)
    shutil.rmtree(check_dir / "tests")
    shutil.copytree(project / "tests", check_dir / "tests")
    res = sandbox.run(default_test_command(check_dir), check_dir)
    solved = task["status"] == "done" and tests_passed(res, True)
    llm = [a["llm"] for a in attempts if "llm" in a]
    row = {
        "project": name,
        "solved": solved,
        "brain_claimed_success": task["status"] == "done" and any((s["result"] or {}).get("fixed") for s in fix_steps),
        "independent_test_run_passed": tests_passed(res, True),
        "tests_untouched": tree_hash(target, True) == tree_hash(project, True),
        "attempts": len(attempts),
        "seconds": round(seconds, 1),
        "llm_seconds_in_fix": round(sum(l["seconds"] for l in llm), 1),
        "tokens_generated_in_fix": sum(l["completion_tokens"] for l in llm),
        "tokens_per_second": round(sum(l["completion_tokens"] for l in llm) / max(1e-9, sum(l["seconds"] for l in llm)), 1) if llm else None,
        "peak_ram_mb": {
            "model_server": round(server.peak_rss_bytes() / 2**20) if server else None,
            "sandbox_tests": ev.get("peak_sandbox_mem_mb"),
            "brain_process": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
        },
        "planner": task["planner"],
        "plan_revisions": task.get("revisions") or 0,
        "task_status": task["status"],
        "timed_out": task["status"] not in ("done", "failed"),
        "changed_file": ev.get("changed_file"),
        "what_happened": [("rejected: " + a["error"]) if a.get("error") else
                          (f"changed {a.get('file')}: " + ("tests passed" if a.get("passed") else
                           "timed out" if a["test"]["timed_out"] else "tests still failing"))
                          for a in attempts] or [(s["proof"] or {}).get("summary") or s["error"] or s["status"]
                                                 for s in steps],
        "task_id": tid,
    }
    if row["peak_ram_mb"]["model_server"] is not None:
        row["peak_ram_mb"]["total"] = round(row["peak_ram_mb"]["model_server"] + row["peak_ram_mb"]["brain_process"]
                                            + (row["peak_ram_mb"]["sandbox_tests"] or 0))
    log(f"  {name}: {'SOLVED' if solved else 'not solved'} | attempts {row['attempts']} | "
        f"{row['seconds']}s | model server peak {row['peak_ram_mb']['model_server']} MB")
    return row, report_text(build_report(store, engine.world, tid))


def write_markdown(results, path):
    rows = results["projects"]
    lines = ["# fix_code benchmark results", "",
             f"- Model: `{results['model']['file']}` ({results['model']['size_mb']} MB, sha256 `{results['model']['sha256'][:16]}…`)",
             f"- llama.cpp: {results['llama_cpp']}",
             f"- Machine: {results['machine']['cpus']} CPU threads, {results['machine']['ram_mb']} MB RAM, {results['machine']['cpu']}",
             f"- Network during the run: {results['network']['method']}; internet reachable: {results['network']['internet_reachable']}",
             f"- Model load: {results['model']['load_seconds']}s, {results['model']['idle_rss_mb']} MB resident after loading",
             f"- **Solved: {results['solved']} of {len(rows)}**", "",
             "| Project | Solved | Attempts | Time (s) | Tokens/s | Peak RAM model server (MB) | Peak RAM total (MB) | What happened |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['project']} | {'yes' if r['solved'] else 'NO'} | {r['attempts']} | {r['seconds']} | "
                     f"{r['tokens_per_second'] or '-'} | {r['peak_ram_mb']['model_server']} | "
                     f"{r['peak_ram_mb'].get('total', '-')} | {'; '.join(str(w) for w in r['what_happened'])} |")
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    model = find_model()
    if model is None or not model.exists():
        sys.exit("NO MODEL FILE. Put a .gguf model in ./models (see scripts/setup_local_model.sh). "
                 "The benchmark will not run without the real model.")
    net = cut_network()
    print(f"network: {net['method']}; internet reachable: {net['internet_reachable']}")
    if net["internet_reachable"]:
        sys.exit("The network could not be cut off - refusing to run an 'offline' benchmark online.")
    run_dir = ROOT / "benchmark" / "run"
    shutil.rmtree(run_dir, ignore_errors=True)
    (run_dir / "scratch").mkdir(parents=True)
    port = 18080
    server = LlamaServer(model, port=port, log=run_dir / "llama-server.log")
    t0 = time.time()
    client = server.start()
    load_seconds = round(time.time() - t0, 1)
    try:
        store = Store(run_dir / "brain.db")
        switch = SimulatedSwitch(run_dir / "network.json")
        switch.set(False)
        world = FakeWorld(run_dir / "world.db", switch)
        tools = default_registry()
        sandbox = Sandbox()
        engine = Engine(store, LlamaCppPlanner(registry=tools, client=client), NetworkMonitor(switch.is_online),
                        world, run_dir / "artifacts", tools=tools, services={"llm": client, "sandbox": sandbox})
        digest = hashlib.sha256()
        with open(model, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        results = {
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": {"file": model.name, "size_mb": round(model.stat().st_size / 2**20), "sha256": digest.hexdigest(),
                      "reported_name": client.model_name(), "load_seconds": load_seconds,
                      "idle_rss_mb": round(server.rss_bytes() / 2**20), "context_tokens": server.ctx,
                      "threads": server.threads},
            "llama_cpp": os.popen(f"{DEFAULT_BIN} --version 2>&1").read().strip().splitlines()[0],
            "machine": {"cpus": os.cpu_count(), "cpu": platform.processor() or platform.machine(),
                        "ram_mb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**20)},
            "network": net, "sandbox": sandbox.describe(), "projects": [],
        }
        reports = []
        for project in sorted(p for p in PROJECTS.iterdir() if p.is_dir()):
            row, text = run_project(engine, store, sandbox, project, run_dir / "scratch", server)
            results["projects"].append(row)
            reports.append(text)
            results["solved"] = sum(r["solved"] for r in results["projects"])
            (ROOT / "benchmark" / "results.json").write_text(json.dumps(results, indent=1))   # save as we go
        results["total_seconds"] = round(sum(r["seconds"] for r in results["projects"]), 1)
        results["peak_model_server_rss_mb"] = max(r["peak_ram_mb"]["model_server"] for r in results["projects"])
        (ROOT / "benchmark" / "results.json").write_text(json.dumps(results, indent=1))
        (ROOT / "benchmark" / "reports.txt").write_text("\n\n".join(reports) + "\n")
        write_markdown(results, ROOT / "benchmark" / "results.md")
        print(f"\nSOLVED {results['solved']} of {len(results['projects'])} in {results['total_seconds']}s")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
