"""Re-examine already delivered phase-5 work after a recorded lock amendment. No agent runs again; the original
score stays in the row and the new one is added next to it under the amendment's name.

  python3 -m benchmark.phase5.rescore --amendment 2 --task L12_long_docstrings
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.phase5.run import examine_task, load_tasks        # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--amendment", required=True)
    ap.add_argument("--task", required=True)
    a = ap.parse_args(argv)
    tasks, base = load_tasks("locked")
    task = next(t for t in tasks if t["id"] == a.task)
    for f in sorted((ROOT / "benchmark" / "results" / "phase5").glob("locked-*.json")):
        res = json.loads(f.read_text())
        for row in res["rows"]:
            if row["task"] != a.task:
                continue
            job = ROOT / "benchmark" / "run" / "phase5" / f.stem / a.task
            if not job.exists():
                print(f"{f.stem}: delivered files not found, not rescored")
                continue
            exam = examine_task(task, base, job, job.parent / f"{a.task}__rescore")
            row[f"after_amendment_{a.amendment}"] = {
                "solved": exam["total"] > 0 and exam["passed"] == exam["total"], "checks_passed": exam["passed"], "checks_total": exam["total"],
                "failed_checks": [c["id"] + (": " + str(c.get("detail"))[:160] if c.get("detail") else "") for c in exam["checks"] if not c["pass"]]}
            print(f"{f.stem} {a.task}: was {row['checks_passed']}/{row['checks_total']}, now {exam['passed']}/{exam['total']}")
        f.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
