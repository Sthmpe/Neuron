"""Write the core-proof task set to disk: tasks/tasks.json, starting projects, hidden tests, app examiner steps and the
document inputs. Run once before the lock; the lock fingerprints everything it writes.

  python3 -m benchmark.proof.make_tasks
"""
import json
import shutil
from pathlib import Path

from .defs_apps import APPS
from .defs_bugs import BUGS
from .defs_docs import DOCS, make_sources
from .defs_features import FEATURES

HERE = Path(__file__).resolve().parent
OUT = HERE / "tasks"


def write_files(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "workspaces").mkdir(parents=True)
    tasks = []
    for a in APPS:
        (OUT / "specs").mkdir(exist_ok=True)
        (OUT / "specs" / f"{a['id']}.json").write_text(json.dumps(a["spec"], indent=1))
        tasks.append({"id": a["id"], "category": "app", "request": a["request"], "budget_s": a["budget_s"],
                      "spec": f"specs/{a['id']}.json", "workspace": None, "inputs": []})
    for t in BUGS + FEATURES:
        write_files(OUT / "workspaces" / t["id"], t["files"])
        write_files(OUT / "hidden" / t["id"], t["hidden"])
        tasks.append({"id": t["id"], "category": t["category"], "request": t["request"], "budget_s": t["budget_s"], "lang": t["lang"],
                      "workspace": f"workspaces/{t['id']}", "hidden": f"hidden/{t['id']}", "test_cmd": t["test_cmd"],
                      "hidden_cmd": t["hidden_cmd"], "original_tests": sorted(p for p in t["files"] if _is_test(p)), "inputs": []})
    make_sources(OUT / "sources")
    for d in DOCS:
        tasks.append({k: v for k, v in d.items()})
    (OUT / "tasks.json").write_text(json.dumps(tasks, indent=1))
    counts = {}
    for t in tasks:
        counts[t["category"]] = counts.get(t["category"], 0) + 1
    print(len(tasks), "tasks", counts)


def _is_test(rel):
    name = Path(rel).name
    return rel.startswith(("tests/", "test/")) or name.endswith("_test.go") or name.startswith("test_")


if __name__ == "__main__":
    main()
