"""Final report: steps done, steps failed, and the proof for each."""
import time


def build_report(store, world, task_id):
    task = store.get_task(task_id)
    if not task:
        return None
    steps = store.steps(task_id)
    execs = store.executions(task_id)
    ledger = world.ledger(task_id + ":")
    count = lambda st: [s["no"] for s in steps if s["status"] == st]
    done_runs = {}
    for e in execs:
        if e["outcome"] == "done":
            done_runs[e["step_no"]] = done_runs.get(e["step_no"], 0) + 1
    done = [s for s in steps if s["status"] == "done"]
    verified = [s for s in done if (s["proof"] or {}).get("verified")]
    failed = [s for s in steps if s["status"] == "failed" and not s["superseded"]]
    if task["status"] == "done":
        verdict = (f"COMPLETED. {len(verified)} of {len(done)} finished steps were independently checked"
                   + (f"; {len(done) - len(verified)} rest on output that was NOT independently checked."
                      if len(done) != len(verified) else "."))
    elif task["status"] == "failed":
        tried = "; ".join(f"step {s['no']} ({s['action']}): {(s['proof'] or {}).get('summary') or s['error']}"
                          for s in failed)
        verdict = "NOT SOLVED. " + (f"The planner gave up: {task['note']}. " if task.get("note") else "") + \
                  (f"What was tried: {tried}" if tried else "")
    else:
        verdict = "NOT FINISHED YET."
    return {
        "verdict": verdict, "revisions": task.get("revisions") or 0,
        "task_id": task_id, "goal": task["goal"], "status": task["status"], "planner": task["planner"],
        "created_at": task["created_at"], "finished_at": task["finished_at"],
        "totals": {"steps": len(steps), "done": len(count("done")), "failed": len(count("failed")),
                   "rejected": len(count("rejected")), "blocked": len(count("blocked")),
                   "not_finished": len([s for s in steps
                                        if s["status"] not in ("done", "failed", "rejected", "blocked")])},
        "failed_steps": count("failed"), "rejected_steps": count("rejected"), "blocked_steps": count("blocked"),
        "duplicate_check": {
            "steps_completed_more_than_once": sorted(n for n, c in done_runs.items() if c > 1),
            "outside_actions": len(ledger),
            "outside_duplicates_blocked": sum(l["duplicates_blocked"] for l in ledger),
        },
        "steps": [{"no": s["no"], "title": s["title"],
                   "kind": "needs internet" if s["needs_internet"] else "offline",
                   "tool": s["action"], "inputs": s["params"], "superseded": bool(s["superseded"]),
                   "sensitive": s["sensitive"], "status": s["status"], "attempts": s["attempts"],
                   "error": s["error"], "proof": s["proof"]} for s in steps],
        "timeline": [{"at": e["at"], "kind": e["kind"], "message": e["message"]}
                     for e in store.events(task_id)],
    }


def _evidence_line(proof):
    ev = (proof or {}).get("evidence") or {}
    bits = []
    if "receipt" in ev:
        bits.append(f"outside-world receipt #{ev['receipt']['receipt_id']}")
    if "sha256" in ev:
        bits.append(f"file {ev['file'].split('/')[-1]} sha256 {ev['sha256'][:12]}..")
    for k, v in ev.items():
        if k not in ("receipt", "sha256", "file", "bytes", "diff") and not isinstance(v, (dict, list)):
            bits.append(f"{k}={v}")
    return "; ".join(bits)


def report_text(r):
    t = r["totals"]
    lines = [
        f"NEURON REPORT - task {r['task_id']}",
        f"Goal: {r['goal']}",
        f"Status: {r['status']}",
        f"Verdict: {r['verdict']}",
        f"Planner: {r['planner']}" + (f" | plan revised {r['revisions']} time(s)" if r["revisions"] else ""),
        f"Steps: {t['steps']} total | {t['done']} done | {t['failed']} failed | "
        f"{t['rejected']} rejected by host | {t['blocked']} blocked | {t['not_finished']} not finished",
        f"Duplicate check: steps completed more than once = "
        f"{r['duplicate_check']['steps_completed_more_than_once'] or 'none'}; "
        f"outside actions = {r['duplicate_check']['outside_actions']}; "
        f"duplicates blocked by idempotency key = {r['duplicate_check']['outside_duplicates_blocked']}",
        "", "Proof for each step:",
    ]
    for s in r["steps"]:
        p = s["proof"] or {}
        when = time.strftime("%H:%M:%S", time.localtime(p["finished_at"])) if p.get("finished_at") else "--:--:--"
        tag = "internet" if s["kind"] == "needs internet" else "offline "
        lines.append(f" {s['no']:>2}. [{s['status']:<8}] [{tag}]{' [sensitive]' if s['sensitive'] else ''} {s['title']}")
        lines.append(f"       {when}  {p.get('summary', s['error'] or 'no proof recorded')}")
        ev = _evidence_line(p)
        if ev:
            lines.append(f"       proof: {ev}")
        if p.get("verification"):
            lines.append(f"       checked: {'YES' if p.get('verified') else 'NO'} - {p['verification']}")
        if s["superseded"]:
            lines.append("       (this failed step was replaced by a different approach)")
        for a in ((p.get("evidence") or {}).get("attempts") or []):
            if a.get("error"):
                what = f"rejected before testing: {a['error']}"
            else:
                t = a.get("test") or {}
                what = (f"changed {a.get('file')} -> tests "
                        + ("PASSED" if a.get("passed") else
                           "timed out" if t.get("timed_out") else f"still failing (exit code {t.get('exit_code')})"))
            lines.append(f"       attempt {a['n']}: {what}")
    return "\n".join(lines)
