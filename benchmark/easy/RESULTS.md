# Easy work: NEURON versus the bare model (internal tasks)

24 easy items written for this check (8 facts, 8 calculations, 8 short writing tasks; `items.json`), each answered by
the bare model (one call, the request as the only message) and by full NEURON, in the same process with the same loaded
model, network cut, memory off, alternating which goes first. Scoring rule fixed before the runs (`run.py`): facts need an
expected word, calculations the number within 0.5%, writing at least 8 words and an expected word.

| Run | Bare model: right, total time, median | NEURON: right, total time, median | Model calls (bare / NEURON) |
|---|---|---|---|
| 2 GB, first run (`4d2acf5`) | 23/24, 99.0 s, 1.36 s | 21/24, 74.7 s, 1.0 s | 24 / 24 |
| 2 GB, **rerun1** after two fixes (`544467a`) | 23/24, 105.7 s, 1.44 s | **24/24, 79.2 s** | 24 / 24 |
| 4 GB (`544467a`) | 24/24, 527.5 s, 17.7 s | 23/24, 179.2 s, 3.9 s | 24 / 29 |

- NEURON is not slower on easy work: it is faster in every run (calculations come from a short program instead of long
  reasoning, and its prompt asks for a direct answer; the 4 GB bare model writes long replies).
- The first 2 GB run found two general flaws, fixed before rerun1: the ask-for-a-missing-fact rule made the small
  model ask instead of answering general questions (now offered only for personal requests), and "Explain what a
  spreadsheet is" was routed to the spreadsheet builder (a topic question with no verb of making now stays simple).
- The 4 GB miss (W7) is a haiku about rain that does not use the word "rain"; scored as a miss by the fixed rule.
- Raw rows: `benchmark/results/easy/<run>.json`.
