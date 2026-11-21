"""Why each condition failed, from the evidence the runs left behind (examiner checks, the bare model's transcript and
report, NEURON's report). Used for the plain-English list of task types NEURON completes and the bare model fails.

  python3 -m benchmark.proof.explain            (Markdown)
Reads only counted runs (<tier>-run<k>.json) and their job folders under benchmark/run/proof/.
"""
import json
import py_compile
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "benchmark" / "results" / "proof"
RUNS = ROOT / "benchmark" / "run" / "proof"
COUNTED = re.compile(r"^(2gb|4gb)-run([123])\.json$")
KIND = {"app": "business apps and a small website built from a plain request", "bug": "finding and fixing a planted bug in a whole project",
        "feature": "adding a feature across files of an existing project", "document": "Excel, Word, PowerPoint and PDF-answer documents"}


def bare_reason(row, job):
    det = row.get("bare_detail") or {}
    failed = " ".join(row.get("failed_checks") or [])
    if det.get("ended") == "model errors":
        return "its model server was killed by the tier's memory limit (its own test runs count toward the same limit)"
    if row.get("examiner_error") and "zip" in (row["examiner_error"] or "").lower():
        return "it wrote text (usually a Python script) into the .xlsx/.docx/.pptx file instead of running a script that makes the file"
    if row["category"] == "app":
        app = job / "app"
        if "did not answer on port 8000" in failed:
            bad = []
            for f in list(app.glob("*.py")) + list(app.glob("pages/*.py")):
                try:
                    py_compile.compile(str(f), doraise=True)
                except py_compile.PyCompileError:
                    bad.append(f.name)
            schema = (app / "schema.py").read_text(errors="replace") if (app / "schema.py").exists() else ""
            why = ("files that are not valid Python: " + ", ".join(bad)) if bad else \
                  ("schema.py has no setup(app) function" if "def setup(" not in schema else "the app crashes on start")
            return f"the app does not start ({why})" + ("; it said DONE without running it" if row["claim"] == "DONE" else "")
        if "no field for" in failed:
            return "the app starts, but forms lack fields the request asked for (" + ", ".join(sorted(set(re.findall(r"no field for (\w+)", failed)))[:3]) + ")"
        return "the app starts, but some requested behaviour is missing or wrong"
    if row["category"] in ("bug", "feature"):
        if det.get("ended") == "the same reply 3 times in a row":
            return "it got stuck repeating the same reply, and the tests still fail"
        if row["claim"] == "DONE":
            return "it said DONE, but the tests (the project's own or the hidden ones) still fail"
        return "the tests still fail when its time ran out"
    if row["task"].startswith("D8"):
        return "its answers lacked the facts or the right page numbers" if (job / "answers.md").exists() else "it never wrote answers.md"
    return "the document misses what was asked: " + ", ".join(c.split(":")[0] for c in row.get("failed_checks", [])[:3])


def neuron_reason(row, job):
    failed = row.get("failed_checks") or []
    if row["claim"] == "PARTIAL" and row["category"] in ("bug",):
        return "its fix loop and small-change search did not find the fix (it reported PARTIAL, not a false success)"
    if row["category"] == "feature":
        return "NEURON had no capability for adding a feature; the request went to the bug fixer or the docstring writer"
    return ", ".join(c.split(":")[0] for c in failed[:3]) or row["claim"]


def main():
    rows = []
    for f in sorted(RES.glob("*.json")):
        m = COUNTED.match(f.name)
        if m:
            for r in json.loads(f.read_text())["rows"]:
                rows.append(dict(r, tier=m.group(1), run=int(m.group(2)), label=f.stem))
    by_task = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_task[(r["tier"], r["task"])][r["condition"]].append(r)
    print("## Where NEURON completes the task and the bare model does not\n")
    print("A task counts when NEURON solved it in at least 2 of its runs and the bare model in at most 1 (same tier).\n")
    for tier in ("2gb", "4gb"):
        lines = []
        for (t, task), c in sorted(by_task.items()):
            if t != tier or not c.get("neuron") or not c.get("bare"):
                continue
            n_ok, b_ok = sum(r["solved"] for r in c["neuron"]), sum(r["solved"] for r in c["bare"])
            if n_ok >= 2 and b_ok <= 1:
                reasons = Counter(bare_reason(r, RUNS / r["label"] / "bare" / task) for r in c["bare"] if not r["solved"])
                lines.append(f"- **{task}** ({c['neuron'][0]['category']}): NEURON {n_ok}/{len(c['neuron'])}, bare {b_ok}/{len(c['bare'])}. "
                             f"Bare model: {reasons.most_common(1)[0][0] if reasons else '-'}.")
        print(f"### {tier.upper()}\n")
        print("\n".join(lines) or "(none yet)")
        print()
    print("## Where the bare model does better\n")
    for tier in ("2gb", "4gb"):
        for (t, task), c in sorted(by_task.items()):
            if t == tier and c.get("neuron") and c.get("bare"):
                n_ok, b_ok = sum(r["solved"] for r in c["neuron"]), sum(r["solved"] for r in c["bare"])
                if b_ok > n_ok:
                    reasons = Counter(neuron_reason(r, RUNS / r["label"] / "neuron" / task) for r in c["neuron"] if not r["solved"])
                    print(f"- {tier.upper()} **{task}**: bare {b_ok}/{len(c['bare'])}, NEURON {n_ok}/{len(c['neuron'])}. NEURON: "
                          f"{reasons.most_common(1)[0][0] if reasons else '-'}.")
    print("\n## Most common failure reasons per condition\n")
    for cond, fn in (("bare", bare_reason), ("neuron", neuron_reason)):
        cnt = Counter(fn(r, RUNS / r["label"] / cond / r["task"]) for r in rows if r["condition"] == cond and not r["solved"])
        print(f"**{'Bare model' if cond == 'bare' else 'NEURON'}** ({sum(cnt.values())} failed runs):\n")
        for why, n in cnt.most_common(8):
            print(f"- {n} x {why}")
        print()


if __name__ == "__main__":
    main()
