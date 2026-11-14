"""fix_code: make a Python project's failing tests pass.

How it works
  1. Copy the project into a private work folder (the project itself is not touched yet).
  2. Run the tests inside the sandbox. If they already pass there is nothing to fix.
  3. Show the local model the failing test output and the relevant source files; ask for a
     corrected version of ONE source file. Test files are never editable.
  4. Apply the change to a fresh copy, run the tests in the sandbox again.
  5. If they pass, run them once more on another fresh copy (pristine tests) to confirm.
     If they fail, give the model the new test output and try again - at most 3 attempts.
  6. Success is only reported when the sandbox says the tests pass. Otherwise the tool fails
     and reports every attempt: what it changed and what the tests said.

Each attempt is saved to disk as soon as it finishes, so a brain restart in the middle
continues with the next attempt instead of starting over.
"""
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import time
from pathlib import Path

from ..llm import LLMUnavailable
from ..sandbox import SandboxUnavailable
from .base import Tool, ToolFailure, ToolResult

SYSTEM = ("You are a careful Python programmer. A project's tests are failing because of a bug in the "
          "source code. Find the bug and fix it so the tests pass. Never change the tests. "
          "Change as little as possible.")
REPLY_FORMAT = ("Reply in exactly this format and nothing else:\n"
                "FILE: <path of the ONE source file you change>\n"
                "```python\n<the complete new content of that file>\n```")
IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv", "venv", "node_modules", ".mypy_cache")
SOURCE_BUDGET, TEST_BUDGET, OUTPUT_TAIL = 10_000, 5_000, 2_500


def is_test_file(rel):
    parts = Path(rel).parts
    name = parts[-1]
    return (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
            or any(p in ("tests", "test") for p in parts[:-1]))


def default_test_command(root):
    cmd = ["python3", "-m", "unittest", "discover"]
    if (root / "tests").is_dir():
        cmd += ["-s", "tests"] + (["-t", "."] if (root / "tests" / "__init__.py").exists() else [])
    return cmd


def tests_passed(res, default_cmd):
    if not res.ok:
        return False
    if default_cmd:  # "0 tests ran" is not a pass
        m = re.search(r"^Ran (\d+) tests?", res.output, re.M)
        return bool(m and int(m.group(1)) > 0)
    return True


def tail(text, n=OUTPUT_TAIL):
    return text if len(text) <= n else "[...]\n" + text[-n:]


def parse_reply(text, editable, originals):
    """Return (path, new_content, None) or (None, None, problem)."""
    blocks = re.findall(r"```[a-zA-Z0-9]*[ \t]*\n(.*?)```", text, re.S)
    if not blocks:
        return None, None, "the reply contained no complete code block"
    m = re.search(r"FILE:\s*[`'\"]?([^\s`'\"]+)", text)
    path = None
    if m:
        cand = m.group(1).replace("\\", "/")
        cand = re.sub(r"^(\./|/workspace/)", "", cand)
        if cand in editable:
            path = cand
        else:
            same_name = [e for e in editable if Path(e).name == Path(cand).name]
            if len(same_name) == 1:
                path = same_name[0]
            else:
                return None, None, f"the reply names '{cand}', which is not an editable source file"
    elif len(editable) == 1:
        path = editable[0]
    else:
        return None, None, "the reply did not say which file it changes"
    code = blocks[0].rstrip() + "\n"
    try:
        compile(code, path, "exec")
    except SyntaxError as e:
        return None, None, f"the proposed code is not valid Python: {e.msg} (line {e.lineno})"
    if code.strip() == originals[path].strip():
        return None, None, "the proposed file is identical to the original (no change)"
    return path, code, None


def build_prompt(sources, tests, test_output, attempts, omitted):
    parts = ["The tests of this Python project fail.", "", "## Failing test output", "```", tail(test_output), "```",
             "", "## Source files (you may change ONE of these)"]
    for rel, text in sources:
        parts += [f"### {rel}", "```python", text.rstrip(), "```"]
    if omitted:
        parts.append(f"(not shown, too large: {', '.join(omitted)})")
    if tests:
        parts += ["", "## Test files (read-only, do not change)"]
        for rel, text in tests:
            parts += [f"### {rel}", "```python", text.rstrip(), "```"]
    if attempts:
        parts += ["", "## Earlier attempts that did NOT work - try something different"]
        for a in attempts:
            parts.append(f"### Attempt {a['n']}")
            if a.get("diff"):
                parts += ["```diff", tail(a["diff"], 1500), "```", "Result:", "```",
                          tail(a.get("test_output_tail") or "", 1200), "```"]
            else:
                parts.append(f"Rejected before testing: {a.get('error')}")
    parts += ["", REPLY_FORMAT]
    return "\n".join(parts)


class FixCodeTool(Tool):
    name = "fix_code"
    description = ("Fix a bug in a Python project whose tests are failing. Reads the code, changes one source "
                   "file, runs the tests in an isolated sandbox and retries up to 3 times. Works offline.")
    inputs = {
        "project": {"type": "path", "description": "Folder of the project, exactly as given in the task",
                    "required": True},
        "test_command": {"type": "string", "description": "Command that runs the tests "
                         "(optional; default: python3 -m unittest discover)"},
        "write_back": {"type": "boolean", "description": "Copy the fix back into the project folder (default true)"},
    }
    MAX_ATTEMPTS = 3

    def run(self, ctx):
        llm, sandbox = ctx.services.get("llm"), ctx.services.get("sandbox")
        project = Path(str(ctx.params.get("project") or "")).expanduser()
        if not project.is_dir():
            raise ToolFailure(f"project folder not found: {project}")
        project = project.resolve()
        if sandbox is None or not sandbox.available():
            raise ToolFailure("no isolated sandbox is available, so the project's code was not run at all")
        base = ctx.dir / f"fix_code_step{ctx.step['no']}"
        orig, work, state_file = base / "original", base / "work", base / "attempts.json"
        if not orig.exists():
            base.mkdir(parents=True, exist_ok=True)
            tmp = base / "original.tmp"
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(project, tmp, ignore=IGNORE, symlinks=True)
            os.replace(tmp, orig)
        custom = ctx.params.get("test_command")
        cmd = shlex.split(custom) if custom else default_test_command(orig)
        state = json.loads(state_file.read_text()) if state_file.exists() else {"baseline": None, "attempts": []}

        def save():
            tmp = state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=1))
            os.replace(tmp, state_file)

        def run_tests(change=None):
            shutil.rmtree(work, ignore_errors=True)
            shutil.copytree(orig, work, symlinks=True)
            if change:
                (work / change[0]).write_text(change[1])
            try:
                return sandbox.run(cmd, work)
            except SandboxUnavailable as e:
                raise ToolFailure(str(e)) from e

        def record(res):
            return {"exit_code": res.exit_code, "timed_out": res.timed_out, "oom_killed": res.oom_killed,
                    "seconds": round(res.duration, 2), "peak_mem_mb": round(res.peak_mem_bytes / 2**20, 1),
                    "output_tail": tail(res.output), "output_sha256": hashlib.sha256(res.output.encode()).hexdigest()}

        files = sorted(str(p.relative_to(orig)) for p in orig.rglob("*.py"))
        editable = [f for f in files if not is_test_file(f)]
        originals = {f: (orig / f).read_text(errors="replace") for f in files}

        if state["baseline"] is None:
            res = run_tests()
            state["baseline"] = {**record(res), "passed": tests_passed(res, not custom)}
            save()
        baseline = state["baseline"]
        common = {"project": str(project), "test_command": " ".join(cmd), "tests_before": baseline,
                  "sandbox": sandbox.describe()}
        if baseline["passed"]:
            return ToolResult({"fixed": False, "already_passing": True},
                              "The tests already pass - nothing to fix", common, verified=True,
                              verification="tests run in the sandbox: exit code 0")
        if not editable:
            raise ToolFailure("the project has no editable Python source files", common)
        if llm is None:
            raise ToolFailure("no local model is configured, so no fix was attempted", common)

        # choose what the model gets to read
        out = baseline["output_tail"]
        mentioned = [f for f in files if Path(f).name in out]
        test_text = "\n".join(originals[f] for f in files if is_test_file(f))
        rank = lambda f: (f not in mentioned, Path(f).stem not in test_text, len(originals[f]))
        sources, omitted, used = [], [], 0
        for f in sorted(editable, key=rank):
            if used + len(originals[f]) > SOURCE_BUDGET and sources:
                omitted.append(f)
                continue
            sources.append((f, originals[f]))
            used += len(originals[f])
        shown = [f for f, _ in sources]
        tests, used = [], 0
        for f in sorted((f for f in files if is_test_file(f)), key=lambda f: (f not in mentioned, len(originals[f]))):
            if not originals[f].strip() or used >= TEST_BUDGET:
                continue
            text = originals[f][: TEST_BUDGET - used]
            tests.append((f, text))
            used += len(text)

        winner = next((a for a in state["attempts"] if a.get("passed")), None)
        last_output = state["attempts"][-1].get("test_output_tail") if state["attempts"] else None
        while winner is None and len(state["attempts"]) < self.MAX_ATTEMPTS:
            n = len(state["attempts"]) + 1
            prompt = build_prompt(sources, tests, last_output or out, state["attempts"], omitted)
            attempt = {"n": n, "passed": False}
            t0 = time.time()
            try:
                reply = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                                 max_tokens=2048, temperature=0.2 if n == 1 else 0.7)
            except LLMUnavailable as e:
                raise ToolFailure(f"the local model could not be used on attempt {n}: {e}",
                                  {**common, "attempts": state["attempts"]}) from e
            attempt["llm"] = reply.stats()
            (base / f"attempt{n}_reply.txt").write_text(reply.text)
            path, code, problem = parse_reply(reply.text, shown, originals)
            if problem and reply.finish_reason == "length":
                problem = "the model's reply was cut off by the length limit; " + problem
            if problem:
                attempt["error"] = problem
            else:
                attempt["file"] = path
                attempt["diff"] = "".join(difflib.unified_diff(
                    originals[path].splitlines(True), code.splitlines(True), f"a/{path}", f"b/{path}"))
                (base / f"attempt{n}_file.txt").write_text(code)
                res = run_tests((path, code))
                ok = tests_passed(res, not custom)
                attempt["test"] = {k: v for k, v in record(res).items() if k != "output_tail"}
                attempt["test_output_tail"] = tail(res.output)
                if ok:  # confirm on a second fresh copy with pristine tests
                    res2 = run_tests((path, code))
                    ok = tests_passed(res2, not custom)
                    attempt["confirm_run_passed"] = ok
                    if not ok:
                        attempt["test_output_tail"] = tail(res2.output)
                attempt["passed"] = ok
                last_output = attempt["test_output_tail"]
            attempt["seconds"] = round(time.time() - t0, 2)
            state["attempts"].append(attempt)
            save()
            if attempt["passed"]:
                winner = attempt

        evidence = {**common, "attempts_used": len(state["attempts"]), "attempts": state["attempts"],
                    "work_folder": str(base),
                    "llm_seconds": round(sum(a.get("llm", {}).get("seconds", 0) for a in state["attempts"]), 2),
                    "peak_sandbox_mem_mb": max([baseline["peak_mem_mb"]] + [a["test"]["peak_mem_mb"]
                                               for a in state["attempts"] if "test" in a])}
        if winner is None:
            raise ToolFailure(f"could not make the tests pass in {len(state['attempts'])} attempts", evidence)
        code = (base / f"attempt{winner['n']}_file.txt").read_text()
        path = winner["file"]
        write_back = ctx.params.get("write_back", True)
        if write_back:
            (project / path).write_text(code)
        evidence.update({"changed_file": path, "diff": winner["diff"], "written_back_to_project": bool(write_back),
                         "sha256_before": hashlib.sha256(originals[path].encode()).hexdigest(),
                         "sha256_after": hashlib.sha256(code.encode()).hexdigest(),
                         "tests_after": winner["test"]})
        return ToolResult({"fixed": True, "file": path, "attempts": winner["n"]},
                          f"Fixed {path}: tests pass in the sandbox after attempt {winner['n']} of {self.MAX_ATTEMPTS}",
                          evidence, verified=True,
                          verification="tests run twice in the sandbox on fresh copies: exit code 0 both times")


TOOLS = [FixCodeTool()]
