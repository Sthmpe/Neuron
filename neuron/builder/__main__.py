"""Command line for the builder. A killed run is continued by running the same command again.

  python3 -m neuron.builder build --project DIR --request-file FILE --tier 2gb [--condition full|base]
  python3 -m neuron.builder fix   --project DIR --tier 2gb
  optional: --model ID (all roles) or --role-model planner=ID (repeatable), --max-seconds N, --summary FILE
"""
import argparse
import json
import sys
from pathlib import Path

from ..brain.models import ModelManager, ModelRunner
from ..brain.sandbox import Sandbox
from .bugfix import fix_project
from .build import build_base, build_full


def main(argv=None):
    ap = argparse.ArgumentParser(description="NEURON builder")
    ap.add_argument("cmd", choices=["build", "fix"])
    ap.add_argument("--project", required=True)
    ap.add_argument("--request-file")
    ap.add_argument("--tier", required=True)
    ap.add_argument("--condition", choices=["full", "base"], default="full")
    ap.add_argument("--model")
    ap.add_argument("--role-model", action="append", default=[])
    ap.add_argument("--max-seconds", type=float)
    ap.add_argument("--summary")
    ap.add_argument("--port", type=int, default=18080)
    a = ap.parse_args(argv)
    overrides = {r: a.model for r in ("planner", "reviewer", "builder")} if a.model else {}
    overrides.update(dict(x.split("=", 1) for x in a.role_model))
    runner = ModelRunner(ModelManager(), a.tier, port=a.port, overrides=overrides,
                         log_dir=Path(a.project).parent)
    sandbox = Sandbox(timeout=60, mem_mb=256)
    log = lambda msg: print(msg, flush=True)
    try:
        if a.cmd == "build":
            request = Path(a.request_file).read_text().strip()
            fn = build_full if a.condition == "full" else build_base
            summary = fn(a.project, request, runner, sandbox, log=log, max_seconds=a.max_seconds)
        else:
            summary = fix_project(a.project, runner, sandbox, log=log, max_seconds=a.max_seconds)
    finally:
        runner.unload()
    if a.summary:
        Path(a.summary).write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "history"})[:600], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
