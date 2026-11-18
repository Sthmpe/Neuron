# eval2: second locked evaluation (LOCKED)

Locked on 2026-11-18, before any tuning on it, as step 5 of the owner's plan. Fingerprint of every task, source,
project and examiner file: `e72a2d9eea673a34e0e46879a4ddc5faa578c91bf6132a041841b4481bde5322` (per-file SHA-256 in
`LOCK.json`; `python3 benchmark/eval2/verify_lock.py` re-checks them). All content is invented for this evaluation.

| Task | What | Judged by |
|---|---|---|
| E01 | Answers from a 3-page PDF report, with page numbers (6 questions) | facts in the answer and the cited page |
| E02 | Excel summary per department: total visits and total fees (quantity x price), Total row, formulas | LibreOffice recalculation vs an independent calculation |
| E03 | Word notice with three headings, 200-400 words, a costed table with a total | python-docx: headings, length, table values and total |
| E04 | 5-slide PowerPoint training deck, at most 5 bullets, must mention the kitchen and 75 degrees | python-pptx + rendering |
| E05-E08 | One planted bug each in Python, JavaScript (Node), Go and Rust projects | the project's ORIGINAL tests, restored before running |
| E09 | C++17 program csvsum from a description | 4 hidden CSV cases against a reference implementation |
| E10 | Unseen repair-shop app with login, customers, repairs with computed totals and a total-billed dashboard; killed halfway and resumed | a real browser, like a person, at desktop and phone width; restart |
| E11 | Docstrings for every undocumented function of a project; killed halfway and resumed | AST: code unchanged, docstrings present and meaningful, original tests pass |
| E12 | A question that needs calculation (VAT on a purchase) | the right number in the answer |

Every examiner was validated before the lock (`validation.json`): a correct reference passes it, a wrong or empty
delivery fails it. Run with `python3 -m benchmark.phase5.run --suite eval2 --set locked --tier <tier>`.

Rules: no tuning on these tasks; examiner changes only as numbered amendments below, with the reason; reruns are
labelled; evaluations run with knowledge memory off.

## Amendments

(none)
