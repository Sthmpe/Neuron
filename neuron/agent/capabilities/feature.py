"""Add or change behaviour in an existing project, in any installed language.

Found by the core proof (2026-11-20): NEURON had no way to do this. A request like "Add discount codes to this invoice
project. Create invoice/discounts.py with apply_code(subtotal, code) ..." was sent to the bug fixer, which saw the
tests already passing and called the job VERIFIED with nothing written.

The loop: plan which files to create or change (the files the request names are always included) -> write each file
-> the project's own tests must still pass -> NEURON writes a test of the requested behaviour, from the examples in the
request, in the project's language -> both must pass. A failure goes back to the model with the output (the reviewer
decides whether the code or the new test is wrong). Guards: a rewritten file may not lose a function it had, every
file and function the request names must exist at the end, and a failing NEURON test is removed rather than left
behind. Success is decided by running code, never by the model's opinion.
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
PLAN_SCHEMA = {"type": "object", "required": ["files"], "properties": {"files": {"type": "array", "maxItems": 5, "items": {
    "type": "object", "required": ["path", "action", "what"],
    "properties": {"path": {"type": "string"}, "action": {"type": "string", "enum": ["create", "change"]}, "what": {"type": "string"}}}}}}
BLAME_SCHEMA = {"type": "object", "required": ["wrong", "file", "why"],
                "properties": {"wrong": {"type": "string", "enum": ["code", "test"]}, "file": {"type": "string"}, "why": {"type": "string"}}}
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

    def _write(self, job, ws, request, plan_text, item, note=""):
        rel = item["path"]
        path = ws / rel
        before = path.read_text(errors="replace") if path.exists() else ""
        keep = defined_names(rel, before)
        ask = (f"Request:\n{request}\n\nThe plan:\n{plan_text}\n\nProject files:\n{self._context(ws)}\n\n"
               + (f"What went wrong last time:\n{clip(note, 1500)}\n\n" if note else "")
               + (f"Write the complete new content of {rel} (a new file): {item['what']}" if not before else
                  f"Write the complete new content of {rel}, keeping everything it already does: {item['what']}"))
        for attempt in range(2):
            reply = job.ask_text("builder", "You change an existing project. Reply with one code block containing the complete "
                                 "content of the file, nothing else.", ask, max_tokens=1800)
            code = extract_code(reply)
            if not code or not code.strip():
                continue
            lost = keep - defined_names(rel, code)
            if lost:                          # a rewrite that drops a function would break the rest of the project
                ask += f"\n\nYour last version dropped {', '.join(sorted(lost))}. Keep every existing function."
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code.rstrip("\n") + "\n")
            return True
        return False

    def _run_feature_test(self, job, ws, cmd):
        """Run NEURON's test on a copy of the project, so build caches and outputs never land in the owner's folder."""
        import shutil
        work = ws.parent / (ws.name + "__feature")
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(ws, work, ignore=shutil.ignore_patterns(".neuron", "__pycache__", ".git", "*.o"))
        r = job.sandbox.run(cmd, work, timeout=180)
        shutil.rmtree(work, ignore_errors=True)
        return r.ok and not r.timed_out, r.output[-2500:]

    def run(self, job, params):
        ws = job.workspace
        cmd = detect_test_command(ws)
        lang = project_language(ws)
        if cmd is None or lang is None:
            return Outcome(False, "no project with a test command found here", evidence={"no_retry": True})
        request = job.state.goal()["request"]
        named_paths, named_funcs = named_in_request(request, ws)
        plan = job.ask_json("planner", "You plan a change to an existing project: which files to create or change.",
                            f"Request:\n{request}\n\nProject files:\n{self._context(ws, 5000)}\n\nList the files to create or change "
                            "(the source files only, not tests) and what each must do.", PLAN_SCHEMA, max_tokens=500) or {"files": []}
        items, seen = [], set()
        for it in plan.get("files", []):
            p = str(it.get("path", "")).strip().lstrip("./")
            if p and ".." not in Path(p).parts and not is_test_file(p) and p not in seen and Path(p).suffix in SOURCE_EXT:
                items.append({"path": p, "action": "change" if (ws / p).exists() else "create", "what": it.get("what", "")})
                seen.add(p)
        for p in named_paths:                 # a file the owner named is always part of the plan
            if p not in seen and not is_test_file(p):
                items.insert(0, {"path": p, "action": "change" if (ws / p).exists() else "create", "what": "as the request says"})
                seen.add(p)
        if not items:
            return Outcome(False, "could not decide which files to change")
        plan_text = "\n".join(f"- {it['action']} {it['path']}: {it['what']}" for it in items)
        job.state.decide("feature", "plan", plan_text)
        written = [it["path"] for it in items if self._write(job, ws, request, plan_text, it, params.get("feedback", ""))]
        test_path, test_cmd = feature_test_plan(ws, lang, written)
        test_ok = proj_ok = False
        out = ""
        for rnd in range(MAX_ROUNDS):
            proj_ok, res = run_project_tests(job)
            if not proj_ok:
                out = "The project's tests fail:\n" + (res.output[-2500:] if res else "")
                blame = job.ask_json("reviewer", "You decide which changed file breaks the project's tests.",
                                     f"Request:\n{request}\n\nChanged files: {', '.join(written)}\n\n{out}\n\nWhich file must be fixed, and why?",
                                     BLAME_SCHEMA, max_tokens=300)
                target = next((it for it in items if blame and it["path"] == blame.get("file")), items[0])
                self._write(job, ws, request, plan_text, target, out + (f"\nReviewer: {blame['why']}" if blame else ""))
                continue
            if test_path is None:
                break
            if not (ws / test_path).exists():
                reply = job.ask_text("builder", "You write a test of new behaviour. Reply with one code block: the complete test file.",
                                     f"Request:\n{request}\n\nProject files:\n{self._context(ws)}\n\nWrite {test_path}: "
                                     f"{TEST_STYLE.get(lang, 'a test file')}. Check only what the request states, with the exact "
                                     "values the request gives (its examples and rules); do not invent other behaviour.", max_tokens=1200)
                code = extract_code(reply)
                if not code:
                    continue
                (ws / test_path).parent.mkdir(parents=True, exist_ok=True)
                (ws / test_path).write_text(code.rstrip("\n") + "\n")
            test_ok, tout = self._run_feature_test(job, ws, test_cmd)
            if test_ok:
                break
            out = f"NEURON's test of the new behaviour ({test_path}) fails:\n{tout}"
            blame = job.ask_json("reviewer", "A new test of requested behaviour fails. Decide whether the code or the test is wrong, "
                                 "judged only by what the request says.",
                                 f"Request:\n{request}\n\nTest file {test_path}:\n{clip((ws / test_path).read_text(errors='replace'), 2500)}\n\n"
                                 f"Changed files: {', '.join(written)}\n\n{out}", BLAME_SCHEMA, max_tokens=300)
            if blame and blame.get("wrong") == "test":
                (ws / test_path).unlink(missing_ok=True)       # written again in the next round, with the reason
                request_note = f"\n(An earlier test was wrong: {blame.get('why', '')})"
                request = request + request_note if request_note not in request else request
                continue
            target = next((it for it in items if blame and it["path"] == blame.get("file")), items[0])
            self._write(job, ws, request, plan_text, target, out + (f"\nReviewer: {blame['why']}" if blame else ""))
        if test_path and not test_ok and (ws / test_path).exists():
            (ws / test_path).unlink()                          # never leave a failing test of our own behind
        missing = [p for p in named_paths if not (ws / p).exists()]
        src_text = "\n".join((ws / f).read_text(errors="replace") for f in files(ws) if Path(f).suffix in SOURCE_EXT and not is_test_file(f))
        absent = [f for f in named_funcs if not re.search(rf"\b{re.escape(f)}\b", src_text)]
        ok = bool(proj_ok and test_ok and not missing and not absent)
        why = ("the project's tests pass and NEURON's test of the new behaviour passes" if ok else
               "; ".join(x for x in [("the project's tests fail" if not proj_ok else ""),
                                     ("NEURON's test of the new behaviour did not pass" if proj_ok and not test_ok else ""),
                                     (f"missing files {missing}" if missing else ""), (f"missing functions {absent}" if absent else "")] if x))
        return Outcome(ok, why, {"plan": items, "written": written, "feature_test": test_path if test_ok else None,
                                 "feature_test_cmd": test_cmd, "named_files": named_paths, "named_functions": named_funcs,
                                 "feedback": out[-1500:]}, written, made_by="model")

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
        return Verdict(all(c["pass"] for c in checks), checks, "project tests + NEURON's test of the requested behaviour, run in the sandbox")


CAPABILITIES = [AddFeature]
