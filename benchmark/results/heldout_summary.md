# Step-3 held-out scoring (finished 2026-11-18 02:50)

Tasks written before any tuning, run once per tier and condition, network off, everything inside the tier's
memory limit. "Solved" is decided only by the examiners (the project's original tests for bugs; HTTP and
browser workflows for builds). Base = one prompt per attempt, no saved state, no roles. Full = NEURON's loop
(saved state, small tasks, planner/builder/reviewer roles, checks after every step). Same model, kit and
sandbox in both; 3 code attempts per bug in both. The plain kit was used (the design system was not yet the
default), and there was no template fallback.

| Tier | Loop | Bugs (of 20) | Builds: checks passed | Builds solved | Workspace bugs (of 10) | Minutes | Peak MB | Limit hits | Model |
|---|---|---|---|---|---|---|---|---|---|
| 2 GB | base | 5 | 0/13, 5/19, 5/19 | 0 of 3 | 0 | 46 | 1467 | 0 | qwen2.5-coder-1.5b-q4 |
| 2 GB | full | 7 | 13/13, 19/19, 19/19 | 3 of 3 | 3 | 23 | 1510 | 0 | qwen2.5-coder-1.5b-q4 |
| 4 GB | base | 19 | 0/13, 5/19, 19/19 | 1 of 3 | 3 | 70 | 3996 | 0 | qwen3.5-4b-q4 |
| 4 GB | full | 20 | 13/13, 19/19, 19/19 | 3 of 3 | 6 | 58 | 3996 | 0 | qwen3.5-4b-q4 |
| 8 GB | base | 19 | 12/13, 19/19, 19/19 | 2 of 3 | 5 | 85 | 5655 | 0 | gemma-4-e4b-q4 |
| 8 GB | full | 19 | 13/13, 19/19, 19/19 | 3 of 3 | 7 | 51 | 5735 | 0 | gemma-4-e4b-q4 |

Builds: b1 landing page (13 checks), b2 customer and stock app (19), b3 the same app killed with SIGKILL halfway
and resumed (19). Workspace bugs: 10 tasks in two whole multi-module codebases (shop, clinic).

What it shows:
- The loop matters most for the weakest model and for builds: with the full loop every tier built all three
  apps; without it the 2 GB model built none.
- The 4 GB and 8 GB models fix single-file bugs almost as well without the loop (19 of 20); the loop's gain
  there is in whole workspaces (3 -> 6 and 5 -> 7 of 10) and in time (the full loop was faster at every tier).
- Whole-workspace bugs are the hardest task here: best is 7 of 10.
- The 8 GB tier did not beat the 4 GB tier on these tasks (bugs 19 vs 20, workspace 7 vs 6). On this machine
  the 4 GB model is the best value; the frozen choice per tier stays (rule: chosen on the dev set beforehand).

Interruptions (infrastructure, not the model): the cloud machine restarted three times. Each time the finished
rows were kept and the task in progress was rerun from a clean copy: 2gb-base b3_shop_app_resumed,
2gb-base w06_lunch_slots, 8gb-base w03_due_date_weekend. Raw rows: `benchmark/results/heldout/` and
`benchmark/results/workspace/`; log: `benchmark/heldout.log`.
