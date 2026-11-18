"""Resume the reference sites' waiting photo steps, politely, until every picture is found or the tries run out.

  python3 -m benchmark.reference_sites.photos [--rounds 12 --every 900]
Each round: for every site with an 'Image needed' slot whose wait is over, the same NEURON job is resumed (the photo
step needs no model), then the screenshots are taken again if a photo arrived. Rounds that overlap a running
scorecard are noted in benchmark/overlap.log (screenshots use a little CPU for about a minute).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--every", type=int, default=900)
    a = ap.parse_args()
    reqs = {t["id"]: t["request"] for t in json.loads((HERE / "requests.json").read_text())}
    log = ROOT / "benchmark" / "reference_sites" / "photos.log"
    for rnd in range(a.rounds):
        left = 0
        for sid, request in reqs.items():
            ws = ROOT / "benchmark" / "run" / "reference_sites" / sid
            man = ws / "app" / "images.json"
            if not man.exists():
                continue
            before = json.loads(man.read_text())["slots"]
            plan = json.loads((ws / ".neuron" / "job" / "plan.json").read_text()) if (ws / ".neuron" / "job" / "plan.json").exists() else []
            wait = next((t.get("not_before", 0) for t in plan if t["id"] == "images" and t["status"] == "waiting_network"), 0)
            if all(s["status"] != "needed" for s in before) or wait > time.time():
                left += any(s["status"] == "needed" for s in before)
                continue
            busy = subprocess.run(["pgrep", "-f", "benchmark.scorecard.run"], capture_output=True).returncode == 0
            subprocess.run([sys.executable, "-m", "neuron.agent", request, "--workspace", str(ws), "--tier", "8gb",
                            "--report", str(ws / ".neuron" / "final_report.json")], cwd=ROOT, capture_output=True, timeout=1800)
            after = json.loads(man.read_text())["slots"]
            got = [s["slot"] for s in after if s["status"] == "licensed" and s not in before]
            changed = [s["slot"] for s, b in zip(after, before) if s["status"] != b["status"] or (s.get("source") or {}).get("page") != (b.get("source") or {}).get("page")]
            if changed:
                subprocess.run([sys.executable, "-m", "benchmark.reference_sites.run", "--shots-only", "--only", sid], cwd=ROOT,
                               capture_output=True, timeout=900)
                if busy:
                    with open(ROOT / "benchmark" / "overlap.log", "a") as f:
                        f.write(f"[{time.strftime('%F %T')}] reference-site screenshots ({sid}) for about a minute while the scorecard ran\n")
            left += any(s["status"] == "needed" for s in after)
            with open(log, "a") as f:
                f.write(f"[{time.strftime('%F %T')}] round {rnd + 1} {sid}: {json.dumps({s['slot']: s['status'] for s in after})}"
                        f"{' (screenshots retaken)' if changed else ''}\n")
        if not left:
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()
