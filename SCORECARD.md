# NEURON scorecard

Real measured scores of NEURON's three frozen reasoning models on four public benchmarks, each **model alone** and inside **full NEURON**. These are **fixed samples, not full runs** (a full run of four benchmarks on three models on a 4-core CPU would take days); the same items, in the same order, for every model and condition. Small samples have wide confidence intervals: read the intervals, not just the scores.

## How it was measured

- Machine: 4 CPU cores, no GPU, 16 GB RAM; llama.cpp; one model in memory; each run inside its tier's memory limit; network cut (new empty network namespace).
- NEURON code: commit `a655659` for every run (harness `benchmark/scorecard/run.py`).
- **Model alone**: one call per item, the same prompt for every model.
- **Full NEURON**: its general mechanisms only (no benchmark-specific tricks): questions go through think, compute (Python in the sandbox when useful) and check; code is run on the problem's public examples and repaired up to twice from the failures (hidden tests stay hidden); function calls use schema-constrained output, checked against the function's parameters, one retry.
- Benchmark data lives outside the repository (only item ids are stored), never enters NEURON's memory, and was never used for tuning.

| Benchmark | Sample |
|---|---|
| MMLU-Pro | 28 questions (2 per subject), 10 options |
| GPQA Diamond | 20 questions, 4 options shuffled with a fixed seed |
| LiveCodeBench v6 | 10 AtCoder problems from 2025 (4 easy, 4 medium, 2 hard), all tests, pass@1 |
| BFCL v3 | 30 function-calling items (15 simple, 15 multiple), AST check |

## Scores

| Tier, model | Condition | MMLU-Pro | GPQA Diamond | LiveCodeBench v6 | BFCL v3 | Time | Peak RAM | Tokens | Model calls | Tools used |
|---|---|---|---|---|---|---|---|---|---|---|
| 2GB, qwen2.5-coder-1.5b (Q4_K_M) `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` | model alone | **5/28** (18%, 95% CI 8%-36%) | **2/20** (10%, 95% CI 3%-30%) | **0/10** (0%, 95% CI 0%-28%) | **26/30** (87%, 95% CI 70%-95%) | 18 min | 1640 MB | 13,330 | 88 | none |
| 2GB, qwen2.5-coder-1.5b (Q4_K_M) `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` | full NEURON | **4/28** (14%, 95% CI 6%-32%) | **2/20** (10%, 95% CI 3%-30%) | **0/10** (0%, 95% CI 0%-28%) | **26/30** (87%, 95% CI 70%-95%) | 26 min | 1625 MB | 18,439 | 155 | check pass 48, public example runs 28, python runs 1, repairs 18, schema constrained 30, validation retry 0 |
| 4GB, Qwen3.5-4B (Q4_K_M) `Qwen3.5-4B-Q4_K_M.gguf` | alone | running | running | running | running | 18/88 items so far | | | | |
| 4GB, Qwen3.5-4B (Q4_K_M) | neuron | not started | not started | not started | not started | | | | | |
| 8GB, gemma-4-E4B (Q4) | alone | not started | not started | not started | not started | | | | | |
| 8GB, gemma-4-E4B (Q4) | neuron | not started | not started | not started | not started | | | | | |

Run status: 2gb alone: finished (2026-11-18 11:41:19); 2gb neuron: finished (2026-11-18 12:11:06); 4gb alone: running (18 of 88 items); 4gb neuron: not started; 8gb alone: not started; 8gb neuron: not started.

## Comparison with published scores

Not made. Published scores for these benchmarks use the full test sets, other prompts, other answer extraction and often GPUs with long thinking budgets; ours are small fixed samples with our own prompts on a CPU. Putting them side by side would compare different measurements. A comparison will be added only for a run under matching conditions (same full set, same protocol).

## Notes

- Times include model loading and are wall-clock on a shared 4-core machine. Some 4 GB model-alone item times were measured while tests ran beside them; the windows are in `benchmark/overlap.log` (scores are not affected: those items were multiple-choice, with no time limit). The run was also paused by hand once, with no other model running in between (`benchmark/scorecard.log`).
- Raw per-item results: `benchmark/results/scorecard/<tier>-<condition>.json`; log: `benchmark/scorecard.log`.
- Regenerate this page: `python3 -m benchmark.scorecard.report`.
