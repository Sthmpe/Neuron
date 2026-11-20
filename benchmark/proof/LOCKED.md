# Core proof: 32 complex tasks, bare model vs full NEURON (LOCKED)

Locked on 2026-11-20, before any run and before any tuning on these tasks. Fingerprint of every task, workspace,
hidden test, spec, source and examiner file: see `whole` in `LOCK.json` (per-file SHA-256 there;
`python3 benchmark/proof/verify_lock.py` re-checks them, and the runner refuses to start if anything changed).
All content is invented for this evaluation.

The question: does the same model complete complex multi-step work more often, faster or with less memory inside
NEURON than on its own? Not a smarter model: the same frozen model per tier (2 GB `qwen2.5-coder-1.5b-q4`,
4 GB `qwen3.5-4b-q4`) in both conditions.

| Ids | What | Judged by |
|---|---|---|
| A1-A7 | Business apps from a plain request: login, records, linked records, computed values, rules, dashboards, search | a real browser, used like a person, from an empty database: login required, wrong password refused, the task's flows with expected numbers, phone width, no server errors, data still there after a restart |
| A8 | A small business website (no login) | the same browser examiner: facts present, phone width, no errors |
| B1-B8 | One planted bug in a whole project (Python, JavaScript, Go, C++) | the project's ORIGINAL tests, put back over any edits, plus hidden tests |
| C1-C8 | A multi-file feature in an existing project (new module + changes to existing code) | the original tests plus hidden tests of the feature |
| D1-D3 | Excel summaries from a CSV, with formulas and a Total row | eval2's examiner (recalculated, compared with an independent calculation) |
| D4-D5 | Word documents with headings, a word range and a table with a total | eval2's examiner |
| D6-D7 | PowerPoint decks with a slide count, required content and a bullet limit | eval2's examiner |
| D8 | Six answers from a 3-page PDF, with page numbers | eval2's examiner (fact and cited page) |

Time budget per task (the same for both conditions): apps 900 s, bugs 600 s, features 720 s, documents 480 s.
Each condition is killed at budget + 60 s and whatever it delivered is examined.

Every examiner was validated before the lock (`validation.json`): a correct reference passes it, an empty or
as-shipped delivery fails it.

## Protocol (fixed before the first run)

* Conditions. NEURON: `python3 -m neuron.agent <request> --workspace JOB --tier T --max-seconds BUDGET`, exactly as a
  person would run it. Bare model: `benchmark/proof/bare.py`, a plain tool loop (WRITE a file, RUN a command, READ a
  file, DONE) with the same model, the same sandbox (bubblewrap, no network, compilers mounted) and the same budget.
  To keep the comparison conservative the bare model also gets things a plain chat would not: the project's text files
  and its test command up front, the extracted text of the inputs, and for apps NEURON's kit already in place with its
  guide and example files.
* Same model, tier and seed. Both run as their own process inside the tier's memory cgroup (the model server too),
  network cut, knowledge memory off, `NEURON_SEED` = the run number (1, 2, 3) for both.
* Order. Per task the two conditions alternate which goes first.
* Runs. Each task 3 times per condition on 2 GB and on 4 GB: 384 runs.
* Reported. Completion rate (solved = every examiner check passed), wall time, peak memory of the tier, model calls
  (counted from the model server's log), and false claims (NEURON says VERIFIED or the bare model says DONE, but the
  examiner fails it).
* The bare loop also stops after 3 replies in a row with no action, or the same reply 3 times in a row (with a fixed
  seed it would keep repeating).

## Rules

No tuning on these tasks. Examiner changes only as numbered amendments below, with the reason. Reruns are labelled.
Any change to NEURON or to the bare harness after the first counted run is an amendment, and the affected runs are
repeated and labelled.

Known before the runs and deliberately left unfixed: NEURON's builder rejects its own correct template for
A5_library_loans (with a refusing stock rule its dashboard self-check expects the wrong count). Found while
validating the examiner; fixing it before the runs would be tuning on the locked set. It is fixed after the counted
runs, with a labelled rerun.

Harness smoke tests (not counted, kept as `2gb-run1-smoke*.json`), 2 GB, run 1, to check that both conditions start,
deliver and are examined: B1_py_invoice and D3_excel_expenses (smoke), the same two for the bare model after a prompt
fix (smoke2), and A6_gym_members (smoke3). Only harness and examiner faults may be fixed after them.
* smoke: the 1.5B model copied the bare protocol's placeholder literally ("WRITE path/to/file"). The bare prompt now
  shows a concrete example reply instead (harness fault, fixed before any counted run; it helps the bare model).
* smoke: NEURON's own report undercounts model calls made inside its fix loops (1 reported, 7 in the server log). The
  runner therefore counts model calls and tokens from the model server's log for both conditions; the self-reports
  are kept beside them.
* smoke3: examiner fault, see proposed amendment 1 (not applied).
* smoke3, deliberately NOT changed: NEURON labelled a dashboard card "Members under 10000" and the A6 examiner only
  accepts "less" or "below" near that number. Widening the accepted words after seeing NEURON's output would tilt the
  examiner toward NEURON, so the labels stay exactly as validated. The examiner is strict here for both conditions.

## Amendments

(none applied; the counted runs use the examiners exactly as locked)

Proposed, awaiting the owner's decision:

1. (2026-11-20, found by smoke3, before any counted run) `app_exam.js` opens a page by clicking the first link whose
   name contains the page's word. In A6 that was the logo "Gym Members", which leads to the dashboard, so every step
   on the Members page failed although the page and its form were there (NEURON's smoke3 app: 6/12 with the locked
   examiner, 11/12 when opened correctly). The proposed fix clicks the link named exactly like the page first, then
   the shortest visible link containing the word, opening the phone menu if needed, and only then types the address.
   Files: `amendments/amendment1.diff`, `amendments/app_exam_amendment1.js`; with it every examiner still passes its
   validation (`amendments/validation_amendment1.json`: references pass, empty deliveries fail).
   Changing a locked examiner and rewriting the fingerprint is the owner's decision, so it was not applied. If it is
   approved, no condition is rerun: the app folders already delivered (all kept under `benchmark/run/proof/`) are
   examined again with the fixed examiner and both scores are reported, as in phase 5's amendments 2 and 3. The fault
   can only hide successes (an app whose logo contains a page's word); it never passes a broken app.
