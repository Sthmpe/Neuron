# NEURON

NEURON is a personal AI computer that works offline. A small open model runs on your own computer; you
describe a goal in plain words from your phone, and NEURON plans the work, does it with real tools
(spreadsheets, documents, slides, answers from PDFs, fixing bugs in whole code projects, building small
business web apps), checks the result with independent tests, and shows you the evidence. The internet
is never required. An optional online boost can be switched on by the owner.

Read [`VISION.md`](VISION.md) for where this is going, [`TESTING.md`](TESTING.md) to try it yourself,
[`PROGRESS.md`](PROGRESS.md) for the detailed log, [`HARDWARE.md`](HARDWARE.md) for what limits it on real
machines.

## Where it stands (2026-11-18)

| Phase | What | State |
|---|---|---|
| 0 | Finish step 3: model selection, held-out scoring, design system, honest numbers | **Done**: held-out scored (below); design system on by default, 20-request proof run once (19 of 20 built) |
| 1 | `VISION.md` | Done |
| 2 | One frozen model per memory tier | **Done**: `model_manifests/frozen.json` |
| 3 | Better intelligence with the same models (state, context slices, shared loop, strategies, roles, verification) | Built in `neuron/agent/`; **measured** in phase 5 (below) |
| 4 | Tool registry with purpose, inputs, outputs, internet, permissions, resources, verification; honest missing-tool reports | Built: 20 capabilities |
| 5 | New evaluation, tasks locked before tuning | **Done** on all three tiers (below), with three recorded examiner amendments |
| 6 | Owner release: installer, phone web page with secure pairing, offline, `TESTING.md` | Built and tested in a cloud Linux container; not yet on a home PC or a real phone |
| 7 | Optional online boost; hardware bottleneck log; this README | Done: boost (off by default), `HARDWARE.md`, this README |

Owner's execution plan of 2026-11-18 (backlog with evidence in [`MASTER_ROADMAP.md`](MASTER_ROADMAP.md)):

| Step | State |
|---|---|
| 1. Master roadmap | Done |
| 2. Usable release (clean Linux retest, Windows via WSL2) | Linux retested from a clean setup (4/4 real tasks after fixes); Windows written, **waiting for your test** |
| 3. Scorecard (MMLU-Pro, GPQA Diamond, LiveCodeBench, BFCL) | **Done** ([`SCORECARD.md`](SCORECARD.md)): full NEURON beats the model alone on MMLU-Pro for 4 GB (10 to 18 of 28) and 8 GB (9 to 17), both shown by a paired test; no shown difference elsewhere; samples, not full runs |
| 4. Knowledge memory | Built (keyword + meaning search, 2 GB-friendly embedding model, fallback); no reliable effect on an easy task pair |
| 5. New locked set, honesty, totals, C++/Go | eval2 locked before tuning and run: 2 GB 7/12, 4 GB 9/12, 8 GB 11/12; false "verified" claims 2, 1, 0 ([results](benchmark/eval2/RESULTS.md)); the two causes are being fixed; repair-shop app with totals solved on every tier |
| 6. Offline to online | Built: waiting steps resume by themselves, crash-safe outside actions, licensed photos with sources, safe package upgrades (real pip and npm runs) |
| 7. Creative quality | Content rules built; 3 reference sites built, **waiting for your approval** ([`docs/REFERENCE_SITES.md`](docs/REFERENCE_SITES.md)) |

## Try it

Linux: tested on Ubuntu 24.04 (cloud machine, clean setup, real download and real tasks: see below).
Windows 10/11: installer through WSL2 written (`scripts/install-windows.ps1`), **not yet run on Windows**; the owner's
test is in `TESTING.md` section 1b. Mac: not supported yet.

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

### Release retest from a clean setup (2026-11-18)

Fresh copy of the code, empty NEURON home, llama.cpp built from source, the real 4.64 GB model download for the tier
the installer picked (8 GB on this 16 GB machine), checksum matched, model self-test 5.6 tokens/s, sandbox passed.
Then four new real tasks through the phone API (`benchmark/release/retest.py`): run 1 solved 2 of 4 and found three
bugs (a llama.cpp build break from changed UI downloads, a Word letter routed to code fixing because it said "fix",
an app without a dashboard opening on "Not found"); after the fixes, run 2 (labelled rerun) solved **4 of 4**:
Excel with formulas plus a follow-up, a Word letter, an answer, and a bookshop app with a stock rule.
Screenshots of the real install: `docs/screens/release/`.

### Phase 5: locked evaluation (2026-11-18)

12 tasks locked before the system was built: answers from two PDFs with page citations, an Excel summary with
formulas, a Word proposal with a budget table, a PowerPoint pitch, a C++ command-line program, three bugs in a C++
project and two in a Go project, an unseen shop app (killed halfway, then resumed), and a docstring job too big for
one context window (killed halfway, then resumed). Judged only by independent examiners (LibreOffice recalculation
and rendering, the projects' original tests, a real browser). Full tables: [`benchmark/results/phase5_summary.md`](benchmark/results/phase5_summary.md).

| Task | 2 GB | 4 GB | 8 GB |
|---|---|---|---|
| PDF answers with citations | 9/16 | 15/16 | 14/16 |
| Excel with formulas | yes | yes | yes |
| Word proposal | yes | yes | yes |
| PowerPoint pitch | yes | yes | yes |
| C++ program from a description | no (did not build) | no (did not build) | **yes (7/7)** |
| C++ project bugs (3) | 1 | 1 | 2 |
| Go project bugs (2) | 0 | 0 | 0 |
| Shop app, killed and resumed | 0/17 | 5/17 * | 13/17 |
| Docstrings, killed and resumed | yes | 3/4 * | yes |
| **Solved (of 12)** | **5** | **4** | **7** |

\* The 4 GB official run hit NEURON bugs: the resumed jobs could not restart their model server (the old one's port
was still reserved), and NEURON's own app checks rejected a correct page. Both were fixed before the 2 GB and 8 GB
runs. Labelled reruns of the two resumed tasks at 4 GB after the fixes: shop app 13/17, docstrings 4/4. In the same
run the memory limit killed the model server during one C++ bug task and it was not restarted (fixed after all
runs). So the tiers did not run identical code; each result file records its commit.

What this says:
- Documents are dependable on every tier: Excel, Word and PowerPoint were solved by all three models.
- Resuming after a kill works (after the fixes): both resumed tasks continued from their saved state and finished.
- The shop app gets the hard parts right (login, stock goes down when an order is added, an oversized order is
  refused, data survives a restart) but not computed order totals, a revenue sum on the dashboard, or writing its
  own tests: the builder cannot express those yet.
- Bugs in compiled-language projects are weak: 1 to 2 of 5, and no tier fixed a Go bug.
- **False claims:** in the official runs the agent said "verified" on 3 tasks the examiner did not fully pass: the PDF
  answers at 4 GB and 8 GB (the quote was really on the cited page, but an answer was wrong) and the shop app at 8 GB
  (features it cannot build were silently left out); the 4 GB shop rerun did the same. Fixing this honesty gap is
  the next priority. (A first fix is in: unbuildable requested features are now reported and the job says PARTIAL;
  answer numbers must appear in the quote. Not yet re-measured.)

### Step 3 held-out scoring (2026-11-18)

20 new bug projects, 3 new app builds (a landing page, a customer and stock app, the same app killed halfway and
resumed) and 10 bugs in whole multi-module codebases. Written before tuning, run once per tier, with the NEURON
loop (full) and without it (base: one prompt per attempt, no saved state, no roles).
Details: [`benchmark/results/heldout_summary.md`](benchmark/results/heldout_summary.md).

| Tier | Loop | Bugs (of 20) | App builds (of 3) | Workspace bugs (of 10) | Minutes | Peak MB |
|---|---|---|---|---|---|---|
| 2 GB | base | 5 | 0 | 0 | 46 | 1467 |
| 2 GB | **full** | 7 | **3** | 3 | 23 | 1510 |
| 4 GB | base | 19 | 1 | 3 | 70 | 3996 |
| 4 GB | **full** | **20** | **3** | 6 | 58 | 3996 |
| 8 GB | base | 19 | 2 | 5 | 85 | 5655 |
| 8 GB | **full** | 19 | **3** | **7** | 51 | 5735 |

The loop matters most for the weak model and for app builds (every tier built all three apps with it), and it was
faster at every tier. The 4 GB model is the best value on this machine.

Labelled rerun of the 3 builds with the system as it runs now (design system on, template fallback, links and rules):
first it exposed a regression (the 2 GB model invented rules and its plans were rejected: 0/19 on both shop apps);
after the fix, **9 of 9 builds pass on all tiers**, every page written by the model (no template needed), 0 design
check failures. (`benchmark/heldout_current.log`)

### Design system proof (20 requests, 2 GB model)

19 of 20 sites built; 20 different palettes, 5 hero layouts, any two designs share at most 4 of 8 main choices,
every colour the owner named was kept. Screenshots: [`benchmark/design/results.md`](benchmark/design/results.md).
Problems it found, since fixed: a form called "join" (an SQL keyword) broke one build; the hero repeated the next
section; section gaps too large; the model copied the example's database file into a site.

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

- **The agent sometimes claims more than it did** (3 false "verified" claims in the official locked runs, listed above).
  Every result still shows its evidence, and the examiners caught these, but the claim itself is not yet trustworthy.
- **Compiled-language bug fixing is weak** (C++ 1 to 2 of 3, Go 0 of 2 in the locked set). One-token bugs are now
  fixed by a model-free search (4 of 4 on the dev set); real-model runs of the new system are still to come.
- **The 2 GB model is weak**: it never produced a valid plan for the shop app, and fixed 7 of 20 held-out bugs.
- **The 4 GB tier is tight**: the memory limit killed the model server once while a C++ project compiled (the
  runner now restarts it). Peak 4084 of 4096 MB.
- **Small computers are slow.** Writing speed follows memory bandwidth: about 4 tokens per second for the
  8 GB model here, 17 to 36 for the smallest. A task can take many minutes.
- **Web apps are simple data apps** (lists, forms, search, login, dashboard counts and sums, linked records with one
  rule each, computed totals such as quantity times price). Computed totals are not yet measured with the real models.
  Websites are one page.
- **Licensed photos could not be fully tested here**: Wikimedia rate-limits the cloud machine's shared address, so
  sites show labelled "Image needed" placeholders until photos arrive (your own photos always come first).
- **Phone traffic is plain HTTP by default** on the local network. Pairing protects access; `start.sh --https`
  encrypts it with a certificate made on your computer (the phone warns once; compare the printed fingerprint).
- **Tested only in a cloud Linux container**, not yet on a home PC, a real phone, Windows or Mac. That machine
  restarted several times during the evaluations; finished results were kept and interrupted tasks rerun from
  scratch (all noted in the logs).

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
