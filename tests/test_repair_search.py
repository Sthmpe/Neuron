"""Small one-token changes tried before the model (C++/Go bug fixing, step 5). Real compilers in the sandbox."""
import shutil
import tempfile
import unittest
from pathlib import Path

from neuron.agent.capability import default_registry
from neuron.agent.loop import Agent, Job
from neuron.agent.repair_search import mutants
from neuron.brain.sandbox import Sandbox
from tests.fakes import ScriptedLLM

ROOT = Path(__file__).resolve().parents[1]
SBX = Sandbox(timeout=120, mem_mb=1024, toolchains=True)


class MutantTests(unittest.TestCase):
    def test_operators_but_not_strings_comments_generics_or_signs(self):
        src = ('int f(int a, std::vector<int> v) {\n'
               '    if (a > 3) return a - 1;  // a > 9 in a comment\n'
               '    std::string s = "x > y";\n'
               '    return -a * 2;\n'
               '}\n')
        got = [(n, d) for n, _, _, d in mutants(src, 1, 5)]
        self.assertIn((2, "'>' -> '>='"), got)
        self.assertIn((2, "'-' -> '+'"), got)
        self.assertIn((4, "'*' -> '/'"), got)
        self.assertNotIn(3, [n for n, _ in got if "'" in _])          # nothing inside the string
        self.assertFalse(any(n == 1 and d.startswith("'<'") for n, d in got))   # vector<int> is not a comparison
        self.assertFalse(any(n == 4 and d == "'-' -> '+'" for n, d in got))     # -a is a sign
        self.assertFalse(any("9 ->" in d for n, d in got))                       # numbers in comments are left alone


class Runner:
    def __init__(self, llm):
        self.llm = llm

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


@unittest.skipUnless(SBX.available() and shutil.which("go") and shutil.which("g++"), "needs bubblewrap, go and g++")
class FixBugSearchTests(unittest.TestCase):
    def run_on(self, name):
        ws = Path(tempfile.mkdtemp()) / name
        shutil.copytree(ROOT / "benchmark" / "repair_dev" / "workspaces" / name, ws)
        llm = ScriptedLLM(["ok"] * 5)
        job = Job(ws, Runner(llm), SBX, registry=default_registry(), log=lambda *_: None)
        rep = Agent(job).run("The tests of this project fail. Find the bug in the source code and fix it so the tests pass. "
                             "Do not change the tests.")
        return rep, job, llm

    def test_go_one_token_bug_fixed_without_the_model(self):
        rep, job, llm = self.run_on("go_stock")
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertEqual(rep["made_by"], {"search": 1, "deterministic": 1} if "deterministic" in rep["made_by"] else {"search": 1})
        self.assertIn("return target - left", (job.workspace / "stock" / "reorder.go").read_text())
        self.assertEqual(rep["model_calls"], 0)

    def test_cpp_one_token_bug_fixed_and_tests_untouched(self):
        rep, job, llm = self.run_on("cpp_tickets")
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertIn("age >= 65", (job.workspace / "src" / "tickets.cpp").read_text())
        self.assertEqual((job.workspace / "tests" / "test.cpp").read_text(),
                         (ROOT / "benchmark/repair_dev/workspaces/cpp_tickets/tests/test.cpp").read_text())


if __name__ == "__main__":
    unittest.main()
