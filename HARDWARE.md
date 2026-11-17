# Hardware bottleneck log (for the future NEURON device)

What limits NEURON on real hardware, measured, not guessed. Each entry says where the number comes from.
Updated as new measurements arrive. Last update: 2026-11-17.

## The machine these numbers come from

Cloud container: 4 virtual cores of an Intel Xeon at 2.3 GHz, 16 GB memory, no graphics card, Linux.
Models run on the processor with llama.cpp (CPU build, `GGML_NATIVE=ON`), 4-bit or 8-bit model files.
A home computer or a purpose-built device will differ; the patterns below are what to watch.

## 1. Writing speed follows memory speed

Measured writing speed (tokens per second, one short answer, nothing else running; `models/measure.log`):

| Model | File size | Memory used | Writing speed | File size x speed |
|---|---|---|---|---|
| qwen3.5-0.8b (8-bit) | 0.76 GB | 1376 MB | 36.0 | 27 GB/s |
| qwen2.5-coder-1.5b (5-bit) | 1.20 GB | 1544 MB | 17.0 | 20 GB/s |
| qwen2.5-coder-3b (4-bit) | 1.96 GB | 2417 MB | 10.1 | 20 GB/s |
| qwen3.5-4b (4-bit) | 2.55 GB | 3656 MB | 7.1 | 18 GB/s |
| qwen2.5-coder-7b (4-bit) | 4.36 GB | 5077 MB | 5.2 | 23 GB/s |
| qwen3.5-9b (4-bit) | 5.29 GB | 6003 MB | 3.9 | 21 GB/s |

The last column stays near 20 GB/s whatever the model: each written token reads roughly the whole model file
from memory once. That is what you expect when **memory bandwidth** is the limit, not processor cores.
For the device: a 9B-class model at 10 tokens per second needs about 50 GB/s of usable memory bandwidth;
at 20 tokens per second, about 100 GB/s. (Consistent with the data; not separately proven with a
bandwidth benchmark yet.)

## 2. The model is most of the waiting

From the model-selection runs (12 tasks each, `benchmark/results/dev/*-full-sel-*.json`):

| Tier and model | Total time | Time inside the model | Share | Peak memory of everything |
|---|---|---|---|---|
| 2 GB, qwen2.5-coder-1.5b (frozen) | 462 s | 282 s | 61% | 1566 MB |
| 4 GB, qwen3.5-4b (frozen) | 1215 s | 707 s | 58% | 3994 MB |
| 4 GB, gemma-4-e2b | 1252 s | 984 s | 79% | 3620 MB |
| 8 GB, gemma-4-e4b (frozen) | 1143 s | 584 s | 51% | 5736 MB |
| 8 GB, qwen3.5-9b | 1778 s | 1094 s | 61% | 6291 MB |
| 8 GB, qwen2.5-coder-7b | 1522 s | 931 s | 61% | 5263 MB |

The rest is running tests, building apps, starting browsers and spreadsheet checks. Inside the model,
the effective speed during real tasks (2.6 tokens per second for the 9B model) is lower than the clean
measurement above (3.9), because the model also has to **read** long prompts (code, test output) before
writing. Faster prompt reading (more cores, matrix units) matters as well as bandwidth.

## 3. Memory: the 4 GB tier is right at its edge

- 4 GB tier with qwen3.5-4b: peak **3994 MB of 4096 MB** for everything NEURON ran (model, sandboxes,
  app servers, browser checks). No limit hits, but only 2.5% to spare.
- 8 GB tier with qwen3.5-9b: peak 6291 MB of 8192 MB.
- A device sold as "4 GB" also has to fit its operating system in those 4 GB. The installer keeps
  max(1 GB, 15%) for the system, so a 4 GB computer gets the 2 GB tier and an 8 GB computer the 4 GB tier.
- For the device: 12 GB or more lets the 8 GB tier run with room for the system and the checking tools.

## 4. Never two models at once

During installer testing a second model ran while the 8B benchmark was running. The small 1.5B model
wrote at **0.5 tokens per second** (its 5-bit sibling measured 17 on its own) (both fight for the same memory bandwidth and the
same 4 cores; the processor load reached 7.8 on 4 cores). NEURON's design keeps one model in memory and runs
one job at a time; the device should do the same and keep other heavy work away while the model writes.

## 5. Loading a model

Load time 2 to 9 seconds (bigger model, longer). NEURON uses one model for every role inside a tier, so
it loads once per job, not once per step.

## 6. Disk

- Model files: 0.8 to 5.7 GB each. One tier's model plus NEURON, LibreOffice and the browser: about 10 GB.
- Keeping every candidate model for comparisons took about 30 GB and filled this machine's disk twice.
- For the device: 32 GB storage is enough for all three tier models plus tools; 64 GB leaves room for
  owner files and job history.

## 7. Things that are not bottlenecks (so far)

- The phone web page, pairing and job storage: negligible processor and memory.
- Spreadsheet, document and slide checks with LibreOffice: a few seconds each.

## Open questions to measure next

- Real home hardware (laptop, mini PC, single-board computer) with the frozen models.
- Prompt-reading speed versus writing speed separately, from the model server's own timings.
- Heat and sustained speed over a long job.
- Phone and computer on a busy home Wi-Fi.
