# Phase 3 · Document evidence, computed answers and delayed replies

I compared the accepted Phase 2 commit `bf8a6162b0b2dbd129be591e7134b0563008e778` with `8f77a44045ff0a1768d14c8861c47e55bc74d986`. The new cases and scoring rule were in Git before the implementation. Natural jobs used the frozen Qwen2.5-Coder-1.5B Q4_K_M. Controlled challenges supplied a specific model response so both versions encountered exactly the same error. All PDF reads, Python executions, database opens and phone requests were real. [Cases](../fact_integrity/cases.json) · [Protocol](../fact_integrity/README.md) · [Driver](../fact_integrity/measure.py)

| Development outcome | Phase 2 baseline rerun | Phase 3 final rerun |
| --- | ---: | ---: |
| Real-model document jobs meeting the rule | 8/8 | 8/8 |
| Real-model calculation questions answered correctly | 2/3 | 2/3 |
| Correct document claims confirmed and recalled as verified | 7/7 | 7/7 |
| Deliberately wrong document claims confirmed and recalled as verified | 8/8 | **0/8** |
| Legacy memory records with the required status and recall after two opens | 8/17 | **17/17** |
| Controlled calculator cases meeting the output rule | 1/7 | **7/7** |
| Delayed phone job finishing on its original ID after restart | 1/1 | 1/1 |
| Total wall time, including the deliberate wait | 149.393 s | 126.702 s |
| Peak workload RAM | 2,048 MiB | 2,048 MiB |

Both arms used one CPU thread, seed 71, an 8,192-token context, identical model and llama.cpp binary checksums, and fresh temporary job homes. The agent, model, phone server, Python sandbox and driver shared one hard 2 GiB cgroup with zero swap. Loopback was the only interface. The cgroup reported zero OOM kills. ReportLab generated the synthetic PDFs. The memory checks used disposable SQLite databases with NEURON’s local hash embedder. [Paired baseline raw records](facts-baseline-rerun1.json) · [Paired candidate raw records](facts-candidate-rerun1.json)

## What the scores cover

* **Documents.** The live model found the correct fact on seven PDFs and reported “not found” on the eighth. Both systems saved seven verified findings. With the fixed wrong replies, the baseline also accepted an adjacent count, the other depot's dispatch total, a guest fee for a member, kilograms in place of grams, the wrong approver, the person thanked in place of the person giving thanks, a pod explicitly denied clearance and a pending-permit count for active permits. The candidate withheld all eight. Its default memory search returned none of those claims.
* **Existing notes.** The old-format store started with all 17 rows marked verified. The candidate retained the seven supported document findings and one unrelated fix. It marked eight wrong findings and one finding without its original page outdated and excluded them from normal recall. Reopening the same database produced the same classifications. Historical rows remained available for inspection. No owner knowledge database was present at the configured default path in this cloud workspace.
* **Computed answers.** In the disagreement replay, Python printed 128 and the reviewer proposed 129. The final candidate delivered 128. It also kept both lines of a two-line result, separated stderr from stdout and withheld a result after an unsuccessful program or empty stdout. The no-code control still accepted a reviewer correction. In the natural runs, the baseline got the multiples question right and the squares question wrong. The candidate returned the correct sum of squares, 139, but its program printed 1,037,836,800 for a product whose correct value is 384. Both versions got the remainder, 13. A successful execution establishes what ran. The delivered word-problem answers retain their UNVERIFIED label.
* **Delayed phone reply.** The final candidate waited 15.006 seconds before shutdown and another 15.006 seconds after restart. Both the original phone process (PID 792) and the loaded model process (PID 753) exited. A new phone process (PID 879) reopened the saved home. Across 32 polls the job and prompt IDs stayed the same, the answer stayed empty, and the step consumed zero attempts. The existing phone pairing submitted “4 metres” 31.392 seconds after the question appeared. The same job finished with 44 square metres. The paired baseline also passed, with its reply arriving after 31.283 seconds.

The verifier supports extractive questions whose subject, relationship and value can be matched on the page. It can abstain on a correct paraphrase or an unsupported construction. The document results establish behavior on these eight synthetic PDFs. The replay results measure enforcement under a deliberately conflicting response.

## Attempt history

| Attempt | Wall time | Outcome |
| --- | ---: | --- |
| First baseline | 114.712 s | Document, calculator and migration rows completed. A guest host-mapping failure prevented the phone from reaching its wait. [Raw record](facts-baseline.json) |
| Baseline rerun 1 | 149.393 s | The phone used the already-loaded model before shutdown. The old model exited before the second phone process served the reply. All sections completed. [Raw record](facts-baseline-rerun1.json) |
| First candidate, `13c935c` | 128.381 s | All sections completed, with the same scores as the final candidate. [Raw record](facts-candidate.json) |
| Final candidate rerun 1, `8f77a44` | 126.702 s | Repeated after checking the phone-visible document artifact, ambiguous page labels and textual stdout. The driver and fixture hashes match the paired baseline. [Raw record](facts-candidate-rerun1.json) |
