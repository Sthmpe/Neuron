"""fix_code: propose, apply, test in the sandbox, retry up to 3 times, never claim success without passing tests.
The model is a scripted test double; the sandbox and the test runs are real."""
import shutil
import tempfile
import unittest
from pathlib import Path

from neuron.brain.llm import LLMUnavailable
from neuron.brain.report import build_report, report_text
from neuron.brain.sandbox import Sandbox
from neuron.brain.tools.fix_code import parse_reply
from tests.fakes import ScriptedLLM
from tests.helpers import Rig

ROOT = Path(__file__).resolve().parent.parent
BUGGY = ROOT / "benchmark" / "projects" / "05_date_utils"
GOOD = (ROOT / "benchmark" / "solutions" / "05_date_utils" / "dateutils.py").read_text()
WRONG = (BUGGY / "dateutils.py").read_text().replace("year % 100 != 0", "year % 100 == 0")
SBX = Sandbox(timeout=30, mem_mb=256)


def reply(code, path="dateutils.py"):
    return f"FILE: {path}\n```python\n{code}```\n"


class Crash(BaseException):
    pass


@unittest.skipUnless(SBX.available(), "bubblewrap is not installed on this machine")
class FixCodeTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="neuron-fix-")) / "proj"
        shutil.copytree(BUGGY, self.project)

    def start(self, replies, sandbox=SBX):
        self.llm = ScriptedLLM(replies)
        r = Rig(services={"llm": self.llm, "sandbox": sandbox})     # rule-based planner -> one fix_code step
        self.addCleanup(r.close)
        tid = r.engine.submit(f"Fix the failing tests in {self.project}")
        return r, tid

    def step(self, r, tid):
        return r.store.steps(tid)[0]

    def test_fix_on_first_attempt(self):
        r, tid = self.start([reply(GOOD)])
        r.run()
        s = self.step(r, tid)
        self.assertEqual((r.store.get_task(tid)["status"], s["action"], s["status"]), ("done", "fix_code", "done"))
        self.assertEqual(s["result"], {"fixed": True, "file": "dateutils.py", "attempts": 1})
        ev = s["proof"]["evidence"]
        self.assertTrue(s["proof"]["verified"])
        self.assertFalse(ev["tests_before"]["passed"])
        self.assertEqual(ev["tests_after"]["exit_code"], 0)
        self.assertTrue(ev["attempts"][0]["confirm_run_passed"])
        self.assertIn("+    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0", ev["diff"])
        self.assertEqual(ev["sandbox"]["network"], "none (empty network namespace)")
        self.assertEqual((self.project / "dateutils.py").read_text(), GOOD)          # written back
        prompt = self.llm.calls[0]["messages"][1]["content"]
        self.assertIn("AssertionError", prompt)                                       # saw the failing output
        self.assertIn("def is_leap_year", prompt)                                     # saw the source
        self.assertIn("test_century_years", prompt)                                   # saw the test
        self.assertIn("checked: YES", report_text(build_report(r.store, r.world, tid)))

    def test_wrong_then_right_uses_the_test_output(self):
        r, tid = self.start([reply(WRONG), reply(GOOD)])
        r.run()
        s = self.step(r, tid)
        self.assertEqual(s["result"]["attempts"], 2)
        first = s["proof"]["evidence"]["attempts"][0]
        self.assertFalse(first["passed"])
        self.assertNotEqual(first["test"]["exit_code"], 0)
        second_prompt = self.llm.calls[1]["messages"][1]["content"]
        self.assertIn("Earlier attempts that did NOT work", second_prompt)
        self.assertIn("year % 100 == 0", second_prompt)                               # its own failed change
        self.assertEqual((self.project / "dateutils.py").read_text(), GOOD)

    def test_gives_up_after_three_attempts_and_says_so(self):
        r, tid = self.start([reply(WRONG), reply(WRONG.replace("% 4", "% 8")), reply(WRONG.replace("% 4", "% 2")),
                             reply(GOOD)])
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "failed")
        self.assertEqual(len(self.llm.calls), 3)                                      # never a 4th attempt
        self.assertEqual((self.project / "dateutils.py").read_text(), (BUGGY / "dateutils.py").read_text())
        rep = build_report(r.store, r.world, tid)
        self.assertIn("NOT SOLVED", rep["verdict"])
        self.assertIn("could not make the tests pass in 3 attempts", rep["verdict"])
        text = report_text(rep)
        for n in (1, 2, 3):
            self.assertIn(f"attempt {n}: changed dateutils.py -> tests still failing", text)

    def test_model_may_not_edit_the_tests(self):
        cheat = "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
        r, tid = self.start([reply(cheat, "tests/test_dateutils.py")] * 3)
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "failed")
        attempts = self.step(r, tid)["proof"]["evidence"]["attempts"]
        self.assertTrue(all("not an editable source file" in a["error"] for a in attempts))
        self.assertEqual((self.project / "tests" / "test_dateutils.py").read_text(),
                         (BUGGY / "tests" / "test_dateutils.py").read_text())

    def test_unusable_replies_count_as_attempts(self):
        r, tid = self.start(["I would change the leap year rule.", reply("def broken(:\n"),
                             reply((BUGGY / "dateutils.py").read_text())])
        r.run()
        errors = [a["error"] for a in self.step(r, tid)["proof"]["evidence"]["attempts"]]
        self.assertIn("no complete code block", errors[0])
        self.assertIn("not valid Python", errors[1])
        self.assertIn("identical to the original", errors[2])
        self.assertEqual(r.store.get_task(tid)["status"], "failed")

    def test_already_passing_project_needs_no_model(self):
        (self.project / "dateutils.py").write_text(GOOD)
        r, tid = self.start([])
        r.run()
        s = self.step(r, tid)
        self.assertEqual((s["status"], s["result"]), ("done", {"fixed": False, "already_passing": True}))
        self.assertEqual(self.llm.calls, [])

    def test_restart_in_the_middle_does_not_repeat_finished_attempts(self):
        r, tid = self.start([reply(WRONG), Crash()])
        with self.assertRaises(Crash):
            r.run()
        self.assertEqual(self.step(r, tid)["status"], "running")
        self.llm.replies = [reply(GOOD)]
        self.assertEqual(r.restart(), [(tid, 1)])
        r.run()
        s = self.step(r, tid)
        self.assertEqual(s["result"]["attempts"], 2)                                  # attempt 1 was kept
        self.assertEqual([a["n"] for a in s["proof"]["evidence"]["attempts"]], [1, 2])
        self.assertEqual(len(self.llm.calls), 3)                                      # wrong, crash, right

    def test_no_sandbox_means_no_run(self):
        for sandbox in (None, type("Off", (), {"available": lambda self: False})()):
            r, tid = self.start([reply(GOOD)], sandbox=sandbox)
            r.run()
            self.assertEqual(r.store.get_task(tid)["status"], "failed")
            self.assertIn("no isolated sandbox", self.step(r, tid)["error"])
            self.assertEqual(self.llm.calls, [])

    def test_model_unreachable_is_reported(self):
        r, tid = self.start([LLMUnavailable("connection refused")])
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "failed")
        self.assertIn("local model could not be used", self.step(r, tid)["error"])

    def test_hostile_fix_cannot_touch_the_machine(self):
        marker = Path(tempfile.mkdtemp(prefix="neuron-outside-")) / "owned.txt"
        hostile = (f"import socket\ntry:\n    open({str(marker)!r}, 'w').write('x')\nexcept OSError:\n    pass\n"
                   "try:\n    socket.create_connection(('1.1.1.1', 53), timeout=2)\n    ONLINE = True\n"
                   "except OSError:\n    ONLINE = False\nassert not ONLINE\n" + GOOD)
        r, tid = self.start([reply(hostile)])
        r.run()
        self.assertFalse(marker.exists())                    # could not write outside its workspace
        self.assertEqual(self.step(r, tid)["status"], "done")   # and 'assert not ONLINE' held: no network

    def test_infinite_loop_fix_is_stopped_by_the_time_limit(self):
        loop = GOOD.replace("def is_leap_year(year):", "def is_leap_year(year):\n    while True:\n        pass")
        r, tid = self.start([reply(loop), reply(GOOD)], sandbox=Sandbox(timeout=3, mem_mb=256))
        r.run()
        attempts = self.step(r, tid)["proof"]["evidence"]["attempts"]
        self.assertTrue(attempts[0]["test"]["timed_out"])
        self.assertTrue(attempts[1]["passed"])

    def test_missing_project(self):
        from neuron.brain.planner import Plan, Planner, PlanStep

        class P(Planner):
            name = "fixed"

            def plan(self, goal):
                return Plan([PlanStep(1, "fix", "fix_code", params={"project": "/no/such/place"})], "fixed")

        r = Rig(planner=P(), services={"llm": ScriptedLLM([]), "sandbox": SBX})
        self.addCleanup(r.close)
        tid = r.engine.submit("fix it")
        r.run()
        self.assertIn("project folder not found", r.store.steps(tid)[0]["error"])


class ParseReplyTests(unittest.TestCase):
    ORIG = {"a.py": "x = 1\n", "pkg/b.py": "y = 2\n"}

    def parse(self, text, editable=("a.py", "pkg/b.py")):
        return parse_reply(text, list(editable), self.ORIG)

    def test_normal(self):
        self.assertEqual(self.parse("FILE: a.py\n```python\nx = 2\n```"), ("a.py", "x = 2\n", None))

    def test_tolerates_small_format_slips(self):
        self.assertEqual(self.parse("Sure!\nFILE: `./pkg/b.py`\n```\ny = 3\n```\nDone.")[:2], ("pkg/b.py", "y = 3\n"))
        self.assertEqual(self.parse("FILE: /workspace/b.py\n```py\ny = 3\n```")[0], "pkg/b.py")
        self.assertEqual(self.parse("```python\nx = 5\n```", editable=("a.py",))[0], "a.py")

    def test_rejections(self):
        self.assertIn("did not say which file", self.parse("```python\nx = 5\n```")[2])
        self.assertIn("not an editable", self.parse("FILE: ../../etc/passwd\n```\nroot\n```")[2])
        self.assertIn("no complete code block", self.parse("FILE: a.py\n```python\nx = 2")[2])
        self.assertIn("not valid Python", self.parse("FILE: a.py\n```python\nx = = 2\n```")[2])
        self.assertIn("identical", self.parse("FILE: a.py\n```python\nx = 1\n```")[2])


if __name__ == "__main__":
    unittest.main()
