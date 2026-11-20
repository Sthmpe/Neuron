import json
import unittest

from neuron.agent.document_facts import facts_backed, document_proof
from tests.test_agent import run


class DocumentFactTests(unittest.TestCase):
    def test_neighbouring_counts_and_incomplete_excerpts(self):
        q = "How many yellow chairs are there?"
        page = "There are 16 blue chairs and 3 yellow chairs."
        for answer,quote,want in [("16 yellow chairs",page,False),("3",page,True),("3 yellow chairs",page,True),
                                  ("3 yellow chairs and one spare",page,False),("16","16 blue chairs",False)]:
            self.assertEqual(facts_backed(q,answer,quote,page),want)
        self.assertFalse(facts_backed("Who signed the report?", "June", "June signed the report", "If asked, June signed the report."))

    def test_subject_object_direction_negation_and_conflicts(self):
        q = "Who did Ellis thank?"
        page = "Ellis thanked Pat. Noel thanked Ellis."
        self.assertTrue(facts_backed(q,"Pat","Ellis thanked Pat",page))
        self.assertFalse(facts_backed(q,"Noel","Noel thanked Ellis.",page))
        q = "What is the charge for freight?"
        claim = "The charge for freight is 8 euros."
        for other in [" The charge for freight is 18 euros.", " The charge for freight is not 8 euros."]:
            self.assertFalse(facts_backed(q,"8 euros",claim,claim+other))
        self.assertFalse(facts_backed(q,"8 dollars",claim,claim))
        self.assertFalse(facts_backed(q,"8 euros","freight is 8 euros",claim))
        self.assertFalse(facts_backed(q,"8 euros",claim,claim.replace("8","-8")))

    def test_unproven_claim_is_withheld_from_delivered_file_and_notes(self):
        import tempfile
        from pathlib import Path
        from neuron.agent.state import JobState
        with tempfile.TemporaryDirectory() as t:
            ws = Path(t)
            quote = "There are 10 metal cards and 2 paper cards."
            q = "How many paper cards are there?"
            st = JobState(ws)
            st.create(q)
            st.update_goal(kind="pdf_qa")
            st.set_plan([{"id":"answer", "title":"Read the indexed page", "capability":"answer_from_documents"}])
            (st.dir / "index.json").write_text(json.dumps([{"doc":"cards", "page":1, "text":quote}]))
            wrong=json.dumps({"answer":"10 paper cards","doc":"cards","page":1,"quote":quote})
            report,job,_=run(q,[wrong]*6,workspace=ws)
            self.assertNotEqual(report["verdict"],"VERIFIED")
            row=json.loads((job.workspace/"answers.json").read_text())[0]
            self.assertFalse(row["verified"])
            self.assertNotIn("10 paper cards",(job.workspace/"answers.md").read_text())
            self.assertIsNone(document_proof(row,quote))

    def test_category_identifier_tense_and_citation_boundaries(self):
        cases = [
            ("Which truck has clearance?", "The south pod", "The south pod has clearance."),
            ("What is the rate for Pier A?", "5 euros", "The rate for Pier is 5 euros."),
            ("Who signed the receipt?", "Jame", "James signed the receipt."),
            ("What is the price for buses?", "9 euros", "The price for buses was 9 euros."),
            ("Who signed the receipt?", "James", "James signed the receipt?"),
        ]
        for q,answer,page in cases:
            with self.subTest(q=q,answer=answer):
                self.assertFalse(facts_backed(q,answer,page,page))
        q="Who signed the receipt?"
        page="If appointed, Mira signed the receipt on Tuesday. Mira signed the receipt."
        self.assertFalse(facts_backed(q,"Mira","Mira signed the receipt on Tuesday",page))

    def test_phone_artifact_and_duplicate_page_labels_must_agree(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from neuron.agent.capabilities.research import AnswerFromDocuments, render_answers
        from neuron.agent.capability import Outcome
        from neuron.agent.state import JobState
        with tempfile.TemporaryDirectory() as t:
            ws = Path(t)
            state = JobState(ws)
            q = "Who signed the order?"
            state.create(q)
            state.set_plan([{"id":"answer"}])
            source = {"doc":"orders", "page":1, "text":"Mina signed the order."}
            index = state.dir / "index.json"
            row = {"doc":"orders", "page":1, "question":q, "answer":"Mina", "quote":source["text"], "verified":True}
            (ws/"answers.json").write_text(json.dumps([row]))
            outcome = Outcome(True, "", {"answers":[row]})
            cap = AnswerFromDocuments()
            job = SimpleNamespace(state=state, workspace=ws)
            for pages,md,expected in [([source],render_answers([row]),True), ([source],"Ned signed the order.",False),
                                      ([source,{**source,"text":"Ned signed the order."}],render_answers([row]),False)]:
                index.write_text(json.dumps(pages))
                (ws/"answers.md").write_text(md)
                self.assertEqual(cap.verify(job,{},outcome).passed,expected)
                self.assertEqual(bool(outcome.result["memory_notes"]),expected)
