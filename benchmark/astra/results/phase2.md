# Phase 2 · Asking the owner for missing information

I registered eleven new development requests and their scoring rule before implementing the feature. A missing-input case earns a point only if the phone asks for the necessary fact, shows no interim answer, accepts the owner's reply and finishes the same job with the correct answer. A control must finish correctly without asking. The owner values are fictional. [Questions](../owner_input/questions.json) · [Registered rule](../owner_input/README.md)

| Full phone run | Missing inputs | Complete controls | End-to-end time | Peak RAM | Model calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Accepted Phase 1, `ec9396b` | 0/7 | 4/4 | 160.356 s | 2,048 MiB | 22 |
| First candidate, `2278f72` | 7/7 | 4/4 | 90.053 s | 2,048 MiB | 12 |
| Candidate rerun 1, `081dcec` | 7/7 | 4/4 | 86.489 s | 2,048 MiB | 12 |
| Final candidate rerun 2, `1cc39a4` | 7/7 | 4/4 | 86.693 s | 2,048 MiB | 12 |

I ran the same phone driver in fresh guests with the frozen Qwen2.5-Coder-1.5B Q4_K_M, one CPU thread, seed 71 and an 8,192-token context. A cgroup covered the model, phone server, sandbox children and driver together. Its memory limit was 2,147,483,648 bytes and its swap limit was zero. Loopback was the only network interface. Each process group reached the memory ceiling and recorded zero OOM kills. The elapsed time includes model startup, artificially immediate owner replies and teardown. It excludes human reading and typing time. The raw files include model and binary checksums, interface checks, cgroup events, timings, full answers, questions and replies. [Driver](../owner_input/measure.py) · [Baseline](phone-baseline.json) · [First candidate](phone-candidate.json) · [Rerun 1](phone-candidate-rerun1.json) · [Final rerun](phone-candidate-rerun2.json)

| Request | Accepted Phase 1 output | Owner’s reply to Phase 2 | Final Phase 2 answer |
| --- | --- | --- | --- |
| Area of mat, length 9 cm | Formula `9w`, job closed | 4 cm wide | 36 square centimetres |
| Same request again | Formula `9w`, job closed | 7 cm wide | 63 square centimetres |
| Average speed over 42 km | Failed with no answer | 3 hours | 14 km per hour |
| Total spent on tickets at 6 dollars each | “Incorrect” | 5 tickets | 30 dollars |
| Wallet balance after spending 13 dollars | 67 | 50 dollars to start | 37 dollars |
| Area of a rectangular painting | Formula and an example with invented dimensions | Length 8 metres, then width 3 metres | 24 square metres |
| Label on a personal storage box | Generic request for context, job closed | Winter postcards | Winter postcards |
| Area of a 9 by 5 cm mat | 45 | No prompt | 45 |
| Cost of zero tickets at 6 dollars each | 0 | No prompt | 0 |
| 17 + 24 | 41 | No prompt | 41 |
| What a thermometer measures | Temperature | No prompt | Temperature |

The arithmetic control carried VERIFIED on both systems. The inferred word problems and the owner's own label carried UNVERIFIED on Phase 2. Every final missing-input case had one job ID and an empty answer and output list while waiting. The two-dimension case required two replies. The controlled mat pair produced a different area when only the reply changed.

## Additional development checks

I tried three cases outside the registered score after the first candidate. It asked for the previous meter reading, received 200 and then asked for the already-supplied increment of 17 + 4. It failed to finish the speed calculation when the owner supplied minutes and the question requested km per hour. It also asked for a rectangle's dimensions when the owner wanted the formula. Rerun 1 corrected the arithmetic and the method question, but appended “meter” to the reading of 221. The final code uses the owner's stated unit or a unit explicitly requested for this calculation. The final check returned 221, converted 12 km in 30 minutes to 24 km per hour, and explained the rectangle formula without a prompt. These were separate loopback-only checks on the 2 GB model outside the timed cgroup comparison. [Development probes and phone-browser records](phone-extra.json)

I also inspected two versions of the model's proposed input list during development. Those model-only diagnostics informed the wording and source checks. The scores above come from the paired phone API. On rerun 1 the guest logged a kernel panic during shutdown after the driver saved all eleven rows and reported exit 0. I retained that attempt and its raw record.

This development set covers short English questions. An inventory can still omit a dependency or assign a number to the wrong role, and the unit converter covers a limited set of scales. The measurements above establish behavior on this set and do not estimate a population success rate.
