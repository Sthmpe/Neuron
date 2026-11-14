"""The NEURON v0.1 demo.

A 20-step "find leads" task on fake data:
  1. host sends the task to the brain
  2. the network is cut right after step 8
  3. the brain does the offline steps it still can, then waits and retries
  4. the brain process is killed (kill -9) and started again
  5. the network is restored
  6. the brain carries on from step 9, asks permission for the sensitive step,
     and finishes - with no step done twice

Run:  python3 -m demo.run_demo
"""
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from neuron.host.client import BrainUnreachable, HostClient  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_brain(data_dir, port, step_delay):
    log = open(Path(data_dir) / "brain.log", "a")
    proc = subprocess.Popen(
        [sys.executable, "-m", "neuron.brain.server", "--port", str(port), "--data", str(data_dir),
         "--step-delay", str(step_delay), "--retry-base", "0.5", "--retry-cap", "2"],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    client = HostClient(f"http://127.0.0.1:{port}")
    for _ in range(100):
        try:
            client.health()
            return proc, client
        except BrainUnreachable:
            time.sleep(0.05)
    proc.kill()
    raise RuntimeError("brain did not start")


def run_demo(data_dir, step_delay=0.4, out=print):
    data_dir = Path(data_dir)
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True)
    port = free_port()
    seen = {"id": 0}
    checks = {}

    def say(msg=""):
        out(msg)

    def host(msg):
        out(f"[HOST ] {msg}")

    def show_events(client, tid):
        for e in client.events(tid, seen["id"]):
            seen["id"] = e["id"]
            out(f"[BRAIN] {time.strftime('%H:%M:%S', time.localtime(e['at']))}  {e['message']}")

    def wait(client, tid, cond, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            d = client.task(tid)
            show_events(client, tid)
            if cond(d):
                return d
            time.sleep(0.05)
        raise TimeoutError("demo condition not reached")

    def by_status(d, *statuses):
        return [s["no"] for s in d["steps"] if s["status"] in statuses]

    proc, client = start_brain(data_dir, port, step_delay)
    try:
        say("=== 1. Host sends the task ===")
        pid1 = client.health()["pid"]
        host(f"brain is up (process {pid1}). Sending task: 'Find leads for our sales team'")
        d = client.send_task("Find leads for our sales team")
        tid = d["task"]["id"]
        host(f"brain accepted task {tid} and planned {len(d['steps'])} steps:")
        for s in d["steps"]:
            out(f"          {s['no']:>2}. [{'needs internet' if s['needs_internet'] else 'offline':<14}]"
                f"{' [SENSITIVE]' if s['sensitive'] else ''} {s['title']}")
        checks["planned_20_steps"] = len(d["steps"]) == 20

        say("\n=== 2. Steps 1-8 run, then the network is cut ===")
        wait(client, tid, lambda d: 8 in by_status(d, "done"))
        client.set_network(False)
        host("*** NETWORK CUT (simulated switch set to OFF) right after step 8 ***")

        say("\n=== 3. Brain switches to offline work, then waits and retries ===")
        d = wait(client, tid, lambda d: d["task"]["status"] == "waiting_network" and d["task"]["retry_count"] >= 1)
        done_before = by_status(d, "done")
        execs_before = len(d["executions"])
        offline_done = [n for n in done_before if n > 8]
        host(f"task status: {d['task']['status']}")
        host(f"done so far: {done_before}")
        host(f"done while offline (skipped ahead to offline-only work): {offline_done}")
        host(f"waiting for internet: {by_status(d, 'waiting_network')}; "
             f"waiting on those: {by_status(d, 'waiting_dependency')}")
        checks["offline_steps_done_while_offline"] = offline_done == [10, 12, 13]
        checks["step_9_waiting_for_network"] = by_status(d, "waiting_network") == [9]

        say("\n=== 4. Brain process is killed and restarted ===")
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait()
        host(f"*** BRAIN KILLED (kill -9 on process {pid1}) ***")
        try:
            client.health()
            checks["brain_was_really_dead"] = False
        except BrainUnreachable:
            checks["brain_was_really_dead"] = True
            host("brain does not answer - it is really gone")
        proc, client = start_brain(data_dir, port, step_delay)
        pid2 = client.health()["pid"]
        host(f"*** BRAIN RESTARTED (new process {pid2}) - network is still off ***")

        def retried_since_restart(d):
            ev = client.events(tid, 0)
            boot = max(e["id"] for e in ev if f"pid {pid2}" in e["message"])
            return any(e["id"] > boot and "still offline" in e["message"] for e in ev)

        d = wait(client, tid, retried_since_restart)
        checks["new_process_after_restart"] = pid1 != pid2
        checks["nothing_rerun_after_restart"] = (by_status(d, "done") == done_before
                                                 and len(d["executions"]) == execs_before)
        host(f"after restart: done steps still {by_status(d, 'done')}, nothing was run again, "
             f"task still {d['task']['status']}")

        say("\n=== 5. Network is restored ===")
        client.set_network(True)
        host("*** NETWORK RESTORED (simulated switch set to ON) ***")

        say("\n=== 6. Brain resumes from step 9; host approves the sensitive step ===")
        d = wait(client, tid, lambda d: bool(client.permissions("pending")))
        perm = client.permissions("pending")[0]
        checks["sensitive_step_waited_for_approval"] = (
            perm["step_no"] == 18 and 18 not in by_status(d, "done", "running"))
        host(f">>> PERMISSION REQUEST: step {perm['step_no']} '{perm['description']}' -> host APPROVES")
        client.decide(perm["id"], True)
        d = wait(client, tid, lambda d: d["task"]["status"] in ("done", "failed"))

        first_after = d["executions"][execs_before]["step_no"]
        done_counts = {}
        for e in d["executions"]:
            if e["outcome"] == "done":
                done_counts[e["step_no"]] = done_counts.get(e["step_no"], 0) + 1
        report = client.report(tid)
        dup = report["duplicate_check"]
        checks["resumed_from_step_9"] = first_after == 9
        checks["all_20_steps_done"] = d["task"]["status"] == "done" and len(by_status(d, "done")) == 20
        # A step may be *attempted* and stopped by the dead connection (that attempt does
        # nothing), but it may only ever *complete* once.
        other = sorted({e["outcome"] for e in d["executions"]} - {"done"})
        checks["every_step_completed_exactly_once"] = (sorted(done_counts) == list(range(1, 21))
                                                       and set(done_counts.values()) == {1}
                                                       and other in ([], ["network_lost"]))
        checks["outside_world_saw_no_duplicates"] = (dup["outside_actions"] == 8
                                                     and dup["outside_duplicates_blocked"] == 0)

        say("\n=== 7. Final report from the brain ===")
        say(report["text"])
        say("\n=== Demo checks ===")
        for name, ok in checks.items():
            say(f"  {'PASS' if ok else 'FAIL'}  {name}")
        say(f"\nDEMO RESULT: {'PASS' if all(checks.values()) else 'FAIL'}"
            f" (first step run after the network came back: step {first_after})")
        return {"checks": checks, "ok": all(checks.values()), "report": report}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    lines = []

    def out(msg=""):
        print(msg, flush=True)
        lines.append(msg)

    result = run_demo(ROOT / "demo" / "run_data", out=out)
    (ROOT / "demo" / "demo_output.txt").write_text("\n".join(lines) + "\n")
    sys.exit(0 if result["ok"] else 1)
