"""Easy work goes straight to the model (owner's routing requirement): no classification call, no planning, one model
call, keyword-only memory search; calculations still come from a program run in the sandbox; anything unsafe falls
back to the careful path."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("NEURON_EMBEDDER", "hash")
from neuron.agent.router import is_simple                       # noqa: E402
from tests.test_agent import run                                # noqa: E402


class FastPathTests(unittest.TestCase):
    def test_plain_request_is_one_model_call_with_no_classification(self):
        rep, job, llm = run("Tell me a short joke about cats", ["Why did the cat sit on the computer? To keep an eye on the mouse."])
        self.assertEqual((rep["verdict"], rep["model_calls"]), ("UNVERIFIED", 1))
        self.assertTrue(job.state.goal()["fast"])
        self.assertIn("keep an eye on the mouse", (job.workspace / "answer.md").read_text())
        self.assertIn("Unverified.", (job.workspace / "answer.md").read_text())

    def test_calculation_comes_from_a_program_in_one_call(self):
        reply = "```python\nprint(round(18500 * 0.85 + 2000, 2))\n```"
        rep, job, llm = run("A dress costs 18500 naira. The shop gives 15% off and then adds a 2000 naira delivery fee. How much do I pay?", [reply])
        self.assertEqual((rep["verdict"], rep["model_calls"]), ("UNVERIFIED", 1))
        self.assertTrue((job.workspace / "answer.md").read_text().startswith("17725"))

    def test_invented_number_takes_the_careful_path_and_asks_the_owner(self):
        rep, job, llm = run("I used 7 litres from my tank. How much is left?", ["```python\nprint(100 - 7)\n```"])
        self.assertEqual(rep["verdict"], "WAITING_INPUT")             # 100 was never given: ask, never guess
        self.assertIn("starting amount", job.state.task("answer")["input_request"]["question"])

    def test_numeric_question_without_a_number_is_not_delivered(self):
        rep, job, llm = run("How much would my trip cost?", ["bad plan", "bad check"] * 3)
        self.assertEqual(rep["verdict"], "FAILED")
        self.assertFalse((job.workspace / "answer.md").exists())

    def test_what_is_not_simple(self):
        self.assertTrue(is_simple("Why is the sky blue?"))
        self.assertFalse(is_simple("Write memo.docx to staff about parking"))
        self.assertFalse(is_simple("Build a website for my bakery"))
        self.assertFalse(is_simple("Summarise this", attachments=["a.pdf"]))
        self.assertFalse(is_simple("x" * 600))
        ws = Path(tempfile.mkdtemp())
        (ws / "main.py").write_text("print(1)\n")
        self.assertFalse(is_simple("Why does this fail?", workspace=ws))
        shutil.rmtree(ws)


if __name__ == "__main__":
    unittest.main()
