"""Step 7: content quality. Invented facts, leftover template text, filler, repetition and duplicated sections are
caught by rules; a site's planner is told and must fix them; anything invented that survives is removed and recorded.
Sites get pictures: the owner's photos first, on-brand 'Image needed' placeholders offline."""
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("NEURON_DESIGN_HISTORY", os.path.join(tempfile.mkdtemp(prefix="neuron-hist-"), "h.json"))
from neuron.brain.sandbox import Sandbox                        # noqa: E402
from neuron.builder import templates                           # noqa: E402
from neuron.builder.build import build_full                    # noqa: E402
from neuron.design import content as C                         # noqa: E402
from tests.fakes import ScriptedLLM                            # noqa: E402

SBX = Sandbox(timeout=60, mem_mb=256)
REQ = ("Website for Adeyemi & Co, a family law firm in Ikeja, Lagos. We handle divorce, child custody and property disputes. "
       "Phone 0803 412 7788, office at 14 Allen Avenue, Ikeja. Open Monday to Friday, 9am to 5pm. A first consultation costs "
       "25,000 naira. Add a form where people leave their name and phone to book a consultation.")


class CheckTests(unittest.TestCase):
    def test_owner_facts_pass(self):
        good = [("hero:title", "Adeyemi & Co, family law in Ikeja"), ("hero:text", "Advice on divorce, custody and property, in plain words."),
                ("section1:title", "Visit us"), ("section1:text", "14 Allen Avenue, Ikeja. Call 0803-412-7788, Monday to Friday, 9am to 5pm."),
                ("section2:title", "Fees"), ("section2:text", "A first consultation costs 25,000 naira.")]
        self.assertEqual(C.check(good, REQ), [])

    def test_invented_facts_and_template_text_caught(self):
        bad = [("hero:title", "Adeyemi & Co, award-winning lawyers"), ("hero:text", "Over 20 years of experience and 500+ happy clients."),
               ("section1:title", "Testimonials"), ("section1:text", '"They saved my marriage and my sanity, truly wonderful people" - Funmi'),
               ("section2:title", "Contact"), ("section2:text", "Call 0809 111 2222 or email info@adeyemi.com. Open daily, 8am to 8pm. Lorem ipsum."),
               ("section3:title", "Contact"), ("section3:text", "We are passionate about justice and your family.")]
        kinds = {(p["kind"], p["detail"].split(" '")[0]) for p in C.check(bad, REQ)}
        for k in [("invented", "credential"), ("invented", "statistic"), ("invented", "testimonial"), ("invented", "contact detail"),
                  ("invented", "opening hours"), ("placeholder", "leftover template text"), ("filler", "stock phrase"),
                  ("duplicate", "heading")]:
            self.assertIn(k, kinds)

    def test_repetition_and_near_duplicate_sections(self):
        s = "We help families in Ikeja settle property disputes calmly and quickly."
        probs = C.check([("section1:text", s), ("section2:text", s), ("section3:text", "Bread. " * 2)], REQ)
        self.assertIn("repetition", {p["kind"] for p in probs})
        self.assertIn("duplicate", {p["kind"] for p in probs})

    def test_remove_invented_keeps_owner_facts(self):
        spec = {"home": {"headline": "Adeyemi & Co", "subheadline": "Family law in Ikeja. Trusted by 500+ families.", "sections": [
            {"title": "Visit", "text": "14 Allen Avenue, Ikeja. Open daily 8am to 8pm.", "items": []},
            {"title": "Reviews", "text": "", "items": [{"title": "Funmi", "text": "Rated 5 stars by clients."}]}]}, "forms": []}
        removed = C.remove_invented(spec, REQ)
        self.assertEqual(spec["home"]["subheadline"], "Family law in Ikeja.")
        self.assertEqual(spec["home"]["sections"][0]["text"], "14 Allen Avenue, Ikeja.")
        self.assertEqual([s["title"] for s in spec["home"]["sections"]], ["Visit"])
        self.assertEqual(len(removed), 3)


class CoverageTests(unittest.TestCase):
    def test_owner_facts_must_all_be_on_the_page(self):
        spec = {"home": {"headline": "Adeyemi & Co", "subheadline": "Family law in Ikeja.", "sections": [
            {"title": "Fees", "text": "A first consultation costs 25,000 naira.", "items": []}]}, "forms": []}
        missing = {p["fact"] for p in C.missing_facts(REQ, C.spec_pieces(spec))}
        self.assertEqual(missing, {"14 Allen Avenue", "9am", "5pm", "Monday to Friday"})
        self.assertIn('add the owner\'s address "14 Allen Avenue" exactly as given', C.feedback(C.missing_facts(REQ, C.spec_pieces(spec))))

    def test_empty_cards_are_reported(self):
        spec = {"home": {"sections": [{"title": "What we handle", "text": "", "items": [{"title": "Divorce", "text": ""}]}]}}
        self.assertEqual(C.thin_items(spec)[0]["kind"], "thin")

    def test_facts_beside_the_form_are_moved_not_repeated(self):
        from neuron.kit_next import ui
        page = ui.page("Welcome", ui.hero("Adeyemi & Co", "Family law."), ui.section("Visit us", ui.text("14 Allen Avenue, Ikeja.")),
                       ui.section("Book a consultation", ui.form("/b", ui.field("Name", "name"), submit="Book"), id="b"))
        self.assertEqual(str(page).count("14 Allen Avenue, Ikeja."), 1)


SITE = {"app_name": "Adeyemi & Co", "kind": "site", "login_required": False, "username": "", "password": "",
        "home": {"headline": "Adeyemi & Co, family law in Ikeja", "subheadline": "Award-winning lawyers trusted by 500+ families.",
                 "sections": [{"title": "What we handle", "text": "", "items": [
                     {"title": "Divorce", "text": "We guide you through each step."},
                     {"title": "Child custody", "text": "Arrangements that put children first."},
                     {"title": "Property disputes", "text": "Clear advice on who owns what."}]},
                     {"title": "Visit us", "text": "14 Allen Avenue, Ikeja. Monday to Friday, 9am to 5pm. Call 0803 412 7788.", "items": []},
                     {"title": "Fees", "text": "A first consultation costs 25,000 naira.", "items": []}]},
        "forms": [{"name": "bookings", "title": "Book a consultation", "fields": [{"name": "name", "type": "text"}, {"name": "phone", "type": "phone"}],
                   "button": "Book", "thanks": "Thank you, we will call you to confirm."}],
        "entities": [], "dashboard": []}


class Runner:
    def __init__(self, llm):
        self.llm, self.loads = llm, 1

    def client(self, role):
        return self.llm

    def model_for(self, role):
        return "scripted"


@unittest.skipUnless(SBX.available() and shutil.which("node"), "needs bubblewrap and node")
class SiteBuildTests(unittest.TestCase):
    def test_planner_told_about_invented_facts_then_site_has_pictures(self):
        project = Path(tempfile.mkdtemp(prefix="neuron-csite-")) / "site"
        seen = []

        def reply(messages):
            sys_, last = messages[0]["content"], messages[-1]["content"]
            if sys_.startswith("You turn a plain-language request"):
                seen.append(last)
                if "problems" in last:                   # second round: the planner fixed its words
                    fixed = json.loads(json.dumps(SITE))
                    fixed["home"]["subheadline"] = "Clear advice on divorce, custody and property."
                    return json.dumps(fixed)
                return json.dumps(SITE)
            if "check a web page against" in sys_:
                return '{"ok": true, "missing": []}'
            m = re.search(r"# Your task: (\S+)", last)
            spec = json.loads((project / ".neuron" / "spec.json").read_text())["spec"]
            return "```python\n" + templates.reference_files(spec)[m.group(1)] + "```" if m else "ok"
        photos = Path(tempfile.mkdtemp())
        (photos / "our_office.jpg").write_bytes(b"\xff\xd8" + b"x" * 4000)
        r = build_full(project, REQ, Runner(ScriptedLLM([reply] * 40)), SBX, log=lambda *_: None, design=True, photos=[photos / "our_office.jpg"])
        self.assertTrue(r["ok"], r)
        self.assertIn("problems", seen[1])
        self.assertIn("award-winning", seen[1].lower())
        self.assertEqual(r["content_problems"], [])
        home = (project / "pages" / "home.py").read_text()
        self.assertIn('image="static/images/', home)
        self.assertIn("ui.photos(", home)
        m = json.loads((project / "images.json").read_text())["slots"]
        self.assertEqual(sorted(s["status"] for s in m), ["needed", "needed", "owner"])
        self.assertTrue(all((project / s["file"]).exists() for s in m))
        self.assertIn("IMAGE NEEDED", (project / "IMAGE_CREDITS.md").read_text())

    def test_invented_facts_that_survive_are_removed_and_recorded(self):
        project = Path(tempfile.mkdtemp(prefix="neuron-csite-")) / "site"

        def reply(messages):
            sys_, last = messages[0]["content"], messages[-1]["content"]
            if sys_.startswith("You turn a plain-language request"):
                return json.dumps(SITE)                  # never fixes it
            if "check a web page against" in sys_:
                return '{"ok": true, "missing": []}'
            m = re.search(r"# Your task: (\S+)", last)
            spec = json.loads((project / ".neuron" / "spec.json").read_text())["spec"]
            return "```python\n" + templates.reference_files(spec)[m.group(1)] + "```" if m else "ok"
        r = build_full(project, REQ, Runner(ScriptedLLM([reply] * 40)), SBX, log=lambda *_: None, design=True)
        self.assertTrue(r["ok"], r)
        home = (project / "pages" / "home.py").read_text()
        self.assertNotIn("500+", home)
        self.assertNotIn("Award-winning", home)
        self.assertTrue(any(n.startswith("removed subheadline") for n in r["content_notes"]), r["content_notes"])
        self.assertIn('"kind": "content"', (project / ".neuron" / "decisions.jsonl").read_text())


if __name__ == "__main__":
    unittest.main()
