"""Looking at a project and running its tests. Deterministic: no model involved."""
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from ...brain.tools.fix_code import default_test_command, tests_passed
from ..capability import Capability, Outcome, Verdict
from ..context import CODE_EXT, files

LANG = {".py": "python", ".cpp": "c++", ".cc": "c++", ".h": "c++", ".hpp": "c++", ".c": "c", ".go": "go", ".rs": "rust",
        ".java": "java", ".js": "javascript", ".ts": "typescript", ".dart": "dart"}


def detect_test_command(ws):
    """The project's own test command, from its build files. None if there is no way to run tests."""
    ws = Path(ws)
    mk = ws / "Makefile"
    if mk.exists() and re.search(r"^test\s*:", mk.read_text(errors="replace"), re.M):
        return ["make", "-s", "test"]
    if (ws / "go.mod").exists():
        return ["go", "test", "./..."]
    if (ws / "Cargo.toml").exists():
        return ["cargo", "test", "--offline", "--quiet"]
    pkg = ws / "package.json"
    if pkg.exists():
        try:
            if json.loads(pkg.read_text()).get("scripts", {}).get("test"):
                return ["npm", "test", "--silent"]
        except ValueError:
            pass
    if any(ws.rglob("test*.py")) or any(ws.rglob("*_test.py")):
        return default_test_command(ws)
    return None


def run_project_tests(job, ws=None):
    ws = Path(ws or job.workspace)
    cmd = detect_test_command(ws)
    if cmd is None:
        return None, None
    work = ws.parent / (ws.name + "__tests")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(ws, work, ignore=shutil.ignore_patterns(".neuron", "__pycache__", ".git", "*.o"))
    res = job.sandbox.run(cmd, work, timeout=300)
    shutil.rmtree(work, ignore_errors=True)
    passed = tests_passed(res, cmd[:2] == ["python3", "-m"]) if cmd[0] == "python3" else res.ok
    return passed, res


class InspectWorkspace(Capability):
    name = "inspect_workspace"
    purpose = "List the project's files, languages, build system and test command"
    outputs = ["languages", "file list", "test command"]
    verification = "deterministic file scan"
    domains = ("code",)

    def run(self, job, params):
        ws = job.workspace
        fl = files(ws)
        langs = Counter(LANG[Path(f).suffix] for f in fl if Path(f).suffix in LANG)
        cmd = detect_test_command(ws)
        builds = [f for f in fl if Path(f).name in ("Makefile", "CMakeLists.txt", "go.mod", "Cargo.toml", "package.json", "pyproject.toml", "pubspec.yaml")]
        result = {"files": len(fl), "languages": dict(langs.most_common()), "build_files": builds, "test_command": cmd,
                  "code_files": [f for f in fl if Path(f).suffix in CODE_EXT][:200]}
        job.state.learn(f"project: {result['files']} files, languages {result['languages']}, tests: {' '.join(cmd) if cmd else 'none found'}",
                        "inspect_workspace")
        return Outcome(True, f"{result['files']} files; languages {dict(langs.most_common(3))}; test command: {' '.join(cmd) if cmd else 'none'}", result)

    def verify(self, job, params, outcome):
        return Verdict(True, [{"id": "scanned", "pass": True, "detail": outcome.summary}], "deterministic")


class RunTests(Capability):
    name = "run_tests"
    purpose = "Run the project's own tests in the sandbox"
    outputs = ["pass or fail", "test output"]
    permissions = ("read_workspace", "run_code")
    verification = "the project's test command exits successfully"
    domains = ("code",)

    def run(self, job, params):
        passed, res = run_project_tests(job)
        if passed is None:
            return Outcome(False, "this project has no test command NEURON can find", evidence={"no_retry": True})
        return Outcome(True, "tests pass" if passed else "tests fail", {"passed": passed, "output": res.output[-3000:]})

    def verify(self, job, params, outcome):
        ok = bool(outcome.result.get("passed"))
        return Verdict(ok, [{"id": "tests_pass", "pass": ok, "detail": outcome.result.get("output", "")[-600:]}], "project test command")


CAPABILITIES = [InspectWorkspace(), RunTests()]
