"""Write benchmark/results/phase5_summary.md from the phase-5 result files (official runs first, labelled reruns after)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "benchmark" / "results" / "phase5"


def score(row):
    """The score after any recorded lock amendment (the original is kept in the row)."""
    for k in sorted((k for k in row if k.startswith("after_amendment_")), reverse=True):
        a = row[k]
        return a["solved"], a["checks_passed"], a["checks_total"], k.replace("after_amendment_", "amendment ")
    return row["solved"], row["checks_passed"], row["checks_total"], ""


def table(f):
    d = json.loads(f.read_text())
    lines = [f"### {f.stem}", "", f"Model: {d.get('model', {}).get('builder')} | tier limit {d.get('tier_limit_mb')} MB | code "
             f"{(d.get('code_commit') or '')[:10]} | network: {d.get('network')}", "",
             "| Task | Solved | Checks | Minutes | Peak MB | Model calls | Agent said | False claim | Made by |", "|---|---|---|---|---|---|---|---|---|"]
    solved = 0
    for r in d["rows"]:
        ok, p, t, note = score(r)
        solved += ok
        mins = round(r["seconds"] / 60, 1) if isinstance(r.get("seconds"), (int, float)) else "?"
        claim = "yes" if (r.get("agent_verdict") == "VERIFIED" and not ok) else ""
        made = ", ".join(f"{k} {v}" for k, v in (r.get("made_by") or {}).items())
        lines.append(f"| {r['task']} | {'yes' if ok else 'no'} | {p}/{t}{' (' + note + ')' if note else ''} | {mins} | {r.get('peak_mb') or '?'} | "
                     f"{r.get('model_calls') if r.get('model_calls') is not None else '?'} | {r.get('agent_verdict')} | {claim} | {made} |")
    lines += ["", f"Solved {solved} of {len(d['rows'])}.", ""]
    fails = [(r["task"], score(r)) for r in d["rows"] if not score(r)[0]]
    if fails:
        lines.append("What failed (examiner's words):")
        for r in d["rows"]:
            if not score(r)[0]:
                fc = r.get(max((k for k in r if k.startswith("after_amendment_")), default="", key=str), {}).get("failed_checks") if any(k.startswith("after_amendment_") for k in r) else r["failed_checks"]
                lines.append(f"- {r['task']}: " + "; ".join(str(x).replace("\n", " ")[:150] for x in (fc or [])[:3]))
        lines.append("")
    return lines, solved, len(d["rows"])


def main():
    out = ["# Phase 5: locked evaluation results", "",
           "12 tasks locked on 2026-11-17 before the system was built or tuned on them (`benchmark/phase5/LOCKED.md`, three",
           "recorded examiner amendments). Network off, every process inside the tier's memory limit, results judged only by",
           "independent examiners. Official runs are the first run per tier; 'rerun' files are labelled reruns after fixing",
           "NEURON bugs that an official run exposed, and are not a clean held-out measurement.", ""]
    summary = []
    for f in sorted(RES.glob("locked-*.json"), key=lambda p: ("rerun" in p.stem, p.stem)):
        lines, s, n = table(f)
        out += lines
        summary.append((f.stem, s, n))
    out = out[:7] + ["| Run | Solved |", "|---|---|"] + [f"| {a} | {s} of {n} |" for a, s, n in summary] + [""] + out[7:]
    (ROOT / "benchmark" / "results" / "phase5_summary.md").write_text("\n".join(out) + "\n")
    print("\n".join(f"{a}: {s}/{n}" for a, s, n in summary))


if __name__ == "__main__":
    main()
