"""A quote copied exactly but cited with the wrong page number is cited where it really is (core proof D8, 2 GB run 1:
two of six answers quoted page 1 and 2 correctly but cited the next page). A quote that is on no page stays unconfirmed."""
import json
import unittest
from pathlib import Path

from tests.test_agent import P5, run

PDF = str(P5 / "sources" / "dev_library_rules.pdf")


class Citations(unittest.TestCase):
    def test_exact_quote_with_the_wrong_page_is_cited_where_it_is(self):
        req = "Answer from the attached PDF with page numbers.\n1. How long is the standard loan period?"
        wrong_page = json.dumps({"answer": "21 days", "doc": "dev_library_rules", "page": 2, "quote": "The standard loan period is 21 days."})
        rep, job, llm = run(req, [wrong_page], [PDF])
        a = json.loads((job.workspace / "answers.json").read_text())[0]
        self.assertEqual(a["page"], 1)
        self.assertIn("cited where it is", (job.state.dir / "decisions.jsonl").read_text())

    def test_a_quote_on_no_page_is_not_confirmed(self):
        req = "Answer from the attached PDF with page numbers.\n1. How long is the standard loan period?"
        invented = json.dumps({"answer": "30 days", "doc": "dev_library_rules", "page": 1, "quote": "The loan period is 30 days for everyone."})
        rep, job, llm = run(req, [invented] * 4, [PDF])
        self.assertFalse(json.loads((job.workspace / "answers.json").read_text())[0]["verified"])
        self.assertNotEqual(rep["verdict"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
