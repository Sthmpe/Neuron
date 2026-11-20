import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neuron.agent.document_facts import document_proof, legacy_identity
from neuron.memory import Memory, context_text
from neuron.memory.embed import HashEmbedder


class DocumentMemoryUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.path = self.home / "memory/knowledge.db"
        self.env = patch.dict(os.environ, NEURON_MEMORY="on")
        self.env.start()
        self.addCleanup(self.env.stop)
        self.mem = self.open()
        self.addCleanup(lambda: self.mem.db.close())
        self.page = "There are 4 green tokens and 17 white tokens."

    def open(self):
        return Memory(self.path, HashEmbedder())

    def row(self, answer):
        return {"doc":"tokens","page":1,"question":"How many green tokens are there?","answer":answer,"quote":self.page,"verified":True}

    def legacy(self, row, archive=True):
        text,source = legacy_identity(row)
        nid = self.mem.add("finding",text,source)
        self.mem.db.execute("UPDATE notes SET status='verified',uses=4 WHERE id=?", (nid,))
        self.mem.db.commit()
        if archive:
            ws = self.home/"jobs"/str(nid)/"workspace"
            ix = ws/".neuron/job/index.json"
            ix.parent.mkdir(parents=True)
            ix.write_text(json.dumps([{"doc":"tokens","page":1,"text":self.page}]))
            (ws/"answers.json").write_text(json.dumps([row]))
        return nid

    def test_reopen_removes_wrong_notes_from_recall_and_preserves_good_records(self):
        good, bad = self.legacy(self.row("4")), self.legacy(self.row("17"))
        lost = self.legacy({**self.row("4 green tokens"),"doc":"missing"},archive=False)
        fix = self.mem.add("fix","Token scanner consumes its terminator.","job parser",verified=True)
        self.mem.db.close()
        self.mem = self.open()
        def state():
            return [tuple(r) for r in self.mem.db.execute("SELECT id,status,uses,last_checked FROM notes ORDER BY id")]
        first = state()
        self.assertEqual([(r[0],r[1],r[2]) for r in first],[(good,"verified",4),(bad,"outdated",4),(lost,"outdated",4),(fix,"verified",0)])
        self.mem.mark(bad,status="verified")
        self.assertEqual(first,state())
        self.mem.db.close()
        self.mem = self.open()
        self.assertEqual(state(),first)
        hits=self.mem.search("green tokens scanner",k=10)
        self.assertEqual({r["id"] for r in hits},{good,fix})
        self.assertNotIn("there? 17 (quote:",context_text(hits))
        self.assertIn(bad,{r["id"] for r in self.mem.search("tokens",include_outdated=True)})

    def test_disabled_memory_hides_unsupported_notes_without_changing_disk(self):
        bad=self.legacy(self.row("17"))
        self.mem.db.close()
        with patch.dict(os.environ, NEURON_MEMORY="off"):
            self.mem=self.open()
            self.assertEqual(self.mem.search("green tokens"),[])
            self.assertEqual(self.mem.db.execute("SELECT status FROM notes WHERE id=?",(bad,)).fetchone()[0],"verified")

    def test_bad_new_write_and_promotion_are_rejected_but_supported_duplicate_can_recover(self):
        bad=self.row("17")
        text,source=legacy_identity(bad)
        fake={**bad,"version":1,"page_text":self.page}
        self.assertIsNone(self.mem.add("finding",text,source,verified=True,meta={"document_fact":fake}))
        good=self.row("4")
        nid=self.legacy(good,archive=False)
        self.mem.db.close()
        self.mem=self.open()
        text,source=legacy_identity(good)
        self.assertEqual(self.mem.search("tokens"),[])
        self.assertEqual(self.mem.add("finding",text,source,verified=True,meta={"document_fact":document_proof(good,self.page)}),nid)
        self.assertEqual([(h["id"],h["status"],h["uses"]) for h in self.mem.search("tokens")],[(nid,"verified",4)])
