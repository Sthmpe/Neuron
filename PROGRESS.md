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
| 2 GB | Qwen2.5-Coder-1.5B q4_k_m (1.04 GB) | Qwen3.5-0.8B Q8_0 (0.76 GB) - Qwen3.5-2B was planned but measured 1892 MB, so the model manager refuses it for 2 GB |
| 4 GB | Qwen2.5-Coder-3B q4_k_m (1.96 GB, non-commercial licence) | Qwen3.5-4B Q4_K_M (2.55 GB) |
| 8 GB | Qwen2.5-Coder-7B q4_k_m (4.36 GB) | Qwen3.5-9B Q4_K_M (5.29 GB) |

## Owner's standing goal (2026-11-17)

NEURON must build full apps and fix bugs in full workspaces no matter which model is installed. The model
is swappable; the system around it (state, small tasks, kit, checks, repairs) has to carry the weight.

## Extra candidates (added 2026-11-17 at the owner's request, before their results)

Gemma 4 E2B and Granite 4.1 3B for 4 GB; Gemma 4 E4B and Granite 4.1 8B for 8 GB (all Apache-2.0).
Same dev set, same rule. A model that does not fit its tier after measurement is refused and skipped.
Not possible: Claude (no open weights), gpt-oss-20b (needs ~13 GB), Kimi (smallest open model 48B).

## Model choice rule (written before any selection result)

Per tier, both candidates run the full dev set (10 bugs + 2 builds) in the FULL condition inside the tier.
Score = bugs solved + build checks passed / checks total (so each item counts 1). Highest score wins;
a tie goes to the lower total time. The winner is activated with the model manager and used for both
held-out conditions.

## Step list and status

- [x] 0. Plan, PROGRESS.md, start model downloads
- [x] 1. Tier memory limits (cgroup) + sandbox nested inside the tier
- [x] 2. Model manager (install / swap / rollback / fit check) + one-model-at-a-time runner
- [x] 3. App kit + design system (components, CSS) for built apps; sandboxed dev server
- [x] 4. Project state on disk (A)
- [x] 5. Builder loop (B) for bug fixing and for builds
- [x] 6. Benchmark tasks: 2 dev builds, 20 held-out bugs, 3 held-out builds, browser examiners
- [x] 7a. Dev-set tuning (FROZEN at the commit after this line)
- [ ] 7b. Model choice per tier on the dev set (FULL condition)
- [ ] 8. Freeze, then held-out scoring: 3 tiers × BASE/FULL
- [ ] 9. README

## Log
- 2026-11-16: plan written, six candidate downloads started (`models/download.log`).
- 2026-11-17: dev tuning done and frozen. Fixes found on dev: indented methods, fault localisation
  (trace which functions failing tests run), OLD/NEW edit on attempt 2, planner site example, mandatory
  login fields, comma repair, one-line-per-section home page, reviewer claims checked against the page,
  guide left out of retries. Last dev run, 2 GB, qwen2.5-coder-1.5b-q4: 8/12 (bugs 6/10, builds 2/2).

## Queued task: design taste (requested 2026-11-17, after step 3)

Goal: any site NEURON builds should look like a good human designer made it; two sites never the same
template. Taste lives in the kit and rule-based code; the model only writes words.

Built so far (all in new folders so the running step-3 benchmark is not affected):
- `neuron/design/`: OKLCH colour engine (tints, shades, neutrals, lightness-only contrast fixes, button
  pairs), colour words (`names.py`), 11 moods with palettes / font pairings / shape / depth / rhythm /
  layout preferences (`mood.py`), the design engine with plain-English reasons and a no-repeat history
  (`engine.py`), browser designer checks (`check.js`, `check.py` with token fixes).
- `neuron/kit_next/`: token-only kit (16 bundled font families, 162 icons, copy rules: no em dashes,
  no stock phrases), layout variants: hero x5, features x5, fact x3, form x3, nav x3, rhythm x3.
- `neuron/builder/design_step.py` + switch `NEURON_DESIGN=1` in build.py (OFF by default until step 3
  scoring is finished; then: flip the default, rename kit -> kit_v1 and kit_next -> kit).
- `benchmark/design/requests.json` (20 requests, 11 name colours) and `run_design.py` (proof runner).

Next for design: after step-3 held-out scoring -> swap kit, run the 20-request proof (2 GB tier model),
commit screenshots, rerun held-out builds with the design system, README section.

## Planned after step-3 held-out scoring (so it does not change what is being measured)

- Swap to the design kit by default (see design track).
- "Full app no matter the model": when the builder model fails a build task 3 times, generate that file
  from the spec with deterministic templates (the reference builder, promoted from tests into the
  system). Report in every result how many files the model wrote and how many came from templates.
- Workspace benchmark (10 whole-codebase bug tasks) is part of the held-out queue.
