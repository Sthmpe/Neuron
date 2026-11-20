"""Exact arithmetic and the delivered answer's evidence label (Astra's tests from research/astra 6847ef3, adapted:
on this branch a plain unchecked answer has the status "answered", not "done")."""
import unittest

from neuron.agent.arithmetic import exact_answer
from neuron.agent.capabilities.research import AnswerQuestion
from neuron.agent.capability import Outcome
from neuron.agent.loop import Agent
from tests.test_agent import run


class AnswerEvidenceTests(unittest.TestCase):
    def test_exact_arithmetic_uses_the_complete_request(self):
        cases = {"Compute (0.1 + 0.2) / 2": "0.15", "What is −5 × 2?": "-10",
                 "1 / 7": "1/7", "Evaluate 3 / 4 as a fraction": "3/4",
                 "What is 0.5 + 0.25? Give the exact fraction.": "3/4"}
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(exact_answer(question)[1], expected)
        for question in ["What do I owe after 3 + 8?", "2 + 2 days", "3 + 4; name the author",
                         "1 / 0", "3 // 2", "2**999", "round(2.5)", "2 + ", "What is 8?",
                         "1 + 1? Give the exact fraction and your opinion.", "9" * 300 + "+1"]:
            with self.subTest(question=question):
                self.assertIsNone(exact_answer(question))

    def test_checked_answer_comes_from_the_file(self):
        report, job, model = run("What is 7 * (6 - 2)?", [])
        self.assertEqual((report["verdict"], report["made_by"], len(model.calls)), ("VERIFIED", {"deterministic": 1}, 0))
        self.assertEqual((job.workspace / "answer.md").read_text().strip(), "28")
        (job.workspace / "answer.md").write_text("29\n")
        self.assertFalse(AnswerQuestion().verify(job, {}, Outcome(True, "28")).passed)

    def test_model_answer_is_delivered_once_labelled_and_stays_unverified_on_resume(self):
        report, job, model = run("Which planet do humans live on?", ["Mars."])
        self.assertEqual((report["verdict"], report["tasks"], report["files"]), ("UNVERIFIED", {"answer": "done"}, ["answer.md"]))
        self.assertIn("Unverified.", (job.workspace / "answer.md").read_text())
        self.assertEqual(Agent(job).run("")["verdict"], "UNVERIFIED")
        self.assertEqual(len(model.calls), 1)

    def test_empty_final_answer_is_not_delivery(self):
        report, _, _ = run("What happened in 1912?", ["no final line"] * 6)
        self.assertEqual(report["verdict"], "FAILED")
        self.assertEqual(report["files"], [])


if __name__ == "__main__":
    unittest.main()
