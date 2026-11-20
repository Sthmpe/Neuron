"""The owner's reply belongs to one pending question on one durable job."""
import tempfile
import unittest
from pathlib import Path

from neuron.agent.capability import Capability, NeedsOwnerInput, Outcome, Registry
from neuron.agent.state import JobState
from tests.test_server import Client, start, wait_for


class AskTwice(Capability):
    name = "answer_question"

    def run(self, job, params):
        turns = params.get("owner_inputs", [])
        if len(turns) < 2:
            raise NeedsOwnerInput(("What date?", "What time?")[len(turns)])
        text = " at ".join(t["answer"] for t in turns)
        (job.workspace / "answer.md").write_text(text)
        return Outcome(True, text, files=["answer.md"])


class OwnerInputTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.registry = Registry()
        self.registry.add(AskTwice())
        self.connect()
        self.addCleanup(self.close)

    def connect(self):
        self.httpd, base = start(self.home, [], self.registry)
        self.phone = Client(base)
        self.phone.call("POST", "/api/pair", {"code": self.httpd.neuron["pairing"].new_code()})

    def close(self):
        jobs = self.httpd.neuron["jobs"]
        jobs.stopping = True
        jobs.wake.set()
        jobs.thread.join(3)
        self.httpd.shutdown()
        self.httpd.server_close()

    def begin(self):
        jid = self.phone.call("POST", "/api/jobs", {"goal": "When is my appointment?"})[1]["id"]
        url = "/api/jobs/" + jid
        self.phone.call("POST", url + "/start")
        detail = wait_for(self.phone, jid, {"waiting_input"})
        self.assertEqual((detail["answer"], detail["outputs"], detail["plan"][0]["tries"]), ("", [], 0))
        self.assertEqual((detail["report"]["verdict"], detail["input_request"]["question"]), ("WAITING_INPUT", "What date?"))
        return jid, url, detail["input_request"]["id"]

    def test_same_job_restarts_and_replies_are_idempotent(self):
        jid, url, first = self.begin()
        self.close()
        self.connect()
        self.assertEqual(self.phone.call("GET", url)[1]["input_request"]["id"], first)
        body = {"id": first, "answer": "Friday"}
        self.assertEqual(Client(self.phone.base).call("POST", url + "/input", body)[0], 401)
        self.assertEqual(self.phone.call("POST", url + "/input", body, headers={"X-Neuron": "0"})[0], 403)
        for bad in [{"id": first, "answer": "  "}, {"id": "old", "answer": "Friday"}, {"id": first, "answer": "a"*1201}]:
            self.assertEqual(self.phone.call("POST", url + "/input", bad)[0], 400)
        for _ in range(2):
            self.assertEqual(self.phone.call("POST", url + "/input", body)[0], 200)
        second = wait_for(self.phone, jid, {"waiting_input"})["input_request"]
        self.assertNotEqual(second["id"], first)
        self.assertEqual(second["question"], "What time?")
        self.assertEqual(self.phone.call("POST", url + "/input", {"id": first, "answer": "Saturday"})[0], 400)
        self.phone.call("POST", url + "/input", {"id": second["id"], "answer": "noon"})
        done = wait_for(self.phone, jid, {"done"})
        self.assertEqual(done["answer"], "Friday at noon")
        self.assertEqual([t["id"] for t in done["thread"]], [jid])
        self.assertEqual(done["plan"][0]["tries"], 1)
        self.assertEqual(self.phone.call("POST", url + "/input", body)[0], 200)

    def test_restart_after_reply_before_queue_write(self):
        jid, _, first = self.begin()
        self.close()
        state = JobState(self.home / "jobs" / jid / "workspace")
        state.answer_input(first, "Monday", accept_new=True)
        self.connect()
        detail = wait_for(self.phone, jid, {"waiting_input"})
        self.assertEqual(detail["input_request"]["question"], "What time?")
        self.assertEqual(detail["owner_inputs"], [{"question": "What date?", "answer": "Monday"}])


class MissingFactTests(unittest.TestCase):
    def test_unsourced_and_reused_numbers_need_an_owner(self):
        from neuron.agent.owner_input import bind_plan
        def bind(value):
            return bind_plan({"operation": "divide", "inputs": [
                {"name": "mass", "value": "18", "question": "What was the mass?"},
                {"name": "volume", "value": value, "question": "Was the volume 12 litres?"}]}, "The sample weighs 18 grams.")
        for guessed in ["12", "18", "?"]:
            field = bind(guessed)["inputs"][1]
            self.assertIsNone(field["value"])
            self.assertEqual(field["question"], "What is the volume?")

    def test_unusable_reply_keeps_the_step_open(self):
        from neuron.agent.loop import Agent
        from tests.test_agent import run
        report, job, model = run("I used 7 litres from my tank. How much is left?", [])
        self.assertEqual(report["verdict"], "WAITING_INPUT")
        for reply in ["not sure", "blue", "12 or 20 litres", "19 litres"]:
            prompt = job.state.task("answer")["input_request"]
            self.assertIn("starting amount", prompt["question"])
            job.state.answer_input(prompt["id"], reply, accept_new=True)
            report = Agent(job).run("")
        self.assertEqual(report["verdict"], "UNVERIFIED")
        self.assertTrue((job.workspace / "answer.md").read_text().startswith("12 litres\n"))
        self.assertEqual(model.calls, [])

    def test_numeric_units_and_words(self):
        from neuron.agent.owner_input import can_calculate, numbers
        self.assertEqual(numbers("twenty-five minutes"), ["25"])
        self.assertEqual(numbers("There were 1,250 more and then −8."), ["1250", "-8"])
        self.assertFalse(can_calculate("I walked 12 km. How fast in km per hour?", ["30 minutes"]))
        self.assertTrue(can_calculate("I walked 12 km. How fast in km per hour?", ["2 hours"]))

    def test_concept_can_ask_using_the_normal_answer_path(self):
        from neuron.agent.loop import Agent
        from tests.test_agent import run
        report, job, _ = run("Which room received the parcel?", ["NEED_INPUT: What room is written on the delivery slip?", "The parcel went to Room B."])
        self.assertEqual(report["verdict"], "WAITING_INPUT")
        prompt = job.state.task("answer")["input_request"]
        job.state.answer_input(prompt["id"], "Room B", accept_new=True)
        self.assertEqual(Agent(job).run("")["verdict"], "UNVERIFIED")
        self.assertIn("Room B", (job.workspace / "answer.md").read_text())

    def test_mixed_units_use_the_requested_scale(self):
        import json
        from neuron.agent.loop import Agent
        from tests.test_agent import run
        plan = {"operation": "divide", "unit": "km/h", "inputs": [
            {"name": "distance", "value": "15", "question": "How far did you go?"},
            {"name": "duration", "value": "?", "question": "How long did you travel?"}]}
        _, job, _ = run("I went 15 km. What was my speed in km per hour?", [json.dumps(plan)])
        for reply in ("30 kg", "30 minutes"):
            prompt = job.state.task("answer")["input_request"]
            job.state.answer_input(prompt["id"], reply, accept_new=True)
            report = Agent(job).run("")
        self.assertEqual(report["verdict"], "UNVERIFIED")
        self.assertTrue((job.workspace / "answer.md").read_text().startswith("30 km per hour\n"))

    def test_explicit_missing_fact_keeps_compound_arithmetic(self):
        from neuron.agent.loop import Agent
        from tests.test_agent import run
        report, job, model = run("What is the balance after adding 9 + 8? I have not given the opening balance.",
                                 ['{"expression":"110+9+8","unit":""}'])
        self.assertEqual(len(model.calls), 0)
        prompt = job.state.task("answer")["input_request"]
        self.assertEqual(prompt["question"], "What is the opening balance?")
        job.state.answer_input(prompt["id"], "110", accept_new=True)
        self.assertEqual(Agent(job).run("")["verdict"], "UNVERIFIED")
        self.assertTrue((job.workspace / "answer.md").read_text().startswith("127\n"))
        self.assertEqual(len(model.calls), 1)
