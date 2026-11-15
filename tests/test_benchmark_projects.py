"""The benchmark itself must be honest: every project really fails as shipped, really is
fixable, and the runner's 'solved' is decided by an independent test run."""
import shutil
import tempfile
import unittest
from pathlib import Path

from benchmark.run_benchmark import run_project
from neuron.brain.planner import RuleBasedPlanner
from neuron.brain.sandbox import Sandbox
from neuron.brain.tools.fix_code import default_test_command, is_test_file, tests_passed
from tests.fakes import ScriptedLLM
from tests.helpers import Rig

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = sorted(p for p in (ROOT / "benchmark" / "projects").iterdir() if p.is_dir())
SOLUTIONS = ROOT / "benchmark" / "solutions"
SBX = Sandbox(timeout=30, mem_mb=256)


@unittest.skipUnless(SBX.available(), "bubblewrap is not installed on this machine")
class BenchmarkProjectTests(unittest.TestCase):
    def run_tests(self, folder):
        work = Path(tempfile.mkdtemp(prefix="neuron-bench-")) / "p"
        shutil.copytree(folder, work)
        return work, SBX.run(default_test_command(work), work)

    def test_there_are_ten_projects(self):
        self.assertEqual(len(PROJECTS), 10)

    def test_each_project_fails_as_shipped_and_passes_with_its_reference_fix(self):
        for project in PROJECTS:
            with self.subTest(project=project.name):
                work, res = self.run_tests(project)
                self.assertFalse(tests_passed(res, True), "tests should fail on the buggy project")
                self.assertIn("FAILED", res.output)
                self.assertRegex(res.output, r"Ran [4-9] tests")
                fixes = [p for p in (SOLUTIONS / project.name).rglob("*.py")]
                self.assertEqual(len(fixes), 1, "exactly one file holds the bug")
                rel = fixes[0].relative_to(SOLUTIONS / project.name)
                self.assertFalse(is_test_file(str(rel)))
                shutil.copy(fixes[0], work / rel)
                res = SBX.run(default_test_command(work), work)
                self.assertTrue(tests_passed(res, True), res.output[-500:])

    def test_solutions_are_not_inside_the_projects(self):
        for project in PROJECTS:
            self.assertFalse(any("solution" in str(p).lower() for p in project.rglob("*")))

    def test_runner_plumbing_and_independent_check(self):
        """Plumbing only - a scripted double plays the model. NOT a benchmark result."""
        project = PROJECTS[2]
        good = next((SOLUTIONS / project.name).glob("*.py"))
        bad = (project / good.name).read_text().replace("return -1", "return -2")
        scratch = Path(tempfile.mkdtemp(prefix="neuron-bench-run-"))

        def run(replies):
            llm = ScriptedLLM(replies)
            r = Rig(planner=RuleBasedPlanner(), services={"llm": llm, "sandbox": SBX})
            self.addCleanup(r.close)
            row, text = run_project(r.engine, r.store, SBX, project, scratch, log=lambda *_: None)
            return row, text

        row, text = run([f"FILE: {good.name}\n```python\n{good.read_text()}```"])
        self.assertTrue(row["solved"] and row["independent_test_run_passed"] and row["tests_untouched"])
        self.assertEqual(row["attempts"], 1)
        self.assertIn("COMPLETED", text)

        row, text = run([f"FILE: {good.name}\n```python\n{bad}```"] * 3)
        self.assertFalse(row["solved"])
        self.assertEqual(row["attempts"], 3)
        self.assertIn("NOT SOLVED", text)
        self.assertEqual(row["what_happened"], [f"changed {good.name}: tests still failing"] * 3)


if __name__ == "__main__":
    unittest.main()
