"""Add or change behaviour in an existing project, in any installed language.

Found by the core proof (2026-11-20): NEURON had no way to do this. A request like "Add discount codes to this invoice
project. Create invoice/discounts.py with apply_code(subtotal, code) ..." was sent to the bug fixer, which saw the
tests already passing and called the job VERIFIED with nothing written.

The loop, lean because a 4B model on a CPU takes a minute or more per long reply: one call writes every file to create
or change -> the project's own tests must still pass (else one call per round with the output) -> one call writes
NEURON's test of the requested behaviour, from the examples in the request, in the project's language -> if it fails,
one combined call decides from the request whether the code or the test is wrong and sends the corrected file(s).
Guards: test files of the project are never edited, a rewritten file may not lose a function it had, a correction that
breaks the project's tests is undone, every file and function the request names must exist at the end, and a failing
NEURON test is removed rather than left behind. Success is decided by running code, never by the model's opinion.
"""
import re
from pathlib import Path

from ...builder.build import extract_code
from ..capability import Capability, Outcome, Verdict
from ..context import clip, files
from .code import functions_in
from .workspace import LANG, detect_test_command, run_project_tests

SOURCE_EXT = {".py", ".js", ".mjs", ".ts", ".go", ".cpp", ".cc", ".c", ".h", ".hpp", ".rs", ".java"}
NAMED_PATH = re.compile(r"(?<![\w/.-])((?:[\w-]+/)*[\w-]+\.(?:py|js|mjs|ts|go|cpp|cc|c|h|hpp|rs|java))\b")
NAMED_FUNC = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
NOT_NAMES = {"if", "for", "while", "print", "return", "and", "or", "not", "with", "e", "g", "i", "ie", "eg"}
MAX_ROUNDS = 3


def is_test_file(rel):
    name = Path(rel).name
    return bool(re.search(r"(^|/)(tests?|spec)/", rel) or re.match(r"test_", name) or re.search(r"[._-](test|spec)\.[a-z]+$", name)
                or name.endswith("_test.go"))


def project_language(ws):
    counts = {}
    for rel in files(ws):
        lang = LANG.get(Path(rel).suffix)
        if lang and not is_test_file(rel):
            counts[lang] = counts.get(lang, 0) + 1
    return max(counts, key=counts.get) if counts else None


def defined_names(rel, text):
    """Function (and class/struct) names a file defines; used to stop a rewrite from silently dropping one."""
    if rel.endswith(".py"):
        return set(re.findall(r"^\s*(?:def|class)\s+([A-Za-z_]\w*)", text, re.M))
    if rel.endswith((".js", ".mjs", ".ts")):
        return set(re.findall(r"\bfunction\s+([A-Za-z_]\w*)", text)) | set(re.findall(r"\b(?:const|let)\s+([A-Za-z_]\w*)\s*=\s*(?:\([^)]*\)|\w+)\s*=>", text))
    names = {n.split("::")[-1] for n, _, _ in functions_in(rel, text)}
    return names | set(re.findall(r"\b(?:struct|class|type)\s+([A-Za-z_]\w*)", text))


def named_in_request(request, ws):
    paths = list(dict.fromkeys(NAMED_PATH.findall(request)))
    funcs = [f for f in dict.fromkeys(NAMED_FUNC.findall(request)) if f.lower() not in NOT_NAMES and len(f) > 1]
    return paths, funcs


def feature_test_plan(ws, lang, touched):
    """(path of NEURON's own test file, command that runs it) for the project's language."""
    ws = Path(ws)
    existing = [f for f in files(ws) if is_test_file(f)]
    if lang == "python":
        tdir = next((str(Path(f).parent) for f in existing if Path(f).name.startswith("test")), ".")
        path = str(Path(tdir) / "test_neuron_feature.py") if tdir != "." else "test_neuron_feature.py"
        return path, ["python3", "-m", "unittest", "-v", path[:-3].replace("/", ".")]
    if lang == "go":
        pkg = next((str(Path(t).parent) for t in touched if t.endswith(".go") and not t.endswith("_test.go")), None) \
            or next((str(Path(f).parent) for f in files(ws) if f.endswith(".go") and not f.endswith("_test.go")), ".")
        return str(Path(pkg) / "neuron_feature_test.go"), ["go", "test", "./" + pkg if pkg != "." else "."]
    if lang in ("javascript", "typescript"):
        tdir = next((str(Path(f).parent) for f in existing), "test")
        path = str(Path(tdir) / "neuron_feature.check.js")
        return path, ["node", path]
    if lang in ("c++", "c"):
        tdir = next((str(Path(f).parent) for f in existing), "tests")
        path = str(Path(tdir) / "neuron_feature_test.cpp")
        srcs = [f for f in files(ws) if Path(f).suffix in (".cpp", ".cc") and not is_test_file(f)
                and not re.search(r"\bint\s+main\s*\(", (ws / f).read_text(errors="replace"))]
        incs = sorted({str(Path(f).parent) for f in files(ws) if Path(f).suffix in (".h", ".hpp")})
        cmd = "g++ -std=c++17 " + " ".join(f"-I{d}" for d in incs) + f" {path} " + " ".join(srcs) + " -o /tmp/neuron_feature && /tmp/neuron_feature"
        return path, ["bash", "-c", cmd]
    return None, None


TEST_STYLE = {
    "python": "a unittest file (import unittest, a TestCase class, unittest.main() at the end)",
    "go": "a Go test file in the same package (package clause like the package's other files, import \"testing\", func TestX(t *testing.T))",
    "javascript": "a plain Node script that requires the project's modules with relative paths, checks with require('assert'), "
                  "and prints ok at the end (a failed check must throw)",
    "typescript": "a plain Node script that requires the project's modules, checks with require('assert') and prints ok",
    "c++": "a C++17 program with its own main() that includes the project's headers, checks with if/return 1 (print what failed), "
           "and returns 0 when every check passes",
    "c": "a C program with its own main() that includes the project's headers and returns 0 only when every check passes",
}


class AddFeature(Capability):
    name = "add_feature"
    purpose = "Add or change behaviour in an existing project (any installed language): write the new code, keep its tests passing, test the new behaviour"
    permissions = ("read_workspace", "write_workspace", "run_code", "use_model")
    resources = {"ram_mb": 300, "uses_model": True}
    verification = "the project's own tests pass, NEURON's test of the requested behaviour passes, and the named files and functions exist"
    domains = ("code",)
    strategies = ("write the files again with what failed",)

    def _context(self, ws, limit=7000):
        parts, used = [], 0
        for rel in files(ws):
            if Path(rel).suffix in SOURCE_EXT | {".json", ".mod"} or Path(rel).name == "Makefile":
                text = (ws / rel).read_text(errors="replace")
                if used + len(text) > limit:
                    parts.append(f"--- {rel} --- (not shown)")
                    continue
                parts.append(f"--- {rel} ---\n{text}")
                used += len(text)
        return "\n".join(parts)

    def _run_feature_test(self, job, ws, cmd):
        """Run NEURON's test on a copy of the project, so build caches and outputs never land in the owner's folder."""
        import shutil
        work = ws.parent / (ws.name + "__feature")
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(ws, work, ignore=shutil.ignore_patterns(".neuron", "__pycache__", ".git", "*.o"))
        r = job.sandbox.run(cmd, work, timeout=180)
        shutil.rmtree(work, ignore_errors=True)
        return r.ok and not r.timed_out, r.output[-2500:]

    def _files_from(self, reply, ws, allow_tests=()):
        """FILE: <path> + code block pairs from a reply, kept only for safe paths (inside the project, source files, not
        tests unless allowed), and never a rewrite that drops a function the file had. Returns ({path: code}, notes)."""
        out, notes = {}, []
        for path, code in re.findall(r"FILE:\s*[`'\"]?([\w./-]+)[`'\"]?\s*\n+```[^\n]*\n(.*?)```", reply, re.S):
            path = path.strip().lstrip("./")
            if ".." in Path(path).parts or Path(path).suffix not in SOURCE_EXT or not code.strip():
                continue
            if is_test_file(path) and path not in allow_tests:
                notes.append(f"{path} is a test of the project and was not changed")
                continue
            before = (ws / path).read_text(errors="replace") if (ws / path).exists() else ""
            lost = defined_names(path, before) - defined_names(path, code)
            if lost:
                notes.append(f"{path} was not changed: the new version dropped {', '.join(sorted(lost))}")
                continue
            out[path] = code.rstrip("\n") + "\n"
        return out, notes

    def run(self, job, params):
        """Lean on purpose (a 4B model on a CPU takes a minute or more per long reply): one call writes every file, one
        writes NEURON's test, one combined call per repair round."""
        ws = job.workspace
        cmd = detect_test_command(ws)
        lang = project_language(ws)
        if cmd is None or lang is None:
            return Outcome(False, "no project with a test command found here", evidence={"no_retry": True})
        request = job.state.goal()["request"]
        named_paths, named_funcs = named_in_request(request, ws)
        system = ("You change an existing project to do what is asked. Reply with the complete content of every source file "
                  "you create or change (not the tests), each as a line 'FILE: <path>' followed by one code block. Keep "
                  "everything the existing files already do.")
        ask = (f"Request:\n{request}\n\nProject files:\n{self._context(ws)}\n\n"
               + (f"Files the request names: {', '.join(named_paths)}\n" if named_paths else "")
               + (f"What went wrong last time:\n{clip(params['feedback'], 1200)}\n" if params.get("feedback") else ""))
        written, notes, out = [], [], ""
        proj_ok = False
        for rnd in range(MAX_ROUNDS):
            reply = job.ask_text("builder", system, ask + ("" if not out else f"\n{out}\nSend the corrected files."), max_tokens=2000)
            files_, notes = self._files_from(reply, ws)
            if not files_:
                out = "The last reply had no usable 'FILE: <path>' block. " + " ".join(notes)
                continue
            for path, code in files_.items():
                (ws / path).parent.mkdir(parents=True, exist_ok=True)
                (ws / path).write_text(code)
                if path not in written:
                    written.append(path)
            proj_ok, res = run_project_tests(job)
            if proj_ok:
                break
            out = "The project's tests now fail:\n" + (res.output[-2000:] if res else "")
        job.state.decide("feature", "files", ", ".join(written) or "none")
        test_path, test_cmd = feature_test_plan(ws, lang, written)
        test_ok = False
        if proj_ok and test_path:
            reply = job.ask_text("builder", "You write a test of new behaviour. Reply with one code block: the complete test file.",
                                 f"Request:\n{request}\n\nProject files:\n{self._context(ws)}\n\nWrite {test_path}: "
                                 f"{TEST_STYLE.get(lang, 'a test file')}. Check only what the request states, with the exact "
                                 "values the request gives (its examples and rules); do not invent other behaviour.", max_tokens=1200)
            code = extract_code(reply)
            if code:
                (ws / test_path).parent.mkdir(parents=True, exist_ok=True)
                (ws / test_path).write_text(code.rstrip("\n") + "\n")
                for rnd in range(2):
                    test_ok, tout = self._run_feature_test(job, ws, test_cmd)
                    if test_ok:
                        break
                    # one combined call: the code or NEURON's own test may be wrong; judged only by the request
                    reply = job.ask_text("reviewer", "A new test of requested behaviour fails. Decide, from the request alone, "
                                         "whether the code or the test is wrong, and reply with the complete corrected file(s), "
                                         "each as 'FILE: <path>' followed by one code block.",
                                         f"Request:\n{request}\n\nProject files:\n{self._context(ws)}\n\nTest output:\n{tout[-1800:]}",
                                         max_tokens=2000)
                    fixed, more = self._files_from(reply, ws, allow_tests=(test_path,))
                    notes += more
                    backup = {p: (ws / p).read_text(errors="replace") if (ws / p).exists() else None for p in fixed}
                    for path, code in fixed.items():
                        (ws / path).write_text(code)
                    if fixed and not run_project_tests(job)[0]:       # a fix that breaks the project's tests is undone
                        for path, text in backup.items():
                            (ws / path).write_text(text) if text is not None else (ws / path).unlink(missing_ok=True)
                        notes.append("a correction broke the project's tests and was undone")
                    for path in fixed:
                        if path not in written and path != test_path:
                            written.append(path)
                if not test_ok:
                    test_ok, _ = self._run_feature_test(job, ws, test_cmd)
            if not test_ok and (ws / test_path).exists():
                (ws / test_path).unlink()                      # never leave a failing test of our own behind
        missing = [p for p in named_paths if not (ws / p).exists()]
        src_text = "\n".join((ws / f).read_text(errors="replace") for f in files(ws) if Path(f).suffix in SOURCE_EXT and not is_test_file(f))
        absent = [f for f in named_funcs if not re.search(rf"\b{re.escape(f)}\b", src_text)]
        ok = bool(proj_ok and test_ok and not missing and not absent)
        why = ("the project's tests pass and NEURON's test of the new behaviour passes" if ok else
               "; ".join(x for x in [("the project's tests fail" if not proj_ok else ""),
                                     ("NEURON's test of the new behaviour did not pass" if proj_ok and not test_ok else ""),
                                     (f"missing files {missing}" if missing else ""), (f"missing functions {absent}" if absent else "")] if x))
        return Outcome(ok, why, {"written": written, "feature_test": test_path if test_ok else None, "feature_test_cmd": test_cmd,
                                 "named_files": named_paths, "named_functions": named_funcs, "notes": notes[-6:], "feedback": out[-1500:]},
                       written, made_by="model")

    def verify(self, job, params, outcome):
        ws = job.workspace
        proj_ok, res = run_project_tests(job)
        checks = [{"id": "project_tests_pass", "pass": bool(proj_ok), "detail": (res.output if res else "")[-400:]}]
        t, cmd = outcome.result.get("feature_test"), outcome.result.get("feature_test_cmd")
        if t and cmd and (ws / t).exists():
            ok, out = self._run_feature_test(job, ws, cmd)
            checks.append({"id": "new_behaviour_test_passes", "pass": ok, "detail": out[-400:]})
        else:
            checks.append({"id": "new_behaviour_test_passes", "pass": False, "detail": "no passing test of the new behaviour"})
        for p in outcome.result.get("named_files", []):
            checks.append({"id": f"file {p} exists", "pass": (ws / p).exists()})
        # The project's tests prove nothing broke, but the only check of the NEW behaviour is a test the same model wrote,
        # which can share the code's mistake (after-fixes rerun try 1, C2 on 2 GB: both agreed on a wrong export, the
        # hidden tests failed, and the job said VERIFIED). So a finished feature is reported as done but unverified.
        return Verdict(all(c["pass"] for c in checks), checks,
                       "project tests (nothing broke) + NEURON's own test of the new behaviour (written by the same model, "
                       "so not independent)", unverified=True)


CAPABILITIES = [AddFeature]
