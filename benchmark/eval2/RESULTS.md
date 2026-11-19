# eval2: official locked runs (2026-11-19)

The second locked evaluation (`LOCKED.md`; tasks, sources, projects and examiners fingerprinted before any tuning; the
lock check passed right before the runs). One official run per tier, the same NEURON code for all three (no change
under `neuron/` between the runs), knowledge memory off, network cut, each run inside its tier's memory limit; tasks
E10 and E11 killed halfway and resumed. "Says" is NEURON's own verdict; a false claim is "VERIFIED" for a task the
examiner did not pass. Raw results: `benchmark/results/phase5/eval2-locked-<tier>.json`; logs:
`benchmark/run/phase5/eval2-locked-<tier>/`.

| Task | 2 GB | 4 GB | 8 GB |
|---|---|---|---|
| E01_pdf_market | not solved (10/12), says VERIFIED **FALSE CLAIM** | solved (12/12), says VERIFIED | solved (12/12), says VERIFIED |
| E02_excel_clinic | solved (10/10), says VERIFIED | solved (10/10), says VERIFIED | solved (10/10), says VERIFIED |
| E03_word_notice | not solved (3/5), says PARTIAL | not solved (3/5), says PARTIAL | not solved (3/5), says PARTIAL |
| E04_pptx_training | solved (9/9), says VERIFIED | solved (9/9), says VERIFIED | solved (9/9), says VERIFIED |
| E05_python_bug | solved (1/1), says VERIFIED | solved (1/1), says VERIFIED | solved (1/1), says VERIFIED |
| E06_js_bug | solved (1/1), says VERIFIED | solved (1/1), says VERIFIED | solved (1/1), says VERIFIED |
| E07_go_bug | not solved (0/1), says PARTIAL | solved (1/1), says VERIFIED | solved (1/1), says VERIFIED |
| E08_rust_bug | solved (1/1), says VERIFIED | solved (1/1), says VERIFIED | solved (1/1), says VERIFIED |
| E09_cpp_csvsum | not solved (0/1), says PARTIAL | not solved (1/5), says PARTIAL | solved (5/5), says VERIFIED |
| E10_repair_app | solved (11/11), says VERIFIED | solved (11/11), says VERIFIED | solved (11/11), says VERIFIED |
| E11_long_docstrings | solved (4/4), says VERIFIED | solved (4/4), says VERIFIED | solved (4/4), says VERIFIED |
| E12_computed_answer | not solved (1/2), says VERIFIED **FALSE CLAIM** | not solved (1/2), says VERIFIED **FALSE CLAIM** | solved (2/2), says VERIFIED |
| **Total** | **7/12**, false claims 2, 19 min | **9/12**, false claims 1, 58 min | **11/12**, false claims 0, 35 min |

## What it shows

- The target of zero false "verified" claims is **met on 8 GB and not met on 2 GB (2) or 4 GB (1)**.
- Both causes are general and are fixed in the system (commit 4215bc7), measured on dev tasks only, never on these:
  1. E12 (2 and 4 GB): a plain answer to a question was reported VERIFIED although nothing independent had checked it
     (its own check said "unverified"). Fix: such answers get their own verdict, "answered, not checked", never VERIFIED.
  2. E01 (2 GB): one of six questions was answered "not found", and the job still said VERIFIED. Fix: an unanswered
     question makes the job PARTIAL and names the question.
- E03 (Word notice) failed on every tier with the same two checks: a recurring weakness in long documents with tables.
- The unseen repair-shop app with computed totals (E10) was solved on every tier, including after a kill and resume.
- C++ from a description (E09) only on 8 GB; Go bug fixing (E07) on 4 and 8 GB (the locked phase-5 set had 0 of 2 on
  every tier before the repair improvements).

## After the fixes (dev tasks only; eval2 is not rerun)

`benchmark/honesty_dev` (3 calculation questions and 1 PDF question the document does not answer), 2 GB model:
0 false claims, 4 of 4 honest verdicts (UNVERIFIED for the answers, PARTIAL naming the unanswered question). It also
showed the 2 GB model's answers were wrong or empty (0 of 3); calculations now always run as a program in the sandbox
and an empty answer is a failure. Labelled rerun (`2gb-rerun1-require-code`): 2 of 3 right, still 0 false claims.
