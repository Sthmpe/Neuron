"""NEURON on the code-repair dev set (not locked): network cut, memory off, the tier's memory limit.

  python3 -m benchmark.repair_dev.run --tier 4gb [--tag before]
Per project: solved (the project's own tests pass on a fresh copy of what NEURON left, and the tests themselves are
unchanged), time, who made the fix (search = a one-token change found without the model; model), model calls,
NEURON's own verdict and whether it claimed a fix that is not there. Results: benchmark/results/repair_dev/<tier>[-tag].json
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.run_benchmark import cut_network                # noqa: E402
from neuron.brain.tiers import Tier                            # noqa: E402

REQUEST = ("The tests of this project fail. Find the bug in the source code and fix it so the tests pass. "
           "Do not change the tests.")                          # the same wording as the locked bug tasks


def tests_of(d):
    return sorted(p for p in Path(d).rglob("*") if p.is_file() and ("tests" in p.relative_to(d).parts or p.name.endswith("_test.go")))


def check(project, original):
    work = Path(tempfile_dir()) / project.name
    shutil.copytree(project, work, ignore=shutil.ignore_patterns(".neuron", "tests/run"))
    cmd = ["go", "test", "./..."] if (work / "go.mod").exists() else ["make", "-s", "test"]
    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=300)
    same = all((project / t.relative_to(original)).read_text() == t.read_text() for t in tests_of(original))
    shutil.rmtree(work.parent, ignore_errors=True)
    return r.returncode == 0, same, (r.stdout + r.stderr)[-300:]


def tempfile_dir():
    import tempfile
    return tempfile.mkdtemp(prefix="repair-check-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="4gb")
    ap.add_argument("--tag", default="")
    ap.add_argument("--only")
    a = ap.parse_args()
    out = ROOT / "benchmark" / "results" / "repair_dev" / (a.tier + (f"-{a.tag}" if a.tag else "") + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    res = json.loads(out.read_text()) if out.exists() else {"rows": []}
    net = cut_network()
    if net["internet_reachable"]:
        sys.exit("The network could not be cut off; refusing to run.")
    Tier(a.tier).enter()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res.update(tier=a.tier, network=net["method"], code_commit=commit, started=res.get("started") or time.strftime("%Y-%m-%d %H:%M:%S"))
    done = {r["project"] for r in res["rows"]}
    scratch = ROOT / "benchmark" / "run" / "repair_dev" / (a.tier + (f"-{a.tag}" if a.tag else ""))
    for original in sorted((HERE / "workspaces").iterdir()):
        if original.name in done or (a.only and original.name != a.only):
            continue
        ws = scratch / original.name
        shutil.rmtree(ws, ignore_errors=True)
        shutil.copytree(original, ws)
        t0 = time.time()
        env = dict(os.environ, NEURON_MEMORY="off")
        with open(scratch / f"{original.name}.log", "w") as log:
            subprocess.run([sys.executable, "-m", "neuron.agent", REQUEST, "--workspace", str(ws), "--tier", a.tier,
                            "--max-seconds", "1800", "--report", str(ws / ".neuron" / "final_report.json")],
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=3600)
        rep = json.loads((ws / ".neuron" / "final_report.json").read_text()) if (ws / ".neuron" / "final_report.json").exists() else {}
        ok, same, tail = check(ws, original)
        solved = ok and same
        row = {"project": original.name, "solved": solved, "tests_pass": ok, "tests_unchanged": same, "seconds": round(time.time() - t0, 1),
               "made_by": rep.get("made_by"), "model_calls": rep.get("model_calls"), "agent_verdict": rep.get("verdict"),
               "false_claim": rep.get("verdict") == "VERIFIED" and not solved, "detail": "" if solved else tail}
        res["rows"].append(row)
        out.write_text(json.dumps(res, indent=1))
        print(json.dumps(row), flush=True)
    rows = res["rows"]
    res["summary"] = {"solved": sum(r["solved"] for r in rows), "of": len(rows), "false_claims": sum(r["false_claim"] for r in rows),
                      "seconds": round(sum(r["seconds"] for r in rows), 1)}
    out.write_text(json.dumps(res, indent=1))
    print("SUMMARY", res["summary"])


if __name__ == "__main__":
    main()
