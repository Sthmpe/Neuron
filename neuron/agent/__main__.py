"""Run NEURON's general agent on a goal. Running the same command again resumes the job from disk.

  python3 -m neuron.agent "Make an Excel summary of this data" --workspace ~/jobs/sales --attach sales.csv --tier 4gb
  python3 -m neuron.agent --capabilities          # what this machine can do, and what is missing
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from ..brain.models import ModelManager, ModelRunner
from ..brain.sandbox import Sandbox
from .capability import default_registry
from .loop import Agent, Job


def main(argv=None):
    ap = argparse.ArgumentParser(description="NEURON general agent")
    ap.add_argument("goal", nargs="?")
    ap.add_argument("--workspace", default="job")
    ap.add_argument("--attach", nargs="*", default=[])
    ap.add_argument("--tier", default="4gb")
    ap.add_argument("--model", help="use this installed model for every role")
    ap.add_argument("--max-seconds", type=float)
    ap.add_argument("--capabilities", action="store_true")
    ap.add_argument("--report", help="also write the final report to this JSON file")
    a = ap.parse_args(argv)
    reg = default_registry()
    if a.capabilities:
        for c in reg.report():
            print(f"{c['name']:<24} {'ready' if c['available'] else 'MISSING ' + ', '.join(c['missing'])}  - {c['purpose']}")
        return 0
    ws = Path(a.workspace)
    ws.mkdir(parents=True, exist_ok=True)
    attached = []
    for f in a.attach:                        # attachments are copied into the job, so the job is self-contained
        dst = ws / "inputs" / Path(f).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f, dst)
        attached.append(str(dst))
    overrides = {r: a.model for r in ("planner", "reviewer", "builder")} if a.model else {}
    runner = ModelRunner(ModelManager(), a.tier, overrides=overrides, log_dir=ws / ".neuron")
    from ..memory import default_memory, memory_enabled
    memory = default_memory() if memory_enabled() else None          # evaluations run with NEURON_MEMORY=off
    job = Job(ws, runner, Sandbox(timeout=120, mem_mb=1024, toolchains=True), registry=reg, log=lambda m: print(m, flush=True),
              memory=memory)
    try:
        rep = Agent(job).run(a.goal or "", attached, max_seconds=a.max_seconds)
    finally:
        runner.unload()
    print(json.dumps(rep, indent=1))
    if a.report:
        Path(a.report).write_text(json.dumps(rep, indent=1))
    return 0 if rep["verdict"] == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
