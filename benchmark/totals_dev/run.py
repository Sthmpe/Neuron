"""Computed totals in a business app, measured on a dev task (not locked): NEURON builds a catering-orders app and a
browser checker uses it like a person (dishes, orders, each order's total, dashboard count and total, search).

  python3 -m benchmark.totals_dev.run --tier 4gb        # network cut, memory off
  python3 -m benchmark.totals_dev.run --validate        # a correct reference app passes, one without totals fails
Results: benchmark/results/totals_dev/<tier>.json
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
TASK = json.loads((HERE / "task.json").read_text())


def check(app, out_dir):
    from neuron.brain.sandbox import Sandbox
    for old in Path(app).glob("data.db*"):
        old.unlink()
    srv = Sandbox(timeout=900, mem_mb=256).start(["python3", "app.py"], app) if (Path(app) / "app.py").exists() else None
    if not (srv and srv.wait_ready("/")):
        if srv:
            srv.stop()
        return {"checks": [{"id": "app_runs", "pass": False, "detail": "the app was not running"}], "passed": 0, "total": 1}
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    try:
        out = subprocess.run(["node", str(HERE / "check.js"), srv.url, "1", str(out_dir)], capture_output=True, text=True, env=env, timeout=600).stdout
        checks = json.loads(out.strip().splitlines()[-1])["checks"]
    finally:
        srv.stop()
    return {"checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks)}


REF_SPEC = {"app_name": "Catering", "kind": "app", "login_required": True, "username": "chef", "password": "jollof7",
            "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
            "entities": [{"name": "dishes", "fields": [{"name": "name", "type": "text"}, {"name": "price", "type": "number"}], "search_field": "name"},
                         {"name": "orders", "fields": [{"name": "dish", "type": "link", "to": "dishes"}, {"name": "plates", "type": "number"},
                                                       {"name": "customer", "type": "text"}, {"name": "event_date", "type": "date"},
                                                       {"name": "total", "type": "computed", "formula": "plates * dish.price"}],
                          "search_field": "customer"}],
            "dashboard": [{"label": "Orders", "entity": "orders", "kind": "count"},
                          {"label": "Total value", "entity": "orders", "kind": "sum", "field": "total"}]}


def reference(project, with_totals=True):
    from neuron.brain.sandbox import Sandbox
    from neuron.builder import templates
    from neuron.builder.build import build_full
    from tests.fakes import ScriptedLLM
    spec = json.loads(json.dumps(REF_SPEC))
    if not with_totals:
        spec["entities"][1]["fields"] = spec["entities"][1]["fields"][:-1]
        spec["dashboard"] = spec["dashboard"][:1]

    class Runner:
        loads = 1

        def __init__(self, llm):
            self.llm = llm

        def client(self, role):
            return self.llm

        def model_for(self, role):
            return "scripted"

    def reply(messages):
        sys_, last = messages[0]["content"], messages[-1]["content"]
        if sys_.startswith("You turn a plain-language request"):
            return json.dumps(spec)
        if "check a web page against" in sys_:
            return '{"ok": true, "missing": []}'
        m = re.search(r"# Your task: (\S+)", last)
        st = json.loads((Path(project) / ".neuron" / "spec.json").read_text())["spec"]
        return "```python\n" + templates.reference_files(st)[m.group(1)] + "```" if m else "ok"
    return build_full(project, TASK["request"], Runner(ScriptedLLM([reply] * 60)), Sandbox(timeout=60, mem_mb=256), log=lambda *_: None, design=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="4gb")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--force", action="store_true", help="run again although a result exists (a rerun: label it)")
    ap.add_argument("--tag", default="", help="label for a rerun, e.g. rerun1-owner-words (never overwrites the original)")
    a = ap.parse_args()
    if a.validate:
        ok = True
        for with_totals in (True, False):
            d = Path(tempfile.mkdtemp()) / "app"
            r = reference(d, with_totals)
            res = check(d, d.parent / "shots")
            good = (res["passed"] == res["total"]) == with_totals
            ok &= good and r["ok"]
            print(f"{'OK ' if good else 'BAD'} reference {'with' if with_totals else 'WITHOUT'} totals: {res['passed']}/{res['total']}",
                  [c["id"] for c in res["checks"] if not c["pass"]])
        print("VALID" if ok else "INVALID")
        return
    f = ROOT / "benchmark" / "results" / "totals_dev" / (a.tier + (f"-{a.tag}" if a.tag else "") + ".json")
    if f.exists() and not a.force:                     # recorded already: never silently rerun (use --force and say so)
        print(f"already recorded: {f}")
        return
    from benchmark.run_benchmark import cut_network
    from neuron.brain.tiers import Tier
    net = cut_network()
    if net["internet_reachable"]:
        sys.exit("The network could not be cut off; refusing to run.")
    Tier(a.tier).enter()
    ws = ROOT / "benchmark" / "run" / "totals_dev" / (a.tier + (f"-{a.tag}" if a.tag else ""))
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    t0 = time.time()
    with open(ws.parent / f"{ws.name}.log", "w") as log:
        subprocess.run([sys.executable, "-m", "neuron.agent", TASK["request"], "--workspace", str(ws), "--tier", a.tier, "--max-seconds", "5400",
                        "--report", str(ws / ".neuron" / "final_report.json")], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, NEURON_MEMORY="off"), timeout=7200)
    rep = json.loads((ws / ".neuron" / "final_report.json").read_text()) if (ws / ".neuron" / "final_report.json").exists() else {}
    res = check(ws / "app", ws / "shots")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"task": TASK["id"], "tier": a.tier, "rerun_label": a.tag or None, "code_commit": commit, "network": net["method"], "seconds": round(time.time() - t0, 1),
           "solved": res["passed"] == res["total"], **res, "agent_verdict": rep.get("verdict"), "made_by": rep.get("made_by"),
           "model_calls": rep.get("model_calls"), "false_claim": rep.get("verdict") == "VERIFIED" and res["passed"] != res["total"]}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("solved", "passed", "total", "agent_verdict", "false_claim", "seconds")}))


if __name__ == "__main__":
    main()
