"""Does knowledge memory help on a second, similar task? Same model, same task, with and without memory.

  python3 -m benchmark.memory_effect --tier 4gb --repeats 3

Task A (learn): dev project cpp_grades, a boundary bug (`mark > 40` where 40 must pass).
Task B (measure): dev project cpp_tickets, a similar boundary bug (`age > 65` where 65 rides free).
  without: B with an empty memory
  with:    A first (its verified fix is saved to a fresh memory), then B with that memory
Both are dev projects written for development, not locked or benchmark data. Each condition is repeated; results go to
benchmark/results/memory_effect.json with success, model calls, tokens, seconds and fix attempts for every run of B.
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.run_benchmark import cut_network               # noqa: E402
from neuron.agent.loop import Agent, Job                       # noqa: E402
from neuron.brain.models import ModelManager, ModelRunner      # noqa: E402
from neuron.brain.sandbox import Sandbox                       # noqa: E402
from neuron.brain.tiers import Tier                            # noqa: E402
from neuron.memory import Memory                               # noqa: E402

DEV = ROOT / "benchmark" / "phase5" / "dev" / "workspaces"
REQUEST = "The tests of this project fail. Find the bug in the source code and fix it so the tests pass. Do not change the tests."


def run_job(project, runner, memory):
    ws = Path(tempfile.mkdtemp(prefix="memfx-")) / project
    shutil.copytree(DEV / project, ws)
    job = Job(ws, runner, Sandbox(timeout=120, mem_mb=1024, toolchains=True), log=lambda *_: None, memory=memory)
    t0 = time.time()
    rep = Agent(job).run(REQUEST)
    fix = next((t for t in json.loads((ws / ".neuron" / "job" / "plan.json").read_text()) if t["id"] == "fix"), {})
    return {"verdict": rep["verdict"], "seconds": round(time.time() - t0, 1), "model_calls": rep["model_calls"], "tokens": rep["tokens"],
            "fix_attempts": len(fix.get("attempts", [])), "memory_notes_offered": len(job.memory_notes)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="4gb")
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args(argv)
    if cut_network()["internet_reachable"]:
        sys.exit("The network could not be cut off; refusing to run.")
    tier = Tier(a.tier).enter()
    mgr = ModelManager()
    runner = ModelRunner(mgr, a.tier, log_dir=ROOT / "benchmark" / "run" / "memory_effect")
    out = {"tier": a.tier, "model": mgr.active(a.tier, "builder"), "repeats": a.repeats, "without": [], "with": [], "learn": []}
    out_file = ROOT / "benchmark" / "results" / "memory_effect.json"
    try:
        for i in range(a.repeats):
            out["without"].append(run_job("cpp_tickets", runner, Memory(Path(tempfile.mkdtemp()) / "k.db")))
            mem = Memory(Path(tempfile.mkdtemp()) / "k.db")
            out["learn"].append(run_job("cpp_grades", runner, mem) | {"notes_saved": mem.stats()["notes"]})
            out["with"].append(run_job("cpp_tickets", runner, mem) | {"notes_helped": mem.stats()["helped"]})
            out_file.write_text(json.dumps(out, indent=1))
            print(f"repeat {i + 1}: without {out['without'][-1]} | learn {out['learn'][-1]} | with {out['with'][-1]}", flush=True)
    finally:
        runner.unload()
        tier.leave()
    for cond in ("without", "with"):
        runs = out[cond]
        out[f"{cond}_summary"] = {"solved": sum(r["verdict"] == "VERIFIED" for r in runs), "of": len(runs),
                                  "mean_seconds": round(sum(r["seconds"] for r in runs) / len(runs), 1),
                                  "mean_model_calls": round(sum(r["model_calls"] for r in runs) / len(runs), 2),
                                  "mean_fix_attempts": round(sum(r["fix_attempts"] for r in runs) / len(runs), 2)}
    out_file.write_text(json.dumps(out, indent=1))
    print("MEMORY-EFFECT-DONE", json.dumps({k: out[k] for k in ("without_summary", "with_summary")}))


if __name__ == "__main__":
    main()
