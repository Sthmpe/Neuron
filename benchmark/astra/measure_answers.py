"""Measure one arm of the ordinary-answer development experiment inside an offline cgroup v2."""
import argparse
import hashlib
import json
import os
import platform
import socket
import sys
import tempfile
import time
from pathlib import Path


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def conditions():
    rel = next(line[3:] for line in Path("/proc/self/cgroup").read_text().splitlines()
               if line.startswith("0::"))
    group = Path("/sys/fs/cgroup") / rel.lstrip("/")
    limits = {f: (group / f).read_text().strip() for f in ("memory.max", "memory.swap.max")}
    interfaces = sorted(name for _, name in socket.if_nameindex())
    if limits != {"memory.max": "2147483648", "memory.swap.max": "0"} or interfaces != ["lo"]:
        raise RuntimeError(f"required offline 2 GiB tier unavailable: {limits}, {interfaces}")
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=2):
            pass
    except OSError as err:
        probe = str(err)
    else:
        raise RuntimeError("external connection succeeded")
    return group, {"cgroup": rel, **limits, "interfaces": interfaces, "external_probe": probe,
                   "kernel": platform.release(), "python": platform.python_version()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="git archive with a REVISION file")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="a new file for this attempt")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    group, environment = conditions()
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    from neuron.agent.loop import Agent, Job
    from neuron.brain.models import ModelManager, ModelRunner
    from neuron.brain.sandbox import Sandbox

    cases = Path(__file__).with_name("questions.json")
    tasks = json.loads(cases.read_text())
    frozen = json.loads((source / "model_manifests/frozen.json").read_text())["tiers"]["2gb"]
    if file_hash(args.model) != frozen["sha256"]:
        raise ValueError("frozen model checksum mismatch")
    binary = Path(os.environ["NEURON_LLAMA_BIN"])
    metadata = {"label": args.label, "source_commit": (source / "REVISION").read_text().strip(),
                "cases_sha256": file_hash(cases), "driver_sha256": file_hash(Path(__file__)),
                "model": frozen["id"], "model_sha256": frozen["sha256"], "llama_server_sha256": file_hash(binary),
                "context": frozen["context_tokens"], "seed": 71, "threads": 1, "environment": environment}
    rows = []
    journal = args.output.with_suffix(".jsonl")
    with args.output.open("x") as record, journal.open("x") as checkpoints, tempfile.TemporaryDirectory() as temp:
        def checkpoint(entry):
            checkpoints.write(json.dumps(entry) + "\n")
            checkpoints.flush()
            os.fsync(checkpoints.fileno())

        checkpoint({"start": metadata})
        root = Path(temp)
        log_dir = args.output.parent / (args.output.stem + "-logs")
        log_dir.mkdir()
        mgr = ModelManager(root / "models")
        (mgr.store / frozen["file"]).symlink_to(args.model.resolve())
        mgr.install({**frozen, "request_extra": {**frozen["request_extra"], "seed": 71}}, verify=False)
        mgr.activate("2gb", frozen["id"])
        runner = ModelRunner(mgr, "2gb", threads=1, log_dir=log_dir)
        started = time.monotonic()
        try:
            runner.client("builder")
            for case in tasks:
                job = Job(root / case["id"], runner, Sandbox(timeout=120, mem_mb=1024, toolchains=True),
                          log=lambda msg: print(msg, flush=True))
                step = time.monotonic()
                report = Agent(job).run(case["question"])
                seconds = time.monotonic() - step
                path = job.workspace / "answer.md"
                rows.append({"id": case["id"], "verdict": report["verdict"], "kind": report["kind"],
                             "answer": path.read_text().strip() if path.exists() else None,
                             "task_status": report["tasks"], "made_by": job.state.task("answer").get("made_by"),
                             "model_calls": report["model_calls"], "tokens": report["tokens"],
                             "online_calls": report["online_calls"], "seconds": round(seconds, 3),
                             "evidence": job.state.lines("evidence.jsonl")})
                checkpoint({"row": rows[-1], "elapsed_seconds": round(time.monotonic() - started, 3),
                            "peak_bytes_so_far": int((group / "memory.peak").read_text())})
                print(case["id"], report["verdict"], round(seconds, 3), flush=True)
        finally:
            runner.unload()
        elapsed = time.monotonic() - started
        raw = {**metadata, "seconds": round(elapsed, 3), "peak_bytes": int((group / "memory.peak").read_text()),
               "events": (group / "memory.events").read_text().splitlines(), "loads": runner.loads,
               "load_seconds": round(runner.load_seconds, 3), "rows": rows}
        json.dump(raw, record, indent=2)
        record.write("\n")
        print("Completed", raw["label"], raw["seconds"], raw["peak_bytes"], flush=True)


if __name__ == "__main__":
    main()
