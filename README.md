# NEURON — offline-first personal AI computer

| Step | What | State |
|---|---|---|
| 1 | Task engine: plan, checkpoint, survive network loss and restarts, permissions, proof | **Done.** Demo passes. |
| 2 | Local brain: local model, tool interface, reasoning loop, `answer` + `fix_code`, sandbox, benchmark | **Code and tests done. The model is NOT downloaded and the benchmark has NOT been run** — see "Step 2" below. |

All 84 automated tests pass (21 from step 1, 63 new). Python 3 standard library only, SQLite for
storage, no paid services.

---

# Step 1 — the task engine (v0.1)

NEURON takes a task, breaks it into steps, and keeps working through lost connections and
restarts without ever doing a finished step twice.

## What was built

Two programs that talk over local HTTP with JSON messages:

- **host** (`neuron/host/`) — pretends to be the phone. It sends a task, shows
  progress, and approves or rejects permission requests.
- **brain** (`neuron/brain/`) — the NEURON device. It receives the task and runs it.

Inside the brain:

| Part | File | What it does |
|---|---|---|
| Planner | `planner.py` | Breaks a task into numbered steps, each marked "needs internet" or "offline", and flags sensitive ones. `Planner` is the interface; `RuleBasedPlanner` is the simple version in use; `LlamaCppPlanner` is the plug-in point for a local model. |
| Task store | `store.py` | Every task, step, status, result and proof is written to SQLite the moment it changes. |
| Executor | `engine.py` | Runs steps one at a time. After each step it saves a checkpoint (status + result + proof in one database transaction). |
| Network monitor | `network.py` | Notices when the connection is lost or restored. For testing it reads a simulated network switch. |
| Recovery | `engine.py` | When offline: does every offline step it still can, marks the rest as waiting, and re-checks the connection on a schedule (0.5s, 1s, 2s … up to a cap). When back online it carries on from the exact step where it stopped. |
| Permissions | `engine.py`, `store.py` | A sensitive step (such as sending a message) does not run until the host approves it. If the host rejects it, it is skipped and reported. |
| Scheduler | `engine.py` | A task can be given a later start time. |
| Report | `report.py` | Final summary: steps done, failed, rejected, and the proof for each. |

**Proof** means: for each step the brain records what happened, when, a hash of
any file it wrote, and — for online steps — a receipt number from the "outside
world". The fake outside world (`world.py`) keeps its own separate record of
every action it was asked to do, so there is an independent witness for "did
anything happen twice?".

**How "never twice" works.** The brain only runs a step whose saved status is
not "done". Every online action also carries a unique key (task id + step
number). If the brain dies after an action happened but before it could save
that fact, it tries the step again after restart with the same key, and the
outside world returns the original answer instead of acting again.

## How the demo went

`python3 -m demo.run_demo` — the full output of the last run is in
[`demo/demo_output.txt`](demo/demo_output.txt). **Result: PASS.**

A 20-step "find leads" task on fake company data, with a real separate brain process:

1. The host sent the task. The brain planned 20 steps (8 need internet, 12 offline, step 18 sensitive).
2. Steps 1–8 ran. The network was cut right after step 8.
3. Step 9 (needs internet) had just started, hit the dead connection, did nothing, and went to "waiting".
   The brain then skipped ahead and did the offline steps that did not depend on it — **10, 12 and 13** —
   marked the other nine steps as waiting, and started retrying the connection.
4. The brain process was killed with `kill -9` and started again as a new process. It read its state
   from SQLite, ran nothing again, and kept waiting and retrying.
5. The network was restored.
6. On its next retry the brain resumed at **step 9**, then 11, 14, 15, 16, 17. It asked the host for
   permission before step 18 (send a message); the host approved; it finished 18, 19 and 20.
7. Final report: 20 of 20 steps done, 0 failed, each step completed exactly once, 8 outside
   actions for 8 online steps, 0 duplicates.

One honest detail: step 9 shows "attempt 2" in the log. Attempt 1 was the one stopped by the cut
connection before anything happened; it was not a completed step being repeated.

## Tests

`python3 -m unittest discover -s tests -t .` — **21 step-1 tests, all pass** (last run of the whole suite saved in
[`tests/last_test_run.txt`](tests/last_test_run.txt)).

- **Resume** (`tests/test_resume.py`): offline steps get done and the rest wait; after a restart and
  network restore the first step run is step 9; the retry schedule backs off and is respected;
  a connection lost in the middle of a step leaves no trace outside; changes are on disk immediately.
- **No duplicates** (`tests/test_no_duplicates.py`): each step completes exactly once through
  cut + restart + restore; also when the brain is restarted after *every single step*; a finished
  task is never touched again; and the worst case — crash after a message was sent but before
  the checkpoint — still results in only one message.
- **Permissions** (`tests/test_permissions.py`): a sensitive step waits; approved runs once;
  rejected never runs; a pending request survives a restart and is not asked twice; a decision
  cannot be changed afterwards.
- **Other** (`tests/test_other.py`): scheduler, planner, a failing step is reported and blocks
  the steps that depend on it, host and brain over real HTTP, and the full demo with a real `kill -9`.

## How to run it

```
python3 -m demo.run_demo                              # the whole demo
python3 -m unittest discover -s tests -t .            # the tests

python3 -m neuron.brain.server --port 8765 --data data     # start the brain
python3 -m neuron.host.cli send "find leads" --watch       # host: send a task and watch it
python3 -m neuron.host.cli send "find leads" --delay 60    # start in 60 seconds
python3 -m neuron.host.cli network off                     # simulated network switch
python3 -m neuron.host.cli permissions                     # then: approve <id> / reject <id>
python3 -m neuron.host.cli report <task_id>
```

## What is not done yet (step 1)

- **The rule-based planner is not intelligent.** It knows the "find leads" recipe, questions, and
  "fix the tests in <folder>". Anything else is split on "then" and only *simulated*.
- **All data and the "internet" are fake.** No real searching, email, messaging or CRM.
- **The network is a simulated switch.** A real connectivity probe is written (`tcp_probe`) but not wired in or tested.
- **"Never twice" for real services depends on them.** The guarantee for the crash-mid-step case
  relies on the outside service honouring a unique key. The fake world does; real services vary.
- **A failed step is not retried.** It is marked failed, steps that depend on it are blocked, and
  the report says so. Only network loss triggers retries.
- **No security.** The HTTP API is plain, unauthenticated, and bound to this machine only. There is
  no pairing between a real phone and the device.
- **The host is a command-line program**, not a phone app, and it polls instead of receiving push updates.
- **One step at a time, one brain.** No parallel steps, no cancel/pause command, no clean-up of old tasks.
- **Scheduling is start-time only** — no repeating tasks.
- Not tried on real NEURON hardware; only on a Linux machine with Python 3.13.

---

# Step 2 — a local brain that works with no internet

## The honest status first

| Part | State |
|---|---|
| 1. llama.cpp on this machine (CPU only) | **Built and runs** (`llama-server`, version 0.5.0-dev, commit 0c1e570, AVX2/AVX-512). |
| 1. The model | **NOT downloaded. Blocked.** See below. Nothing was substituted for it. |
| 2. Tool interface + registry | Done, tested. |
| 3. Reasoning loop (plan, review, revise, fall back, never claim success without proof) | Done. Tested with a scripted stand-in for the model. **Never yet run against the real model.** |
| 4. `answer` and `fix_code` tools | Done. `fix_code` tested with the real sandbox and real test runs, but with a scripted stand-in for the model. |
| 5. Isolation | Done, tested with real break-out attempts. |
| 6. Benchmark | The 10 buggy projects and the runner exist and are tested. **The benchmark has not been run. There are no results.** |
| 7. Results (model, score, speed, memory, what the model could not do) | **None yet.** Nothing in this README is a model result. |

### What is blocked, exactly

The model file lives on `huggingface.co`. This machine's network rules refuse that host (the
network proxy answers "connection rejected / 403"). Asking the owner to allow it failed twice because
the Claude mobile app version in use could not display the approval prompt. Until that host is allowed,
there is no model, so no real planning, no real answers, no real fixes and no benchmark numbers.

To unblock: allow these hosts for the cloud environment (named "korra"), then run
`scripts/setup_local_model.sh` and `python3 -m benchmark.run_benchmark`:

- `huggingface.co`
- `cas-bridge.xethub.hf.co` and `cdn-lfs-us-1.hf.co` (Hugging Face's download servers; if the download
  is redirected to a different server, that one must be allowed too)

### Which model, and why (chosen, not yet tested)

**Qwen2.5-Coder-1.5B-Instruct**, GGUF file `qwen2.5-coder-1.5b-instruct-q6_k.gguf` (about 1.5 GB) from
the official `Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF` repository. Apache-2.0 licence.

How it was chosen (checked on 14 Nov 2026): a web search for small code models that fit in about
2 GB found no newer code-specialised model in that size class. The alternatives looked at:

- *Qwen2.5-Coder-3B* — stronger, but about 2.5 GB in memory at 4-bit and a non-commercial licence.
- *Qwen3.5-2B* — newer and general-purpose; no published evidence found that it beats the code model on code.
- *Yi-Coder-1.5B* — similar size, older, less widely tested.
- *Phi mini (3.8B)* and larger — do not fit.

The expected memory use (about 1.8 GB with an 8k context) is an estimate. It has **not been measured**.
If the measured figure is well over 2 GB the smaller `q4_k_m` file (about 1.1 GB) is the fallback.

llama.cpp itself: `github.com` downloads were also refused, so the source was taken from the
`llama-cpp-python` 0.3.36 package on PyPI, which bundles the complete llama.cpp source tree, and
built with cmake (CPU only). The exact commands are in `scripts/setup_local_model.sh`.

## 2. Tool interface (`neuron/brain/tools/`)

Every capability is a `Tool` with: **name, description, inputs, needs internet or not, sensitive or
not**, and one method `run(ctx)`. Tools live in a **registry**. The engine does not know any tool by
name — it looks the step's tool up in the registry and runs it.

- Built-in tools are discovered automatically from the `tools/` folder.
- Extra tools plug in from any folder (`--tools-dir` or `NEURON_TOOLS_DIR`): a `.py` file that defines
  `TOOLS = [MyTool()]`. A test does exactly this with a pretend image tool and a pretend SMS tool,
  and runs them through the unchanged engine (the sensitive one waits for host approval).
- The 17 step-1 "find leads" actions now go through the same interface.
- `GET /tools` on the brain lists everything registered.

A tool must return a result **with evidence**. If it returns none, the engine marks the step failed
("gave no proof"). A tool that cannot do its job raises `ToolFailure` with a record of what it tried.

## 3. Reasoning loop (`planner.py`, `engine.py`)

1. **Plan.** `LlamaCppPlanner` sends the task and the list of tools to the local model and asks for
   steps as JSON (the reply is constrained to a JSON schema by llama.cpp).
2. **Validate.** Every step must name a registered tool with valid inputs; at most 6 steps. Whether a
   step needs internet or is sensitive is taken from the tool, never from what the model says.
   One repair round is allowed. If the plan is still unusable, or the model is unreachable, the
   **rule-based planner** is used and the task records that ("rule-based (fallback: …)").
3. **Run** each step through the step-1 engine (checkpoint + proof after each).
4. **Review.** After every finished step the model sees what happened and answers *continue*,
   *revise* (replace the steps not yet run — this is how it tries another approach after a failure)
   or *give up*. Revisions are validated the same way, may not repeat a step already tried with the
   same inputs, and are capped at 3 per task. Reviews survive a restart.
5. **Report.** The report has a verdict line. "COMPLETED" also says how many steps were
   independently checked and how many rest on unchecked model output. "NOT SOLVED" says why and
   lists what was tried, attempt by attempt.

## 4. The first two tools

- **`answer`** — answers a question with the local model. The answer is saved with timing and token
  counts, and is always labelled **not fact-checked**: the brain cannot prove a model's answer is right.
- **`fix_code`** — for a Python project with failing tests:
  1. copies the project to a private work folder and runs the tests in the sandbox;
  2. gives the model the failing output, the relevant source files and the tests (read-only), and asks
     for a corrected version of **one** source file — test files can never be edited;
  3. applies it to a fresh copy and runs the tests in the sandbox;
  4. on a pass, runs them a second time on another fresh copy to confirm, then writes the one changed
     file back to the project; on a fail, feeds the test output back and retries — **3 attempts at most**;
  5. reports success only if the sandbox says the tests pass. Otherwise it fails and lists every
     attempt. The original project is left untouched on failure.
  Each attempt is saved to disk, so a restart mid-way continues with the next attempt.

## 5. Isolation (`neuron/brain/sandbox.py`)

Generated code and project tests run only inside a sandbox built from **bubblewrap + Linux namespaces +
cgroups + a seccomp filter** — the strongest option available on this machine (no virtual-machine or
container runtime is usable inside it; Docker's daemon is not running). If bubblewrap is missing the
sandbox refuses to run anything rather than run code unprotected.

**What it does** (each point is covered by a test that tries to break it):

- **No network.** Empty network namespace: no internet, no DNS, and no access to services on this machine.
- **No files outside the workspace.** The code sees its workspace (read-write), a private empty `/tmp`,
  and the system's `/usr` (read-only). `/home`, `/root`, `/etc`, `/var` do not exist inside.
- **Not root.** Runs as "nobody" with all privileges dropped and "no new privileges" set.
- **Cannot see other processes**, and gets none of the brain's environment variables.
- **Time limit:** killed after the limit (60 s by default).
- **Memory limit:** killed above the limit (512 MB by default), enforced by a memory cgroup.
- **Process limit:** at most 64 processes (a fork bomb is contained).
- **File size limit** of 32 MB per file, and output capped.
- **Kernel calls:** about 45 dangerous ones (mount, ptrace, new namespaces, kernel modules, bpf …) are refused.

**What it does NOT protect against:**

- **Kernel bugs.** The sandbox shares this machine's Linux kernel. It is not a virtual machine; a kernel
  exploit could escape it.
- **Reading `/usr`.** System programs and libraries are readable. Anything secret stored under `/usr` would be too.
- **A fix that cheats the tests from inside.** The model's code runs in the same process as the tests,
  so code that deliberately sabotages the test runner could fake a pass. Test files are restored
  before every run and cannot be edited, but this in-process trick is not prevented.
- **The fix after it leaves the sandbox.** Once a fix is written back to your project, running that
  project normally runs model-written code with no protection.
- **Disk filling.** Many files just under the size limit can still fill the workspace disk.
- **CPU hogging** within the time limit, and timing side-channels.
- **Weaker machines.** The kernel-call filter is a block-list, not an allow-list. On a system without
  cgroup v1 the memory limit falls back to a weaker address-space limit and the process limit is not enforced.
- It needs root or working user namespaces to start at all.

## 6. Benchmark (`benchmark/`) — built, NOT run

Ten small Python projects, each with one real bug and tests that fail because of it:

| # | Project | The bug |
|---|---|---|
| 01 | shopping_cart | discount applied as the price instead of taken off it |
| 02 | text_stats | splits on single spaces only |
| 03 | binary_search | loop stops one element early |
| 04 | bank_transfer (2 files) | credits the receiver before checking the sender can pay |
| 05 | date_utils | leap-year rule misses the 400-year case |
| 06 | matrix | wrong dimension used for the result's width |
| 07 | lru_cache | reading an entry does not mark it as recently used |
| 08 | csv_parser | drops an empty last field |
| 09 | todo_app (2 files) | shared mutable default argument |
| 10 | intervals | merging can shrink an interval |

The projects and bugs were fixed **before** any model was available and will not be changed to suit
the results. A test checks that all ten fail as shipped and pass with their reference fix
(`benchmark/solutions/`, which the model never sees).

The runner (`python3 -m benchmark.run_benchmark`):

- moves itself into an empty network namespace and verifies the internet is unreachable, or refuses to run;
- refuses to run without the real model file;
- gives each project to the brain as a normal task, then **independently** re-runs the original tests
  on the result — only that run decides "solved";
- records per project: solved or not, attempts, time, peak RAM (model server, sandbox, brain), tokens per second;
- writes `benchmark/results.json`, `benchmark/results.md` and the full reports.

## 7. Results

**None.** Model: not downloaded. Solved out of 10: not measured. Speed: not measured. Memory: not
measured. What the model could not do: unknown. This section will be filled in from
`benchmark/results.json` after the benchmark has actually run.

## Tests for step 2 (63 new, all pass)

- `tests/test_tools.py` — registry discovery, input checking, plug-in tools without engine changes,
  no evidence = not done, failures say what was tried.
- `tests/test_sandbox.py` — the break-out attempts listed above.
- `tests/test_reasoning.py` — plan validation, repair, fallback, review/revise/give-up, revision
  limit, review surviving a restart, and the client's wire format against a stand-in HTTP server.
- `tests/test_fix_code.py` — first-try fix, wrong-then-right, giving up after 3, tests cannot be
  edited, unusable replies, restart mid-way, no sandbox = no run, a hostile "fix" cannot reach the
  network or the machine, an infinite-loop "fix" is stopped.
- `tests/test_benchmark_projects.py` — the ten projects are real failures with real fixes; the runner's
  independent check works.

**Important limit of these tests:** wherever a model is needed, the tests use a scripted stand-in
(`tests/fakes.py`) that replies with prepared text. That proves the logic *around* the model. It proves
nothing about how well the real model plans, answers or fixes code.

## How to run step 2 (once the model is available)

```
scripts/setup_local_model.sh                 # build llama.cpp, install bubblewrap, download the model
python3 -m benchmark.run_benchmark           # the offline benchmark

~/llama/build/bin/llama-server -m models/<model>.gguf --port 8080 -c 8192 &
python3 -m neuron.brain.server --port 8765 --data data --llama-url http://127.0.0.1:8080
python3 -m neuron.host.cli send "Fix the failing tests in /path/to/project" --watch
python3 -m neuron.host.cli send "What is a mutex?" --watch
```

## What is not done yet (step 2)

- **The model is not downloaded, and nothing involving the real model has been run** — planning,
  reviewing, answering, fixing, the benchmark, memory and speed.
- The prompts and the reply format for `fix_code` are untried on the real model and may need changes.
- `fix_code` only handles Python, changes one file per attempt, and rewrites the whole file — so it
  is limited to small files.
- The model planner only knows two tools (`answer`, `fix_code`) plus whatever is plugged in.
- No image, audio, messaging or app tools exist yet — only the interface they will plug into.
- The brain does not start or supervise `llama-server` by itself outside the benchmark.
