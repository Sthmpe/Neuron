"""Write SCORECARD.md from the recorded scorecard runs (benchmark/results/scorecard/*.json).

  python3 -m benchmark.scorecard.report
Runs that have not finished are listed as running or not started; nothing is estimated or filled in.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "benchmark" / "results" / "scorecard"
BENCH = [("mmlu_pro", "MMLU-Pro", "28 questions (2 per subject), 10 options"),
         ("gpqa", "GPQA Diamond", "20 questions, 4 options shuffled with a fixed seed"),
         ("lcb", "LiveCodeBench v6", "10 AtCoder problems from 2025 (4 easy, 4 medium, 2 hard), all tests, pass@1"),
         ("bfcl", "BFCL v3", "30 function-calling items (15 simple, 15 multiple), AST check")]
TIERS = [("2gb", "qwen2.5-coder-1.5b (Q4_K_M)"), ("4gb", "Qwen3.5-4B (Q4_K_M)"), ("8gb", "gemma-4-E4B (Q4)")]
CODE = "a655659"      # neuron/agent/thinking.py, sandbox, model runner and the harness: unchanged during every run


def load(tier, cond):
    f = RES / f"{tier}-{cond}.json"
    return json.loads(f.read_text()) if f.exists() else None


def pct(x):
    return f"{100 * x:.0f}%"


def cell(s):
    return f"**{s['correct']}/{s['n']}** ({pct(s['score'])}, 95% CI {pct(s['ci95'][0])}-{pct(s['ci95'][1])})"


def mcnemar(a_rows, n_rows, bench):
    """Paired exact test on the same items: (alone wrong & NEURON right, alone right & NEURON wrong, two-sided p)."""
    from math import comb
    a = {r["id"]: r["correct"] for r in a_rows if r["bench"] == bench}
    n = {r["id"]: r["correct"] for r in n_rows if r["bench"] == bench}
    b = sum(1 for i in a if i in n and not a[i] and n[i])
    c = sum(1 for i in a if i in n and a[i] and not n[i])
    k, m = min(b, c), b + c
    p = min(1.0, 2 * sum(comb(m, j) for j in range(k + 1)) / 2 ** m) if m else 1.0
    return b, c, p


def tools(rows):
    t = {}
    for r in rows:
        for k, v in (r.get("tools") or {}).items():
            t[k] = t.get(k, 0) + (v if isinstance(v, (int, float)) else 1)
    return ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(t.items())) or "none (one model call per item)"


def main():
    out = ["# NEURON scorecard", "",
           "Real measured scores of NEURON's three frozen reasoning models on four public benchmarks, each **model alone** "
           "and inside **full NEURON**. These are **fixed samples, not full runs** (a full run of four benchmarks on three "
           "models on a 4-core CPU would take days); the same items, in the same order, for every model and condition. "
           "Small samples have wide confidence intervals: read the intervals, not just the scores.", "",
           "## How it was measured", "",
           "- Machine: 4 CPU cores, no GPU, 16 GB RAM; llama.cpp; one model in memory; each run inside its tier's memory limit; "
           "network cut (new empty network namespace).",
           f"- NEURON code: commit `{CODE}` for every run (harness `benchmark/scorecard/run.py`).",
           "- **Model alone**: one call per item, the same prompt for every model.",
           "- **Full NEURON**: its general mechanisms only (no benchmark-specific tricks): questions go through think, compute "
           "(Python in the sandbox when useful) and check; code is run on the problem's public examples and repaired up to "
           "twice from the failures (hidden tests stay hidden); function calls use schema-constrained output, checked "
           "against the function's parameters, one retry.",
           "- Benchmark data lives outside the repository (only item ids are stored), never enters NEURON's memory, and "
           "was never used for tuning.", ""]
    out += ["| Benchmark | Sample |", "|---|---|"] + [f"| {name} | {what} |" for _, name, what in BENCH] + [""]
    out += ["## Scores", ""]
    head = "| Tier, model | Condition | " + " | ".join(n for _, n, _ in BENCH) + " | Time | Peak RAM | Tokens | Model calls | Tools used |"
    out += [head, "|" + "---|" * (len(BENCH) + 7)]
    status = []
    for tier, model in TIERS:
        for cond in ("alone", "neuron"):
            d = load(tier, cond)
            label = f"{tier.upper()}, {model}" + (f" `{d['model_file']}`" if d and d.get("model_file") else "")
            if not d:
                out.append(f"| {label} | {cond} | " + " | ".join("not started" for _ in BENCH) + " | | | | | |")
                status.append(f"{tier} {cond}: not started")
                continue
            s = d.get("summary") or {}
            rows = d.get("rows", [])
            if not s:
                done = len(rows)
                out.append(f"| {label} | {cond} | " + " | ".join("running" for _ in BENCH) + f" | {done}/88 items so far | | | | |")
                status.append(f"{tier} {cond}: running ({done} of 88 items)")
                continue
            secs = sum(v["seconds"] for v in s.values())
            peak = max(v["peak_mb"] for v in s.values())
            toks = sum(v["tokens"] for v in s.values())
            calls = sum(v["calls"] for v in s.values())
            out.append(f"| {label} | {'full NEURON' if cond == 'neuron' else 'model alone'} | "
                       + " | ".join(cell(s[b]) if b in s else "-" for b, _, _ in BENCH)
                       + f" | {secs / 60:.0f} min | {peak} MB | {toks:,} | {calls} | {tools(rows) if cond == 'neuron' else 'none'} |")
            status.append(f"{tier} {cond}: finished ({d.get('started', '')})")
    out += ["", "Run status: " + "; ".join(status) + ".", ""]
    lines = []
    for tier, model in TIERS:
        a, n = load(tier, "alone"), load(tier, "neuron")
        if not (a and n and a.get("summary") and n.get("summary")):
            continue
        parts = []
        for b, name, _ in BENCH:
            x, y = a["summary"][b], n["summary"][b]
            d = y["correct"] - x["correct"]
            gain, loss, pv = mcnemar(a["rows"], n["rows"], b)
            verdict = "" if not d else (f" (paired test p = {pv:.3f}: shown)" if pv < 0.05 else f" (paired test p = {pv:.2f}: not shown)")
            parts.append(f"{name} {x['correct']} -> {y['correct']} of {x['n']}{verdict}")
        lines.append(f"- {tier.upper()} ({model}), model alone -> full NEURON: " + "; ".join(parts) + ".")
    if lines:
        out += ["### Reading the results", "", "Correct answers, model alone -> full NEURON, on the same items:", ""] + lines + [
            "", "Both conditions answered the same items, so differences are judged with a paired exact test (McNemar): "
            "a difference counts as shown only when p < 0.05. With samples this small, most differences are not shown.", ""]
    out += ["### Answers with no letter found (multiple choice)", "",
            "Every multiple-choice answer may use at most 400 tokens (the same limit for every model and condition). An answer "
            "cut off before it names a letter counts as wrong. These counts show how much of a low score is that limit "
            "rather than the model's knowledge:", "",
            "| Run | MMLU-Pro: no letter | GPQA Diamond: no letter |", "|---|---|---|"]
    for tier, _ in TIERS:
        for cond in ("alone", "neuron"):
            d = load(tier, cond)
            if not d or not d.get("summary"):
                continue
            rows = d.get("rows", [])
            nol = {b: sum(1 for r in rows if r["bench"] == b and not r.get("given")) for b in ("mmlu_pro", "gpqa")}
            tot = {b: sum(1 for r in rows if r["bench"] == b) for b in ("mmlu_pro", "gpqa")}
            out.append(f"| {tier.upper()} {'full NEURON' if cond == 'neuron' else 'model alone'} | {nol['mmlu_pro']} of {tot['mmlu_pro']} "
                       f"| {nol['gpqa']} of {tot['gpqa']} |")
    out += ["", "A second pass with a larger answer limit, recorded as a separate protocol next to this one, is planned.", ""]
    out += ["## Comparison with published scores", "",
            "Not made. Published scores for these benchmarks use the full test sets, other prompts, other answer extraction "
            "and often GPUs with long thinking budgets; ours are small fixed samples with our own prompts on a CPU. Putting "
            "them side by side would compare different measurements. A comparison will be added only for a run under "
            "matching conditions (same full set, same protocol).", "",
            "## Notes", "",
            "- Times include model loading and are wall-clock on a shared 4-core machine. Some 4 GB model-alone item times "
            "were measured while tests ran beside them; the windows are in `benchmark/overlap.log` (scores are not "
            "affected: those items were multiple-choice, with no time limit). The run was also paused by hand once, with no "
            "other model running in between (`benchmark/scorecard.log`).",
            "- Raw per-item results: `benchmark/results/scorecard/<tier>-<condition>.json`; log: `benchmark/scorecard.log`.",
            "- Regenerate this page: `python3 -m benchmark.scorecard.report`."]
    (ROOT / "SCORECARD.md").write_text("\n".join(out) + "\n")
    print("\n".join(status))


if __name__ == "__main__":
    main()
