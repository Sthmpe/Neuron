"""Independent checkers for code deliverables. Generated code is untrusted: it is built and run only inside
NEURON's sandbox (no network, workspace-only files, time and memory limits)."""
import ast
import os
import random
import re
import shutil
import tempfile
from pathlib import Path

from neuron.brain.sandbox import Sandbox
from neuron.brain.tools.fix_code import default_test_command, tests_passed

SBX = Sandbox(timeout=120, mem_mb=1024, toolchains=True)


def _result(checks):
    return {"checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks)}


def _copy(project):
    work = Path(tempfile.mkdtemp(prefix="exam-")) / "p"
    shutil.copytree(project, work, ignore=shutil.ignore_patterns(".neuron", "__pycache__", ".git"))
    return work


# ---- the budget CLI (L05) -------------------------------------------------------------------------
def budget_reference(tx_lines, budget_lines=None):
    totals = {}
    for line in tx_lines[1:]:
        if not line.strip():
            continue
        _, cat, amt = line.split(",")
        totals[cat] = totals.get(cat, 0) + round(float(amt) * 100)
    out = [f"{c}: {totals[c] / 100:.2f}" for c in sorted(totals)]
    out.append(f"TOTAL: {sum(totals.values()) / 100:.2f}")
    if budget_lines is not None:
        limits = {l.split(",")[0]: round(float(l.split(",")[1]) * 100) for l in budget_lines[1:] if l.strip()}
        for c in sorted(totals):
            if c in limits and totals[c] > limits[c]:
                out.append(f"OVER: {c} by {(totals[c] - limits[c]) / 100:.2f}")
    return "\n".join(out)


def _budget_cases(seed=5):
    rnd = random.Random(seed)
    cases = []
    for n in range(4):
        cats = rnd.sample(["food", "rent", "transport", "school", "data", "health"], 4)
        tx = ["date,category,amount"] + [f"2026-0{1 + i % 9}-1{i % 9},{rnd.choice(cats)},{rnd.randint(1, 900)}.{rnd.randint(0, 99):02d}"
                                          for i in range(12 + n * 5)]
        bud = ["category,limit"] + [f"{c},{rnd.randint(300, 1500)}" for c in cats[:3]] if n % 2 else None
        cases.append((tx, bud))
    cases.append((["date,category,amount", "2026-01-01,a,0.10", "2026-01-02,a,0.20"], ["category,limit", "a,0.25"]))   # float trap
    return cases


def budget_cli(project, binary="budget"):
    work = _copy(project)
    checks = []
    build = SBX.run(["make"], work)
    exe = work / binary
    checks.append({"id": "builds_with_make", "pass": build.ok and exe.exists(), "detail": build.output[-400:]})
    if not exe.exists():
        return _result(checks)
    for i, (tx, bud) in enumerate(_budget_cases()):
        (work / f"tx{i}.csv").write_text("\n".join(tx) + "\n")
        argv = [f"./{binary}", f"tx{i}.csv"]
        if bud:
            (work / f"bud{i}.csv").write_text("\n".join(bud) + "\n")
            argv.append(f"bud{i}.csv")
        r = SBX.run(argv, work, timeout=20)
        want = budget_reference(tx, bud)
        checks.append({"id": f"case{i + 1}_output_correct", "pass": r.exit_code == 0 and r.output.strip() == want,
                       "detail": f"got {r.output.strip()[:160]!r} want {want[:160]!r}"})
    r = SBX.run([f"./{binary}", "missing.csv"], work, timeout=20)
    checks.append({"id": "missing_file_error", "pass": r.exit_code == 1 and "error: cannot open missing.csv" in r.output,
                   "detail": r.output[-160:]})
    return _result(checks)


# ---- workspace bugs (L06-L10): the ORIGINAL tests, re-run independently -----------------------------
def workspace_bug(project, original, lang):
    work = _copy(project)
    tests_dir = {"cpp": "tests", "go": None}[lang]
    if tests_dir:
        shutil.rmtree(work / tests_dir, ignore_errors=True)
        shutil.copytree(Path(original) / tests_dir, work / tests_dir)
    else:
        for t in Path(original).rglob("*_test.go"):
            shutil.copy(t, work / t.relative_to(original))
    cmd = ["make", "-s", "test"] if lang == "cpp" else ["go", "test", "./..."]
    r = SBX.run(cmd, work, timeout=300)
    return _result([{"id": "original_tests_pass", "pass": r.ok, "detail": r.output[-300:]}])


# ---- long task: docstrings everywhere, behaviour unchanged (L12) -------------------------------------
def _strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def docstrings(project, original):
    project, original = Path(project), Path(original)
    is_test = lambda rel: rel.parts[0] == "tests" or rel.name.startswith("test_")
    checks, missing, short, changed = [], [], [], []
    for src in sorted(original.rglob("*.py")):
        rel = src.relative_to(original)
        if is_test(rel):
            continue
        new = project / rel
        if not new.exists():
            changed.append(f"{rel} (missing)")
            continue
        had_doc = {f"{rel}:{n.name}" for n in ast.walk(ast.parse(src.read_text()))
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(n)}   # left alone, as asked
        try:
            t_new = ast.parse(new.read_text())
        except SyntaxError as e:
            changed.append(f"{rel} (syntax error {e.lineno})")
            continue
        if _strip_docstrings(ast.parse(src.read_text())) != _strip_docstrings(ast.parse(new.read_text())):
            changed.append(str(rel))
        for node in ast.walk(t_new):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                if not doc:
                    missing.append(f"{rel}:{node.name}")
                elif len(doc.split()) < 5 and f"{rel}:{node.name}" not in had_doc:
                    short.append(f"{rel}:{node.name}")          # only docstrings NEURON added (amendment 2)
    total = sum(1 for src in original.rglob("*.py") if not is_test(src.relative_to(original))
                for n in ast.walk(ast.parse(src.read_text())) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    checks.append({"id": "every_function_documented", "pass": not missing, "detail": f"{total - len(missing)} of {total}; missing {missing[:6]}"})
    checks.append({"id": "docstrings_say_something", "pass": not short, "detail": short[:6]})
    checks.append({"id": "code_unchanged_apart_from_docstrings", "pass": not changed, "detail": changed[:6]})
    work = _copy(project)
    shutil.rmtree(work / "tests", ignore_errors=True)
    shutil.copytree(original / "tests", work / "tests")
    r = SBX.run(default_test_command(work), work)
    checks.append({"id": "all_original_tests_pass", "pass": tests_passed(r, True), "detail": r.output[-200:]})
    return _result(checks)


# ---- dev: wc2 (D05) --------------------------------------------------------------------------------
def wc2_reference(text):
    words = text.split()
    longest = ""
    for w in words:
        if len(w) > len(longest):
            longest = w
    return f"lines: {len(text.splitlines())}\nwords: {len(words)}\nlongest: {longest}"


def wc2_cli(project):
    work = _copy(project)
    build = SBX.run(["make"], work)
    checks = [{"id": "builds_with_make", "pass": build.ok and (work / "wc2").exists(), "detail": build.output[-300:]}]
    if not (work / "wc2").exists():
        return _result(checks)
    for i, txt in enumerate(["the cat sat\non the mat\n", "one\n\ntwo three four\nalphabetical zebra\n", "a bb ccc dd e\n"]):
        (work / f"in{i}.txt").write_text(txt)
        r = SBX.run(["./wc2", f"in{i}.txt"], work, timeout=20)
        checks.append({"id": f"case{i + 1}", "pass": r.output.strip() == wc2_reference(txt), "detail": r.output[-120:]})
    return _result(checks)


def has_passing_tests(project, min_tests=2):
    """The project's OWN tests: they must exist, be more than a token, and pass."""
    import re as _re
    if not Path(project).exists():                         # nothing delivered: fail, do not crash (amendment 3)
        return _result([{"id": "own_tests_exist", "pass": False, "detail": "no project folder was delivered"},
                        {"id": "own_tests_pass", "pass": False, "detail": "no project folder was delivered"}])
    work = _copy(project)
    files = [f for f in work.rglob("test*.py") if "kit" not in f.parts]
    count = sum(len(_re.findall(r"^\s*def test_", f.read_text(), _re.M)) for f in files)
    r = SBX.run(default_test_command(work), work)
    return _result([{"id": "own_tests_exist", "pass": count >= min_tests, "detail": f"{count} tests in {len(files)} files"},
                    {"id": "own_tests_pass", "pass": count >= min_tests and tests_passed(r, True), "detail": r.output[-200:]}])


# ---- eval2 ---------------------------------------------------------------------------------------------
TEST_PLACES = {"python": ["tests"], "javascript": ["test"], "rust": ["tests"], "cpp": ["tests"], "go": []}
TEST_COMMANDS = {"python": ["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."], "javascript": ["node", "--test"],
                 "go": ["go", "test", "./..."], "rust": ["cargo", "test", "--offline", "-q"], "cpp": ["make", "-s", "test"]}


def workspace_bug_any(project, original, lang):
    """Put the ORIGINAL tests back (whatever the agent did to them), then run the project's own test command."""
    if not Path(project).exists():
        return _result([{"id": "original_tests_pass", "pass": False, "detail": "no project delivered"}])
    work = _copy(project)
    for d in TEST_PLACES[lang]:
        shutil.rmtree(work / d, ignore_errors=True)
        shutil.copytree(Path(original) / d, work / d)
    if lang == "go":
        for t in Path(original).rglob("*_test.go"):
            shutil.copy(t, work / t.relative_to(original))
    r = SBX.run(TEST_COMMANDS[lang], work, timeout=600)
    return _result([{"id": "original_tests_pass", "pass": r.ok, "detail": r.output[-300:]}])


def csvsum_reference(text):
    lines = [l for l in text.strip().splitlines() if l.strip()]
    header = [h.strip() for h in lines[0].split(",")]
    cols = list(zip(*[[c.strip() for c in l.split(",")] for l in lines[1:]]))
    out = []
    for name, values in zip(header, cols):
        try:
            total = sum(float(v) for v in values)
        except ValueError:
            continue
        out.append(f"{name}: {total:.2f}")
    return "\n".join(out)


CSVSUM_CASES = [
    "item,qty,price\nrice,2,1250.5\nbeans,3,800\n",
    "name,score,age,city\nAda,71.5,30,Lagos\nBola,64,41,Ibadan\nChidi,88.25,27,Enugu\n",
    "a,b\n1,x\n2,3\n",
    "x\n-1.5\n2.25\n0\n",
]


def csvsum(project):
    work = _copy(project) if Path(project).exists() else None
    if work is None:
        return _result([{"id": "builds_with_make", "pass": False, "detail": "no project"}])
    for f in work.glob("csvsum"):
        f.unlink()
    b = SBX.run(["make"], work, timeout=300)
    checks = [{"id": "builds_with_make", "pass": b.ok and (work / "csvsum").exists(), "detail": b.output[-200:]}]
    if not checks[0]["pass"]:
        return _result(checks)
    for i, text in enumerate(CSVSUM_CASES, 1):
        (work / f"case{i}.csv").write_text(text)
        r = SBX.run(["./csvsum", f"case{i}.csv"], work, timeout=20)
        want = csvsum_reference(text)
        checks.append({"id": f"case{i}", "pass": r.output.strip() == want, "detail": f"got {r.output.strip()[:120]!r} want {want!r}"})
    return _result(checks)


def number_answer(project, expect):
    f = Path(project) / "answer.md"
    text = f.read_text() if f.exists() else ""
    flat = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", flat)]
    return _result([{"id": "answer_given", "pass": bool(text.strip()), "detail": text[:120]},
                    {"id": "number_correct", "pass": any(abs(n - expect) < 0.5 for n in nums), "detail": f"want {expect}; found {nums[:8]}"}])
