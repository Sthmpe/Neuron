# Core proof: bare model vs full NEURON on 32 complex tasks

**The question.** Does the same model finish complex, multi-step work more often, faster or with less memory inside
NEURON than on its own? This doesn't test whether the model got smarter. Both sides used the same frozen model per
tier (2 GB `qwen2.5-coder-1.5b-q4`, 4 GB `qwen3.5-4b-q4`).

**The setup.** 32 new tasks were written and locked before any run or tuning (`LOCKED.md`, `LOCK.json`): 8 business app
builds, 8 whole-project bug fixes, 8 multi-file features, 8 documents (Excel, Word, PowerPoint, PDF answers). Both
sides ran each task 3 times on 2 GB and on 4 GB, for 384 runs. They had the same model, tier, sandbox, time budget and
seed, with the network cut and knowledge memory off. The bare model ran a plain tool loop (write a file, run a command,
read a file, done). To keep the comparison conservative it also got extra help: the project files and the test
command up front, the input text, and NEURON's app kit with its guide. A task counts as completed only when an
independent examiner passes every check. Apps are used in a real browser, code is tested with the original tests put
back plus hidden tests, and documents are checked by eval2's examiners.

Counted runs: 2026-11-20 09:35 to 2026-11-21 04:48, code at `d41f5b0` (NEURON's code did not change during the runs).

## Results (counted runs, examiners exactly as locked)

| Tier | Condition | Runs | Completed | Rate | Median time | Median time when completed | Peak RAM, median / max | False claims |
|---|---|---|---|---|---|---|---|---|
| 2 GB | bare model | 96 | 4 | 4.2% | 43.8 s | 42.5 s | 1461 / 1735 MB | 61 |
| 2 GB | **NEURON** | 96 | **25** | **26.0%** | 65.8 s | 17.5 s | 1517 / 1768 MB | 31 |
| 4 GB | bare model | 96 | 39 | 40.6% | 259.1 s | 124.6 s | 4075 / 4087 MB | 20 |
| 4 GB | **NEURON** | 96 | **44** | **45.8%** | 164.8 s | 90.0 s | 3914 / 4078 MB | 22 |

- **Completion.** NEURON completes more on both tiers: about 6 times as many tasks on 2 GB (25 vs 4) and somewhat more
  on 4 GB (44 vs 39).
- **Time.** On 4 GB, in the 20 runs where both sides completed the same task, NEURON was faster in 17 (median 90 s vs
  154 s). Over all 4 GB runs NEURON used 6.2 hours and the bare model 7.9. On 2 GB the two never completed the same
  run, so there's no paired time.
- **Memory.** About the same: both run up to the tier's limit, because the model dominates. On 4 GB the bare model's
  model server was killed by the limit 15 times (its sandboxed test runs count toward the same limit). NEURON's
  peaks were slightly lower.
- **False claims** (NEURON says VERIFIED, or the bare model says DONE, but the examiner fails the delivery). NEURON
  made half as many as the bare model on 2 GB (31 vs 61) and about the same on 4 GB (22 vs 20). That's still far
  from zero; see below.

### By kind of task

| Tier | Kind | Bare model | NEURON |
|---|---|---|---|
| 2 GB | app builds | 0/24 | **9/24** |
| 2 GB | bug fixes | 1/24 | 1/24 |
| 2 GB | features | **3/24** | 0/24 |
| 2 GB | documents | 0/24 | **15/24** |
| 4 GB | app builds | 0/24 | **9/24** |
| 4 GB | bug fixes | **22/24** | 17/24 |
| 4 GB | features | **13/24** | 0/24 |
| 4 GB | documents | 4/24 | **18/24** |

Per task (completed runs out of 3):

| Task | 2 GB bare | 2 GB NEURON | 4 GB bare | 4 GB NEURON |
|---|---|---|---|---|
| A1 pharmacy (stock rule) | 0 | 0 | 0 | 3 |
| A2 tailor | 0 | 3 | 0 | 3 |
| A3 school fees | 0 | 3 | 0 | 3 |
| A4 savings group | 0 | 3 | 0 | 0 |
| A5 library loans (stock rule) | 0 | 0 | 0 | 0 |
| A6 gym members | 0 | 0 | 0 | 0 |
| A7 event tickets (seat rule) | 0 | 0 | 0 | 0 |
| A8 repair shop website | 0 | 0 | 0 | 0 |
| B1 Python invoice | 0 | 0 | 3 | 3 |
| B2 Python inventory | 0 | 0 | 3 | 3 |
| B3 Python schedule | 0 | 0 | 2 | 3 |
| B4 JavaScript cart | 0 | 1 | 3 | 1 |
| B5 JavaScript CSV | 0 | 0 | 3 | 3 |
| B6 Go payroll | 0 | 0 | 3 | 0 |
| B7 Go stats | 1 | 0 | 3 | 3 |
| B8 C++ bank | 0 | 0 | 2 | 1 |
| C1 Python discounts | 0 | 0 | 0 | 0 |
| C2 Python CSV export | 0 | 0 | 3 | 0 |
| C3 JavaScript delivery fee | 0 | 0 | 2 | 0 |
| C4 Go payslip | 3 | 0 | 3 | 0 |
| C5 Python notes search | 0 | 0 | 0 | 0 |
| C6 JavaScript overdue items | 0 | 0 | 0 | 0 |
| C7 C++ triangle | 0 | 0 | 3 | 0 |
| C8 Python temperatures | 0 | 0 | 2 | 0 |
| D1 Excel regional sales | 0 | 3 | 0 | 3 |
| D2 Excel staff costs | 0 | 3 | 0 | 3 |
| D3 Excel expenses | 0 | 3 | 0 | 3 |
| D4 Word repair letter | 0 | 0 | 0 | 0 |
| D5 Word leave policy | 0 | 0 | 0 | 0 |
| D6 PowerPoint AGM | 0 | 3 | 3 | 3 |
| D7 PowerPoint fire safety | 0 | 3 | 1 | 3 |
| D8 PDF clinic answers | 0 | 0 | 0 | 3 |

## What NEURON completes and the bare model fails, and why

- **Business apps with a login, records, linked records, computed costs and a dashboard** (A2, A3, A4 on 2 GB; A1,
  A2, A3 on 4 GB; every run). On 2 GB the bare model's apps start, but the forms lack fields the request named, or the
  app doesn't start at all (it forgot the setup function and said DONE without running it). On 4 GB the bare model
  writes long files over many turns, and its sandboxed test runs push the 4 GB limit until the model server is killed.
  NEURON plans the app into a specification, builds it from tested templates and checks it in the sandbox, in 85 to
  300 seconds and 4 model calls.
- **Excel workbooks with real formulas from a CSV** (D1 to D3, every run on both tiers). The bare model on 2 GB writes
  a Python script into the `.xlsx` file itself, or never produces the file. On 4 GB it runs out of the 8 minutes, or its
  workbook has values instead of formulas. NEURON makes each workbook in 10 to 30 seconds with one model call, and
  recalculates it in LibreOffice to check it.
- **PowerPoint decks with required content** (D6, D7 on 2 GB; D7 on 4 GB). The bare 1.5B model writes a script into
  the `.pptx` file. On 4 GB it gets there for D6, but misses required facts in D7 in 2 of 3 runs.
- **Answers from a PDF with page numbers** (D8 on 4 GB, every run). The bare model answers without the right facts or
  pages. NEURON indexes the pages and quotes them; on 4 GB it was right in every run, though it labelled itself only
  PARTIAL (its fact check is cautious).

## Where the bare model does better, and why

- **Adding a feature to an existing project** (C2, C3, C4, C7, C8 on 4 GB; C4 on 2 GB). NEURON had **no capability for
  this**. The requests went to the bug fixer, which saw the tests already passing and called the job VERIFIED with
  nothing written, or to the docstring writer. That's 0 of 48 completed, and it's the source of most of NEURON's false
  claims (30 of 53). The bare 4B model, given the whole small project and the test output, wrote the feature in 2 to 5
  calls.
- **Bug fixing with the 4B model** (B4, B6, B8). NEURON's narrow pipeline (point at one function, ask for a two-line
  OLD/NEW patch) missed bugs the plain loop fixed. In B4 the model's diagnosis was right but its edit "could not be
  applied". In B6 the wrong value was a constant outside any function, which NEURON never looked at, and the diagnosis
  was cut off at 300 tokens. In B8 a fee was charged twice. NEURON did report these honestly as PARTIAL (no false
  claims on bugs).

## Also not completed by either

- **A5** (library stock rule): NEURON's builder rejected its own correct app (a defect found while validating the
  examiner and deliberately left unfixed before the runs).
- **A6**: NEURON's dashboard counts members "under 10000". The locked examiner accepts only "less" or "below", and it
  also clicked the app's logo instead of the menu item (see amendment 1 below).
- **A7**: on 2 GB the sale form lacks the tickets field.
- **A8** (website): the request says "fix charging ports", and a router defect sent it to the bug fixer in an empty
  folder (0.5 seconds, PARTIAL).
- **D4, D5** (Word): the requested table was not recognised and the word range was missed.

## Integrity notes

- Examiners and tasks were never changed after the lock (`verify_lock.py`: LOCK INTACT).
- **Runner amendments**, recorded in `LOCKED.md`, change how a pass proceeds, not what is measured. R1: an examiner
  crash on an unreadable file (a script saved as `.xlsx`) now counts as a failed check instead of stopping the pass.
  R2: the 4 GB limit killed the runner itself once, so the runner can no longer be the process the limit picks, and
  orphans are cleared. Three attempts that produced no row were run again; each is labelled in its row's `note`.
- **Proposed examiner amendment 1, not applied (your decision).** The app examiner opens a page by clicking the first
  link containing the page's word. In A6 that is the logo "Gym Members", and in A7 on 4 GB it is "Ticket Sales". Only
  NEURON's 12 A6/A7 deliveries are affected. With the fix, 2 of them become completed (4 GB A7 runs 2 and 3: 8/15 to
  15/15), which would make 4 GB NEURON 46/96 instead of 44/96. Details: `amendments/amendment1_effect.json`.
- **Not changed on purpose.** I didn't widen the A6 dashboard wording after seeing NEURON's "under": that would tilt the
  examiner toward NEURON.
- Smoke tests before the counted runs are kept as `2gb-run1-smoke*.json` and not counted.

## After the runs: fixes made, and labelled reruns

These fixes come from failures on these same tasks, so a rerun on them **overstates** the general gain. They are
labelled `after-fixes` and kept apart from the counted results above. The bare model's results stay as counted (its
harness did not change).

1. **Add a feature to an existing project** (new capability `add_feature`). One call writes all files, the project's
   tests must keep passing, NEURON writes its own test from the request's examples, and one combined call fixes
   failures. Guards: tests are never edited, functions are never dropped, a failing own test is removed.
2. **No VERIFIED for a bug fix that changed nothing** (tests already passing).
3. **Router**: the "is there code here?" check was always true. Apps NEURON built no longer count as code.
4. **Bug fixing**: wider standard repair changes (scale a constant, drop or add `/ 100`, widen an index to a slice,
   delete a duplicated statement). The search now covers Python and constants outside functions. Edits apply despite
   spacing differences, the diagnosis gets room to finish, and a whole-file rewrite with the test output is the
   second strategy (the plain-loop approach, with NEURON's guards).
5. **Builder**: dashboard checks follow stock rules (A5). A stock rule the request describes but the plan dropped is
   built from the request (A1 on 2 GB) or reported as not built. Counts below a threshold say "fewer than".
6. **Word**: tables in ordinary phrasing are recognised, and the word range is met by code.
7. **PDF**: an exact quote cited with the wrong page is cited where it is. Answers are checked with Astra's stricter
   fact matcher (adopted from `research/astra` 8f77a44).

Labelled rerun results: see the next section (filled in as the runs finish).

### After-fixes reruns (labelled; NEURON only)

(in progress)
