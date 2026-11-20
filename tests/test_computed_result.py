import unittest
from types import SimpleNamespace

from neuron.agent.thinking import solve
from neuron.brain.sandbox import Sandbox
from tests.test_agent import run


class ComputedResultTests(unittest.TestCase):
    def solve(self, replies):
        seq = iter(replies)
        def chat(messages, tokens):
            reply = next(seq)
            if isinstance(reply, Exception):
                raise reply
            return SimpleNamespace(text=reply, completion_tokens=1)
        return solve(chat, Sandbox(), "Return the calculation.")

    def test_disagreement_cannot_change_delivered_file(self):
        report, job, _ = run("How much is 31 times 4?", ["```python\nprint(31*4)\n```\nAnswer: 102", "Answer: 126"])
        result = job.state.task("answer")["result"]
        self.assertEqual((result["answer"], result["review_answer"], result["computed"]), ("124", "126", True))
        self.assertEqual(report["verdict"], "UNVERIFIED")
        self.assertTrue((job.workspace/"answer.md").read_text().startswith("124\n\n"))

    def test_stdout_is_separate_and_multiline_and_survives_failed_review(self):
        out = self.solve(["```python\nimport sys\nprint('warning 88',file=sys.stderr)\nprint('A: 6\\nB: 9')\n```",
                          RuntimeError("review unavailable")])
        self.assertEqual(out["answer"], "A: 6\nB: 9")

    def test_empty_failed_and_truncated_output_cannot_become_an_answer(self):
        for code in ["print(30)\nraise ValueError()", "import sys\nprint(18,file=sys.stderr)", "print('a'*200100)"]:
            with self.subTest(code=code):
                out = self.solve(["```python\n"+code+"\n```", "Answer: 30"])
                self.assertFalse(out["computed"])
                self.assertEqual(out["answer"], "")

    def test_repaired_program_and_model_only_control(self):
        out = self.solve(["```python\nprint(2/0)\n```", "```python\nprint(52//4)\n```", "Answer: 19"])
        self.assertEqual((out["answer"],out["tool_runs"]), ("13",2))
        self.assertEqual(self.solve(["Answer: 12","Answer: 13"])["answer"],"13")
