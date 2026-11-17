"""Apply the model-choice rule written in PROGRESS.md before any result was seen:
score = bugs solved + (build checks passed / checks total) per build; highest wins; tie -> lower total time.
Activates each tier's winner with the model manager and writes benchmark/results/selection.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from neuron.brain.models import ModelManager   # noqa: E402

CANDIDATES = {"2gb": ["qwen2.5-coder-1.5b-q4", "qwen3.5-0.8b-q8"],
              "4gb": ["qwen2.5-coder-3b-q4", "qwen3.5-4b-q4", "gemma-4-e2b-q4", "granite-4.1-3b-q4"],
              "8gb": ["qwen2.5-coder-7b-q4", "qwen3.5-9b-q4", "gemma-4-e4b-q4", "granite-4.1-8b-q4"]}


def score(path):
    rows = json.loads(path.read_text())["rows"]
    s = sum(1.0 if r["solved"] else 0.0 for r in rows if r["type"] == "bug") + \
        sum(r["passed"] / r["total"] for r in rows if r["type"] == "build")
    return round(s, 3), round(sum(r["seconds"] for r in rows), 1), len(rows), \
        sum(r["solved"] for r in rows if r["type"] == "bug"), [f"{r['passed']}/{r['total']}" for r in rows if r["type"] == "build"]


def main():
    mgr, out = ModelManager(), {}
    for tier, models in CANDIDATES.items():
        table = []
        for m in models:
            f = ROOT / "benchmark" / "results" / "dev" / f"{tier}-full-sel-{m}.json"
            if not f.exists():
                table.append({"model": m, "missing": True})
                continue
            s, t, n, bugs, builds = score(f)
            table.append({"model": m, "score": s, "of": 12, "seconds": t, "tasks_run": n, "bugs_solved": bugs, "builds": builds})
        ok = [r for r in table if not r.get("missing") and r["tasks_run"] == 12]   # a model that did not fit has no result
        winner = sorted(ok, key=lambda r: (-r["score"], r["seconds"]))[0]["model"] if ok else None
        if winner:
            mgr.activate(tier, winner)
        out[tier] = {"candidates": table, "winner": winner}
        print(tier, "->", winner, table)
    (ROOT / "benchmark" / "results" / "selection.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
