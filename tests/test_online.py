"""Offline to online (step 6): steps that need the internet wait and resume by themselves; outside actions happen at
most once even across a crash; pictures (owner photos, placeholders, licensed photos with their source); package
upgrades in an isolated copy with tests and rollback. No real network: registries and photo sites are stand-ins."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("NEURON_EMBEDDER", "hash")
from neuron.agent.capability import Capability, Outcome, Verdict, default_registry     # noqa: E402
from neuron.agent.effects import Effects, Uncertain                                     # noqa: E402
from neuron.agent.loop import Agent, Job                                                # noqa: E402
from neuron.media import images                                                         # noqa: E402
from neuron.online import packages                                                      # noqa: E402
from tests.fakes import ScriptedLLM                                                     # noqa: E402


class Runner:
    def client(self, role):
        return ScriptedLLM([])

    def model_for(self, role):
        return "scripted"


class Crash(BaseException):
    """Stands for NEURON's process dying in the middle of an action (power cut, restart)."""


def job(ws, reg, online=False):
    j = Job(ws, Runner(), None, registry=reg, log=lambda *_: None)
    j.online = online
    return j


class EffectsTests(unittest.TestCase):
    def setUp(self):
        self.f = Path(tempfile.mkdtemp()) / "effects.jsonl"
        self.calls = 0

    def act(self):
        self.calls += 1
        return {"n": self.calls}

    def test_done_action_is_never_repeated(self):
        e = Effects(self.f)
        self.assertEqual(e.once("send:1", "send the invoice", self.act), {"n": 1})
        self.assertEqual(Effects(self.f).once("send:1", "send the invoice", self.act), {"n": 1})    # a later session
        self.assertEqual(self.calls, 1)
        self.assertEqual(Effects(self.f).summary()["duplicates_blocked"], 1)

    def test_interrupted_action_asks_instead_of_repeating(self):
        def dies():
            self.calls += 1
            raise Crash()
        with self.assertRaises(Crash):
            Effects(self.f).once("send:2", "send the invoice", dies)
        with self.assertRaises(Uncertain):
            Effects(self.f).once("send:2", "send the invoice", self.act)
        self.assertEqual(self.calls, 1)
        Effects(self.f).resolve("send:2", happened=True)                 # the owner says it went out
        self.assertIsNone(Effects(self.f).once("send:2", "send the invoice", self.act))
        self.assertEqual(self.calls, 1)

    def test_owner_says_it_did_not_happen(self):
        with self.assertRaises(Crash):
            Effects(self.f).once("k", "x", lambda: (_ for _ in ()).throw(Crash()))
        Effects(self.f).resolve("k", happened=False)
        self.assertEqual(Effects(self.f).once("k", "x", self.act), {"n": 1})

    def test_repeat_safe_action_runs_again(self):
        with self.assertRaises(Crash):
            Effects(self.f).once("file", "write a file", lambda: (_ for _ in ()).throw(Crash()), repeat_safe=True)
        self.assertEqual(Effects(self.f).once("file", "write a file", self.act, repeat_safe=True), {"n": 1})


def reg_with(*caps):
    r = default_registry()
    for c in caps:
        r.add(c)
    return r


class BuildThenFetch(Capability):
    """Stands for a builder that made something offline and found it still needs something from the internet."""
    name = "answer_question"
    purpose = "x"

    def run(self, job, params):
        (job.workspace / "site.txt").write_text("built")
        return Outcome(True, "built offline", {"add_tasks": [{"id": "fetch", "capability": "fetch_thing",
                                                               "title": "Fetch photos", "params": {}}]}, files=["site.txt"])

    def verify(self, job, params, out):
        return Verdict(True, [{"id": "built", "pass": True, "detail": ""}], "x")


class FetchThing(Capability):
    name = "fetch_thing"
    purpose = "x"
    needs_internet = True
    runs = 0

    def run(self, job, params):
        FetchThing.runs += 1
        (job.workspace / "photo.jpg").write_bytes(b"x" * 2000)
        return Outcome(True, "fetched", files=["photo.jpg"])

    def verify(self, job, params, out):
        return Verdict((job.workspace / "photo.jpg").exists(), [{"id": "photo", "pass": True, "detail": ""}], "x")


class WaitForInternetTests(unittest.TestCase):
    def test_waits_offline_and_resumes_online(self):
        ws, reg = Path(tempfile.mkdtemp()), reg_with(BuildThenFetch(), FetchThing())
        FetchThing.runs = 0
        rep = Agent(job(ws, reg, online=False)).run("Why is the sky blue?")
        self.assertEqual(rep["tasks"], {"answer": "done", "fetch": "waiting_network"})
        self.assertEqual(rep["waiting_network"], ["fetch"])
        self.assertIn("waiting for the internet", rep["not_done"]["fetch"][0])
        self.assertEqual(rep["verdict"], "PARTIAL")          # never VERIFIED while a step waits
        self.assertEqual(FetchThing.runs, 0)
        rep = Agent(job(ws, reg, online=True)).run("Why is the sky blue?")       # the connection is back
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertEqual(FetchThing.runs, 1)

    def test_job_manager_resumes_waiting_jobs_when_online(self):
        from neuron.server.jobs import JobManager
        home = Path(tempfile.mkdtemp())
        jm = JobManager(home, lambda: Runner(), lambda: None, registry=reg_with(BuildThenFetch(), FetchThing()), log=lambda *_: None)
        jm.online_check = lambda: False
        jid = jm.create("Why is the sky blue?")
        jm.start(jid)
        for _ in range(100):
            if jm.meta(jid)["status"] == "waiting_network":
                break
            time.sleep(0.1)
        self.assertEqual(jm.meta(jid)["status"], "waiting_network")
        jm.online_check = lambda: True
        jm._net_checked = 0
        for _ in range(100):
            if jm.meta(jid)["status"] == "done":
                break
            time.sleep(0.1)
        self.assertEqual(jm.meta(jid)["status"], "done")
        jm.stopping = True


class SendsOnce(Capability):
    """An outside action that is NOT safe to repeat (like sending a message). The first time, NEURON dies right after it."""
    name = "answer_question"
    purpose = "x"
    die = True
    sent = 0

    def run(self, job, params):
        def send():
            SendsOnce.sent += 1
            if SendsOnce.die:
                SendsOnce.die = False
                raise Crash()
            return {"receipt": SendsOnce.sent}
        r = job.effects.once("send:quote-to-client", "send the quote to the client", send)
        return Outcome(True, f"sent ({r})")

    def verify(self, job, params, out):
        return Verdict(True, [{"id": "sent", "pass": True, "detail": ""}], "x")


class CrashTests(unittest.TestCase):
    def test_no_duplicate_after_crash_owner_decides(self):
        ws, reg = Path(tempfile.mkdtemp()), reg_with(SendsOnce())
        SendsOnce.die, SendsOnce.sent = True, 0
        with self.assertRaises(Crash):
            Agent(job(ws, reg)).run("Why is the sky blue?")
        rep = Agent(job(ws, reg)).run("Why is the sky blue?")          # restarted: must not send again on its own
        self.assertEqual(SendsOnce.sent, 1)
        self.assertEqual(rep["tasks"]["answer"], "waiting_approval")
        st = job(ws, reg).state
        ask = [a for a in st.approvals() if a["status"] == "pending"][0]
        self.assertIn("may already have happened", ask["question"])
        st.answer_approval(ask["task"], ask["action"], False)            # owner: it already went out
        st.update_task(ask["task"], status="pending")
        rep = Agent(job(ws, reg)).run("Why is the sky blue?")
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertEqual(SendsOnce.sent, 1)                              # never sent twice


class ImageTests(unittest.TestCase):
    PALETTE = ("#e9b48f", "#7a3e2a", "#c2603e")
    SLOTS = [{"slot": "hero", "purpose": "fresh bread on the counter", "query": "bread bakery"},
             {"slot": "team", "purpose": "the bakers at work", "query": "baker kneading dough"}]

    def project(self):
        p = Path(tempfile.mkdtemp()) / "site"
        p.mkdir()
        return p

    def test_owner_photos_first_matched_by_name(self):
        p, d = self.project(), Path(tempfile.mkdtemp())
        (d / "our_bakers.jpg").write_bytes(b"\xff\xd8" + b"x" * 3000)
        m = images.prepare(p, self.SLOTS, self.PALETTE, owner_photos=[d / "our_bakers.jpg"])
        self.assertEqual(m.get("team")["status"], "owner")
        self.assertEqual(m.get("hero")["status"], "needed")
        self.assertTrue((p / "static/images/team.jpg").exists())

    def test_offline_placeholder_is_on_brand_and_says_image_needed(self):
        p = self.project()
        m = images.prepare(p, self.SLOTS, self.PALETTE)
        svg = (p / m.get("hero")["file"]).read_text()
        self.assertIn("Image needed", svg)
        self.assertIn("fresh bread on the counter", svg)
        self.assertIn(self.PALETTE[2], svg)
        self.assertIn("IMAGE NEEDED", (p / "IMAGE_CREDITS.md").read_text())

    class Provider:
        def __init__(self):
            self.downloads = 0

        def search(self, query, width=1600, limit=12):
            base = {"mime": "image/jpeg", "width": 2400, "height": 1600, "author": "A. Baker", "licence_url": "https://creativecommons.org/licenses/by-sa/4.0"}
            return [dict(base, title="Bakery logo", file_title="File:Logo.jpg", url="u0", page="https://commons/p0", licence="CC BY-SA 4.0"),
                    dict(base, title="Bread", file_title="File:Bread nc.jpg", url="u1", page="https://commons/p1", licence="CC BY-NC 2.0"),
                    dict(base, title="Bread small", file_title="File:Small.jpg", url="u2", page="https://commons/p2", licence="CC BY 4.0", width=400, height=300),
                    dict(base, title=f"Loaves for {query}", file_title="File:Loaves.jpg", url="u3", page=f"https://commons/{query}", licence="CC BY-SA 4.0"),
                    dict(base, title="Other loaves", file_title="File:Loaves2.jpg", url="u4", page="https://commons/p4", licence="CC0")]

        def download(self, cand):
            self.downloads += 1
            import io
            from PIL import Image
            buf = io.BytesIO()
            Image.new("RGB", (2400, 1600), (200, 150, 100)).save(buf, "JPEG")
            return buf.getvalue()

    def test_online_licensed_photo_replaces_placeholder_with_source(self):
        p = self.project()
        m = images.prepare(p, self.SLOTS, self.PALETTE)
        (p / "index.html").write_text('<img src="static/images/hero.svg" alt="">')
        prov = self.Provider()
        r = images.fetch_licensed(m, prov, Effects(p / ".neuron" / "e.jsonl"), log=lambda *_: None)
        self.assertEqual(sorted(r["filled"]), ["hero", "team"])
        hero = images.Manifest(p).get("hero")
        self.assertEqual(hero["status"], "licensed")
        self.assertEqual(hero["source"]["licence"], "CC BY-SA 4.0")          # NC, logo and too-small photos were refused
        self.assertEqual(hero["source"]["author"], "A. Baker")
        self.assertIn('static/images/hero.jpg', (p / "index.html").read_text())
        self.assertFalse((p / "static/images/hero.svg").exists())
        credits = (p / "IMAGE_CREDITS.md").read_text()
        self.assertIn("https://commons/bread bakery", credits)
        self.assertIn("CC BY-SA 4.0", credits)
        self.assertNotEqual(images.Manifest(p).get("team")["source"]["page"], hero["source"]["page"])   # no photo used twice

    def test_find_images_step_waits_offline_then_fills(self):
        from neuron.agent.capabilities.media import FindImages

        class Builds(BuildThenFetch):
            def run(self, job, params):
                images.prepare(job.workspace / "site", ImageTests.SLOTS, ImageTests.PALETTE)
                return Outcome(True, "site built", {"add_tasks": [{"id": "images", "capability": "find_images",
                                                                    "title": "Find licensed photos", "params": {"project": "site"}}]})
        fi = FindImages()
        fi.provider_factory = ImageTests.Provider
        ws, reg = Path(tempfile.mkdtemp()), reg_with(Builds(), fi)
        rep = Agent(job(ws, reg, online=False)).run("Why is the sky blue?")
        self.assertEqual(rep["tasks"]["images"], "waiting_network")
        rep = Agent(job(ws, reg, online=True)).run("Why is the sky blue?")
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertEqual(images.Manifest(ws / "site").summary(), {"licensed": 2})

    def test_rejected_photo_goes_back_to_placeholder_and_is_never_picked_again(self):
        p = self.project()
        m = images.prepare(p, self.SLOTS, self.PALETTE)
        (p / "index.html").write_text('<img src="static/images/hero.svg">')
        images.fetch_licensed(m, self.Provider(), log=lambda *_: None)
        m = images.Manifest(p)
        first = m.get("hero")["source"]["page"]
        images.reject(m, "hero", self.PALETTE, "not right for this business")
        m = images.Manifest(p)
        self.assertEqual(m.get("hero")["status"], "needed")
        self.assertIn("static/images/hero.svg", (p / "index.html").read_text())
        images.fetch_licensed(m, self.Provider(), log=lambda *_: None)
        self.assertNotEqual(images.Manifest(p).get("hero")["source"]["page"], first)
        self.assertEqual(images.Manifest(p).rejected[0]["why"], "not right for this business")

    def test_artworks_are_refused(self):
        c = {"mime": "image/jpeg", "title": "Allegory of war and Law - Prunksaal", "file_title": "File:A.jpg", "width": 3000,
             "height": 2000, "licence": "CC BY 2.5"}
        self.assertIn("not a photo", images.acceptable(c))

    def test_licence_rules(self):
        ok = lambda lic: images.acceptable({"mime": "image/jpeg", "title": "Bread", "file_title": "File:B.jpg", "width": 2000,
                                            "height": 1300, "licence": lic}) == ""
        for lic in ("CC BY-SA 4.0", "CC BY 2.0", "CC0", "Public domain"):
            self.assertTrue(ok(lic), lic)
        for lic in ("CC BY-NC 2.0", "CC BY-ND 4.0", "Fair use", "", "All rights reserved"):
            self.assertFalse(ok(lic), lic)


class PackageTests(unittest.TestCase):
    REGISTRY = {"https://pypi.org/pypi/requests/json": {"info": {"version": "2.32.3", "project_urls": {"Documentation": "https://docs/requests"}}},
                "https://pypi.org/pypi/six/json": {"info": {"version": "1.17.0", "project_urls": {"Changelog": "https://six/changes"}}},
                "https://pypi.org/pypi/attrs/json": {"info": {"version": "24.2.0rc1"}},
                "https://registry.npmjs.org/left-pad/latest": {"version": "1.3.0", "homepage": "https://lp"}}

    def project(self):
        p = Path(tempfile.mkdtemp()) / "proj"
        p.mkdir()
        (p / "requirements.txt").write_text("requests==2.31.0  # http\nsix==1.15.0\nattrs==23.1.0\nflask>=2\n")
        (p / "package.json").write_text(json.dumps({"dependencies": {"left-pad": "^1.1.0", "x": "*"}}))
        return p

    def fetch(self, url):
        return self.REGISTRY[url]

    def test_outdated_reads_pins_and_skips_prereleases(self):
        out = {o["name"]: o for o in packages.outdated(self.project(), self.fetch)}
        self.assertEqual(sorted(out), ["left-pad", "requests", "six"])          # attrs: only a release candidate is newer
        self.assertEqual(out["requests"]["latest"], "2.32.3")
        self.assertEqual(out["requests"]["docs"], {"Documentation": "https://docs/requests"})

    def _failing_tester(self, bad):
        def tester(folder, sandbox, cmd, manager):
            text = (folder / "requirements.txt").read_text()
            return (not any(b in text for b in bad)), "ran"
        return tester

    def test_upgrade_keeps_only_what_passes_and_backs_up(self):
        p = self.project()
        (p / "package.json").unlink()
        rep = packages.upgrade(p, None, ["python3", "-m", "unittest"], fetch=self.fetch, effects=Effects(p / ".neuron" / "e.jsonl"),
                               installer=lambda f, m: (True, "ok"), tester=self._failing_tester(["six==1.17.0"]), log=lambda *_: None)
        self.assertEqual([u["name"] for u in rep["upgraded"]], ["requests"])
        self.assertEqual([k["name"] for k in rep["kept_back"]], ["six"])
        req = (p / "requirements.txt").read_text()
        self.assertIn("requests==2.32.3  # http", req)
        self.assertIn("six==1.15.0", req)
        self.assertIn("flask>=2", req)
        self.assertEqual(packages.rollback(p).name[:2], "20")               # the owner can go back
        self.assertIn("requests==2.31.0", (p / "requirements.txt").read_text())

    def test_nothing_upgraded_when_tests_already_fail_or_missing(self):
        p = self.project()
        (p / "package.json").unlink()
        rep = packages.upgrade(p, None, ["python3", "-m", "unittest"], fetch=self.fetch, installer=lambda f, m: (True, "ok"),
                               tester=lambda *a: (False, "1 failed"), log=lambda *_: None)
        self.assertEqual(rep["upgraded"], [])
        self.assertIn("fail even with the current versions", rep["kept_back"][0]["why"])
        rep = packages.upgrade(p, None, None, fetch=self.fetch, log=lambda *_: None)
        self.assertEqual(rep["upgraded"], [])
        self.assertIn("no tests", rep["summary"])
        self.assertIn("requests==2.31.0", (p / "requirements.txt").read_text())

    def test_failed_install_is_rolled_back_by_discarding_the_copy(self):
        p = self.project()
        (p / "package.json").unlink()
        before = (p / "requirements.txt").read_text()
        rep = packages.upgrade(p, None, ["python3", "-m", "unittest"], fetch=self.fetch,
                               installer=lambda f, m: (("requests==2.32.3" not in (f / "requirements.txt").read_text()), "no wheel"),
                               tester=lambda *a: (True, "ok"), log=lambda *_: None)
        self.assertEqual([u["name"] for u in rep["upgraded"]], ["six"])
        self.assertIn("install failed", rep["kept_back"][0]["why"])
        self.assertNotEqual(before, (p / "requirements.txt").read_text())
        self.assertIn("requests==2.31.0", (p / "requirements.txt").read_text())

    def test_npm_pins_keep_their_prefix(self):
        p = self.project()
        out = [o for o in packages.outdated(p, self.fetch) if o["manager"] == "npm"]
        packages.write_pins(p, out)
        self.assertEqual(json.loads((p / "package.json").read_text())["dependencies"], {"left-pad": "^1.3.0", "x": "*"})

    def test_memory_notes_carry_source_and_version(self):
        rep = {"outdated": [{"manager": "pip", "name": "six", "current": "1.15.0", "latest": "1.17.0", "docs": {"Changelog": "https://six/changes"}}]}
        n = packages.memory_notes(rep, "2026-11-18")[0]
        self.assertEqual((n["version"], n["source"], n["verified"]), ("1.17.0", "https://pypi.org/pypi/six/json", True))
        self.assertIn("checked 2026-11-18", n["text"])


if __name__ == "__main__":
    unittest.main()


class RecheckTests(unittest.TestCase):
    def test_old_notes_rechecked_when_online(self):
        from neuron.memory import Memory
        from neuron.memory.recheck import recheck
        m = Memory(Path(tempfile.mkdtemp()) / "k.db")
        a = m.add("fact", "six 1.16.0 is the newest stable release on PyPI (checked 2026-01-01).", "https://pypi.org/pypi/six/json",
                  version="1.16.0", verified=True, tags=("package", "pip", "six"))
        b = m.add("finding", "The harbour market opens at 6am.", "https://example.org/gone", version="", verified=True)
        c = m.add("finding", "Fish prices rise in December.", "https://example.org/live", version="", verified=True)
        m.db.execute("UPDATE notes SET last_checked = 0")
        m.db.commit()
        r = recheck(m, fetch=lambda url: {"info": {"version": "1.17.0"}}, alive=lambda url: not url.endswith("gone"), log=lambda *_: None)
        self.assertEqual((r["outdated"], r["unverified"], r["unchanged"]), (1, 1, 1))
        status = {row["id"]: row["status"] for row in m.db.execute("SELECT id, status FROM notes")}
        self.assertEqual((status[a], status[b], status[c]), ("outdated", "unverified", "verified"))
        found = m.search("newest release of six", k=3)
        self.assertTrue(any("1.17.0" in n["text"] for n in found))
        self.assertFalse(any("1.16.0 is" in n["text"] for n in found))       # outdated notes are kept but not returned
        self.assertEqual(recheck(m, fetch=lambda u: {}, alive=lambda u: True, log=lambda *_: None)["checked"], 0)   # nothing due now


class RateLimitTests(unittest.TestCase):
    def test_slow_down_answer_stops_asking_and_resumes_later(self):
        from neuron.agent.capabilities.media import FindImages

        class Limited(ImageTests.Provider):
            calls = 0

            def download(self, cand):
                Limited.calls += 1
                if Limited.calls == 2:
                    raise images.RateLimited("slow down", 900)
                return super().download(cand)

        class Builds(BuildThenFetch):
            def run(self, job, params):
                images.prepare(job.workspace / "site", ImageTests.SLOTS, ImageTests.PALETTE)
                return Outcome(True, "site built", {"add_tasks": [{"id": "images", "capability": "find_images",
                                                                    "title": "Find licensed photos", "params": {"project": "site"}}]})
        fi = FindImages()
        fi.provider_factory = Limited
        ws, reg = Path(tempfile.mkdtemp()), reg_with(Builds(), fi)
        rep = Agent(job(ws, reg, online=True)).run("Why is the sky blue?")
        self.assertEqual(rep["tasks"]["images"], "waiting_network")
        self.assertGreater(rep["retry_at"], time.time() + 800)              # at least what the site asked for
        self.assertEqual(images.Manifest(ws / "site").summary(), {"licensed": 1, "needed": 1})   # the first photo is kept
        self.assertIn("tries again by itself", rep["not_done"]["images"][0])
        rep = Agent(job(ws, reg, online=True)).run("Why is the sky blue?")  # too early: does not ask again
        self.assertEqual(Limited.calls, 2)
        j = job(ws, reg, online=True)
        j.state.update_task("images", not_before=0)                         # time has passed
        rep = Agent(j).run("Why is the sky blue?")
        self.assertEqual(rep["verdict"], "VERIFIED", rep)
        self.assertEqual(images.Manifest(ws / "site").summary(), {"licensed": 2})
