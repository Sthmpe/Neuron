# Ordinary answers on the frozen 2 GB model

The alternative earned 8/8 on the development rule, up from 2/8. Judging only answer content, it improved from 5/8 to 7/8. It still invented a meter reading of 121 when the starting reading was missing. The new report called that answer UNVERIFIED.

## Paired results

| Eight development jobs, in the same order | Baseline rerun 7 | Astra development rerun 1 |
| --- | ---: | ---: |
| Answer and verdict met the predeclared rule | 2/8 | 8/8 |
| Correct answer content, independent of verdict | 5/8 | 7/8 |
| Arithmetic questions answered correctly and marked VERIFIED | 2/4 | 4/4 |
| VERIFIED on questions with no independent reference in the job | 4/4 | 0/4 |
| Factually wrong or invented answers marked VERIFIED | 3 | 0 |
| Answers delivered | 8/8 | 8/8 |
| Elapsed seconds, including one model load and unload | 69.585 | 37.947 |
| Model load within that time, seconds | 16.855 | 15.564 |
| Peak aggregate RAM, MiB | 2,048 | 2,048 |
| Kernel OOM kills | 0 | 0 |
| Model calls / generated tokens | 15 / 537 | 7 / 249 |

Each arm used the same model. Astra answered the four arithmetic jobs with deterministic code and attributed them accordingly. The four other jobs used the model. The 31.638-second reduction is one paired timing. The two peaks both reached the cap, including charged file cache. The kernel recorded 1,392 memory.max events in each arm.

## How the eight answers were graded

Arithmetic earned one point for a correct result and a VERIFIED verdict. The other four questions earned one point for a substantive delivered response clearly labeled as lacking independent verification. Their factual content was also judged separately. This lets an owner distinguish an honest label from a correct answer. The questions and rule were recorded at `c6114d27ac3488a783fa99651a953abfb4aecaa1` before implementation. [Development rule](../README.md) · [Questions and answer key](../questions.json)

| Case | Expected content | Baseline answer | Astra answer | Baseline → Astra points |
| --- | --- | --- | --- | ---: |
| Element | Tin | Tin, VERIFIED | Tin, UNVERIFIED | 0 → 1 |
| Grouping | 175 | 191, VERIFIED | 175, VERIFIED | 0 → 1 |
| Train | The itinerary is missing | Said it could not tell, VERIFIED | Said it could not tell, UNVERIFIED | 0 → 1 |
| Decimal | 0.245 | 0.245, VERIFIED | 0.245, VERIFIED | 1 → 1 |
| Roman numeral | XLII | XLII, VERIFIED | XLII, UNVERIFIED | 0 → 1 |
| Signed arithmetic | −4 | 4, VERIFIED | −4, VERIFIED | 0 → 1 |
| Meter | The previous reading is missing | 121, VERIFIED | 121, UNVERIFIED | 0 → 1 |
| Exact quotient | 23/6 | 23/6 in LaTeX, VERIFIED | 23/6, VERIFIED | 1 → 1 |

The baseline’s meter job ran model-written Python and reviewed the output with the model. That supplied no evidence for the missing reading. The new calculation path rejects a request that includes extra prose about the meter. Its model fallback still supplied the same invented value. Both arms lost the content point.

## Measurement conditions

- Baseline source was `1f65640b4c85204652259110e810beb4432e56dc`. Candidate source was `ae1ab306129730b72c311a2d017ed8f2f2259e00`. Each ran from a clean Git archive with the same driver from `aeb5f34`. The driver called the production Agent, Job, ModelRunner and Sandbox. Each job started with an empty workspace and no knowledge memory. The model loaded once per arm. [Driver](../measure_answers.py)
- The model was Qwen2.5-Coder-1.5B-Instruct Q4_K_M, SHA-256 `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`. Both arms used the same native CPU binary built from llama-cpp-python 0.3.36, context 8,192, one inference thread, one slot, seed 71, load mode `none` and cache RAM zero. The raw records contain the hashes of the binary, model, driver and questions. [Frozen manifest](../../../model_manifests/frozen.json)
- Each arm booted a fresh User Mode Linux 6.12.113 guest on the same AMD EPYC 9V74 host. Guest RAM was backed by an executable tmpfs. The guest requested 3,456 MiB so its OS could sit outside the application tier. The init process read the input GGUF into the guest file cache before starting the workload. The workload verified the SHA before timing. Its private cgroup limited the agent, model and every descendant together to 2,147,483,648 bytes, with zero swap. The driver verified those values, found only loopback, and got “Network is unreachable” from its external connection probe. The timer used a monotonic clock. Peak RAM is the kernel’s `memory.peak` in that cgroup.
- The arms ran consecutively. Both completed eight jobs, recorded zero online model calls, and recorded exactly one load. The final records matched the eight separately flushed job checkpoints in each arm. These are author-written development cases. Transfer to other questions and other tiers is unmeasured. [Baseline raw record](baseline-rerun7.json) · [Candidate raw record](candidate-dev-rerun1.json)

## Attempts and reruns

| Attempt | What happened |
| --- | --- |
| Baseline first start | The guest could not mount the results directory. The driver never started. |
| Baseline reruns 1–3 | The model process failed a host-side memory mapping in User Mode Linux. No answers were scored. A later diagnostic reproduced the failure at 65,531 sampled mappings on a host configured for 65,530. |
| Baseline rerun 4 | An emulated full-system VM loaded the model and logged one completed job. The process ended before it wrote a complete result. Its timing and score are excluded from the pair. |
| Baseline rerun 5 | The host denied the request to mount a private tmpfs. The guest never started. |
| Baseline rerun 6 | An existing executable tmpfs for the guest RAM resolved the mapping failure. All eight jobs completed in 72.864 seconds, peaking at 2,048 MiB. All eight answers and verdicts matched rerun 7. [Raw record](baseline-rerun6.json) |
| Baseline rerun 7 and Astra development rerun 1 | The driver gained durable per-job checkpoints after the interrupted run. Baseline and candidate both ran with this identical driver and guest configuration. These are the two columns above. This was the candidate’s first execution on the previously used development questions. |
