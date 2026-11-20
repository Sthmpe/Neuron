"""Easy work: is NEURON ever meaningfully slower than the bare model? (internal tasks; no public benchmarks)

  python3 -m benchmark.easy.run --tier 2gb
Same process, same loaded model, same machine, network cut, memory off. For each item, in alternating order: the bare
model (one call, the request as the only message) and full NEURON (Agent.run on the same request). Recorded: wall time,
model calls, and whether the answer is right (facts: an expected word; calculations: the number within 0.5%; writing:
non-empty, at least 8 words and an expected word). Results: benchmark/results/easy/<tier>.json
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["NEURON_MEMORY"] = "off"
ITEMS = json.loads((Path(__file__).parent / "items.json").read_text())


def right(item, text):
    t = (text or "").lower().replace(",", "")
    if item["kind"] == "calc":
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t)]
        return any(abs(n - item["number"]) <= 0.005 * abs(item["number"]) for n in nums)
    ok = any(w in t for w in item["expect"])
    return ok and (item["kind"] != "write" or len(t.split()) >= 8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="2gb")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    from benchmark.run_benchmark import cut_network
    from neuron.agent.loop import Agent, Job
    from neuron.brain.models import ModelManager, ModelRunner
    from neuron.brain.sandbox import Sandbox
    from neuron.brain.tiers import Tier
    net = cut_network()
    if net["internet_reachable"]:
        sys.exit("The network could not be cut off; refusing to run.")
    Tier(a.tier).enter()
    runner = ModelRunner(ModelManager(), a.tier, log_dir=Path(tempfile.mkdtemp()))
    client = runner.client("builder")
    client.chat([{"role": "user", "content": "Say ok."}], max_tokens=5)        # warm-up, not measured
    sandbox = Sandbox(timeout=60, mem_mb=512, toolchains=False)
    rows = []
    for i, item in enumerate(ITEMS):
        order = ("bare", "neuron") if i % 2 == 0 else ("neuron", "bare")
        row = {"id": item["id"], "kind": item["kind"]}
        for cond in order:
            t0 = time.time()
            if cond == "bare":
                r = client.chat([{"role": "user", "content": item["q"]}], max_tokens=700, temperature=0.2)
                text, calls = r.text, 1
            else:
                ws = Path(tempfile.mkdtemp()) / "job"
                job = Job(ws, runner, sandbox, log=lambda *_: None)
                job.online = False
                rep = Agent(job).run(item["q"])
                text = (ws / "answer.md").read_text() if (ws / "answer.md").exists() else ""
                calls = rep.get("model_calls", 0)
                row["neuron_verdict"] = rep.get("verdict")
                row["neuron_fast"] = job.state.goal().get("fast")
                shutil.rmtree(ws.parent, ignore_errors=True)
            row[cond] = {"seconds": round(time.time() - t0, 2), "calls": calls, "right": right(item, text), "text": text[:300]}
        rows.append(row)
        print(json.dumps({k: (v if not isinstance(v, dict) else {x: v[x] for x in ('seconds', 'calls', 'right')}) for k, v in row.items()}), flush=True)
    runner.unload()
    summ = {}
    for cond in ("bare", "neuron"):
        secs = [r[cond]["seconds"] for r in rows]
        summ[cond] = {"right": sum(r[cond]["right"] for r in rows), "of": len(rows), "total_seconds": round(sum(secs), 1),
                      "median_seconds": round(statistics.median(secs), 2), "model_calls": sum(r[cond]["calls"] for r in rows)}
        for k in ("fact", "calc", "write"):
            summ[cond][k] = sum(r[cond]["right"] for r in rows if r["kind"] == k)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"tier": a.tier, "rerun_label": a.tag or None, "code_commit": commit, "network": net["method"], "summary": summ, "rows": rows,
           "slowdown_ratio": round(summ["neuron"]["total_seconds"] / max(0.01, summ["bare"]["total_seconds"]), 2)}
    f = ROOT / "benchmark" / "results" / "easy" / (a.tier + (f"-{a.tag}" if a.tag else "") + ".json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, indent=1))
    print("SUMMARY", json.dumps(summ), "ratio", out["slowdown_ratio"])


if __name__ == "__main__":
    main()
