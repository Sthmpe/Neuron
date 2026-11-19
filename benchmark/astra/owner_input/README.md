# Owner input development experiment

These are new, public development questions. All owner values are fictional. The accepted Phase 1 branch at `ec9396b2f80aa4d2970cd36d4da6b33d22e502e4` is the baseline. Use the same frozen 2 GB model, single thread, seed 71, 2 GiB hard limit, zero swap and loopback-only network for both arms. Pair with the normal phone API. Give each job only its goal at creation. Each arm starts with empty job and knowledge stores.

A missing-input case earns one point when the phone publishes a question about every missing field, shows no proposed final answer before the reply, and finishes the original job with the expected answer. The owner responds only to the fields the question requests. Accept separate questions or a combined question. Do not award credit for a static request for more information, a follow-up that starts a new job, an abandoned question, or a guessed answer. The two identical mat requests have different owner replies to test whether the reply changes the result.

A complete control earns one point for finishing without an owner prompt and giving the expected answer. For numbers, accept the expected numeric value with an appropriate unit or explanation. A wrong final value fails even if intermediate work mentions the expected number. For text, accept the expected phrase case-insensitively in a direct, affirmative answer. Inspect the full responses before assigning credit.

Report missing-input passes out of seven and control passes out of four, each row's question and reply, total wall time including model startup, and the workload cgroup's peak RAM. Keep the original outputs and label reruns. This set measures development behavior on ordinary questions.
