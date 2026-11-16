"""Runs the browser examiner against a built project: phase 1 on the fresh app, then the app is
stopped and started again, then phase 2. The app runs in the sandbox; the browser reaches it
through the forwarded port. Nothing here trusts what the builder said about its own work."""
import json
import os
import re
import subprocess
from pathlib import Path

EXAMINER = Path(__file__).resolve().parent / "examiner" / "examine.js"
DEAD_URL = "http://127.0.0.1:9"


def _node(task_file, url, phase, out_dir, timeout=420):
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    try:
        p = subprocess.run(["node", str(EXAMINER), str(task_file), url, str(phase), str(out_dir)],
                           capture_output=True, text=True, timeout=timeout, env=env)
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
        return {"checks": [{"id": f"examiner_phase_{phase}_ran", "pass": False, "detail": f"{type(e).__name__}"}], "screenshots": []}


def expected_checks(task):
    """Every check the examiner makes for this task, so the total is the same whether or not the app runs."""
    if task["kind"] == "site":
        need = [re.sub(r"[^a-z0-9]+", "_", n, flags=re.I) for n in task["site"]["must_show"]]
        return (["page_opens", "headline_has_the_name"] + [f"shows_{n}" for n in need] +
                ["looks_right_on_a_phone", "form_can_be_sent_and_thanks_shown", "no_server_errors",
                 "page_opens_after_restart", "no_server_errors_after_restart", "what_was_sent_is_kept_on_disk"])
    ids = ["app_opens", "login_is_required", "wrong_password_is_rejected", "login_works", "dashboard_shows_the_requested_numbers"]
    for e in task["app"]["entities"]:
        ids += [f"{e['link']}_page_opens", f"{e['link']}_can_be_added", f"{e['link']}_search_works"]
    return ids + ["dashboard_counts_are_right", "works_on_a_phone", "no_server_errors", "login_still_works_after_restart",
                  "records_survive_a_restart", "dashboard_right_after_restart", "logout_works", "no_server_errors_after_restart"]


def examine(task_file, project, sandbox, out_dir):
    task = json.loads(Path(task_file).read_text())
    project, out_dir = Path(project), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in project.glob("data.db*"):       # the examiner always starts from an empty database
        stale.unlink()
    checks, shots, logs = [], [], []
    for phase in (1, 2):
        server = None
        url = DEAD_URL
        if (project / "app.py").exists():
            server = sandbox.start(["python3", "app.py"], project)
            if server.wait_ready("/"):
                url = server.url
        result = _node(task_file, url, phase, out_dir) if url != DEAD_URL else {"checks": [], "screenshots": []}
        if server:
            logs.append(server.stop()[-1500:])
        checks += result["checks"]
        shots += result["screenshots"]
    if task["kind"] == "site":                   # "keep what they send": it must be on disk after the app stops
        blob = b"".join(p.read_bytes() for p in project.rglob("*") if p.is_file() and "kit" not in p.parts
                        and ".neuron" not in p.parts and p.stat().st_size < 5_000_000)
        missing = [s for s in task["site"]["stored"] if s.encode() not in blob]
        checks.append({"id": "what_was_sent_is_kept_on_disk", "pass": not missing, "detail": "not found on disk: " + ", ".join(missing)})
    got = {c["id"]: c for c in checks}
    checks = [got.get(i) or {"id": i, "pass": False, "detail": "the app was not running, or the examiner could not get this far"}
              for i in expected_checks(task)]
    passed = sum(c["pass"] for c in checks)
    return {"checks": checks, "passed": passed, "total": len(checks), "verified": passed == len(checks),
            "screenshots": [str(Path(s).name) for s in shots], "app_log_tail": logs}
