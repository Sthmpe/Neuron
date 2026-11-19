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
