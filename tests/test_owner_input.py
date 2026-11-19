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
