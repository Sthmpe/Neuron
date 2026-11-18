"""The builder loop for fixing a bug in an existing project (B), on top of the project state (A).

  state    : the project is mapped (files, functions); its own test suite is the acceptance test.
  review   : the reviewer role reads the failing tests and a slice of the code, names the faulty
             function and says what to change (a diagnosis, saved in decisions).
  build    : the builder role rewrites ONLY that function, given the diagnosis.
  test     : the change is applied to a fresh copy and the tests run in the sandbox.
  fix/next : on failure the reviewer sees what was tried and what the tests said, and diagnoses again.
At most 3 code attempts - the same budget as the step-2 tool it is compared with. Success is claimed
only when the sandbox says the tests pass (twice, on fresh copies).
"""
import ast
import difflib
import json
import re
import shutil
import textwrap
import time
from pathlib import Path

from ..brain.llm import LLMUnavailable
from ..brain.tools.fix_code import default_test_command, is_test_file, tail, tests_passed
from . import localize, pmap, prompts
from .build import Meter, extract_code
from .state import ProjectState

MAX_ATTEMPTS = 3
SOURCE_BUDGET = 7000


def failing_tests(output):
    """Names like 'Class.test_x' of the tests that failed, from unittest output."""
    names = []
    for kind, test, where in re.findall(r"^(FAIL|ERROR): (\w+) \(([\w.]+)\)", output, re.M):
        parts = where.split(".")
        cls = parts[-2] if parts[-1] == test and len(parts) >= 2 else parts[-1]
        names.append(f"{cls}.{test}")
    return list(dict.fromkeys(names))


def pick_function(reply_code, name):
    """From the builder's reply, the source of the function called `name` (bare name)."""
    reply_code = textwrap.dedent(reply_code)        # a method is often sent back still indented
    try:
        tree = ast.parse(reply_code)
    except SyntaxError:
        return None
    found = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if not found:
        return None
    node = found[0]
    lines = reply_code.splitlines()
    start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
    return "\n".join(lines[start: node.end_lineno])


def apply_edit(file_text, function_source, reply):
    """Apply an OLD/NEW edit (two code blocks) inside the function. Returns the new file text or None."""
    blocks = re.findall(r"```[a-zA-Z0-9]*[ \t]*\n(.*?)```", reply, re.S)
    if len(blocks) < 2:
        return None
    old = [l.strip() for l in blocks[0].strip("\n").splitlines() if l.strip()]
    new = textwrap.dedent(blocks[1]).strip("\n").splitlines()
    if not old or [l.strip() for l in new if l.strip()] == old:
        return None
    fn_lines = function_source.splitlines()
    for i in range(len(fn_lines)):
        j, k = i, 0
        while j < len(fn_lines) and k < len(old):
            if not fn_lines[j].strip():
                j += 1
                continue
            if fn_lines[j].strip() != old[k]:
                break
            j, k = j + 1, k + 1
        if k == len(old):
            first = fn_lines[i]
            indent = first[: len(first) - len(first.lstrip())]
            changed = fn_lines[:i] + [(indent + l if l.strip() else l) for l in new] + fn_lines[j:]
            new_fn = "\n".join(changed)
            return file_text.replace(function_source, new_fn, 1) if function_source in file_text else None
    return None


def fix_project(project, runner, sandbox, log=print, test_command=None, write_back=True, max_seconds=None, memory_hint=""):
    project, state, meter, t0 = Path(project), ProjectState(project), Meter(), time.time()
    work = project.parent / (project.name + "__work")
    cmd = test_command or default_test_command(project)
    default_cmd = test_command is None

    def run_tests(change=None):
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(project, work, ignore=shutil.ignore_patterns(".neuron", ".git", "__pycache__", "*.pyc", ".venv", "venv"))
        if change:
            (work / change[0]).write_text(change[1])
        res = sandbox.run(cmd, work)
        return tests_passed(res, default_cmd), res

    if state.exists():
        state.resume()
    else:
        state.create("Make the project's failing tests pass by fixing the bug in the source code. Never change the tests.",
                     "bugfix", {"test_command": cmd}, [{"id": "fix", "title": "Find and fix the bug that makes the tests fail"}],
                     [{"name": "the project's own test suite", "command": cmd}])
    state.journal("session", models={r: runner.model_for(r) for r in ("reviewer", "builder")})
    m = state.map()
    sources = {f: (project / f).read_text(errors="replace") for f in m if not is_test_file(f)}
    tests = {f: (project / f).read_text(errors="replace") for f in m if is_test_file(f)}
    candidates = {}          # "file::qualname" for every function in the source files
    for f in sources:
        for fn in m[f]["functions"]:
            candidates[f"{fn['name']}" if sum(fn["name"] == g["name"] for s in sources for g in m[s]["functions"]) == 1
                       else f"{f}::{fn['name']}"] = (f, fn["name"])

    task = state.task("fix")
    if task["status"] == "done":
        return {"claimed": True, "attempts": len(task["attempts"]), "llm": vars(meter), "seconds": 0.0, "resumed_done": True}
    state.update_task("fix", status="in_progress")
    baseline = next((r for r in state.lines("test_results.jsonl") if r["attempt"] == 0), None)
    if baseline is None:
        ok, res = run_tests()
        state.record_test("fix", 0, ok, "tests pass" if ok else "tests fail", res.output)
        baseline = {"passed": ok, "output_tail": res.output[-2000:]}
    if baseline["passed"]:
        state.update_task("fix", status="done")
        return {"claimed": True, "attempts": 0, "already_passing": True, "llm": vars(meter), "seconds": round(time.time() - t0, 1)}
    if not candidates:
        state.update_task("fix", status="failed")
        return {"claimed": False, "attempts": 0, "error": "no functions found in the source files", "llm": vars(meter)}

    output = baseline["output_tail"]
    failing = failing_tests(output)
    test_src = []
    for f, text in tests.items():
        for name in failing:
            src = pmap.function_source(text, name)
            if src:
                test_src.append(f"# {f}\n{src}")
    test_block = "\n\n".join(test_src)[:2500] or "\n\n".join(tests.values())[:2500]
    # the slice of source the reviewer sees: whole files if small, else the functions the tests touch
    whole = "\n\n".join(f"# file: {f}\n{t.rstrip()}" for f, t in sources.items())
    if len(whole) > SOURCE_BUDGET:
        used = [k for k, (f, q) in candidates.items() if q.split(".")[-1] in (test_block + output)]
        whole = "\n\n".join(f"# {candidates[k][0]}\n{pmap.function_source(sources[candidates[k][0]], candidates[k][1])}"
                            for k in (used or list(candidates))[:12])[:SOURCE_BUDGET]
    # ---- where to look: which functions do the FAILING tests run? (no model involved) ----
    by_place = {v: k for k, v in candidates.items()}
    saved = next((d for d in state.lines("decisions.jsonl") if d["kind"] == "localisation"), None)
    if saved is None:
        ranked = localize.rank_functions(localize.suspicious(project, sandbox, work, cmd), m) if default_cmd else []
        ranked = [(by_place[(f, q)], score) for f, q, score in ranked if (f, q) in by_place][:5]
        state.decide("fix", "localisation", json.dumps(ranked))
    else:
        ranked = [tuple(x) for x in json.loads(saved["text"])]
    choices = [k for k, _ in ranked] or sorted(candidates)
    hint = ("\n\nRunning the tests one by one shows which functions the FAILING tests use most "
            "(most suspicious first): " + ", ".join(f"{k} ({score:.2f})" for k, score in ranked)) if ranked else ""
    schema = {"type": "object", "required": ["function", "problem", "fix"],
              "properties": {"function": {"type": "string", "enum": choices},
                             "problem": {"type": "string"}, "fix": {"type": "string"}}}
    winner = None
    while len(task["attempts"]) < MAX_ATTEMPTS and winner is None:
        if max_seconds is not None and time.time() - t0 > max_seconds:
            break
        n = len(task["attempts"]) + 1
        attempt = {"n": n, "passed": False}
        history = ""
        for a in task["attempts"]:
            history += f"\nAttempt {a['n']}: changed `{a.get('function')}` because: {a.get('problem', '')}. Result: {a.get('failure', '')[:300]}"
        # narrow at first (the most suspicious functions), wider on later attempts
        offered = (choices[: {1: 2, 2: 3}.get(n, 5)] if ranked else choices)
        schema["properties"]["function"]["enum"] = offered
        try:
            # ---- review: diagnose -------------------------------------------------
            user = (f"Failing test output:\n```\n{tail(output, 1800)}\n```\n\nThe failing tests:\n```python\n{test_block}\n```\n\n"
                    f"Source code:\n```python\n{whole}\n```{hint}\n\n" + (f"{memory_hint}\n\n" if memory_hint else "")
                    + f"Functions you can choose: {', '.join(offered)}"
                    + (f"\n\nEarlier attempts that did NOT fix it (choose differently or fix differently):{history}" if history else ""))
            reply = meter.chat(runner.client("reviewer"), [{"role": "system", "content": prompts.DIAGNOSE_SYSTEM},
                                                           {"role": "user", "content": user}],
                               max_tokens=300, temperature=0.1 if n == 1 else 0.6, json_schema=schema)
            try:
                d = json.loads(reply.text[reply.text.index("{"): reply.text.rindex("}") + 1])
            except ValueError:
                d = {}
            key = d.get("function") if d.get("function") in offered else offered[0]
            rel, qual = candidates[key]
            attempt.update(function=key, problem=str(d.get("problem", ""))[:400], fix=str(d.get("fix", ""))[:400])
            state.decide("fix", "diagnosis", f"attempt {n}: {key}: {attempt['problem']} -> {attempt['fix']}")
            # ---- build: rewrite that one function ----------------------------------
            old = pmap.function_source(sources[rel], qual)
            edit_mode = n == 2      # second try: ask for a small OLD/NEW edit, which cannot come back unchanged
            user = (f"The bug: {attempt['problem']}\nThe fix to make: {attempt['fix']}\n\n"
                    f"A failing test:\n```python\n{test_block[:1200]}\n```\n\n"
                    f"The function to rewrite (from {rel}):\n```python\n{textwrap.dedent(old)}\n```\n"
                    + ("\nYour previous rewrite was identical to the original or did not work. Make a real change.\n"
                       if task["attempts"] else "")
                    + (prompts.EDIT_FORMAT if edit_mode else f"\nReply with the complete corrected function `{qual.split('.')[-1]}` only."))
            reply = meter.chat(runner.client("builder"), [{"role": "system", "content": prompts.EDIT_SYSTEM if edit_mode else prompts.FIX_SYSTEM},
                                                          {"role": "user", "content": user}],
                               max_tokens=900, temperature=0.1 if n == 1 else 0.6)
        except LLMUnavailable as e:
            attempt["failure"] = f"the local model could not be used: {e}"
            state.add_attempt("fix", attempt)
            break
        if edit_mode:
            new_text = apply_edit(sources[rel], old, reply.text)
            if new_text is None:
                attempt["failure"] = "the reply was not a usable OLD/NEW edit of that function"
        else:
            code = extract_code(reply.text)
            new_fn = pick_function(code, qual.split(".")[-1]) if code else None
            new_text = pmap.replace_function(sources[rel], qual, new_fn) if new_fn else None
            if new_text is None:
                attempt["failure"] = "the reply did not contain the function"
        if new_text is None:
            pass
        else:
            try:
                compile(new_text, rel, "exec")
            except SyntaxError as e:
                attempt["failure"], new_text = f"the rewritten function is not valid Python: {e.msg}", None
        if new_text is not None and new_text.strip() == sources[rel].strip():
            attempt["failure"], new_text = "the rewritten function is identical to the original (no change)", None
        if new_text is not None:
            attempt["file"] = rel
            attempt["diff"] = "".join(difflib.unified_diff(sources[rel].splitlines(True), new_text.splitlines(True),
                                                           f"a/{rel}", f"b/{rel}"))
            ok, res = run_tests((rel, new_text))
            if ok:
                ok, res = run_tests((rel, new_text))      # confirm on a second fresh copy
            state.record_test("fix", n, ok, "tests pass" if ok else "tests fail" + (" (timed out)" if res.timed_out else ""), res.output)
            attempt["timed_out"] = res.timed_out
            if ok:
                attempt["passed"] = True
                winner = (rel, new_text)
            else:
                attempt["failure"] = "tests still fail: " + tail(res.output, 500)
                output = res.output if not res.timed_out else output
        state.add_attempt("fix", attempt)
        task = state.task("fix")
        log(f"  attempt {n}: {attempt.get('function')} -> {'tests pass' if attempt['passed'] else attempt.get('failure', '')[:90]}")
    shutil.rmtree(work, ignore_errors=True)
    if winner and write_back:
        (project / winner[0]).write_text(winner[1])
        state.refresh_map()
    state.update_task("fix", status="done" if winner else "failed")
    return {"claimed": bool(winner), "attempts": len(task["attempts"]), "file": winner[0] if winner else None,
            "history": [{k: a.get(k) for k in ("n", "function", "problem", "fix", "passed", "failure", "timed_out")} for a in task["attempts"]],
            "llm": vars(meter), "seconds": round(time.time() - t0, 1)}
