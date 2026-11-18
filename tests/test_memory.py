"""Knowledge memory: storage, hybrid search, notes saved by verified steps, reuse only through the tests, off in evaluations."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from neuron.agent.loop import Agent, Job
from neuron.brain.sandbox import Sandbox
from neuron.memory import Memory, context_text
from neuron.memory.embed import HashEmbedder
from tests.fakes import ScriptedLLM

ROOT = Path(__file__).resolve().parents[1]


class Runner:
    def __init__(self, llm):
        self.llm = llm

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


def mem():
    return Memory(Path(tempfile.mkdtemp()) / "k.db", embedder=HashEmbedder())


class StoreTests(unittest.TestCase):
    def test_add_search_mark_and_duplicates(self):
        m = mem()
        a = m.add("fix", "Pagination off by one: start index used page*size, fixed to (page-1)*size", "job 1", verified=True, tags=["python"])
        m.add("finding", "Members may borrow 8 items at once", "rules.pdf page 1", verified=True)
        self.assertEqual(m.add("fix", "Pagination off by one: start index used page*size, fixed to (page-1)*size", "job 9"), a)   # no duplicate
        hits = m.search("the second page shows the first page's items, pagination bug")
        self.assertEqual(hits[0]["id"], a)
        self.assertEqual(m.search("borrow items members", kinds=("finding",))[0]["kind"], "finding")
        m.mark(a, used=True, helped=True)
        self.assertEqual(m.stats()["helped"], 1)
        m.mark(a, status="outdated")
        self.assertNotIn(a, [h["id"] for h in m.search("pagination off by one")])
        text = context_text(m.search("borrow"))
        self.assertIn("check that each applies", text)

    def test_writes_are_off_in_evaluations(self):
        m = mem()
        os.environ["NEURON_MEMORY"] = "off"
        try:
            self.assertIsNone(m.add("fact", "anything", "x"))
        finally:
            del os.environ["NEURON_MEMORY"]
        self.assertEqual(m.stats()["notes"], 0)

    def test_notes_from_outside_sources_come_back_for_rechecking(self):
        m = mem()
        nid = m.add("fact", "Package foo 1.2 renamed bar() to baz()", "https://example.org/changelog", version="foo 1.2", verified=True)
        m.db.execute("UPDATE notes SET last_checked = 0 WHERE id = ?", (nid,))
        self.assertEqual([n["id"] for n in m.due_for_recheck(days=30)], [nid])


@unittest.skipUnless(Sandbox().available(), "needs bubblewrap")
class AgentMemoryTests(unittest.TestCase):
    def test_verified_fix_is_saved_and_offered_to_the_next_similar_job(self):
        m = mem()
        src = ROOT / "benchmark" / "phase5" / "dev" / "workspaces" / "cpp_grades"
        if not src.exists():
            self.skipTest("dev workspace missing")
        sb = Sandbox(timeout=120, mem_mb=1024, toolchains=True)
        # first job: the scripted reviewer names the function the test output points at; the edit fixes it
        ws1 = Path(tempfile.mkdtemp()) / "a"
        shutil.copytree(src, ws1)
        job = Job(ws1, Runner(None), sb, log=lambda *_: None, memory=m)
        from neuron.agent.capabilities.code import functions_in
        text = (ws1 / "src" / "grades.cpp").read_text() if (ws1 / "src" / "grades.cpp").exists() else None
        if text is None:
            self.skipTest("layout changed")
        fn = [n for n, a, b in functions_in("src/grades.cpp", text) if n == "letter"][0]
        diag = json.dumps({"function": f"src/grades.cpp::{fn}", "problem": "the pass mark compares with > instead of >=", "fix": "use >= 40"})
        edit = "OLD:\n```\n    if (mark > 40) return 'D';\n```\nNEW:\n```\n    if (mark >= 40) return 'D';\n```"
        job.runner = Runner(ScriptedLLM([diag, edit] * 3))
        rep = Agent(job).run("The tests fail. Fix the bug without changing the tests.")
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        notes = m.search("grade boundary comparison bug", kinds=("fix",))
        self.assertTrue(notes and notes[0]["status"] == "verified", notes)
        # second, similar job: memory is searched first and the remembered fix is in front of the model
        ws2 = Path(tempfile.mkdtemp()) / "b"
        shutil.copytree(src, ws2)
        llm2 = ScriptedLLM([diag, edit] * 3)
        job2 = Job(ws2, Runner(llm2), sb, log=lambda *_: None, memory=m)
        rep2 = Agent(job2).run("The tests fail. Fix the bug without changing the tests.")
        self.assertEqual(rep2["verdict"], "VERIFIED", rep2)
        prompts = " ".join(c["messages"][-1]["content"] for c in llm2.calls)
        self.assertIn("Notes from NEURON's earlier work", prompts)
        self.assertGreaterEqual(m.stats()["helped"], 1)                 # credited only because the tests passed again


if __name__ == "__main__":
    unittest.main()
