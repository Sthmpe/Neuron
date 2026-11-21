"""Summarise the core-proof results: completion rate, time, peak memory, model calls and false claims per tier and
condition, per category, and per task (how many of the runs each condition solved).

  python3 -m benchmark.proof.summary            (prints Markdown; --json for the numbers)
Only counted runs are read (<tier>-run<k>.json without a tag); smoke and other labelled files are listed separately.
"""
import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "benchmark" / "results" / "proof"
COUNTED = re.compile(r"^(2gb|4gb)-run([123])\.json$")
TAGGED = re.compile(r"^(2gb|4gb)-run([123])-(.+)\.json$")


def load_tag(tag):
    """NEURON rows from a labelled rerun (e.g. after-fixes), to set beside the counted rows."""
    rows = []
    for f in sorted(RES.glob(f"*-{tag}.json")):
        m = TAGGED.match(f.name)
        if m and m.group(3) == tag:
            for r in json.loads(f.read_text())["rows"]:
                rows.append(dict(r, tier=m.group(1), run=int(m.group(2)), condition=r["condition"] + "-" + tag))
    return rows


def load():
    rows, files, other = [], [], []
    for f in sorted(RES.glob("*.json")):
        m = COUNTED.match(f.name)
        if not m:
            other.append(f.name)
            continue
        d = json.loads(f.read_text())
        files.append({"file": f.name, "rows": len(d["rows"]), "commit": d.get("code_commit", "")[:7], "lock": d.get("lock", "")[:12]})
        for r in d["rows"]:
            rows.append(dict(r, tier=m.group(1), run=int(m.group(2))))
    return rows, files, other


def stats(rows):
    if not rows:
        return {}
    secs = [r["seconds"] for r in rows]
    solved_secs = [r["seconds"] for r in rows if r["solved"]]
    return {"n": len(rows), "solved": sum(r["solved"] for r in rows),
            "rate": round(100 * sum(r["solved"] for r in rows) / len(rows), 1),
            "median_s": round(statistics.median(secs), 1), "mean_s": round(statistics.mean(secs), 1),
            "median_s_when_solved": round(statistics.median(solved_secs), 1) if solved_secs else None,
            "peak_mb_max": max(r["peak_mb"] for r in rows), "peak_mb_median": round(statistics.median(r["peak_mb"] for r in rows)),
            "model_calls_median": statistics.median(r["model_calls"] or 0 for r in rows),
            "false_claims": sum(bool(r["false_claim"]) for r in rows),
            "claims": sum(bool(r["false_claim"]) or (r["solved"] and r["claim"] in ("VERIFIED", "DONE")) for r in rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--with-tag", help="also show NEURON rows of this labelled rerun, e.g. after-fixes")
    a = ap.parse_args()
    rows, files, other = load()
    conds = ["bare", "neuron"]
    if a.with_tag:
        rows += load_tag(a.with_tag)
        conds.append("neuron-" + a.with_tag)
    by = defaultdict(list)
    for r in rows:
        by[(r["tier"], r["condition"])].append(r)
        by[(r["tier"], r["condition"], r["category"])].append(r)
    out = {"files": files, "other_files": other,
           "overall": {f"{t} {c}": stats(by[(t, c)]) for t in ("2gb", "4gb") for c in conds},
           "by_category": {f"{t} {c} {cat}": stats(by[(t, c, cat)]) for t in ("2gb", "4gb") for c in conds
                           for cat in ("app", "bug", "feature", "document")}}
    tasks = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        cell = tasks[r["task"]][f"{r['tier']} {r['condition']}"]
        cell[0] += r["solved"]
        cell[1] += 1
    out["by_task"] = {t: {k: f"{v[0]}/{v[1]}" for k, v in sorted(c.items())} for t, c in sorted(tasks.items())}
    if a.json:
        print(json.dumps(out, indent=1))
        return
    print("| Tier | Condition | Runs | Solved | Completion | Median time | Median time when solved | Peak RAM (max) | Median model calls | False claims |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for k, s in out["overall"].items():
        if s:
            t, c = k.split()
            print(f"| {t.upper()} | {'bare model' if c == 'bare' else 'NEURON' + (' (' + c[7:] + ', labelled)' if c != 'neuron' else '')} | {s['n']} | {s['solved']} | {s['rate']}% | {s['median_s']} s | "
                  f"{s['median_s_when_solved'] if s['median_s_when_solved'] is not None else '-'} s | {s['peak_mb_max']} MB | {s['model_calls_median']} | {s['false_claims']} |")
    print("\n| Tier | Category | " + " | ".join(conds) + " |\n|---|---|" + "---|" * len(conds))
    for t in ("2gb", "4gb"):
        for cat in ("app", "bug", "feature", "document"):
            cells = [out["by_category"][f"{t} {c} {cat}"] for c in conds]
            if any(cells):
                f = lambda s: f"{s['solved']}/{s['n']} ({s['rate']}%), median {s['median_s']} s" if s else "-"
                print(f"| {t.upper()} | {cat} | " + " | ".join(f(x) for x in cells) + " |")
    cols = [f"{t} {c}" for t in ("2gb", "4gb") for c in conds]
    print("\n| Task | " + " | ".join(cols) + " |\n|---|" + "---|" * len(cols))
    for t, c in out["by_task"].items():
        print(f"| {t} | " + " | ".join(c.get(k, "-") for k in cols) + " |")


if __name__ == "__main__":
    main()
