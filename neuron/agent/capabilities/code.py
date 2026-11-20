"""Code work in any installed language: fix a bug so the project's tests pass, document every function
without changing behaviour, write a new program from a description. The project's own tests (or the
compiler and example runs) decide success; the model's opinion never does."""
import ast
import json
import re
import shutil
from pathlib import Path

from ...builder.bugfix import apply_edit, fix_project
from ...builder.build import extract_code
from ...kit_next.copy import clean
from ..capability import Capability, Outcome, Verdict
from ..context import clip, files
from .workspace import detect_test_command, run_project_tests

C_LIKE = {".cpp", ".cc", ".c", ".h", ".hpp", ".go", ".rs", ".java", ".js", ".ts", ".dart", ".kt"}
FUNC = {
    ".go": re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\("),
    ".rs": re.compile(r"^\s*(?:pub\s+)?fn\s+([A-Za-z_]\w*)"),
    "default": re.compile(r"^[\w:<>\*&\s,~]*?\b((?:[A-Za-z_]\w*::)*[A-Za-z_~]\w*)\s*\([^;{]*\)\s*(?:const)?\s*(?:noexcept)?\s*(?:->\s*[\w:<>]+)?\s*\{?\s*$"),
}
KEYWORDS = {"if", "for", "while", "switch", "return", "catch", "sizeof", "else", "do"}
CONST_LINE = re.compile(r"^\s*(?:export\s+)?(?:static\s+)?(?:const(?:expr)?|var|let|#define|final)\s+(?:[\w:<>]+\s+)?([A-Za-z_]\w*)"
                        r"\s*(?:[:=]|\s)\s*[^;(){}]*\d[^;(){}]*;?\s*(?://.*)?$")


def functions_in(path, text):
    """[(name, first line, last line)] for brace languages, found by a header pattern and brace matching."""
    pat = FUNC.get(Path(path).suffix, FUNC["default"])
    lines, out = text.splitlines(), []
    i = 0
    while i < len(lines):
        m = pat.match(lines[i])
        name = m.group(1) if m else None
        if name and name.split("::")[-1] not in KEYWORDS and not lines[i].strip().startswith(("//", "#", "*")):
            depth, j, opened = 0, i, False
            while j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                opened = opened or "{" in lines[j]
                if opened and depth <= 0:
                    break
                if not opened and j > i + 2:
                    break
                j += 1
            if opened:
                out.append((name, i + 1, j + 1))
                i = j
        i += 1
    return out


def fix_note(job, lang, function, problem, fix, file):
    """What a verified fix teaches, for memory: the symptom, the cause and the change; plus which remembered fixes were
    in front of the model (they helped only in the sense that this fix then passed the tests)."""
    if not (problem and fix):
        return {}
    text = f"{lang} bug in {function} ({file}): {problem.strip()} Fix: {fix.strip()} The project's tests passed after the change."
    helped = [n["id"] for n in getattr(job, "memory_notes", []) if n["kind"] == "fix"]
    return {"memory_notes": [{"kind": "fix", "text": text[:900], "source": f"job {job.workspace.name}: {file}", "verified": True,
                              "tags": [lang, str(function).split("::")[-1].split(".")[-1]]}], "memory_helped": helped}


class FixBug(Capability):
    name = "fix_bug"
    purpose = "Find the faulty code in a project (any installed language), change it, and run the project's tests"
    permissions = ("read_workspace", "write_workspace", "run_code", "use_model")
    resources = {"ram_mb": 300, "uses_model": True}
    verification = "the project's own test command passes in the sandbox"
    domains = ("code",)
    # Fixed order, no model call to choose. The whole-file rewrite comes second: the core proof's 4 GB run 1 showed the
    # same model, given the whole (small) project and the test output in a plain loop, fixing bugs NEURON's narrow
    # diagnose-one-function-and-patch pipeline missed. NEURON must never do worse than its own model used plainly; it
    # keeps its guards (tests never edited, functions never dropped, the project's tests decide, nothing kept unless
    # they pass).
    strategies = ("rewrite whole files with the test output", "look at more functions", "rewrite the whole suspect function")
    fixed_strategy_order = True

    def run(self, job, params):
        ws = job.workspace
        cmd = detect_test_command(ws)
        if cmd is None:
            return Outcome(False, "no test command found, so a fix could not be proven", evidence={"no_retry": True})
        if params.get("strategy") == "rewrite whole files with the test output":
            return self._rewrite_files(job, params)
        hint = job.memory_context(kinds=("fix",)) if hasattr(job, "memory_context") else ""
        if cmd[0] == "python3":                               # the proven step-3 loop for Python
            import os
            if not params.get("strategy") and os.environ.get("NEURON_REPAIR_SEARCH", "1") != "0":
                found = self._python_search(job, ws, cmd)     # small changes first, as for the other languages
                if found is not None:
                    return found
            r = fix_project(ws, job.runner, job.sandbox, log=lambda *_: None, memory_hint=hint)
            if r.get("already_passing"):          # nothing failed, nothing was changed: not a fixed bug (core proof C1)
                return Outcome(False, "the project's tests already pass, so there was no failing test to fix and nothing was changed",
                               {"already": True}, evidence={"no_retry": True})
            res = {"history": r.get("history")}
            win = next((h for h in (r.get("history") or []) if h.get("passed")), None)
            if r.get("claimed") and win:
                res.update(fix_note(job, "python", win.get("function"), win.get("problem"), win.get("fix"), r.get("file")))
            return Outcome(bool(r.get("claimed")), f"python fix loop: {'fixed' if r.get('claimed') else 'not fixed'} in {r.get('attempts')} attempts",
                           res, [r["file"]] if r.get("file") else [], made_by="model")
        return self._fix_other(job, params, cmd)

    def _rewrite_files(self, job, params, rounds=3):
        from .feature import defined_names, is_test_file
        ws = job.workspace
        passed, res = run_project_tests(job)
        if passed:
            return Outcome(False, "the project's tests already pass, so there was no failing test to fix and nothing was changed",
                           {"already": True}, evidence={"no_retry": True})
        srcs = [f for f in files(ws) if Path(f).suffix in C_LIKE | {".py"} and not is_test_file(f)]
        tests = [f for f in files(ws) if Path(f).suffix in C_LIKE | {".py"} and is_test_file(f)]
        originals = {f: (ws / f).read_text(errors="replace") for f in srcs}
        output = res.output[-3000:] if res else ""
        for rnd in range(rounds):
            ctx, used = [], 0
            for f in tests + srcs:
                text = (ws / f).read_text(errors="replace")
                if used + len(text) < 9000:
                    ctx.append(f"--- {f} ---\n{text}")
                    used += len(text)
            reply = job.ask_text("builder", "You fix a bug so a project's tests pass. The tests are correct and must not change. "
                                 "Reply with the complete corrected content of each source file you change, each as a line "
                                 "'FILE: <path>' followed by one code block.",
                                 f"Test output:\n{clip(output, 2500)}\n\nProject files:\n" + "\n".join(ctx) +
                                 "\n\nWhich source file is wrong? Send the corrected file(s), complete.", max_tokens=1800)
            found = dict(re.findall(r"FILE:\s*[`'\"]?([\w./-]+)[`'\"]?\s*\n+```[^\n]*\n(.*?)```", reply, re.S))
            if not found and len(srcs) == 1:
                code = extract_code(reply)
                found = {srcs[0]: code} if code else {}
            changes = {}
            for path, code in found.items():
                path = path.strip().lstrip("./")
                if path in originals and code.strip() and not (defined_names(path, originals[path]) - defined_names(path, code)):
                    changes[path] = code.rstrip("\n") + "\n"
            if not changes:
                output = output[-2000:] + "\n(The last reply changed no source file of the project. Send FILE: <path> and the whole file.)"
                continue
            for path, code in changes.items():
                (ws / path).write_text(code)
            passed, res = run_project_tests(job)
            if passed:
                job.state.decide("fix", "rewrite", f"round {rnd + 1}: rewrote {', '.join(changes)}; the project's tests pass")
                return Outcome(True, f"fixed by rewriting {', '.join(changes)} with the test output (round {rnd + 1}); the project's tests pass",
                               {"files": list(changes)}, list(changes), made_by="model")
            output = res.output[-3000:] if res else ""
        for path, text in originals.items():                 # never leave a failed attempt behind
            if (ws / path).read_text(errors="replace") != text:
                (ws / path).write_text(text)
        return Outcome(False, f"rewriting whole files with the test output did not make the tests pass in {rounds} rounds: {clip(output, 400)}")

    def _python_search(self, job, ws, cmd):
        """Try small standard changes in the Python functions (and module-level constants) the failing tests point at,
        before the model loop. Core proof 2 GB run 1: the Python path never searched, and missed a rate of 0.75 that
        should be 0.075 and text[0] that should be text[:2]."""
        passed, res = run_project_tests(job)
        if passed or res is None:
            return Outcome(False, "the project's tests already pass, so there was no failing test to fix and nothing was changed",
                           {"already": True}, evidence={"no_retry": True}) if passed else None
        output = res.output[-4000:]
        idents = set(re.findall(r"[A-Za-z_]\w{2,}", output))
        for t in [f for f in files(ws) if f.endswith(".py") and re.search(r"(^|/)tests?/|test_|_test\.py$", f)]:
            text = (ws / t).read_text(errors="replace").splitlines()
            for ln in re.findall(rf"{re.escape(Path(t).name)}\", line (\d+)", output):
                if 0 < int(ln) <= len(text):
                    idents |= set(re.findall(r"[A-Za-z_]\w{2,}", text[int(ln) - 1]))
        cands = []
        for f in files(ws):
            if not f.endswith(".py") or re.search(r"(^|/)tests?/|test_|_test\.py$", f):
                continue
            try:
                tree = ast.parse((ws / f).read_text(errors="replace"))
            except SyntaxError:
                continue
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    score = (5 if node.name in idents else 0) + sum(1 for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in idents) * 0.2
                    cands.append((score, f, node.name, node.lineno, node.end_lineno))
                elif isinstance(node, ast.ClassDef):
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            score = (5 if sub.name in idents else 0) + (2 if node.name in idents else 0)
                            cands.append((score, f, f"{node.name}.{sub.name}", sub.lineno, sub.end_lineno))
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):    # a module-level constant, used by the functions
                    names = {t.id for t in ast.walk(node) if isinstance(t, ast.Name)}
                    cands.append((1.5, f, "(constant " + ", ".join(sorted(names)) + ")", node.lineno, node.end_lineno))
        cands.sort(key=lambda c: -c[0])
        if not cands:
            return None
        from ..repair_search import search
        from ...brain.tools.fix_code import tests_passed
        win = search(ws, [(c[1], c[2], c[3], c[4]) for c in cands[:6]], cmd, job.sandbox,
                     lambda r: tests_passed(r, True) and not r.timed_out, log=job.log)
        if not win:
            return None
        problem = f"line {win['line']} had {win['change']}"
        job.state.decide("fix", "small change", f"{win['file']}:{win['line']} {win['old']} -> {win['new']} ({win['tries']} tries)")
        return Outcome(True, f"fixed {win['file']}::{win['function']} with a small change ({win['change']}), found by trying "
                             f"standard small changes ({win['tries']} tries); the project's tests pass",
                       {**win, **fix_note(job, "python", win["function"], problem, f"changed '{win['old']}' to '{win['new']}'", win["file"])},
                       [win["file"]], made_by="search")

    def _fix_other(self, job, params, cmd):
        ws = job.workspace
        passed, res = run_project_tests(job)
        if passed:
            return Outcome(False, "the project's tests already pass, so there was no failing test to fix and nothing was changed",
                           {"already": True}, evidence={"no_retry": True})
        output = res.output[-4000:]
        srcs = [f for f in files(ws) if Path(f).suffix in C_LIKE and not re.search(r"(^|/)tests?/|_test\.|test_", f)]
        tests = [f for f in files(ws) if Path(f).suffix in C_LIKE and f not in srcs]
        idents = set(re.findall(r"[A-Za-z_]\w{2,}", output))
        failing_lines = []
        for t in tests:                                     # names on the failing test lines
            text = (ws / t).read_text(errors="replace").splitlines()
            for ln in re.findall(rf"{re.escape(Path(t).name)}:(\d+)|line (\d+)", output):
                n = int(ln[0] or ln[1])
                if 0 < n <= len(text):
                    idents |= set(re.findall(r"[A-Za-z_]\w{2,}", text[n - 1]))
                    failing_lines.append(f"{t}:{n}: {text[n - 1].strip()}")
        failing_lines = list(dict.fromkeys(failing_lines))[:8]
        cands = []
        for f in srcs:
            text = (ws / f).read_text(errors="replace")
            for name, a, b in functions_in(f, text):
                body = "\n".join(text.splitlines()[a - 1:b])
                short = name.split("::")[-1]
                score = (5 if short in idents else 0) + sum(1 for i in idents if re.search(rf"\b{re.escape(i)}\b", body)) * 0.2
                cands.append((score, f, name, a, b, body))
        # constants outside any function ("const OvertimeRate = 1.25"): the functions above use them, and a wrong value
        # there is a common bug (core proof B6, 4 GB run 1: only functions were searched and diagnosed)
        bodies = " ".join(c[5] for c in sorted(cands, key=lambda c: -c[0])[:3])
        for f in srcs:
            for n, line in enumerate((ws / f).read_text(errors="replace").splitlines(), 1):
                m = CONST_LINE.match(line)
                if m and not any(c[1] == f and c[3] <= n <= c[4] for c in cands):
                    score = 1.5 + (3 if re.search(rf"\b{re.escape(m.group(1))}\b", bodies) else 0) + (5 if m.group(1) in idents else 0)
                    cands.append((score, f, f"(constant {m.group(1)})", n, n, line))
        cands.sort(key=lambda c: -c[0])
        import os
        if not params.get("strategy") and cands and cands[0][0] > 0 and os.environ.get("NEURON_REPAIR_SEARCH", "1") != "0":
            # first, small one-token changes to the functions the failing tests point at (no model needed)
            from ..repair_search import search
            win = search(ws, [(c[1], c[2], c[3], c[4]) for c in cands[:5] if c[0] > 0], cmd, job.sandbox,
                         lambda r: r.ok and not r.timed_out, log=job.log)
            if win:
                lang = {".go": "go", ".rs": "rust", ".java": "java", ".js": "javascript", ".ts": "typescript"}.get(Path(win["file"]).suffix, "c++")
                problem = f"line {win['line']} had {win['change'].split(' -> ')[0]} where {win['change'].split(' -> ')[1]} was needed"
                job.state.decide("fix", "small change", f"{win['file']}:{win['line']} {win['old']} -> {win['new']} ({win['tries']} tries)")
                return Outcome(True, f"fixed {win['file']}::{win['function']} with a one-token change ({win['change']}), found by "
                                     f"trying small changes ({win['tries']} tries); the project's tests pass",
                               {**win, **fix_note(job, lang, win["function"], problem, f"changed '{win['old']}' to '{win['new']}'", win["file"])},
                               [win["file"]], made_by="search")
        wide = params.get("strategy") == "look at more functions"
        top = cands[: 8 if wide else 5]
        if not top:
            return Outcome(False, "no functions found in the source files")
        keys = [f"{c[1]}::{c[2]}" for c in top]
        ctx = "\n\n".join(f"// {c[1]} lines {c[3]}-{c[4]}\n{clip(c[5], 1500)}" for c in top)
        tried = params.get("feedback", "")
        diag = job.ask_json("reviewer", "You find the one bug that makes the tests fail. The tests are correct.",
                            f"Test output:\n{clip(output, 2500)}\n\n"
                            + (("The failing test lines (what the correct code must produce):\n" + "\n".join(failing_lines) + "\n\n") if failing_lines else "")
                            + f"Candidate functions:\n{ctx}\n\n" + (f"Earlier attempt failed: {clip(tried, 800)}\n" if tried else "")
                            + (f"{job.memory_context(kinds=('fix',))}\n" if hasattr(job, "memory_context") and job.memory_context(kinds=("fix",)) else "")
                            + "Which function has the bug, what is wrong, and what is the fix?",
                            {"type": "object", "required": ["function", "problem", "fix"],
                             "properties": {"function": {"type": "string", "enum": keys}, "problem": {"type": "string"}, "fix": {"type": "string"}}},
                            max_tokens=700)              # 300 cut the 4B model's JSON off mid-sentence: "no diagnosis" 3 times (B6)
        if not diag:
            return Outcome(False, "no diagnosis from the model")
        pick = top[keys.index(diag["function"])] if diag["function"] in keys else top[0]
        _, f, name, a, b, body = pick
        job.state.decide("fix", "diagnosis", f"{f}::{name}: {diag['problem']} -> {diag['fix']}")
        full = (ws / f).read_text()
        if params.get("strategy") == "rewrite the whole suspect function":
            reply = job.ask_text("builder", "You fix one function. Reply with one code block containing only the complete corrected function.",
                                 f"Bug: {diag['problem']}\nFix: {diag['fix']}\n\n```\n{body}\n```", max_tokens=1200)
            new_fn = extract_code(reply)
            new = full.replace(body, new_fn.rstrip("\n")) if new_fn and body in full else None
        else:
            new = None
        edit_prompt = (f"Bug: {diag['problem']}\nFix: {diag['fix']}\n\nFunction:\n```\n{body}\n```\n\n"
                       + (("The failing test lines:\n" + "\n".join(failing_lines) + "\n\n") if failing_lines else "")
                       + "OLD:\n```\n<line(s) copied exactly>\n```\nNEW:\n```\n<corrected line(s)>\n```")
        backup, res, tried_any = full, None, False
        # up to two candidate changes per try (the second asked more freely); the tests decide, a failed one is undone
        for temp in ((None,) if params.get("strategy") == "rewrite the whole suspect function" else (0.2, 0.7)):
            if temp is not None:
                reply = job.ask_text("builder", "You fix a bug by changing as few lines as possible. Reply with two code blocks: "
                                     "the exact old line(s), then the new line(s).", edit_prompt, max_tokens=500, temperature=temp)
                new = apply_edit(full, body, reply.replace("    ", "\t") if "\t" in body and "\t" not in reply else reply) \
                    or apply_edit(full, body, reply)
            if not new or new == full:
                continue
            tried_any = True
            (ws / f).write_text(new)
            passed, res = run_project_tests(job)
            if passed:
                break
            (ws / f).write_text(backup)                       # never leave a failed change behind
        else:
            if not tried_any:
                return Outcome(False, f"the change to {name} could not be applied or changed nothing")
            return Outcome(False, f"changed {f}::{name} but the tests still fail: {clip(res.output if res else '', 600)}")
        if not passed:
            return Outcome(False, f"the change to {name} could not be applied or changed nothing")
        lang = {".go": "go", ".rs": "rust", ".java": "java", ".js": "javascript", ".ts": "typescript"}.get(Path(f).suffix, "c++")
        return Outcome(True, f"fixed {f}::{name}: {diag['problem']}",
                       {"file": f, "function": name, **fix_note(job, lang, name, diag["problem"], diag["fix"], f)}, [f], made_by="model")

    def verify(self, job, params, outcome):
        passed, res = run_project_tests(job)
        return Verdict(bool(passed), [{"id": "project_tests_pass", "pass": bool(passed), "detail": (res.output if res else "")[-500:]}],
                       "project test command in the sandbox")


def _strip_docs(src):
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and n.body:
            f = n.body[0]
            if isinstance(f, ast.Expr) and isinstance(getattr(f, "value", None), ast.Constant) and isinstance(f.value.value, str):
                n.body = n.body[1:] or [ast.Pass()]
    return ast.dump(tree)


class DocumentFunctions(Capability):
    name = "document_functions"
    purpose = "Write a docstring for every undocumented Python function, one at a time, without changing behaviour"
    permissions = ("read_workspace", "write_workspace", "use_model")
    resources = {"ram_mb": 100, "uses_model": True}
    verification = "the code with docstrings removed is identical to the original; every function has a docstring"
    domains = ("code",)

    def _is_test(self, rel):
        return rel.parts[0] in ("tests", "test") or rel.name.startswith("test_")

    def run(self, job, params):
        ws = job.workspace
        orig = job.state.dir / "original"
        if not orig.exists():                              # snapshot once, so a resumed job compares with the real original
            for f in files(ws, {".py"}):
                (orig / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ws / f, orig / f)
        done_file = job.state.dir / "documented.json"
        ph_file = job.state.dir / "placeholders.json"
        done = json.loads(done_file.read_text()) if done_file.exists() else []
        wrote, skipped = 0, []
        for rel in files(ws, {".py"}):
            if self._is_test(Path(rel)):
                continue
            path = ws / rel
            while True:
                src = path.read_text()
                tree = ast.parse(src)
                todo = next((n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not ast.get_docstring(n)
                             and f"{rel}:{n.lineno}:{n.name}" not in skipped), None)
                if todo is None:
                    break
                key = f"{rel}:{todo.name}"
                body0 = todo.body[0]
                if body0.lineno == todo.lineno:            # 'def f(): return x' on one line: leave it, report it
                    skipped.append(f"{rel}:{todo.lineno}:{todo.name}")
                    continue
                fn_src = ast.get_source_segment(src, todo) or todo.name
                text = job.ask_text("builder", "You write short, accurate Python docstrings: what the function does, its inputs, what it returns. "
                                    "1 to 3 sentences of plain text. No quotes, no code, no em dashes.",
                                    f"File {rel}:\n```python\n{clip(fn_src, 2500)}\n```\nDocstring for {todo.name}:", max_tokens=160, temperature=0.2)
                text = clean(re.sub(r'"""|\'\'\'|```.*', "", text)).strip().replace("\\", "\\\\")
                if len(text.split()) < 5:                  # too short: one more try with a plainer request
                    text = job.ask_text("builder", "Describe what a Python function does in one or two plain sentences.",
                                        f"```python\n{clip(fn_src, 2500)}\n```\nIn one or two sentences: what does {todo.name} do, "
                                        "what does it take and what does it give back?", max_tokens=120, temperature=0.5)
                    text = clean(re.sub(r'"""|\'\'\'|```.*', "", text)).strip().replace("\\", "\\\\")
                if len(text.split()) < 5:                  # still nothing useful: a placeholder, and it is reported, not hidden
                    text = f"{todo.name.replace('_', ' ').capitalize()}: see the code below for its inputs and result."
                    placeholders = json.loads(ph_file.read_text()) if ph_file.exists() else []
                    ph_file.write_text(json.dumps(placeholders + [key]))
                lines = src.splitlines()
                indent = " " * body0.col_offset
                lines.insert(body0.lineno - 1 - (len(getattr(body0, "decorator_list", [])) if hasattr(body0, "decorator_list") else 0),
                             f'{indent}"""{text}"""')
                new = "\n".join(lines) + "\n"
                try:
                    ast.parse(new)
                except SyntaxError:
                    skipped.append(f"{rel}:{todo.lineno}:{todo.name}")
                    continue
                path.write_text(new)                       # saved at once: a killed job keeps this function's docstring
                done.append(key)
                done_file.write_text(json.dumps(done))
                wrote += 1
        return Outcome(True, f"wrote {wrote} docstrings this session ({len(done)} in total)" + (f"; skipped {skipped}" if skipped else ""),
                       {"written": wrote, "total": len(done), "skipped": skipped}, sorted({d.split(':')[0] for d in done}), made_by="model")

    def verify(self, job, params, outcome):
        ws, orig = job.workspace, job.state.dir / "original"
        changed, missing = [], []
        for rel in files(orig, {".py"}):
            if self._is_test(Path(rel)):
                continue
            new = (ws / rel).read_text()
            if _strip_docs((orig / rel).read_text()) != _strip_docs(new):
                changed.append(rel)
            missing += [f"{rel}:{n.name}" for n in ast.walk(ast.parse(new)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not ast.get_docstring(n)]
        ph_file = job.state.dir / "placeholders.json"
        placeholders = json.loads(ph_file.read_text()) if ph_file.exists() else []
        checks = [{"id": "behaviour_code_unchanged", "pass": not changed, "detail": changed[:5]},
                  {"id": "every_function_documented", "pass": not missing, "detail": missing[:5]},
                  {"id": "every_docstring_written_by_the_model", "pass": not placeholders,
                   "detail": f"placeholder text (the model gave nothing useful) for: {placeholders[:5]}" if placeholders else ""}]
        return Verdict(not changed and not missing and not placeholders, checks,
                       "AST comparison with the original; placeholders are reported as not done")


CAPABILITIES = [FixBug(), DocumentFunctions()]
