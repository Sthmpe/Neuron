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
        from reportlab.pdfgen.canvas import Canvas
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"cards.pdf"
            pdf=Canvas(str(p))
            quote="There are 10 metal cards and 2 paper cards."
            pdf.drawString(30,750,quote)
            pdf.save()
            wrong=json.dumps({"answer":"10 paper cards","doc":"cards","page":1,"quote":quote})
            report,job,_=run("How many paper cards are there?",[wrong]*6,[str(p)])
            self.assertNotEqual(report["verdict"],"VERIFIED")
            row=json.loads((job.workspace/"answers.json").read_text())[0]
            self.assertFalse(row["verified"])
            self.assertNotIn("10 paper cards",(job.workspace/"answers.md").read_text())
            self.assertIsNone(document_proof(row,quote))
