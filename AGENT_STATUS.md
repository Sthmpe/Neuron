# Astra phase 1

I chose the verdict on ordinary questions. At the starting commit a model answer could be marked VERIFIED even when its own evidence explicitly said “unverified”. I traced this from the capability to the phone and reproduced it with a deliberately wrong scripted answer. The independent review is in `docs/reviews/astra-review.md`.

The implementation is at `ae1ab306129730b72c311a2d017ed8f2f2259e00`. An answer without independent evidence is still delivered. The job report and phone show that it is unverified. A request made entirely of supported arithmetic takes a local exact-calculation path. The checker reads back the delivered file and records the expression and result. Both the calculation and its attribution are deterministic. Other questions still use the frozen reasoning model.

The eight development questions and the scoring rule were committed before the implementation. The benchmark runs the baseline and candidate from separate, clean source snapshots. A scripted regression test caught a tampered arithmetic answer. Sixteen focused checks passed in the first test run.

The first guest setup failed while mounting the results directory. Three subsequent User Mode Linux starts failed while loading the model, at the host mapping limit. None produced a scored answer. The replacement full-system Linux VM passed a real bubblewrap calculation with loopback as its only interface, a 2 GiB hard process-group limit and zero swap. The baseline model loaded successfully there. Paired scores are pending.
