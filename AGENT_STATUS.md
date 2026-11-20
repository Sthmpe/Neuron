# Astra phase 3

NEURON now checks that a cited passage connects the requested subject and relationship to the proposed answer. A number from a neighbouring fact cannot establish that connection. The document check also reads back the answer shown on the phone. Unsupported claims are withheld and do not produce verified memory notes.

When a Python calculation succeeds, NEURON delivers its standard output. The reviewer can record a disagreement. Failed programs, empty output and diagnostic messages do not supply a final value. An answer that depends on model-written code still carries the UNVERIFIED label.

## Before and after

| New development cases, offline 2 GB tier | Accepted Phase 2 | Final Phase 3 rerun |
| --- | ---: | ---: |
| Wrong document claims accepted and stored as verified | 8/8 | **0/8** |
| Correct document claims accepted and stored as verified | 7/7 | 7/7 |
| Legacy notes with correct status and recall | 8/17 | **17/17** |
| Calculator disagreement, failure and control cases passed | 1/7 | **7/7** |
| Real-model document jobs passed, including one missing fact | 8/8 | 8/8 |
| Real-model arithmetic answers correct | 2/3 | 2/3 |
| Total elapsed time, including the delayed reply | 149.393 s | 126.702 s |
| Peak workload RAM | 2,048 MiB | 2,048 MiB |

The paired runs used the same frozen Qwen2.5-Coder-1.5B model, one CPU thread, a hard 2 GiB limit, zero swap and loopback only. The baseline was `bf8a6162b0b2dbd129be591e7134b0563008e778`. The measured candidate was `8f77a44045ff0a1768d14c8861c47e55bc74d986`. The controlled cases deliberately supplied wrong claims and conflicting reviews. The real-model rows used the model’s own replies. [Conditions, per-case results and all attempts](benchmark/astra/results/phase3.md)

## What happened to old notes

Opening an existing knowledge database now checks old verified document findings against the original saved answers and indexed pages. In the upgrade test, eight wrong notes and one note whose page could no longer be found were marked outdated and disappeared from normal recall. Seven supported findings and an unrelated verified fix remained. A second open produced the same result. Quarantine preserves the original text, record ID and usage history. The upgrade ran on seeded old-format databases here. The cloud workspace had no owner database at the default path.

## Delayed phone reply

The banner question stayed open with no interim answer or consumed attempt. I stopped its phone server and loaded model after 15 seconds, started a fresh phone server on the same home, and waited another 15 seconds. The original pairing submitted “4 metres” after 31.392 seconds. The same job returned **44 square metres**. The accepted baseline passed this check too. [Polls, process IDs and delivered answer](benchmark/astra/results/facts-candidate-rerun1.json)

## What failed and what I would try next

A model-written program produced 1,037,836,800 for a product whose correct value is 384. NEURON faithfully delivered that number with its unverified label. The document checker can also abstain on a supported fact expressed in unfamiliar language. I would next test paraphrases, table headings and qualified statements, alongside examples where an independent calculation can detect a mistaken program. The first benchmark attempt lost the phone check to a guest memory-mapping failure. Both paired reruns finished under the original limit.

## Verification

All 215 selected unit and development tests passed. The host ran 212. Three additional sandbox resource tests passed in capped guests. The process-limit guest logged a shutdown error after its first successful test. Its labeled rerun exited cleanly. Six tests that load held-out fixtures were excluded. The regression tests cover source and unit swaps, quotation context, changed answer files, upgrade idempotence, review disagreement, failed programs and delayed replies.

---

# Astra phase 2

NEURON now pauses an ordinary question when it identifies a required fact the owner has not supplied. The phone shows the missing detail, saves the reply and continues the same job. A restart preserves the question. Re-sending the same reply does not start another job.

## What I measured

| Offline 2 GB development run | Accepted Phase 1 | Final Phase 2 rerun |
| --- | ---: | ---: |
| Asked for all missing inputs and finished correctly | 0/7 | 7/7 |
| Answered complete controls correctly without asking | 4/4 | 4/4 |
| End-to-end time | 160.356 s | 86.693 s |
| Peak workload RAM | 2,048 MiB | 2,048 MiB |
| Model calls | 22 | 12 |

I compared `ec9396b2f80aa4d2970cd36d4da6b33d22e502e4` with `1cc39a4683bcc9c1f2386b23231d66d689f4edc9`. Both used the same frozen Qwen2.5-Coder-1.5B model, a hard 2 GiB memory limit, zero swap and loopback only. The artificial owner replied immediately. Two jobs started with the same 9 cm mat. A width of 4 cm produced 36 square centimetres. A width of 7 cm produced 63. A painting with neither dimension supplied took two replies. [Conditions, all eleven scores, earlier attempts and raw results](benchmark/astra/results/phase2.md)

## What changed

The local model identifies facts needed for an answer. For a simple calculation, NEURON checks that each proposed input value occurs in the request before using it. An absent value becomes a specific phone question. Zero is a valid input. NEURON can compute supported arithmetic from the owner's reply and can convert compatible units. The phone marks a result that relies on interpreting the owner's words as unverified.

The pending question and accepted reply live in the job's saved plan. The paired phone session submits a reply against the question ID. The worker can handle other jobs while it waits. Reply retries are safe, and a restart after a reply was saved can still resume the work. This design builds on the branch's existing job records, local model runner and exact arithmetic.

## What failed and what I would try next

The first candidate passed the registered set but asked for an already-given increment, failed a minutes-to-hours conversion and requested dimensions for a formula question. A later attempt called the reading on an instrument “221 meter”. In the final checks, the owner supplied 200 and got a reading of 221, the speed calculation returned 24 km per hour, and the formula question finished without asking. [Exploratory phone records](benchmark/astra/results/phone-extra.json)

The small model can still overlook a dependency or associate a number with the wrong fact. I would next test questions containing plausible but irrelevant numbers, alongside complete questions that mention an unknown value which the answer does not need. The measurements here cover short English development questions on the 2 GB tier.

## Review and verification

I reviewed Claude's main at `d54bf4dc629768fd39eb74e1322f1cec9a96bd2c`. A wrong number attached to the wrong chair colour passed the document verifier and became a verified memory note. A calculation returned 34 after its sandbox printed 33. Formatting also changed which C++ repairs the search considered. The review gives the inputs, outputs and code references. [Independent review](docs/reviews/astra-review.md#phase-2-review-of-claudes-main)

199 selected unit and development tests passed on the final code. The selection excludes six tests that load held-out fixtures and three platform-specific sandbox resource checks. I also used Chromium at a 390 by 844 viewport with the real model and loopback only. The phone retained its question after a reload, kept a partially typed reply, and showed 54 square centimetres after a reply of 6 cm. The job URL stayed the same throughout. [Browser records](benchmark/astra/results/phone-extra.json)

---

# Astra phase 1

I worked on a false assurance in ordinary question answering. The original system could explicitly record that a model answer was unverified and still tell the phone owner “Done and checked”. A saved release run exhibited the mismatch. My scripted check reproduced it with a deliberately wrong answer. [Independent review of 1f65640](docs/reviews/astra-review.md)

## What I built

NEURON now delivers an unsourced answer with an UNVERIFIED verdict. The phone shows “Answered · unverified”, including when an older saved step already carried that evidence. A request consisting entirely of supported arithmetic gets an exact local calculation with a record of the expression and a check of the delivered answer file. The system credits the calculation to code. This work uses the existing agent, model runner and sandbox from the starting commit. I developed the alternative on this branch.

## What I measured

I used the same frozen 2 GB Qwen2.5-Coder-1.5B model in both runs. Each ran offline under a hard 2,048 MiB limit for the entire workload, with zero swap. The questions and scoring rule were in Git before the alternative. The baseline was `1f65640b4c85204652259110e810beb4432e56dc` and the candidate was `ae1ab306129730b72c311a2d017ed8f2f2259e00`.

| On eight development questions | Baseline rerun | Astra rerun |
| --- | ---: | ---: |
| Answer and verification label met the rule | 2/8 | 8/8 |
| Correct answer content | 5/8 | 7/8 |
| Wrong answers labeled VERIFIED | 3 | 0 |
| End-to-end time | 69.585 s | 37.947 s |
| Peak RAM | 2,048 MiB | 2,048 MiB |

The alternative fixed two wrong calculations and labeled four answers without independent evidence. The four arithmetic requests took zero model calls. Both systems delivered eight answers. This is a narrow development result on one tier. [Per-question scores, conditions, attempt history and raw records](benchmark/astra/results/phase1.md)

## What failed and what I would try next

Both systems reported a meter reading of 121 without knowing the previous reading. The new system warned that the answer was unverified. It still gave a value the owner could act on. I would next test whether NEURON can identify a missing input and ask for that value, alongside word problems with enough information to solve.

The first benchmark guests failed to mount their output or load the model. A full-system emulation also stopped before completing the set. Backing the User Mode Linux guest’s RAM with tmpfs let the pinned native build run under the required cap. One earlier complete baseline rerun produced the same answers in 72.864 seconds. The reported pair used the same driver with per-job checkpoints.

## Verification

All 191 selected unit and development tests passed across compatible test environments. Six tests that load held-out requests or workspaces were excluded. The first broad host run was killed during the process-limit test. That test passed with a guest kernel enforcing a 32-process ceiling. Of the other 190 tests, 188 passed on the host. One expects a cgroup v1 directory, and one matched the word “allocated” in Python’s traceback even though allocation failed. Both passed under cgroup v1, alongside a successful ordinary sandbox command. The performance measurements had finished before the broad suite ran.

I also checked the job page and recent-work list in Chromium at a phone-sized viewport. Both showed “Answered · unverified” for a scripted model answer and “Done and checked” for an independently calculated answer. The real-model scores above come from the offline benchmark.
