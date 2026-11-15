"""The model planner: planning, validation, fallback, and the review/revise loop.
The model itself is replaced by a scripted test double (tests/fakes.py)."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from neuron.brain.llm import LlamaClient, LLMUnavailable
from neuron.brain.planner import LlamaCppPlanner
from neuron.brain.report import build_report, report_text
from tests.fakes import ScriptedLLM
from tests.helpers import Rig


def plan_json(*steps):
    return json.dumps({"steps": [{"tool": t, "inputs": i, "why": w} for t, i, w in steps]})


def review_json(decision, reason="because", steps=()):
    return json.dumps({"decision": decision, "reason": reason,
                       "steps": [{"tool": t, "inputs": i, "why": w} for t, i, w in steps]})


ANSWER = ("answer", {"question": "What is 2+2?"}, "answer it")


class PlanningTests(unittest.TestCase):
    def test_valid_plan_is_accepted(self):
        llm = ScriptedLLM([plan_json(ANSWER)])
        plan = LlamaCppPlanner(client=llm).plan("What is 2+2")
        self.assertEqual(plan.planner, "llama.cpp:scripted-test-double")
        self.assertEqual([(s.no, s.action, s.params) for s in plan], [(1, "answer", {"question": "What is 2+2?"})])
        prompt = llm.calls[0]["messages"][0]["content"]
        self.assertIn('"fix_code"', prompt)                       # the model was shown the tools
        self.assertNotIn("search_directory", prompt)              # but not the recipe-internal ones
        self.assertEqual(llm.calls[0]["json_schema"]["properties"]["steps"]["items"]["properties"]["tool"]["enum"],
                         ["answer", "fix_code"])

    def test_flags_come_from_the_tool_not_from_the_model(self):
        sneaky = json.dumps({"steps": [{"tool": "answer", "inputs": {"question": "hi"}, "why": "x",
                                        "needs_internet": True, "sensitive": True}]})
        step = LlamaCppPlanner(client=ScriptedLLM([sneaky])).plan("say hi")[0]
        self.assertEqual((step.needs_internet, step.sensitive), (False, False))

    def test_garbage_twice_falls_back_to_rules(self):
        llm = ScriptedLLM(["I think we should...", "still not json"])
        plan = LlamaCppPlanner(client=llm).plan("What is the capital of France?")
        self.assertTrue(plan.planner.startswith("rule-based (fallback:"), plan.planner)
        self.assertEqual([s.action for s in plan], ["answer"])
        self.assertEqual(len(llm.calls), 2)

    def test_bad_plan_can_be_repaired_once(self):
        bad = plan_json(("teleport", {}, "x"))
        llm = ScriptedLLM([bad, plan_json(ANSWER)])
        plan = LlamaCppPlanner(client=llm).plan("What is 2+2")
        self.assertEqual(plan.planner, "llama.cpp:scripted-test-double")
        self.assertIn("unknown tool 'teleport'", llm.calls[1]["messages"][-1]["content"])

    def test_wrong_inputs_are_rejected(self):
        for bad in (plan_json(("fix_code", {}, "x")),                            # required input missing
                    plan_json(("answer", {"question": "q", "volume": 11}, "x")),  # unknown input
                    plan_json(*[ANSWER] * 9),                                     # too many steps
                    json.dumps({"steps": []}), json.dumps({"steps": "answer"}), json.dumps([1, 2])):
            plan = LlamaCppPlanner(client=ScriptedLLM([bad, bad])).plan("Why is the sky blue?")
            self.assertTrue(plan.planner.startswith("rule-based (fallback:"), bad)

    def test_unreachable_model_falls_back(self):
        plan = LlamaCppPlanner(client=ScriptedLLM([LLMUnavailable("down")])).plan("Why is the sky blue?")
        self.assertIn("model not reachable", plan.planner)
        self.assertEqual([s.action for s in plan], ["answer"])

    def test_known_recipe_is_not_sent_to_the_model(self):
        llm = ScriptedLLM([])
        plan = LlamaCppPlanner(client=llm).plan("find leads")
        self.assertEqual(len(plan), 20)
        self.assertEqual(llm.calls, [])

    def test_rule_based_fix_and_question_plans(self):
        from neuron.brain.planner import RuleBasedPlanner
        folder = tempfile.mkdtemp(prefix="neuron-proj-")
        plan = RuleBasedPlanner().plan(f"Fix the failing tests in {folder}")
        self.assertEqual([(s.action, s.params) for s in plan], [("fix_code", {"project": folder})])
        self.assertEqual([s.action for s in RuleBasedPlanner().plan("How do magnets work")], ["answer"])


class LoopTests(unittest.TestCase):
    def rig(self, replies):
        self.llm = ScriptedLLM(replies)
        r = Rig(planner=LlamaCppPlanner(client=self.llm), services={"llm": self.llm, "sandbox": None})
        self.addCleanup(r.close)
        return r

    def test_plan_run_review_done(self):
        r = self.rig([plan_json(ANSWER), "Four.", review_json("continue", "answered")])
        tid = r.engine.submit("What is 2+2")
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "done")
        self.assertEqual(r.store.steps(tid)[0]["result"], {"answer": "Four."})
        review_prompt = self.llm.calls[2]["messages"][1]["content"]
        self.assertIn("Four.", review_prompt)                      # the model saw the step's result
        rep = build_report(r.store, r.world, tid)
        self.assertIn("NOT independently checked", rep["verdict"])
        self.assertIn("checked: NO", report_text(rep))
        self.assertTrue(any("reviewed step 1" in e["message"] for e in r.store.events(tid)))

    def test_failed_step_then_another_approach(self):
        r = self.rig([plan_json(("fix_code", {"project": "/no/such/folder"}, "fix it")),
                      review_json("revise", "the folder does not exist, explain instead", [ANSWER]),
                      "It is 4.", review_json("continue")])
        tid = r.engine.submit("sort this out")
        r.run()
        task = r.store.get_task(tid)
        self.assertEqual((task["status"], task["revisions"]), ("done", 1))
        steps = r.store.steps(tid)
        self.assertEqual([(s["no"], s["action"], s["status"], s["superseded"]) for s in steps],
                         [(1, "fix_code", "failed", 1), (2, "answer", "done", 0)])
        text = report_text(build_report(r.store, r.world, tid))
        self.assertIn("replaced by a different approach", text)
        self.assertIn("plan revised 1 time", text)

    def test_revision_that_repeats_the_same_step_is_refused(self):
        same = ("fix_code", {"project": "/no/such/folder"}, "again")
        r = self.rig([plan_json(same), review_json("revise", "try again", [same])])
        tid = r.engine.submit("sort this out")
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "failed")
        self.assertEqual(len(r.store.steps(tid)), 1)
        self.assertTrue(any("only repeats what was already tried" in e["message"] for e in r.store.events(tid)))

    def test_give_up_is_reported_as_not_solved(self):
        r = self.rig([plan_json(ANSWER, ("answer", {"question": "and 3+3?"}, "more")), "Four.",
                      review_json("give_up", "I cannot do arithmetic reliably")])
        tid = r.engine.submit("maths homework")
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "failed")
        self.assertEqual(len(r.store.steps(tid)), 1)                # the unrun step was dropped
        rep = build_report(r.store, r.world, tid)
        self.assertIn("NOT SOLVED", rep["verdict"])
        self.assertIn("I cannot do arithmetic reliably", rep["verdict"])

    def test_revisions_are_limited(self):
        replies = [plan_json(ANSWER)]
        for i in range(10):
            replies += [f"answer {i}", review_json("revise", "one more", [("answer", {"question": f"q{i}"}, "more")])]
        r = self.rig(replies)
        tid = r.engine.submit("endless")
        r.run()
        task = r.store.get_task(tid)
        self.assertEqual((task["status"], task["revisions"]), ("done", 3))
        self.assertEqual(len(r.store.steps(tid)), 4)

    def test_unusable_review_leaves_the_plan_alone(self):
        r = self.rig([plan_json(ANSWER), "Four.", "¯\\_(ツ)_/¯"])
        tid = r.engine.submit("What is 2+2")
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "done")

    def test_invalid_revised_plan_is_ignored(self):
        r = self.rig([plan_json(ANSWER), "Four.", review_json("revise", "x", [("teleport", {}, "x")])])
        tid = r.engine.submit("What is 2+2")
        r.run()
        self.assertEqual((r.store.get_task(tid)["status"], len(r.store.steps(tid))), ("done", 1))

    def test_review_survives_a_restart(self):
        r = self.rig([plan_json(ANSWER), "Four."])
        tid = r.engine.submit("What is 2+2")
        r.engine.tick()                                   # step runs; review has not happened yet
        self.assertEqual(r.store.steps(tid)[0]["reviewed"], 0)
        self.llm.replies.append(review_json("continue"))
        r.restart()
        r.run()
        self.assertEqual(r.store.steps(tid)[0]["reviewed"], 1)
        self.assertEqual(r.done_runs(tid), {1: 1})        # the answer was not generated twice

    def test_answer_without_a_model_fails_honestly(self):
        r = Rig(services={"llm": None})
        self.addCleanup(r.close)
        tid = r.engine.submit("What is the capital of France?")
        r.run()
        rep = build_report(r.store, r.world, tid)
        self.assertEqual(rep["status"], "failed")
        self.assertIn("no local model is configured", rep["verdict"])

    def test_empty_answer_is_a_failure(self):
        r = self.rig([plan_json(ANSWER), "   ", review_json("continue")])
        tid = r.engine.submit("What is 2+2")
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "failed")


class _FakeLlamaHandler(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send({"status": "ok"})
        self._send({"data": [{"id": "/models/tiny-test.gguf"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.seen.append(body)
        self._send({"choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 3},
                    "timings": {"predicted_per_second": 21.5}})


class WireFormatTests(unittest.TestCase):
    """LlamaClient against a stand-in HTTP server that answers in llama.cpp's reply shape."""

    def test_client_speaks_the_llama_cpp_protocol(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeLlamaHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        c = LlamaClient(f"http://127.0.0.1:{server.server_address[1]}")
        self.assertTrue(c.healthy())
        reply = c.chat([{"role": "user", "content": "hi"}], max_tokens=5, json_schema={"type": "object"})
        self.assertEqual((reply.text, reply.model, reply.prompt_tokens, reply.completion_tokens, reply.tokens_per_second),
                         ("hello", "tiny-test.gguf", 12, 3, 21.5))
        sent = _FakeLlamaHandler.seen[-1]
        self.assertEqual(sent["response_format"], {"type": "json_object", "schema": {"type": "object"}})
        self.assertEqual(sent["max_tokens"], 5)

    def test_unreachable_server(self):
        c = LlamaClient("http://127.0.0.1:9", timeout=1)
        self.assertFalse(c.healthy())
        with self.assertRaises(LLMUnavailable):
            c.chat([{"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
