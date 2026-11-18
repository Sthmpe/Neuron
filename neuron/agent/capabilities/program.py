"""Writing a new program from a description, in an installed compiled or scripting language.
The model plans the files and writes them; the compiler and example runs in the sandbox judge them."""
import json
import re
import shutil
from pathlib import Path

from ...builder.build import extract_code
from ..capability import Capability, Outcome, Verdict
from ..context import clip

LANGS = {"c++": {"ext": ".cpp", "tool": "g++"}, "go": {"ext": ".go", "tool": "go"}, "rust": {"ext": ".rs", "tool": "cargo"},
         "python": {"ext": ".py", "tool": "python3"}, "java": {"ext": ".java", "tool": "javac"}}


def language_of(req):
    r = req.lower()
    for k, pat in (("c++", r"c\+\+|\bcpp\b"), ("rust", r"\brust\b"), ("go", r"\bgo\b|golang"), ("java", r"\bjava\b"), ("python", r"\bpython\b")):
        if re.search(pat, r):
            return k
    return "python"


def binary_of(req):
    m = re.search(r"(?:program|tool|binary|command)(?: called| named)? [`'\"]?([a-z][\w-]*)", req, re.I)
    return m.group(1) if m else "app"


def program_args(args, binary):
    """Example arguments without the program's own name (planners often write ['wc2', 'file.txt'])."""
    args = [str(a) for a in args]
    while args and args[0].lstrip("./") in (binary, binary + ".exe"):
        args = args[1:]
    return args


class PlanProgram(Capability):
    name = "plan_program"
    purpose = "Plan a new program: language, files and what each file must do, plus example runs to test it"
    permissions = ("use_model",)
    resources = {"ram_mb": 60, "uses_model": True}
    verification = "the plan names at least one source file and one example run"
    domains = ("code",)

    def run(self, job, params):
        req = job.state.goal()["request"]
        lang, binary = language_of(req), binary_of(req)
        ext = LANGS[lang]["ext"]
        data = job.ask_json("planner", "You plan small, correct programs. Keep it to as few files as possible.",
                            f"Request:\n{req}\n\nLanguage: {lang}. Plan the source files (paths like src/main{ext}) with one sentence each, "
                            "and 3 example runs that follow the request exactly: the command-line arguments (without the program's own name), the input files to create "
                            "(name and full content) and the exact output expected on standard output.",
                            {"type": "object", "required": ["files", "examples"],
                             "properties": {"files": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                                 "type": "object", "required": ["path", "purpose"], "properties": {"path": {"type": "string"}, "purpose": {"type": "string"}}}},
                                 "examples": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                                     "type": "object", "required": ["args", "files", "stdout"],
                                     "properties": {"args": {"type": "array", "items": {"type": "string"}},
                                                    "files": {"type": "array", "items": {"type": "object", "required": ["name", "content"],
                                                                                         "properties": {"name": {"type": "string"}, "content": {"type": "string"}}}},
                                                    "stdout": {"type": "string"}}}}}}, max_tokens=1400)
        if not data:
            return Outcome(False, "the model gave no plan")
        files = [f for f in data["files"] if f["path"].endswith(ext) and ".." not in f["path"]] or [{"path": f"src/main{ext}", "purpose": "the whole program"}]
        plan = {"language": lang, "binary": binary, "files": files, "examples": data["examples"]}
        return Outcome(True, f"{lang} program '{binary}': {', '.join(f['path'] for f in files)}; {len(data['examples'])} examples", plan, made_by="model")

    def verify(self, job, params, outcome):
        ok = bool(outcome.result["files"])
        return Verdict(ok, [{"id": "has_files", "pass": ok, "detail": outcome.summary}], "plan check")


def makefile(plan):
    b = plan["binary"]
    if plan["language"] == "c++":
        return f"CXX ?= g++\nCXXFLAGS ?= -std=c++17 -O2 -Wall\n\n{b}: $(wildcard src/*.cpp) $(wildcard src/*.h)\n\t$(CXX) $(CXXFLAGS) -o {b} $(wildcard src/*.cpp)\n\nclean:\n\trm -f {b}\n"
    if plan["language"] == "go":
        return f"{b}:\n\tgo build -o {b} ./...\n"
    return f"{b}:\n\t@true\n"


class WriteProgram(Capability):
    name = "write_program"
    purpose = "Write each planned file, build it, and run the example runs; repair from compiler errors and wrong output"
    permissions = ("write_workspace", "run_code", "use_model")
    resources = {"ram_mb": 400, "uses_model": True}
    verification = "it builds in the sandbox and the example runs give the expected output"
    domains = ("code",)
    strategies = ("rewrite the program from scratch using the failures",)

    def run(self, job, params):
        ws = job.workspace
        plan = job.state.task("design")["result"]
        req = job.state.goal()["request"]
        if plan["language"] in ("c++", "go") and not (ws / "Makefile").exists():
            (ws / "Makefile").write_text(makefile(plan))
        if plan["language"] == "go" and not (ws / "go.mod").exists():
            (ws / "go.mod").write_text(f"module example.com/{plan['binary']}\n\ngo 1.21\n")
        feedback = params.get("feedback", "")
        report = {}
        for rnd in range(3):                       # write -> build -> examples, repairing from what failed
            for f in plan["files"]:
                if rnd > 0 and f["path"] not in report.get("blame", [f["path"]]):
                    continue
                current = (ws / f["path"]).read_text() if (ws / f["path"]).exists() else ""
                others = "\n".join(f"// {o['path']}: {o['purpose']}" for o in plan["files"] if o is not f)
                prompt = (f"Request:\n{req}\n\nWrite the complete file {f['path']} ({f['purpose']}).\n{others}\n"
                          + (f"\nThe current version failed:\n{clip(feedback, 1800)}\n\nCurrent file:\n```\n{clip(current, 4000)}\n```\nWrite the corrected complete file." if feedback else ""))
                code = extract_code(job.ask_text("builder", f"You write correct, complete {plan['language']} code. Reply with one code block with the whole file.",
                                                 prompt, max_tokens=2200, temperature=0.2 if rnd == 0 else 0.4))
                if code:
                    (ws / f["path"]).parent.mkdir(parents=True, exist_ok=True)
                    (ws / f["path"]).write_text(code)
            report = self._build_and_try(job, plan)
            if report["built"] and report["examples_passed"] + report.get("examples_agreed", 0) == len(plan["examples"]):
                break
            feedback = report["feedback"]
        ok = report["built"]
        return Outcome(ok, f"built: {report['built']}; examples matched as written {report['examples_passed']} of {len(plan['examples'])}"
                       + (f"; {report['examples_agreed']} settled by an independent Python version" if report.get("examples_agreed") else ""), report,
                       [f["path"] for f in plan["files"]] + ["Makefile"], made_by="model")

    def _build_and_try(self, job, plan):
        ws = job.workspace
        work = ws.parent / (ws.name + "__build")
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(ws, work, ignore=shutil.ignore_patterns(".neuron"))
        b = job.sandbox.run(["make"], work, timeout=300) if (work / "Makefile").exists() else None
        exe = work / plan["binary"]
        built = (b is None or b.ok) and (exe.exists() or plan["language"] == "python")
        if not built:
            out = b.output if b else ""
            blame = [f["path"] for f in plan["files"] if Path(f["path"]).name in out] or [f["path"] for f in plan["files"]]
            shutil.rmtree(work, ignore_errors=True)
            return {"built": False, "examples_passed": 0, "feedback": "Compiler errors:\n" + clip(out, 2000), "blame": blame}
        passed, fails, outs = 0, [], {}
        for i, ex in enumerate(plan["examples"]):
            for fl in ex.get("files", []):
                (work / Path(fl["name"]).name).write_text(fl["content"])
            args = program_args(ex["args"], plan["binary"])
            argv = ([f"./{plan['binary']}"] if plan["language"] != "python" else ["python3", plan["files"][0]["path"]]) + args
            r = job.sandbox.run(argv, work, timeout=20)
            outs[i] = r.output.strip()
            if outs[i] == ex["stdout"].strip():
                passed += 1
            else:
                fails.append(i)
        agreed, notes, wrong = [], [], []
        if fails:
            ref = self._reference(job, plan)
            for i in fails:
                ex = plan["examples"][i]
                got_ref = None
                if ref:
                    (work / "_reference.py").write_text(ref)
                    rr = job.sandbox.run(["python3", "_reference.py"] + program_args(ex["args"], plan["binary"]), work, timeout=20)
                    got_ref = rr.output.strip() if rr.ok else None
                if got_ref is not None and got_ref == outs[i]:
                    agreed.append(i)
                    notes.append(f"example {i + 1}: the planner expected {ex['stdout'].strip()!r} but the program and an independent "
                                 f"Python version both give {outs[i]!r}; the hand-written expectation is taken as wrong")
                else:
                    wrong.append(f"Example {i + 1}: args {program_args(ex['args'], plan['binary'])}\nexpected:\n{ex['stdout'].strip()}\n"
                                 f"got:\n{outs[i][:600]}" + (f"\nan independent Python version of the same request gives:\n{got_ref[:600]}" if got_ref else ""))
        shutil.rmtree(work, ignore_errors=True)
        return {"built": True, "examples_passed": passed, "examples_agreed": len(agreed), "notes": notes,
                "feedback": "Wrong output:\n" + "\n\n".join(wrong), "blame": [f["path"] for f in plan["files"]]}

    def _reference(self, job, plan):
        """An independent Python version of the same request, written once and kept in the job folder. When the
        program and the planner's example disagree, this settles which one is wrong (models miscount by hand)."""
        f = job.state.dir / "reference.py"
        if f.exists():
            return f.read_text()
        req = job.state.goal()["request"]
        code = extract_code(job.ask_text("builder", "You write correct, complete Python 3 programs using only the standard library. "
                                         "Reply with one code block.",
                                         f"Request:\n{req}\n\nWrite it as one Python 3 program. Read the command-line arguments from "
                                         f"sys.argv[1:] (as if the program were called '{plan['binary']}') and print exactly what the request says.",
                                         max_tokens=1600, temperature=0.1))
        if code:
            f.write_text(code)
        return code

    def verify(self, job, params, outcome):
        r, plan = outcome.result, job.state.task("design")["result"]
        good = r["examples_passed"] + r.get("examples_agreed", 0)
        checks = [{"id": "builds", "pass": r["built"], "detail": ""},
                  {"id": "example_runs_match", "pass": good == len(plan["examples"]),
                   "detail": f"{r['examples_passed']} of {len(plan['examples'])} as written by the planner"
                             + (f", {r['examples_agreed']} more where the program and an independent Python version agree and the planner's "
                                "expectation was wrong" if r.get("examples_agreed") else "") + "; " + clip(r.get("feedback", ""), 400)}]
        return Verdict(all(c["pass"] for c in checks), checks, "sandbox build + example runs; disputed examples settled by an independent Python version")


CAPABILITIES = [PlanProgram(), WriteProgram()]
