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
| W5a. New locked set "eval2" | **written and LOCKED, not yet run** | `benchmark/eval2/` (12 tasks: PDF, Excel, Word, PowerPoint, Python/JS/Go/Rust bugs, C++ program, unseen repair-shop app, long task, computed answer). Locked 2026-11-18 before any tuning, fingerprint in `LOCK.json`; every examiner validated (24/24: references pass, wrong deliveries fail). Next: official runs on 2/4/8 GB with memory off. Acceptance: zero false "verified" claims |
| W5b. Scorecard (MMLU-Pro, GPQA Diamond, LiveCodeBench, BFCL) | **done** (2026-11-19) | `SCORECARD.md`: all three models, model alone and full NEURON, 88 fixed sampled items each, network cut, code a655659. Full NEURON is better on MMLU-Pro for 4 GB (10 to 18 of 28, paired p = 0.008) and 8 GB (9 to 17, p = 0.021); no shown difference elsewhere; the 2 GB model gains nothing. GPQA is low everywhere and largely limited by the 400-token answer limit (counts in the page). No comparison with published scores (conditions differ). Next: a labelled second pass with a larger answer limit |

## W6. Knowledge memory

| | |
|---|---|
| Status | **built** (2026-11-18); effect not yet shown |
| Evidence | `neuron/memory/`: SQLite store, keyword (FTS5) + meaning search (bge-small-en-v1.5, 37 MB, about 60 MB in memory; character-hash fallback), searched before reasoning, notes carry source, date, version and verification status; fixes saved after verified repairs and offered only as hints to be checked. Old notes rechecked when online (`neuron/memory/recheck.py`, step 6). Measured on a second similar task, same 2 GB model (`benchmark/results/memory_effect.json`): without memory 3/3 in 63.4 s, with memory 3/3 in 53.3 s; one learning run saved no note, so no reliable effect on this easy pair |
| Unverified | Effect on a harder pair of tasks; behaviour with thousands of notes |
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
| Computed totals and sums in apps | **built, not yet measured with a real model** | Computed fields (formula over own and linked number fields) and dashboard sums, worked out in the database query; template builds pass their checks. Locked shop app had failed only on totals, revenue sum and own tests (13/17). Next: measure on a dev app with the real 2/4/8 GB models |
| New programs (C++, Go, Python, ...) | **built** | locked C++ program: only 8 GB built it (7/7) |
| Bug fixing: Python | **done** | held-out 4 GB 20/20 bugs, workspaces 6/10 |
| Bug fixing: C++ / Go | **improved, not yet measured with real models** | locked phase 5: C++ 1-2 of 3, Go 0 of 2 at every tier (the model found the right function but wrote wrong fixes). Built: one-token changes tried before the model (`neuron/agent/repair_search.py`), failing test lines shown to the model, two candidate edits per try, Go tab indentation handled. Dev set `benchmark/repair_dev` (6 projects, not locked): the search alone fixes all 4 one-token bugs in 1 to 14 s with no model. Next: `benchmark.repair_dev.run` on 2/4/8 GB with the search on and off |
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
| Status | **built** (2026-11-18, step 6) |
| Evidence | Steps needing the internet wait (`waiting_network`) and resume when it is back; services that say "slow down" get a growing pause (10 min up to 6 h), never repeated asking. Outside actions go through a crash-safe ledger: done ones are never repeated, interrupted ones are not repeated without the owner's answer. Pictures: owner photos first, on-brand "Image needed" placeholders offline, licensed Wikimedia Commons photos online (PD/CC0/CC BY/CC BY-SA only) with source in `IMAGE_CREDITS.md`. Packages: PyPI/npm checked with docs links, upgraded in an isolated copy, tested in the sandbox, swapped in only if tests pass, backup and rollback. Real upgrade run (`benchmark/results/online_upgrade_demo.json`): six upgraded, packaging kept back because 26.3 breaks the project's test, real project untouched by the failing attempt (17.5 s). Real npm run (`online_upgrade_demo_npm.json`): ms 2.0.0 to 2.1.3, uuid kept at 3.4.0 because 14.0.3 breaks the test (13 s). 20 tests in `tests/test_online.py` |
| Unverified | Real photo downloads: the Commons search works from this cloud machine, but downloads are rate-limited for its shared address (recorded in `benchmark/results/online_images_demo.json`; a polite retry runs every 20 minutes). A real crash in the middle of a real outside action (tested with a simulated crash) |
| Acceptance | Internet steps wait and resume by themselves; images: owner's first, offline placeholders marked "images needed", online licensed photos with recorded source; packages checked when online, upgraded in isolation, tested, rolled back on failure; no duplicate side effects after a crash |

## W11. Creative quality and design

| | |
|---|---|
| Status | Design system **done** (20-request proof run 1: 19/20 built); content quality **built**; 3 reference sites **built, waiting for the owner's approval** (`docs/REFERENCE_SITES.md`). Track stopped until approved |
| Evidence | `benchmark/design/results.md`; fixes after run 1 (hero repetition, gaps, keyword names, schema by code). Content rules (`neuron/design/content.py`): leftover template text, filler, repetition, duplicated sections, invented testimonials/statistics/credentials/hours/contact details, owner facts missing from the page, empty cards. The site planner is told and must fix them; invented facts that survive are removed and recorded; anything else is reported and the job says PARTIAL. Sites get pictures (owner photos first, labelled placeholders offline, licensed photos online). Reference builds (8 GB) found and fixed: facts left out, empty cards, a section repeated beside the form, price lists as tall cards, generic line under the headline, info rows numbered like steps, spacing that inflated every page, an artwork chosen as a photo. Final builds: words clean, every owner fact present, 0 design failures, no sideways scrolling at 3 widths; photos 5 of 9 licensed so far (Commons rate-limits this cloud address; NEURON's own retries keep going; the salon is complete and VERIFIED). Tests in `tests/test_content.py` |
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
