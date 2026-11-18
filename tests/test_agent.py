"""The general agent, end to end, with a scripted stand-in for the model. Real files, real LibreOffice,
real sandboxed builds; only the model's words are scripted."""
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("NEURON_DESIGN_HISTORY", os.path.join(tempfile.mkdtemp(prefix="neuron-hist-"), "h.json"))
from neuron.agent.capability import Capability, Outcome, Registry, Verdict, default_registry   # noqa: E402
from neuron.agent.loop import Agent, Job                                              # noqa: E402
from neuron.agent.router import rule_guess                                            # noqa: E402
from neuron.brain.sandbox import Sandbox                                              # noqa: E402
from tests.fakes import ScriptedLLM                                                   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
P5 = ROOT / "benchmark" / "phase5"
SBX = Sandbox(timeout=120, mem_mb=1024, toolchains=True)
HAS_LO = shutil.which("soffice") is not None


class Runner:
    def __init__(self, llm):
        self.llm = llm

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


def run(request, replies, attachments=(), workspace=None, registry=None):
    ws = Path(workspace or tempfile.mkdtemp(prefix="neuron-job-"))
    llm = ScriptedLLM(replies)
    job = Job(ws, Runner(llm), SBX, registry=registry, log=lambda *_: None)
    return Agent(job).run(request, attachments), job, llm


class RouterTests(unittest.TestCase):
    def test_kinds(self):
        g = lambda r, a=(): rule_guess(r, a)[0]
        self.assertEqual(g("Make an Excel workbook from this data", ["x.csv"]), "excel")
        self.assertEqual(g("Write memo.docx to staff about parking"), "word")
        self.assertEqual(g("Create a 5-slide presentation about our shop"), "pptx")
        self.assertEqual(g("What does page 3 say about refunds?", ["policy.pdf"]), "pdf_qa")
        self.assertEqual(g("Write a C++ command-line program that counts words"), "build_program")
        self.assertEqual(g("Build a landing page for my bakery"), "web_app")
        self.assertEqual(g("Why is the sky blue?"), "answer")

    def test_named_output_file_decides(self):
        """Found by the clean-setup release retest: 'Write letter.docx ... asking to fix the leaking roof' became a code fix."""
        from neuron.agent.router import understand

        class J:
            workspace = None

            def ask_json(self, *a, **k):
                raise AssertionError("the model must not be asked when the file is named")
        self.assertEqual(understand(J(), "Write letter.docx to the landlord asking to fix the leaking roof.")[0], "word")
        self.assertEqual(understand(J(), "Fix the totals and save fixed.xlsx")[0], "excel")


@unittest.skipUnless(HAS_LO, "LibreOffice is not installed")
class DocumentJobTests(unittest.TestCase):
    def test_excel_job_is_verified_by_recalculation(self):
        plan = {"group_by": "category", "measures": [{"label": "Total", "op": "sum", "columns": ["amount"]}], "total_row": True, "share_of": ""}
        rep, job, _ = run("Make expenses.xlsx: rows on a sheet Data; a sheet Summary with the total per category and a Total row, using formulas.",
                          [json.dumps(plan)], [str(P5 / "sources" / "dev_expenses.csv")])
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertIn("expenses.xlsx", rep["files"])
        import sys
        sys.path.insert(0, str(P5 / "examiners"))
        import docs
        ex = docs.excel_simple(job.workspace / "expenses.xlsx", P5 / "sources" / "dev_expenses.csv", "category", "amount")
        self.assertEqual(ex["passed"], ex["total"], ex)

    def test_word_job_reworks_when_too_short(self):
        outline = {"title": "New office hours", "sections": [{"heading": h, "points": "x"} for h in ("Change", "Reason", "Questions")]}
        short, long = "Brief note.", " ".join(["The office will open at eight and close at four from the first of May."] * 6)
        rep, job, llm = run("Write memo.docx to staff about the new office hours (8am to 4pm from 1 May) with headings Change, Reason, Questions. 120 to 300 words.",
                            [json.dumps(outline), short, short, short, long, long, long])
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        decisions = (job.state.dir / "decisions.jsonl").read_text()
        self.assertIn('"kind": "rework"', decisions)

    def test_pptx_job_renders(self):
        plan = {"name": "Golden Crust", "tagline": "Bread baked at dawn", "slides": [{"title": "What we bake", "bullets": ["Sourdough", "Cakes"]},
                                                                                      {"title": "How to order", "bullets": ["Call us", "Visit the shop"]}]}
        rep, job, _ = run("Make a 3-slide deck called intro.pptx introducing our bakery Golden Crust: title, what we bake, how to order.", [json.dumps(plan)])
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertTrue((job.workspace / ".neuron" / "job" / "deck_render.pdf").exists())


class ResearchJobTests(unittest.TestCase):
    def test_wrong_quote_is_caught_and_retried(self):
        req = "Answer from the attached PDF with page numbers.\n1. How many items may a member borrow at once?"
        bad = json.dumps({"answer": "8", "doc": "dev_library_rules", "page": 2, "quote": "Members may borrow up to 8 items"})
        good = json.dumps({"answer": "8 items", "doc": "dev_library_rules", "page": 1, "quote": "Members may borrow up to 8 items at a time"})
        rep, job, _ = run(req, [bad, good], [str(P5 / "sources" / "dev_library_rules.pdf")])
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        answers = json.loads((job.workspace / "answers.json").read_text())
        self.assertEqual(answers[0]["page"], 1)


@unittest.skipUnless(SBX.available(), "bubblewrap missing")
class CodeJobTests(unittest.TestCase):
    def test_cpp_bug_is_fixed_and_proven_by_the_tests(self):
        ws = Path(tempfile.mkdtemp()) / "ws"
        shutil.copytree(P5 / "dev" / "workspaces" / "cpp_grades", ws)
        diag = json.dumps({"function": "src/grades.cpp::letter", "problem": "40 should be a D", "fix": "use >= 40"})
        edit = "OLD:\n```\n    if (mark > 40) return 'D';\n```\nNEW:\n```\n    if (mark >= 40) return 'D';\n```"
        rep, job, _ = run("Fix the bug: the tests fail.", [diag, edit], workspace=ws)
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertIn(">= 40", (ws / "src" / "grades.cpp").read_text())

    def test_failed_change_is_rolled_back(self):
        ws = Path(tempfile.mkdtemp()) / "ws"
        shutil.copytree(P5 / "dev" / "workspaces" / "cpp_grades", ws)
        before = (ws / "src" / "grades.cpp").read_text()
        diag = json.dumps({"function": "src/grades.cpp::average", "problem": "wrong", "fix": "x"})
        bad = "OLD:\n```\n    if (marks.empty()) return 0.0;\n```\nNEW:\n```\n    if (marks.empty()) return 1.0;\n```"
        rep, job, _ = run("Fix the bug: the tests fail.", [diag, bad] * 3, workspace=ws)
        self.assertEqual(rep["verdict"], "PARTIAL")
        self.assertEqual((ws / "src" / "grades.cpp").read_text(), before)

    def test_docstrings_job_resumes_after_a_kill(self):
        ws = Path(tempfile.mkdtemp()) / "ws"
        shutil.copytree(ROOT / "benchmark" / "workspaces" / "clinic", ws)

        class Killed(BaseException):
            pass
        doc = "Explains what this function does with its inputs and returns the result."
        replies = [doc] * 6 + [Killed()]
        with self.assertRaises(Killed):
            run("Add a clear docstring to every function in the source code (not the tests). Do not change behaviour; tests must pass.", replies, workspace=ws)
        done_before = json.loads((ws / ".neuron" / "job" / "documented.json").read_text())
        self.assertEqual(len(done_before), 6)
        rep, job, llm = run("ignored on resume", [doc] * 60, workspace=ws)
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        done_after = json.loads((ws / ".neuron" / "job" / "documented.json").read_text())
        self.assertEqual(done_after[:6], done_before)          # nothing redone
        self.assertEqual(len(done_after), len(set(done_after)))


class DocstringPlaceholderTests(unittest.TestCase):
    def test_placeholder_docstrings_are_reported_not_verified(self):
        """Found by the locked L12 rerun: a placeholder docstring (model reply too short, twice) was called VERIFIED."""
        ws = Path(tempfile.mkdtemp()) / "ws"
        shutil.copytree(ROOT / "benchmark" / "workspaces" / "clinic", ws)
        doc = "Explains what this function does with its inputs and returns the result."
        replies = ["ok", "fine"] + [doc] * 80                     # the first function gets two useless replies
        rep, job, llm = run("Add a clear docstring to every function in the source code (not the tests). Do not change behaviour; tests must pass.",
                            replies, workspace=ws)
        self.assertNotEqual(rep["verdict"], "VERIFIED", rep)
        ph = json.loads((ws / ".neuron" / "job" / "placeholders.json").read_text())
        self.assertEqual(len(ph), 1)

    def test_one_short_reply_is_retried(self):
        ws = Path(tempfile.mkdtemp()) / "ws"
        shutil.copytree(ROOT / "benchmark" / "workspaces" / "clinic", ws)
        doc = "Explains what this function does with its inputs and returns the result."
        rep, job, llm = run("Add a clear docstring to every function in the source code (not the tests). Do not change behaviour; tests must pass.",
                            ["ok"] + [doc] * 80, workspace=ws)
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertFalse((ws / ".neuron" / "job" / "placeholders.json").exists())


class HonestyTests(unittest.TestCase):
    def test_missing_tool_is_reported_not_faked(self):
        class NeedsFlutter(Capability):
            name = "answer_question"
            purpose = "x"
            requires = {"binaries": ["flutter-not-installed"], "modules": []}

            def run(self, job, params):
                return Outcome(True, "should never run")
        reg = default_registry()
        reg.add(NeedsFlutter())
        rep, job, _ = run("Why is the sky blue?", [], registry=reg)
        self.assertEqual(rep["verdict"], "FAILED")
        self.assertIn("not installed", rep["failed"]["answer"])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("g++"), "needs g++")
class NewProgramTests(unittest.TestCase):
    CPP = r'''#include <fstream>
#include <iostream>
#include <string>
int main(int argc, char** argv) {
    if (argc < 2) return 1;
    std::ifstream f(argv[1]); std::string line; int n = 0;
    while (std::getline(f, line)) n++;
    std::cout << "lines: " << n << std::endl;
}
'''
    REF = "import sys\nprint('lines:', sum(1 for _ in open(sys.argv[1])))\n"

    def plan(self, wrong_expectation):
        return json.dumps({"files": [{"path": "src/main.cpp", "purpose": "count lines"}], "examples": [
            {"args": ["lc", "a.txt"], "files": [{"name": "a.txt", "content": "x\ny\nz\n"}], "stdout": "lines: 3"},          # program name included
            {"args": ["b.txt"], "files": [{"name": "b.txt", "content": "1\n2\n3\n4\n5\n"}], "stdout": wrong_expectation}]})

    def test_wrong_hand_written_example_is_settled_by_an_independent_version(self):
        rep, job, _ = run("Write a C++17 program called lc that prints 'lines: N' for the text file given as the first argument.",
                          [self.plan("lines: 4"), "```cpp\n" + self.CPP + "```", "```python\n" + self.REF + "```"])
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        r = job.state.task("write")["result"]
        self.assertEqual((r["examples_passed"], r["examples_agreed"]), (1, 1))
        self.assertIn("taken as wrong", r["notes"][0])

    def test_program_wrong_and_reference_disagrees_is_not_verified(self):
        bad = self.CPP.replace("n++", "n += 2")
        rep, job, _ = run("Write a C++17 program called lc that prints 'lines: N' for the text file given as the first argument.",
                          [self.plan("lines: 5"), "```cpp\n" + bad + "```", "```python\n" + self.REF + "```"] + ["```cpp\n" + bad + "```"] * 12)
        self.assertNotEqual(rep["verdict"], "VERIFIED")


class GapTests(unittest.TestCase):
    def test_requested_features_the_builder_cannot_make_are_found(self):
        from neuron.builder.spec import unsupported_features as u
        gaps = u("A shop app with products and orders. Show order totals and total revenue on the dashboard, and add tests.")
        self.assertEqual(len(gaps), 3, gaps)
        self.assertEqual(u("A clinic app with patients, their blood test results and how many visits there were."), [])

    def test_a_step_with_only_stated_gaps_is_partial_delivered_and_not_retried(self):
        class Gappy(Capability):
            name = "answer_question"
            purpose = "x"
            calls = 0

            def run(self, job, params):
                Gappy.calls += 1
                (job.workspace / "app.txt").write_text("built part")
                return Outcome(True, "built what it could", files=["app.txt"])

            def verify(self, job, params, outcome):
                return Verdict(False, [{"id": "built", "pass": True, "detail": ""},
                                       {"id": "every_requested_feature_built", "pass": False, "gap": True, "detail": "charts"}], "test")
        reg = default_registry()
        reg.add(Gappy())
        rep, job, _ = run("Why is the sky blue?", [], registry=reg)
        self.assertEqual(rep["verdict"], "PARTIAL", rep)
        self.assertIn("app.txt", rep["files"])
        self.assertEqual(Gappy.calls, 1)
        self.assertEqual(list(rep["not_done"].values()), [["charts"]])


class AnswerFactsTests(unittest.TestCase):
    def test_answer_numbers_must_be_in_the_quote(self):
        from neuron.agent.capabilities.research import facts_backed as f
        self.assertFalse(f("How much does a student pay?", "Half the adult fare.", "Students pay half the adult fare of 300."))
        self.assertTrue(f("How much does a student pay?", "150 naira.", "Students pay 150 naira, half the adult fare."))
        self.assertFalse(f("Which area uses most?", "Northbank, 31,200 litres.", "Old Town used 19,500 litres."))
        self.assertTrue(f("Which area uses most?", "Northbank.", "Northbank used the most water."))


class WebAppOutcomeTests(unittest.TestCase):
    def test_summary_is_plain_and_the_whole_app_is_one_download(self):
        """Found on the real install's phone page: a raw dictionary as the summary, and only app.py to download."""
        import zipfile
        from neuron.agent.capabilities import web
        ws = Path(tempfile.mkdtemp())
        (ws / "app" / "pages").mkdir(parents=True)
        (ws / "app" / "app.py").write_text("print(1)\n")
        (ws / "app" / "pages" / "books.py").write_text("x = 1\n")
        (ws / "app" / "data.db").write_text("secret rows")

        def fake_build(project, request, runner, sandbox, **k):
            return {"ok": True, "tasks": {"schema": {"status": "done", "made_by": "code"}, "books": {"status": "done", "made_by": "model"}},
                    "made_by": {"model": 1, "code": 1}, "llm": {"calls": 2, "tokens": 10, "seconds": 1.0}, "design": {"fails": 0, "by_rule": {}}}

        class J:
            workspace, design, runner = ws, True, None
            state = type("S", (), {"goal": lambda self: {"request": "a bookshop app"}})()

            def log(self, m):
                pass

            def count(self, *a):
                pass
        real = web.build_full
        web.build_full = fake_build
        try:
            cap = web.BuildWebApp()
            out = cap.run(J(), {})
            verdict = cap.verify(J(), {}, out)
        finally:
            web.build_full = real
        self.assertIn("database (code), books page (model)", out.summary)
        self.assertNotIn("{", out.summary)
        names = zipfile.ZipFile(ws / "app.zip").namelist()
        self.assertIn("app/pages/books.py", names)
        self.assertNotIn("app/data.db", names)                    # the app's own data never goes into the download
        self.assertEqual([c["detail"] for c in verdict.checks if c["id"] == "design_checks"], ["no problems found"])


class ThinkingTests(unittest.TestCase):
    def test_numeric_question_is_computed_in_the_sandbox_and_checked(self):
        replies = ["Let me compute.\n```python\nprint(17 * 23 + 4)\n```",
                   "The program printed 395.\nAnswer: 395",
                   "The arithmetic is right.\nAnswer: 395"]
        rep, job, llm = run("How much is 17 times 23 plus 4?", replies)
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        text = (job.workspace / "answer.md").read_text()
        self.assertIn("395", text)
        self.assertIn("1 Python run", text)
        self.assertIn("Output of your program:\n395", llm.calls[1]["messages"][-1]["content"])   # the real result was fed back

    def test_check_pass_can_correct_the_first_answer(self):
        from neuron.agent.thinking import solve
        from tests.fakes import ScriptedLLM
        llm = ScriptedLLM(["12 + 30 = 41. Answer: 41", "12 + 30 is 42, not 41. Answer: 42"])
        s = solve(lambda m, n: llm.chat(m, max_tokens=n), None, "What is 12 + 30?")
        self.assertEqual((s["first_answer"], s["answer"], s["calls"]), ("41", "42", 2))
