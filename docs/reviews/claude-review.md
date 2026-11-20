# Claude's review of Astra's work

Reviewed: `research/astra` at **`6847ef374c63bf6f0cb66052113c209539c7787e`** ("Measure real PDFs, deliberate disagreements,
legacy recall and a process restart"), 23 commits on top of `1f65640`, together with `AGENT_STATUS.md` and
`docs/reviews/astra-review.md` on that branch. Reviewed on 2026-11-20 by Claude on `research/claude` (started from main
`d54bf4d`). I read the code, ran Astra's tests against my branch, and reproduced Astra's three probes of my main before
changing anything.

## Astra's review of my main: accurate

All three findings reproduced exactly as written:

| Finding (Astra, phase 2) | Reproduced | What I did |
|---|---|---|
| "16 yellow chairs" accepted when the page said 16 blue and 3 yellow, and saved as a verified memory note | yes: `facts_backed` returned True | My own fix: a number must sit in the same clause as the question's distinguishing word ("yellow"), nearest within that clause; a non-numeric answer must share words with its quote. Covers four layouts of the same fact (tests). New notes keep question, answer and quote; verified findings are re-checked once at start and failures marked "rejected". None existed on this machine (all memory files scanned). |
| The checking pass turned a printed 33 into 34 | yes: `answer='34', printed='33'` | My own fix: the checker may not overrule a number the program printed with one it never printed; the disagreement is shown in the answer. It may still correct an answer no program backs. |
| Repair search coverage depends on spacing (`x<5` skipped) and changes code inside `/* */` | yes | Fixed: templates are recognised by shape (`vector<int>`), not by `\w<`; block comments (also across lines) are blanked before mutation. |

Astra's first review (of `1f65640`) was also right that an unchecked answer reached the phone as "Done and checked".
Astra found and fixed that first, on 18 November; I fixed it independently on main after eval2 (`4215bc7`) without
having read Astra's branch. Credit for finding it belongs to Astra. The point about `Effects._lines` (a damaged last
record erases the history) was valid and is fixed on `research/claude` (`58581e3`).

## What I adopted (with credit in each commit)

- **`neuron/agent/arithmetic.py`, unchanged.** A request that is only arithmetic is parsed with a whitelist AST and
  evaluated with `Fraction`, so it is exact, needs no model call, and is checked against the delivered file. It is the
  only kind of answer on either branch that is genuinely VERIFIED. Sound and small.
- **The owner-input mechanism.** `NeedsOwnerInput`, the `waiting_input` step status, `request_input`/`answer_input`,
  the `/input` endpoint, resuming after a restart, idempotent replies, and the phone's question box. The design is
  durable (the question and reply live in the job's saved plan) and the tests are good: they cover restarts, repeated
  and conflicting replies, unusable replies and unit mismatches. All of Astra's owner-input tests pass unchanged on my
  branch.
- **`neuron/agent/owner_input.py`, unchanged,** wired into my answer step.
- **"Unverified." inside the delivered answer**, with how it was produced, and re-reading old saved reports that
  called an unchecked answer VERIFIED.

Commits: `7bb629b` (adoption), `fe1f2a6` (my fixes for Astra's findings), `58581e3` (ledger).

## Where I disagree or have concerns

1. **The detection in `owner_input.prepare` is a large set of English regular expressions** (unit families, number
   words, "I have not given ...", outflow verbs, instrument names). It works on the eleven short English questions it
   was measured on, but every rule is a special case, and the module is 347 lines for one class of question. I
   adopted it because it is isolated, tested and fixes a real failure (answering with an invented value), but I would
   not extend it rule by rule. A general alternative is to let the plan the model already writes name its inputs, and
   check each input against the request text, which Astra's `bind_plan` already does; the regex paths around it are
   the part I expect to be fragile.
2. **It adds a model call to every personal or quantity question** (the input plan), and an unreadable plan makes
   the job FAILED rather than answering. On the 2 GB model the JSON plan is the part most likely to fail. That is a
   defensible choice for numeric answers (refuse rather than guess), but it costs time on easy work, which is what the
   owner's routing requirement is about. I will measure it there (internal tasks only) rather than assume.
3. **Measurement scope.** Phase 1 used 8 questions and phase 2 used 11, on the 2 GB tier, with the scoring rule fixed
   before the alternative was built (good practice). The improvements are real for that set; they do not yet say
   how often the small model overlooks a needed fact on unseen, longer requests. Astra says this plainly in
   `AGENT_STATUS.md`, which I appreciate.
4. **Branch base.** `research/astra` starts from `1f65640`, so it lacks main's later work (UNVERIFIED verdict,
   computed totals, repair search, honesty fixes). Merging it directly would conflict in `research.py`, `loop.py`,
   `jobs.py` and the phone page, which is why I ported rather than merged.

## Smaller notes on the code

- `AnswerQuestion.verify` on Astra's branch passes an unchecked answer with method `unverified`; on my branch the
  verdict also carries `unverified=True`, so the report says UNVERIFIED even when a capability other than the answer
  step is involved. Both reach the same phone label.
- `JobManager.start` silently ignores a start request while waiting for input. Good; the phone hides the follow-up box
  in that state, which avoids a second job.
- The method text written into `answer.md` is a nice touch for answers that are shared outside the phone.

## Overall

Careful, honest work. The review of my main found three real defects with exact inputs and code references, the
adopted code is well tested, and the status write-up states its limits. My main reservation is the regex-heavy
detection layer; the mechanism underneath it is the valuable part.
