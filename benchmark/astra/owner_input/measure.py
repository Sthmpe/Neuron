"""Run one arm of the paired phone experiment in the offline 2 GiB guest."""
import argparse
import json
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_answers import conditions, file_hash


def exercise(phone, case):
    def call(method, path, body=None):
        status, data = phone.call(method, path, body)
        if not 200 <= status < 300:
            raise RuntimeError(f"{method} {path} returned {status}: {data}")
        return data

    start = time.monotonic()
    jid = call("POST", "/api/jobs", {"goal": case["goal"]})["id"]
    url = "/api/jobs/" + jid
    call("POST", url + "/start")
    turns, supplied, states = [], set(), []
    while True:
        job = call("GET", url)
        if job["id"] != jid:
            raise RuntimeError("lost original job")
        if not states or states[-1] != job["status"]:
            states.append(job["status"])
        if job["status"] == "waiting_input":
            prompt = job["input_request"]
            matches = [i for i, field in enumerate(case["fields"]) if i not in supplied
                       and re.search(field["prompt"], prompt["question"], re.I)]
            turn = {"question": prompt["question"], "interim_answer": job.get("answer"),
                    "interim_outputs": [f["path"] for f in job["outputs"]], "fields": matches}
            turns.append(turn)
            if not matches or time.monotonic() - start > 240:
                break
            turn["owner"] = " ".join(case["fields"][i]["reply"] for i in matches)
            call("POST", url + "/input", {"id": prompt["id"], "answer": turn["owner"]})
            supplied.update(matches)
        elif job["status"] not in ("running", "queued"):
            break
        if time.monotonic() - start > 240:
            raise TimeoutError(f"job still running: {case['id']}")
        time.sleep(0.15)
    report = job.get("report") or {}
    return {"id": case["id"], "job": jid, "thread_jobs": [t["id"] for t in job["thread"]],
            "states": states, "turns": turns, "status": job["status"], "answer": job["answer"],
            "verdict": report.get("verdict"), "usage": report.get("usage_all_sessions"),
            "seconds": round(time.monotonic() - start, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    group, environment = conditions()
    sys.path.insert(0, str(args.source.resolve()))
    from benchmark.release.retest import Phone
    from neuron.brain.models import ModelManager, ModelRunner
    from neuron.brain.sandbox import Sandbox
    from neuron.server.app import serve

    os.environ["NEURON_MEMORY"] = "off"
    fixture = Path(__file__).with_name("questions.json")
    frozen = json.loads((args.source / "model_manifests/frozen.json").read_text())["tiers"]["2gb"]
    if file_hash(args.model) != frozen["sha256"]:
        raise ValueError("unexpected model weights")
    record = {"label": args.label, "revision": (args.source / "REVISION").read_text().strip(),
              "fixture_sha256": file_hash(fixture), "driver_sha256": file_hash(Path(__file__)),
              "model": frozen["id"], "model_sha256": frozen["sha256"],
              "server_sha256": file_hash(Path(os.environ["NEURON_LLAMA_BIN"])),
              "seed": 71, "threads": 1, "context": frozen["context_tokens"], "environment": environment, "rows": []}
    with args.output.open("x") as result, args.output.with_suffix(".jsonl").open("x") as journal, tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        mgr = ModelManager(root / "models")
        (mgr.store / frozen["file"]).symlink_to(args.model.resolve())
        mgr.install({**frozen, "request_extra": {**frozen["request_extra"], "seed": 71}}, verify=False)
        mgr.activate("2gb", frozen["id"])
        logs = args.output.parent / (args.output.stem + "-logs")
        logs.mkdir()
        runner = ModelRunner(mgr, "2gb", threads=1, log_dir=logs)
        start = time.monotonic()
        server = serve(root, "127.0.0.1", 0, lambda: runner, lambda: Sandbox(timeout=120, mem_mb=1024, toolchains=True),
                       log=lambda msg: print(msg, flush=True))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            runner.client("builder")
            phone = Phone(f"http://127.0.0.1:{server.server_address[1]}")
            if phone.call("POST", "/api/pair", {"code": server.neuron["pairing"].new_code()})[0] != 200:
                raise RuntimeError("phone pairing failed")
            for case in json.loads(fixture.read_text()):
                row = exercise(phone, case)
                record["rows"].append(row)
                journal.write(json.dumps(row) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
                print(case["id"], row["status"], row["seconds"], flush=True)
        finally:
            jobs = server.neuron["jobs"]
            jobs.stopping = True
            jobs.wake.set()
            server.shutdown()
            server.server_close()
            thread.join()
            jobs.thread.join()
            runner.unload()
        record.update(seconds=round(time.monotonic() - start, 3), peak_bytes=int((group / "memory.peak").read_text()),
                      events=(group / "memory.events").read_text().splitlines(), loads=runner.loads,
                      load_seconds=round(runner.load_seconds, 3))
        json.dump(record, result, indent=2)
        result.write("\n")
        print("Completed", record["label"], record["seconds"], record["peak_bytes"], flush=True)


if __name__ == "__main__":
    main()
