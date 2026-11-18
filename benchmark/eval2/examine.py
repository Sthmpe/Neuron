"""eval2 examiner dispatch: the task and the folder NEURON delivered. Only delivered files and the running app count."""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "examiners"))
import code as code_exam    # noqa: E402
import docs as docs_exam    # noqa: E402

WORD = dict(headings=["Purpose", "Details", "Next steps"], words=(200, 400),
            table={"header": ["Item", "Amount (NGN)"], "rows": {"Rent": 450000, "Service charge": 60000, "Caution deposit": 100000}})
PPTX = dict(slides=5, must_contain=["Mama Put", "75"], max_bullets=5)
APP_CHECKS = {"1": ["login_required", "wrong_password_rejected", "login_works", "add_customers", "add_repairs", "repairs_list_shows_totals",
                    "dashboard_numbers", "works_on_a_phone", "no_server_errors"],
              "2": ["data_survives_restart", "no_server_errors_after_restart"]}


def _repair_app(project, out_dir, sandbox):
    checks = []
    for old in Path(project).glob("data.db*"):           # the examiner always starts from an empty database
        old.unlink()
    for phase in ("1", "2"):
        srv = sandbox.start(["python3", "app.py"], project) if (Path(project) / "app.py").exists() else None
        if not (srv and srv.wait_ready("/")):
            checks += [{"id": i, "pass": False, "detail": "the app was not running"} for i in APP_CHECKS[phase]]
            if srv:
                srv.stop()
            continue
        env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
        try:
            out = subprocess.run(["node", str(HERE / "examiners" / "repair_app.js"), srv.url, phase, str(out_dir)],
                                 capture_output=True, text=True, env=env, timeout=600).stdout
            checks += json.loads(out.strip().splitlines()[-1])["checks"]
        except Exception as e:      # noqa: BLE001
            checks.append({"id": f"examiner_phase_{phase}", "pass": False, "detail": type(e).__name__})
        srv.stop()
    return {"checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks)}


def examine(task, delivered, answers=None, out_dir=None, sandbox=None):
    d, kind = Path(delivered), task["kind"]
    if kind == "pdf_qa":
        return docs_exam.pdf_qa(answers or [], task, HERE / "sources")
    if kind == "excel":
        return docs_exam.excel_products(d / "clinic_summary.xlsx", HERE / "sources" / "clinic_visits_2026.csv", "department", "visits", "fee_per_visit")
    if kind == "word":
        return docs_exam.word(d / "tenancy_notice.docx", **WORD)
    if kind == "pptx":
        return docs_exam.pptx(d / "food_safety.pptx", **PPTX)
    if kind == "workspace_bug":
        return code_exam.workspace_bug_any(d, HERE / "workspaces" / task["workspace"], task["lang"])
    if kind == "cpp_build":
        return code_exam.csvsum(d)
    if kind == "web_app":
        from neuron.brain.sandbox import Sandbox
        return _repair_app(d, out_dir or d.parent / (d.name + "__shots"), sandbox or Sandbox(mem_mb=256))
    if kind == "long_task":
        return code_exam.docstrings(d, HERE / "workspaces" / "pantry_docs")
    if kind == "answer":
        return code_exam.number_answer(d, task["expect_number"])
    raise ValueError(f"no examiner for {task['id']}")
