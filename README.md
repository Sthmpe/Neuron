# NEURON

NEURON is a personal AI computer that works offline. A small open model runs on your own computer; you
describe a goal in plain words from your phone, and NEURON plans the work, does it with real tools
(spreadsheets, documents, slides, answers from PDFs, fixing bugs in whole code projects, building small
business web apps), checks the result with independent tests, and shows you the evidence. The internet
is never required. An optional online boost can be switched on by the owner.

Read [`VISION.md`](VISION.md) for where this is going, [`TESTING.md`](TESTING.md) to try it yourself,
[`PROGRESS.md`](PROGRESS.md) for the detailed log, [`HARDWARE.md`](HARDWARE.md) for what limits it on real
machines.

## Where it stands (2026-11-17)

| Phase | What | State |
|---|---|---|
| 0 | Finish step 3: model selection, held-out scoring, design system, honest numbers | Selection done. Held-out scoring **running** (results below when finished). Design proof after it |
| 1 | `VISION.md` | Done |
| 2 | One frozen model per memory tier | **Done**: `model_manifests/frozen.json` |
| 3 | Better intelligence with the same models (state, context slices, shared loop, strategies, roles, verification) | First version built in `neuron/agent/`; tested with scripted models; **not yet measured with real models** |
| 4 | Tool registry with purpose, inputs, outputs, internet, permissions, resources, verification; honest missing-tool reports | First version built: 20 capabilities |
| 5 | New evaluation, tasks locked before tuning | 12 tasks **locked** with independent examiners; runner written; **not yet run** |
| 6 | Owner release: installer, phone web page with secure pairing, offline, `TESTING.md` | Built and tested in a cloud Linux container; not yet on a home PC or a real phone |
| 7 | Optional online boost; hardware bottleneck log; this README | Boost built (off by default); `HARDWARE.md` started |

## Try it

Linux only for now (tested: Ubuntu 24.04). Windows and Mac are not supported until they have been tested.

```
git clone https://github.com/Sthmpe/Neuron.git && cd Neuron
bash scripts/install.sh          # detects memory, picks the frozen model, downloads and checks it, self-tests, starts
```

Then open the printed address on your phone (same Wi-Fi) and type the pairing code. Step-by-step owner
test, with what a good result looks like: [`TESTING.md`](TESTING.md).

## The models (frozen 2026-11-17)

The installer keeps max(1 GB, 15%) of memory for the operating system and picks the largest tier that fits.
Every number below was measured on a 4-core Xeon at 2.3 GHz, CPU only, network off, everything NEURON ran
counted against the tier's memory limit.

| Tier | Model | File | Licence | Memory in use | Peak of everything in selection | Selection score (of 12) |
|---|---|---|---|---|---|---|
| 2 GB | qwen2.5-coder-1.5b-instruct q4_k_m | 1.04 GB | Apache-2.0 | 1384 MB | 1566 MB | 8.0 (6 of 10 bugs, both builds fully passed) |
| 4 GB | Qwen3.5-4B Q4_K_M | 2.55 GB | Apache-2.0 | 3656 MB | 3994 MB | 12.0 |
| 8 GB | gemma-4-E4B-it Q4_K_M | 4.64 GB | Apache-2.0 | 5491 MB | 5736 MB | 12.0 |

Checksums, sources and llama.cpp settings: [`model_manifests/frozen.json`](model_manifests/frozen.json).

### How they were chosen

Rule written before any result: on the dev set (10 bug projects + 2 app builds, full NEURON loop, inside the
tier), score = bugs solved + build checks passed / checks total; highest wins; a tie goes to the lower total time.

| Tier | Candidates: score of 12 (total time) |
|---|---|
| 2 GB | **qwen2.5-coder-1.5b-q4 8.0 (462 s)**; qwen3.5-0.8b-q8 2.57 (735 s) |
| 4 GB | **qwen3.5-4b-q4 12.0 (1215 s)**; granite-4.1-3b-q4 10.0 (1016 s); qwen2.5-coder-3b-q4 9.0 (901 s); gemma-4-e2b-q4 7.25 (1252 s) |
| 8 GB | **gemma-4-e4b-q4 12.0 (1143 s)**; qwen3.5-9b-q4 12.0 (1779 s, lost the tie on time); qwen2.5-coder-7b-q4 11.0 (1522 s); granite-4.1-8b-q4 10.9 (2519 s) |

Harness problems during selection and what was done about them are listed in `PROGRESS.md` (a load timeout
for qwen3.5-9b, one rerun task; Gemma's thinking mode used up its replies until it was switched off;
granite-4.1-8b's 10th task overlapped my installer test, so its time is inflated; it could not win either way).
The dev set was also used for tuning, so these scores are optimistic. The held-out scores below are the real test.

## Results

### Step 3 held-out scoring: running

20 new bug projects, 3 new builds (a landing page, a customer and stock app, the same app killed halfway and
resumed) and 10 whole-workspace bug tasks, for each tier, with the full NEURON loop and without it (BASE:
one prompt per attempt, no saved state, no roles). Written before any tuning; run once. Progress:
[`benchmark/heldout.log`](benchmark/heldout.log). **No held-out number is reported here until the runs finish.**

### Phase 5 locked evaluation: not run yet

12 tasks locked on 2026-11-17 before any tuning (`benchmark/phase5/LOCKED.md`): answering from two PDFs with
page citations, an Excel summary with formulas, a Word proposal with a budget table, a PowerPoint pitch, a
C++ command-line program, three bugs in a C++ project and two in a Go project, an unseen business app killed
halfway and resumed, and a docstring task larger than one context window, killed and resumed. Each is judged
by an independent examiner (LibreOffice recalculation and rendering, the project's original tests, a real
browser). Runner: `benchmark/phase5/run.py`.

### Step 2 (15 Nov 2026): 5 of 10 bugs fixed

One 1.5B model, single prompt per attempt, network off. Details in [`docs/HISTORY.md`](docs/HISTORY.md).

## What is built

| Part | Where | What it does |
|---|---|---|
| Brain | `neuron/brain/` | Runs the local model with llama.cpp (one model in memory at a time), memory tiers (Linux memory cgroups), model manager (install, swap, roll back, refuse what does not fit), the code sandbox (bubblewrap: no network, only the job folder, no privileges, memory and process limits) |
| Agent | `neuron/agent/` | Understands the goal, picks a workflow, runs it step by step with saved state, checks every step, retries with a different strategy, asks for approval before sensitive actions, writes an honest report (verified, partly done, failed, and who made each result) |
| Tools | `neuron/agent/capabilities/` | Spreadsheets (formulas checked by LibreOffice against an independent calculation), Word documents, PowerPoint decks (rendered to check), answers from documents (quotes must be on the cited page), bug fixing in Python, C++, Go and other languages, docstrings for whole projects, new programs, web apps |
| App builder | `neuron/builder/` | Request, then a specification, then small file-sized tasks, each proven by HTTP checks on the running app; records that point at other records and rules that change them (a sale lowers stock, refused below zero); fixed templates take over a file the model fails three times, and every result says who wrote it |
| Design system | `neuron/design/`, `neuron/kit_next/` | Mood and colour engine (OKLCH, contrast-checked), 16 bundled fonts, 162 icons, layout variants, a browser design checker, no em dashes and no stock phrases in generated text |
| Phone page | `neuron/server/` | Light phone web page on the local network: pairing codes, goals with attachments, follow-ups as a conversation, live steps and evidence, approvals, app previews, downloads, stop and resume, memory and model status, optional HTTPS |
| Installer | `scripts/install.sh`, `neuron/install.py` | Detects memory, picks the frozen model, resumable download with checksum check, self-test, start |
| Online boost | `neuron/online/` | Optional: chosen roles may use an online model when the owner turns it on; any problem falls back to the local model |

## Honest limits

- **Not yet measured with real models:** the general agent and its tools (phase 3 and 4) have only been tested
  with scripted model replies. The phase-5 evaluation will show how they do with the frozen models.
- **The 2 GB model is weak:** 8 of 12 on the dev set, where it was also tuned.
- **Small computers are slow.** Writing speed follows memory bandwidth: about 4 tokens per second for the
  8 GB model here, 17 to 36 for the smallest. A task can take many minutes.
- **The 4 GB tier is tight:** peak 3994 of 4096 MB.
- **Web apps are simple data apps** (lists, forms, search, login, dashboard counts, linked records with one
  rule each). Links use the record's name, so two records with the same name are not told apart.
- **Phone traffic is plain HTTP by default** on the local network. Pairing protects access; `start.sh --https`
  encrypts it with a certificate made on your computer (the phone warns once; compare the printed fingerprint).
- **Tested only in a cloud Linux container**, not yet on a home PC, a real phone, Windows or Mac.
- One full test-suite run of five had one failing test whose name was not captured (it ran while a
  benchmark used every core); the next runs all passed. Logged in `PROGRESS.md`.

## Tests

`python3 -m unittest discover -s tests`: every automated test (the count is printed). Browser tests need
Node with Playwright; sandbox tests need bubblewrap. Tests use scripted model replies so they are fast and
exact; they are never used to produce a benchmark score.

## Repository map

```
neuron/brain/        model runner, tiers, model manager, sandbox, step-1 task engine
neuron/agent/        general agent: loop, state, router, context, capabilities/
neuron/builder/      app builder: spec, tasks, checks, templates, links and rules, design step
neuron/design/       design engine and checks          neuron/kit_next/   kit used by built apps
neuron/server/       phone web page and job manager    neuron/online/     optional online boost
neuron/install.py    installer logic                   scripts/           install and download scripts
benchmark/           step-3 harness, dev and held-out tasks, phase5/ locked evaluation, results/
model_manifests/     model descriptions and frozen.json
docs/                history, phone screenshots
```
