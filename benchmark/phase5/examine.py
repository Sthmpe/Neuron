"""Phase-5 examiner dispatch: one function, the task, and the folder NEURON delivered. Nothing NEURON says
about its own work is used; only the delivered files and the running app."""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "examiners"))
import code as code_exam    # noqa: E402
import docs as docs_exam    # noqa: E402

WORD_SPECS = {
    "L03_word_proposal": dict(headings=["Summary", "The problem", "Our plan", "Budget", "Timeline"], words=(400, 900),
                              table={"header": ["Item", "Cost (USD)"], "rows": {"Solar panels": 180000, "Inverters and batteries": 95000,
                                                                               "Installation": 60000, "Training for school staff": 15000}}),
    "D03_word_memo": dict(headings=["Change", "Reason", "Questions"], words=(120, 300)),
}
PPTX_SPECS = {"L04_pptx_pitch": dict(file="pitch.pptx", slides=6, must_contain=["FarmLink", "400,000"]),
              "D04_pptx_short": dict(file="intro.pptx", slides=3, must_contain=["Golden Crust"], max_bullets=5)}


SHOP_CHECKS = {"1": ["login_required", "wrong_password_rejected", "login_works", "add_products", "product_search", "add_customers",
                     "order_reduces_stock", "second_order", "oversized_order_refused", "orders_list_shows_totals",
                     "dashboard_numbers", "works_on_a_phone", "no_server_errors"],
               "2": ["data_survives_restart", "no_server_errors_after_restart"]}


def _shop_app(project, out_dir, sandbox):
    checks = []
    for old in Path(project).glob("data.db*"):       # the examiner always starts from an empty database
        old.unlink()
    for phase in ("1", "2"):
        srv = sandbox.start(["python3", "app.py"], project) if (Path(project) / "app.py").exists() else None
        if not (srv and srv.wait_ready("/")):
            checks += [{"id": i, "pass": False, "detail": "the app was not running"} for i in SHOP_CHECKS[phase]]
            if srv:
                srv.stop()
            continue
        url = srv.url
        env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
        try:
            out = subprocess.run(["node", str(HERE / "examiners" / "shop_app.js"), url, phase, str(out_dir)],
                                 capture_output=True, text=True, env=env, timeout=600).stdout
            checks += json.loads(out.strip().splitlines()[-1])["checks"]
        except Exception as e:      # noqa: BLE001
            checks.append({"id": f"examiner_phase_{phase}", "pass": False, "detail": type(e).__name__})
        if srv:
            srv.stop()
    checks += code_exam.has_passing_tests(project)["checks"]
    return {"checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks)}


def examine(task, delivered, answers=None, out_dir=None, sandbox=None):
    """task: an entry from locked/ or dev/ tasks.json. delivered: the folder NEURON worked in."""
    d, kind, tid = Path(delivered), task["kind"], task["id"]
    if kind == "pdf_qa":
        return docs_exam.pdf_qa(answers or [], task, HERE / "sources")
    if kind == "excel":
        if tid.startswith("L"):
            return docs_exam.excel(d / "sales_summary.xlsx", HERE / "sources" / "sales_2025.csv")
        return docs_exam.excel_simple(d / "expenses.xlsx", HERE / "sources" / "dev_expenses.csv", "category", "amount")
    if kind == "word":
        return docs_exam.word(d / ("proposal.docx" if tid.startswith("L") else "memo.docx"), **WORD_SPECS[tid])
    if kind == "pptx":
        spec = dict(PPTX_SPECS[tid])
        return docs_exam.pptx(d / spec.pop("file"), **spec)
    if kind == "cpp_build":
        return code_exam.budget_cli(d) if tid.startswith("L") else code_exam.wc2_cli(d)
    if kind == "workspace_bug":
        return code_exam.workspace_bug(d, HERE / "workspaces" / task["workspace"], task["lang"])
    if kind == "long_task":
        return code_exam.docstrings(d, (HERE / task["workspace"]).resolve())
    if kind == "web_app" and tid == "L11_business_app":
        from neuron.brain.sandbox import Sandbox
        return _shop_app(d, out_dir or d.parent / (d.name + "__shots"), sandbox or Sandbox(mem_mb=256))
    raise ValueError(f"no examiner for {tid}")
