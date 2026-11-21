"""What proposed amendment 1 would change (NOT applied to the counted results): the 12 kept deliveries whose app name
contains a page's word (all NEURON's A6 and A7) examined again with the fixed page opening. The locked examiner files
are not touched; the fixed copy is used from this folder.

  python3 -m benchmark.proof.amendments.reexamine_amendment1
"""
import json
import shutil
import tempfile
from pathlib import Path

import benchmark.proof.examine as ex

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AFFECTED = [("2gb-run1", "A6_gym_members"), ("2gb-run1", "A7_event_tickets"), ("2gb-run2", "A6_gym_members"),
            ("2gb-run2", "A7_event_tickets"), ("2gb-run3", "A6_gym_members"), ("2gb-run3", "A7_event_tickets"),
            ("4gb-run1", "A6_gym_members"), ("4gb-run1", "A7_event_tickets"), ("4gb-run2", "A6_gym_members"),
            ("4gb-run2", "A7_event_tickets"), ("4gb-run3", "A6_gym_members"), ("4gb-run3", "A7_event_tickets")]


def main():
    fixed = Path(tempfile.mkdtemp(prefix="amend1-"))
    shutil.copy(HERE / "app_exam_amendment1.js", fixed / "app_exam.js")
    ex.HERE = fixed                                  # examine_app runs HERE/app_exam.js; tasks stay the locked ones
    tasks = {t["id"]: t for t in json.loads((ex.TASKS / "tasks.json").read_text())}
    out = []
    for label, tid in AFFECTED:
        rows = json.loads((ROOT / "benchmark" / "results" / "proof" / f"{label}.json").read_text())["rows"]
        locked = next(r for r in rows if r["task"] == tid and r["condition"] == "neuron")
        r = ex.examine(tasks[tid], ROOT / "benchmark" / "run" / "proof" / label / "neuron" / tid)
        out.append({"run": label, "task": tid, "locked_examiner": f"{locked['checks_passed']}/{locked['checks_total']}",
                    "with_amendment_1": f"{r['passed']}/{r['total']}", "solved_with_amendment_1": r["solved"],
                    "still_failing": [c["id"] + ": " + str(c.get("detail", ""))[:120] for c in r["checks"] if not c["pass"]]})
        print(out[-1]["run"], tid, out[-1]["locked_examiner"], "->", out[-1]["with_amendment_1"], out[-1]["still_failing"][:2], flush=True)
    (HERE / "amendment1_effect.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
