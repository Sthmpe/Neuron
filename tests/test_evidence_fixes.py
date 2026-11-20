"""Regression tests for the defects Astra's review found on main d54bf4d (docs/reviews/astra-review.md, phase 2).

1. A wrong document answer ("16 yellow chairs" where the page says 16 blue and 3 yellow) passed because the number was
   somewhere in the quote, and was saved to memory as a verified finding.
2. The checking pass overrode a code-computed result (the program printed 33, the checker said 34 and won).
3. Repair search skipped `x<5` (taken for a template) and changed code inside block comments.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("NEURON_EMBEDDER", "hash")
from neuron.agent.capabilities.research import AnswerFromDocuments, facts_backed, tied_numbers   # noqa: E402
from neuron.agent.loop import Job                                                               # noqa: E402
from neuron.agent.repair_search import mutants                                                  # noqa: E402
from neuron.agent.thinking import solve                                                         # noqa: E402
from neuron.brain.sandbox import Sandbox                                                        # noqa: E402
from neuron.memory import Memory                                                                # noqa: E402
from neuron.memory.revalidate import revalidate_findings                                        # noqa: E402
from tests.fakes import ScriptedLLM                                                             # noqa: E402

Q = "How many yellow chairs are there?"
PAGE = "Hall plan. There are 16 blue chairs and 3 yellow chairs. Chairs are stacked after each event."


class Runner:
    def __init__(self, llm):
        self.llm = llm

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


class DocumentAssociationTests(unittest.TestCase):
    def test_number_must_belong_to_the_thing_asked_about(self):
        for quote in ["There are 16 blue chairs and 3 yellow chairs.", "Yellow chairs: 3, blue chairs: 16.",
                      "3 of the chairs are yellow, 16 are blue.", "The hall has 19 chairs: 16 blue and 3 yellow."]:
            with self.subTest(quote=quote):
                self.assertFalse(facts_backed(Q, "16 yellow chairs.", quote))
                self.assertTrue(facts_backed(Q, "3 yellow chairs.", quote))
        self.assertIsNone(tied_numbers(Q, "There are 3 yellow chairs."))          # one number: nothing to confuse

    def test_answer_without_numbers_must_share_words_with_its_quote(self):
        quote = "The library was founded by Ada Obi in 1901."
        self.assertTrue(facts_backed("Who founded the library?", "Ada Obi", quote))
        self.assertFalse(facts_backed("Who founded the library?", "Mars", quote))

    def test_wrong_answer_is_not_confirmed_and_not_saved_to_memory(self):
        ws = Path(tempfile.mkdtemp()) / "job"
        bad = json.dumps({"answer": "16 yellow chairs.", "doc": "hall", "page": 1, "quote": "There are 16 blue chairs and 3 yellow chairs."})
        job = Job(ws, Runner(ScriptedLLM([bad])), None, log=lambda *_: None)
        job.state.create("Answer from the attached PDF with page numbers.\n" + Q)
        (job.state.dir / "index.json").write_text(json.dumps([{"doc": "hall", "page": 1, "text": PAGE}]))
        job.state.set_plan([{"id": "answer", "capability": "answer_from_documents", "title": "Answer", "params": {}}])
        out = AnswerFromDocuments().run(job, {})
        self.assertFalse(out.result["answers"][0]["verified"])
        self.assertEqual(out.result["memory_notes"], [])
        self.assertFalse(AnswerFromDocuments().verify(job, {}, out).passed)


class MemoryRevalidationTests(unittest.TestCase):
    def test_old_wrong_verified_finding_is_rejected_once_and_never_returned(self):
        m = Memory(Path(tempfile.mkdtemp()) / "k.db")
        wrong = m.add("finding", f"{Q} 16 yellow chairs. (quote: \"There are 16 blue chairs and 3 yellow chairs.\")", "hall page 1", verified=True)
        right = m.add("finding", f"{Q} 3 yellow chairs. (quote: \"There are 16 blue chairs and 3 yellow chairs.\")", "hall page 1", verified=True)
        r = revalidate_findings(m, log=lambda *_: None)
        self.assertEqual((r["checked"], r["rejected"]), (2, 1))
        status = {row["id"]: row["status"] for row in m.db.execute("SELECT id, status FROM notes")}
        self.assertEqual((status[wrong], status[right]), ("rejected", "verified"))
        self.assertNotIn(wrong, [n["id"] for n in m.search("yellow chairs", k=5, include_outdated=True)])
        self.assertIn("already checked", revalidate_findings(m, log=lambda *_: None)["skipped"])


class ComputedResultTests(unittest.TestCase):
    def test_checker_cannot_overrule_what_the_program_printed(self):
        llm = ScriptedLLM(["```python\nprint(24 + 9)\n```", "Answer: 33", "Answer: 34"])
        s = solve(lambda m, n: llm.chat(m, max_tokens=n), Sandbox(timeout=20), "What is 24 plus 9?", require_code=True)
        self.assertEqual((s["answer"], s["printed"], s["check_disagreed"]), ("33", "33", "34"))

    def test_checker_may_still_correct_an_answer_no_program_backs(self):
        llm = ScriptedLLM(["The answer is 34.\nAnswer: 34", "24 + 9 is 33.\nAnswer: 33"])
        s = solve(lambda m, n: llm.chat(m, max_tokens=n), None, "What is 24 plus 9?")
        self.assertEqual((s["answer"], s["check_disagreed"]), ("33", None))


class RepairSearchFormattingTests(unittest.TestCase):
    def test_spacing_does_not_change_which_changes_are_tried(self):
        a = [d for _, _, _, d in mutants("int f(int x) {\n    return x<5;\n}\n", 1, 3)]
        b = [d for _, _, _, d in mutants("int f(int x) {\n    return x < 5;\n}\n", 1, 3)]
        self.assertEqual(a, b)
        self.assertIn("'<' -> '<='", a)

    def test_comments_are_never_changed_but_templates_are_recognised(self):
        self.assertEqual([d for n, _, _, d in mutants("int f() {\n    /* count 9 + 2 */\n    return 1;\n}\n", 1, 4) if n == 2], [])
        multi = [d for n, _, _, d in mutants("int f(int a) {\n  /* a\n   + 9 */ return a + 1;\n}\n", 1, 4)]
        self.assertEqual(multi.count("'+' -> '-'"), 1)
        gen = [d for n, _, _, d in mutants("int f(std::vector<int> v) {\n    return v.size() > 2;\n}\n", 1, 3)]
        self.assertNotIn("'<' -> '<='", gen)
        self.assertIn("'>' -> '>='", gen)


if __name__ == "__main__":
    unittest.main()
