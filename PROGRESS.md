# NEURON — progress log (resume from here)

A new session must be able to continue from this file plus the repository. Update it after every step.

## Where things are

- Repo: `Sthmpe/neuron`, branch `main`. Step 1 (task engine) and step 2 (local model, tools, sandbox,
  fix_code, first benchmark: 5/10 with a 1.5B model) are done — see README.
- Step 3 (this file) started from commit `2c011a4`.
- Machine set-up that is NOT in git (re-create with the scripts if the machine is new):
  - llama.cpp server binary: `../llama/build/bin/llama-server` → `scripts/setup_local_model.sh`
  - bubblewrap (`bwrap`) → same script
  - model files in `models/store/` → `scripts/download_models.sh` (needs huggingface.co + us.aws.cdn.hf.co allowed)
  - Chromium + Playwright for Node are pre-installed on the cloud machine (`/opt/pw-browsers`, `/opt/node-tools`).

## Step 3 goals (from the owner)

A. Persistent project state on disk, model-independent (spec, acceptance tests, tasks, project map, decisions, test results); per-task context slices; resume from state alone.
B. Builder loop: plan → split → build one → run → test → review → fix → next. Planner/reviewer and builder roles, one model in memory at a time.
C. Benchmarks. Dev set (tuning + model choice): original 10 bug projects + 2 small builds. Held-out (scoring only): 20 new bug projects + 3 builds (landing page; customer+inventory app; same app killed mid-build and resumed). Builds verified by running the app in a real browser. Design system included. Screenshots saved.
D. Tiers: 2 GB / 4 GB / 8 GB TOTAL RAM, enforced on everything. Best model per tier chosen on dev set; scored on held-out with and without A+B. Report score, time to verified result, peak memory.
E. Model manager: install / swap / roll back model files without code changes; refuse models that do not fit the tier.
F. README with every measured number and an honest account.

## Rules I set for myself before measuring anything (do not change after seeing held-out results)

1. Held-out tasks are written before any tuning and are never run until the final scoring run.
   Tuning (prompts, loop, edit format, model choice, time caps) uses the dev set only.
2. One final scoring run per (tier, condition). If the harness itself crashes, fix the harness, say so
   in the README, and re-run only the affected task. Never re-run because a score is disappointing.
3. Conditions: BASE = without A and B (step-2 style: one prompt per attempt, whole project in the
   prompt, no state, no roles). FULL = with A and B. Same model, same kit/design system, same sandbox,
   same number of code attempts for bugs (3).
4. "Solved"/"verified" is decided only by the examiner (original tests for bugs; browser workflows
   for builds), never by the brain's own claim.
5. Everything runs inside the tier's memory limit with the network off.

## Candidate models (2 per tier: a code specialist and a newer general model)

| Tier | Candidate A | Candidate B |
|---|---|---|
| 2 GB | Qwen2.5-Coder-1.5B q4_k_m (1.04 GB) | Qwen3.5-2B Q4_K_M (1.19 GB) |
| 4 GB | Qwen2.5-Coder-3B q4_k_m (1.96 GB, non-commercial licence) | Qwen3.5-4B Q4_K_M (2.55 GB) |
| 8 GB | Qwen2.5-Coder-7B q4_k_m (4.36 GB) | Qwen3.5-9B Q4_K_M (5.29 GB) |

## Step list and status

- [x] 0. Plan, PROGRESS.md, start model downloads
- [ ] 1. Tier memory limits (cgroup) + sandbox nested inside the tier
- [ ] 2. Model manager (install / swap / rollback / fit check) + one-model-at-a-time runner
- [ ] 3. App kit + design system (components, CSS) for built apps; sandboxed dev server
- [ ] 4. Project state on disk (A)
- [ ] 5. Builder loop (B) for bug fixing and for builds
- [ ] 6. Benchmark tasks: 2 dev builds, 20 held-out bugs, 3 held-out builds, browser examiners
- [ ] 7. Dev-set tuning and model choice per tier
- [ ] 8. Freeze, then held-out scoring: 3 tiers × BASE/FULL
- [ ] 9. README

## Log
- 2026-11-16: plan written, six candidate downloads started (`models/download.log`).
