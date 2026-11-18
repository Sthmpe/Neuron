"""Step 7 reference sites: NEURON builds each from the owner's request; screenshots at phone, tablet and desktop width.

  python3 -m benchmark.reference_sites.run --tier 8gb [--only bakery]
For each site: the agent's own report, the design checks, an independent check of the words on the finished page
(neuron.design.content: nothing invented, no template text, filler, repetition or duplicated sections), broken links
or pictures, sideways scrolling. Screenshots: docs/screens/reference/<site>-<phone|tablet|desktop>.png.
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
from neuron.brain.sandbox import Sandbox                      # noqa: E402
from neuron.design import content                             # noqa: E402

SHOTS = ROOT / "docs" / "screens" / "reference"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="8gb")
    ap.add_argument("--only")
    ap.add_argument("--shots-only", action="store_true", help="screenshot the sites already built (after photos arrived)")
    a = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = ROOT / "benchmark" / "results" / "reference_sites.json"
    results = json.loads(out.read_text()) if out.exists() else {}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    for t in json.loads((HERE / "requests.json").read_text()):
        if a.only and t["id"] != a.only:
            continue
        ws = ROOT / "benchmark" / "run" / "reference_sites" / t["id"]
        t0 = time.time()
        rep = {}
        if not a.shots_only:
            shutil.rmtree(ws, ignore_errors=True)
            ws.mkdir(parents=True)
            with open(ws.parent / f"{t['id']}.log", "w") as log:
                subprocess.run([sys.executable, "-m", "neuron.agent", t["request"], "--workspace", str(ws), "--tier", a.tier,
                                "--max-seconds", "5400", "--report", str(ws / ".neuron" / "final_report.json")],
                               cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=7200)
        f = ws / ".neuron" / "final_report.json"
        rep = json.loads(f.read_text()) if f.exists() else {}
        app = ws / "app"
        srv = Sandbox(timeout=900, mem_mb=256).start(["python3", "app.py"], app) if (app / "app.py").exists() else None
        page = {}
        if srv and srv.wait_ready("/"):
            env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
            r = subprocess.run(["node", str(HERE / "shots.js"), srv.url, str(SHOTS / t["id"])], capture_output=True, text=True, env=env, timeout=300)
            page = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr[-300:]}
        if srv:
            srv.stop()
        text = page.pop("text", "")
        words = content.check([(f"line{i}", ln) for i, ln in enumerate(text.splitlines()) if ln.strip()], t["request"])
        pics = json.loads((app / "images.json").read_text())["slots"] if (app / "images.json").exists() else []
        results[t["id"]] = {
            "request": t["request"], "tier": a.tier, "code_commit": commit, "built_at": time.strftime("%Y-%m-%d %H:%M"),
            "seconds": round(time.time() - t0, 1) if not a.shots_only else results.get(t["id"], {}).get("seconds"),
            "agent_verdict": rep.get("verdict") or results.get(t["id"], {}).get("agent_verdict"),
            "not_done": rep.get("not_done") or results.get(t["id"], {}).get("not_done"),
            "model_calls": rep.get("model_calls") or results.get(t["id"], {}).get("model_calls"),
            "page_word_problems": [f"{w['kind']}: {w['detail']}" for w in words],
            "pictures": {s["slot"]: s["status"] for s in pics},
            "overflow_px": {k: v.get("overflow") for k, v in page.items() if isinstance(v, dict) and "overflow" in v},
            "broken": {k: v.get("broken") for k, v in page.items() if isinstance(v, dict) and v.get("broken")},
            "screenshots": [f"docs/screens/reference/{t['id']}-{d}.png" for d in ("phone", "tablet", "desktop")]}
        out.write_text(json.dumps(results, indent=1))
        print(t["id"], json.dumps({k: results[t["id"]][k] for k in ("agent_verdict", "page_word_problems", "pictures", "overflow_px", "seconds")}), flush=True)


if __name__ == "__main__":
    main()
