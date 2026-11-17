"""The workspace benchmark must be honest: each task is a whole codebase whose tests fail only because
of one planted bug, and the reference fix (the clean file) makes them pass."""
import shutil
import tempfile
import unittest
from pathlib import Path

from neuron.brain.sandbox import Sandbox
from neuron.brain.tools.fix_code import default_test_command, tests_passed

ROOT = Path(__file__).resolve().parents[1] / "benchmark" / "workspaces"
SBX = Sandbox(timeout=60, mem_mb=256)


@unittest.skipUnless(SBX.available(), "bubblewrap is not installed on this machine")
class WorkspaceTaskTests(unittest.TestCase):
    def test_clean_codebases_pass(self):
        for base in ("shopkeeper", "clinic"):
            work = Path(tempfile.mkdtemp()) / base
            shutil.copytree(ROOT / base, work)
            self.assertTrue(tests_passed(SBX.run(default_test_command(work), work), True), base)

    def test_each_task_fails_and_its_fix_passes(self):
        tasks = sorted(p for p in (ROOT / "tasks").iterdir() if p.is_dir())
        self.assertEqual(len(tasks), 10)
        for task in tasks:
            with self.subTest(task=task.name):
                work = Path(tempfile.mkdtemp()) / task.name
                shutil.copytree(task, work)
                self.assertGreaterEqual(len(list(work.rglob("*.py"))), 15)
                self.assertFalse(tests_passed(SBX.run(default_test_command(work), work), True))
                fixes = list((ROOT / "task_solutions" / task.name).rglob("*.py"))
                self.assertEqual(len(fixes), 1)
                shutil.copy(fixes[0], work / fixes[0].relative_to(ROOT / "task_solutions" / task.name))
                self.assertTrue(tests_passed(SBX.run(default_test_command(work), work), True))


if __name__ == "__main__":
    unittest.main()
