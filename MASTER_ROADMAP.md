# NEURON master roadmap (the backlog)

`VISION.md` is the direction, this file is the backlog, `PROGRESS.md` is the execution log. Every claim here points at
measured evidence in the repository; anything without evidence is listed as unverified. History is kept: items are
marked done or superseded, never deleted.

Owner's execution plan of 2026-11-18, in order: (1) this roadmap, (2) usable release incl. Windows, (3) scorecard,
(4) knowledge memory, (5) new locked tasks + honesty + totals + C++/Go, (6) offline to online, (7) creative quality
with 3 reference sites, then stop that track for approval. Later: external AI, a second engineer on its own branch,
dedicated hardware.

Status words: **done** (built and measured), **built** (built, tested with scripted models only), **in progress**,
**planned**, **later** (recorded, nothing to build yet), **superseded**.

---

## W1. Release and installation

| | |
|---|---|
| Status | Linux **done in the cloud machine**; Windows (WSL2) **built, unverified**; macOS **later** |
| Evidence | Clean-setup retest 2026-11-18: fresh code copy, empty home, llama.cpp built from source, real 4.64 GB download, checksum, self-tests; 4 of 4 real tasks after fixes (`benchmark/results/release_retest_run2.json`). Windows: `scripts/install-windows.ps1`, rules unit-tested in `windows_plan()` |
| Unverified | Any home PC; stock Ubuntu desktop (cgroup v2 memory limits via systemd and the AppArmor offer were not exercised here); Windows (never run); macOS |
| Acceptance | From a fresh Ubuntu machine: one command installs, picks the right tier, verifies the model, self-tests, starts; a phone pairs and completes a real task offline. Windows: the owner reports the same via WSL2 |
| Depends on | W4 (frozen models) |
| Next | Owner tests: Windows (TESTING.md 1b) and a home Linux PC |

## W2. Phone interface

| | |
|---|---|
| Status | **built** |
| Evidence | `neuron/server/`: pairing codes (single use, 10 min, lockout), hashed tokens, follow-ups as a conversation, approvals, previews, downloads, stop/resume, status, optional HTTPS. Automatic tests incl. a phone-size browser journey over HTTP and HTTPS (`tests/test_server*.py`); screenshots `docs/screens/phone/` |
| Unverified | A real phone on a real home network; long jobs from the phone with a real model |
| Acceptance | The owner's acceptance test in `TESTING.md` passes on their own phone |
| Depends on | W1 |
| Next | Real-task check during the step-2 clean retest |

## W3. Core agent (loop, state, router, tools)

| | |
|---|---|
| Status | **done** (measured) |
| Evidence | `neuron/agent/`: 20 capabilities, on-disk job state, resume after kill. Phase-5 locked runs (`benchmark/results/phase5_summary.md`): 2 GB 5/12, 4 GB 4/12, 8 GB 7/12. Dev: 6/7 then 7/7 after fixes (4 GB) |
| Unverified | Behaviour on tasks outside the measured kinds; multi-hour jobs |
| Acceptance | New locked set (W5) shows improvement with zero false claims |
| Next | Memory (W6) and honesty work (W7) feed into it |

## W4. Models and tiers

| | |
|---|---|
| Status | **done**: frozen 2026-11-17 (2 GB qwen2.5-coder-1.5b-q4, 4 GB Qwen3.5-4B-Q4_K_M, 8 GB gemma-4-E4B-Q4_K_M). Specialist models (vision, speech, image) **later** |
| Evidence | Selection by a rule written before results (`benchmark/results/selection.json`); memory per model in `HARDWARE.md` |
| Unverified | Behaviour on non-x86 hardware |
| Acceptance | No change to the reasoning models without the owner; the system improves around them |
| Next | Scorecard (W5b) measures each model alone and inside NEURON |

## W5. Evaluation

| Item | Status | Evidence / next |
|---|---|---|
| Step-3 held-out (bugs, builds, workspaces) | **done** | `benchmark/results/heldout_summary.md`; labelled rerun of builds with the current system 9/9 |
| Phase-5 locked set | **done** | 3 examiner amendments recorded in `benchmark/phase5/LOCKED.md`; official + labelled reruns kept apart |
| W5a. New locked set (phase 6 evaluation) | **planned, step 5** | Written and locked before tuning: code in several languages, Excel, Word, PowerPoint, PDF, an unseen app. Acceptance: zero false "verified" claims |
| W5b. Scorecard (MMLU-Pro, GPQA Diamond, LiveCodeBench, BFCL) | **planned, step 3** | `SCORECARD.md`: model alone vs full NEURON per tier, fixed samples labelled as samples, version/count/score/time/RAM/tokens/tools. Benchmark data never enters memory or tuning |

## W6. Knowledge memory

| | |
|---|---|
| Status | **planned, step 4** |
| Evidence | none yet (the agent keeps per-job state only) |
| Acceptance | Local store, keyword + meaning search (embedding model that fits 2 GB, with a fallback); searched before reasoning; findings saved with source, date, version and verification status; fixes reused only after checking they apply; old notes rechecked when online; measured effect on a second similar task with the same model |
| Depends on | W3 |

## W7. Honesty and verification

| | |
|---|---|
| Status | **in progress** |
| Evidence | Phase-5 official runs had 3 false "verified" claims (PDF answers at 4 and 8 GB, shop app at 8 GB). First fix (2026-11-18): unbuildable requested features reported as gaps (job says PARTIAL); answer numbers must be in the quote. Not yet measured with real models |
| Acceptance | Zero false "verified" claims on the new locked set (W5a) |
| Next | Step 5 |

## W8. Software building and code

| Item | Status | Evidence / next |
|---|---|---|
| Web apps (lists, forms, search, login, dashboard counts, links, one rule per record type) | **done** | held-out builds 3/3 on all tiers (step-3 and current system) |
| Computed totals and sums in apps | **planned, step 5** | Locked shop app failed only on totals, revenue sum and own tests (13/17) |
| New programs (C++, Go, Python, ...) | **built** | locked C++ program: only 8 GB built it (7/7) |
| Bug fixing: Python | **done** | held-out 4 GB 20/20 bugs, workspaces 6/10 |
| Bug fixing: C++ / Go | **weak** | locked: C++ 1-2 of 3, Go 0 of 2 at every tier. Step 5 improves on dev tasks |
| Mobile, desktop, games, Flutter | **later** | not built; reported as missing |

## W9. Documents and data

| | |
|---|---|
| Status | **done** for Excel, Word, PowerPoint (solved on every tier in the locked set); PDF research **partial** (best 15/16) |
| Unverified | Charts, longer reports, scanned PDFs (no OCR) |
| Next | Covered again by the new locked set |

## W10. Offline to online

| | |
|---|---|
| Status | **planned, step 6** (the step-1 task engine already waits for the network in its own tests; the agent marks `needs_internet` steps but nothing fetches yet) |
| Acceptance | Internet steps wait and resume by themselves; images: owner's first, offline placeholders marked "images needed", online licensed photos with recorded source; packages checked when online, upgraded in isolation, tested, rolled back on failure; no duplicate side effects after a crash |

## W11. Creative quality and design

| | |
|---|---|
| Status | Design system **done** (20-request proof run 1: 19/20 built); content quality **planned, step 7** |
| Evidence | `benchmark/design/results.md`; fixes after run 1 (hero repetition, gaps, keyword names, schema by code) |
| Acceptance | 3 reference sites (law firm, bakery, salon) at paying-client standard with phone, tablet and desktop screenshots; no invented testimonials, statistics, credentials, hours or contacts; then **stop for the owner's approval** before documents, slides and the 20-request rerun |

## W12. Security and isolation

| | |
|---|---|
| Status | **done** for code (bubblewrap sandbox: no network, workspace only, no privileges, memory and process limits) and phone access (pairing, hashed tokens, optional HTTPS) |
| Unverified | Independent security review |

## W13. Hardware and the device

| | |
|---|---|
| Status | Bottleneck log **done** (`HARDWARE.md`); dedicated device **later** |
| Evidence | Writing speed follows memory bandwidth (~20 GB/s here); 4 GB tier peaks at the limit and once killed the model server while compiling |

## W14. External AI (ChatGPT, Claude, Gemini through official APIs)

| | |
|---|---|
| Status | **later** (owner decision 2026-11-18: record now, build nothing yet) |
| Rules when it is built | NEURON stays the task owner; plan and memory stay local; cloud answers are tested and may be rejected; asks before sending sensitive data; caps spending; keeps working offline |
| Existing code | `neuron/online/boost.py` (2026-11-17): an optional chat-completions fallback, off by default, never required. It predates this decision; it is kept as is and not extended until this phase starts |

## W15. Second engineer (Codex) on its own branch

**later**. Will work on a separate branch; merges only through tests and review.

## W16. Media (vision, speech, images, video) and W17. Automation (apps, terminals, scheduled jobs, messages)

**later**. Reported as missing capabilities until built and verified.
