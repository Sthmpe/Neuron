# NEURON v0.1 — offline-first autonomous task engine

Step 1 of a personal AI computer. NEURON takes a task, breaks it into steps, and
keeps working through lost connections and restarts without ever doing a
finished step twice.

Python 3 standard library only. SQLite for storage. No paid services, nothing to install.

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

`python3 -m unittest discover -s tests -t .` — **21 tests, all pass** (last run saved in
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

## What is not done yet

- **The planner is not intelligent.** It knows one recipe ("find leads") by keyword. Any other
  task is split on "then" and its steps are only *simulated*, not really carried out.
- **The llama.cpp planner is untested.** The plug-in point exists and falls back safely, but no
  local model has been run against it, and model-planned steps would also only be simulated.
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
