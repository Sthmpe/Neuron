# Phase 5 evaluation: LOCKED

Locked on 2026-11-17 before any of the new system was built or tuned on it.
Fingerprint of every task, input, checker and workspace file: `58c9d515c4f189686786acdc21ad8489b1095e0f725f82e21c6e3c8e2b063f2b`
(per-file SHA-256 in `LOCK.json`; `python3 benchmark/phase5/verify_lock.py` re-checks them).

- `locked/tasks.json`: 12 tasks used only for scoring (PDF research, Excel, Word, PowerPoint, a C++ program,
  3 C++ and 2 Go workspace bugs, an unseen shop web app killed halfway and resumed, a long docstring task
  killed halfway and resumed).
- `dev/tasks.json`: 7 tasks for building and tuning the system. Never mixed with the locked set.
- Every checker was validated: a correct reference passes it, a broken or empty one fails it.

## Amendments

1. 2026-11-17: `examiners/docs.py` totals-row detection fixed (a column header named "Total" was
   mistaken for the totals row, which would have failed correct workbooks). Found by a dev-set test before any
   locked task was run. New fingerprint `20e5fa0a39cfadcc85314244f8d427d2e60f08d62d72efbf53cff70116927fe7` (old `58c9d515c4f189686786acdc21ad8489b1095e0f725f82e21c6e3c8e2b063f2b`).
2. 2026-11-18: `examiners/code.py` docstring check fixed: it marked short docstrings that were already in the
   original project (`format_naira`), although the task asks only for functions that do not already have one.
   Found AFTER locked runs (4 GB L12 official run and two labelled reruns). No agent was rerun for this: the files
   already delivered were examined again with the fixed checker, and both scores are kept in the results.
   New fingerprint `acd637db90683f5b7ed811375dc7ae632a542382e77245ec7985ab883a352d33` (old `20e5fa0a39cfadcc85314244f8d427d2e60f08d62d72efbf53cff70116927fe7`).
3. 2026-11-18: `examiners/code.py` crashed (FileNotFoundError) when a task delivered no app folder, instead of
   failing its checks; this stopped the 2 GB locked run at L11. Fixed to fail the checks. The agent was NOT rerun:
   the folder it delivered was examined with the fixed checker (`run.py --examine-existing`).
   New fingerprint `69198864bfe616904a24d2cebee0ce8ceda64b9e80d97c17b2c96183bbab9c97` (old `acd637db90683f5b7ed811375dc7ae632a542382e77245ec7985ab883a352d33`).
