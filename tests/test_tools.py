"""The common tool interface and the registry."""
import tempfile
import textwrap
import unittest
from pathlib import Path

from neuron.brain.planner import Plan, Planner, PlanStep
from neuron.brain.report import build_report, report_text
from neuron.brain.tools import Tool, ToolFailure, ToolRegistry, ToolResult, UnknownTool, default_registry
from tests.helpers import Rig

PLUGIN = textwrap.dedent('''
    from neuron.brain.tools import Tool, ToolResult

    class DescribeImage(Tool):
        name = "describe_image"
        description = "Say what is in a picture (pretend version for the test)."
        inputs = {"image": {"type": "path", "description": "Picture file", "required": True}}
        def run(self, ctx):
            return ToolResult({"caption": "a cat"}, "Described the picture", {"image": ctx.params["image"]})

    class SendSms(Tool):
        name = "send_sms"
        description = "Send a text message."
        inputs = {"to": {"type": "string", "required": True}, "text": {"type": "string", "required": True}}
        needs_internet = True
        sensitive = True
        def run(self, ctx):
            return ToolResult({"sent": True}, "Sent the text", {"to": ctx.params["to"]})

    TOOLS = [DescribeImage(), SendSms()]
''')


class FixedPlanner(Planner):
    name = "fixed"

    def __init__(self, steps):
        self.steps = steps

    def plan(self, goal):
        return Plan(self.steps, self.name)


class RegistryTests(unittest.TestCase):
    def test_built_in_tools_are_discovered(self):
        reg = default_registry()
        for name in ("answer", "fix_code", "search_directory", "send_message"):
            self.assertTrue(reg.has(name), name)
        self.assertEqual([t["name"] for t in reg.specs()], ["answer", "fix_code"])   # what a model may pick
        spec = reg.get("fix_code").spec()
        self.assertEqual(set(spec), {"name", "description", "inputs", "needs_internet", "sensitive"})
        self.assertFalse(spec["needs_internet"])
        self.assertTrue(reg.get("send_message").sensitive and reg.get("send_message").needs_internet)

    def test_unknown_tool(self):
        with self.assertRaises(UnknownTool):
            ToolRegistry().get("teleport")

    def test_input_checking(self):
        tool = default_registry().get("fix_code")
        self.assertEqual(tool.check_inputs({"project": "/x"}), [])
        self.assertIn("missing input 'project'", tool.check_inputs({}))
        self.assertIn("unknown input 'colour'", tool.check_inputs({"project": "/x", "colour": "red"}))
        self.assertIn("input 'write_back' must be boolean", tool.check_inputs({"project": "/x", "write_back": "yes"}))

    def test_new_kinds_of_tool_plug_in_without_touching_the_engine(self):
        plug = Path(tempfile.mkdtemp(prefix="neuron-plugins-"))
        (plug / "media.py").write_text(PLUGIN)
        reg = default_registry([plug])
        self.assertIn("describe_image", [t["name"] for t in reg.specs()])
        sms = reg.get("send_sms")
        steps = [PlanStep(1, "Look at the photo", "describe_image", params={"image": "cat.jpg"}),
                 PlanStep(2, "Text Ada", "send_sms", sms.needs_internet, sms.sensitive, [1],
                          {"to": "Ada", "text": "it is a cat"})]
        r = Rig(planner=FixedPlanner(steps), tools=reg)
        self.addCleanup(r.close)
        tid = r.engine.submit("what is in cat.jpg? text Ada")
        r.run()
        self.assertEqual(r.status(tid), {1: "done", 2: "waiting_approval"})      # sensitive tool waits
        r.approve_all()
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "done")


class NoProofNoSuccessTests(unittest.TestCase):
    def run_one(self, tool):
        reg = default_registry()
        reg.register(tool)
        r = Rig(planner=FixedPlanner([PlanStep(1, "do it", tool.name)]), tools=reg)
        self.addCleanup(r.close)
        tid = r.engine.submit("do it")
        r.run()
        return r, tid

    def test_tool_without_evidence_is_not_counted_as_done(self):
        class Lazy(Tool):
            name = "lazy"

            def run(self, ctx):
                return ToolResult({"ok": True}, "All good, trust me", {})

        r, tid = self.run_one(Lazy())
        self.assertEqual(r.status(tid)[1], "failed")
        self.assertEqual(r.store.get_task(tid)["status"], "failed")
        self.assertIn("gave no proof", r.store.steps(tid)[0]["error"])

    def test_tool_returning_something_else_is_not_counted_as_done(self):
        class Sloppy(Tool):
            name = "sloppy"

            def run(self, ctx):
                return {"ok": True}

        r, tid = self.run_one(Sloppy())
        self.assertEqual(r.store.get_task(tid)["status"], "failed")

    def test_failure_says_what_was_tried(self):
        class Honest(Tool):
            name = "honest"

            def run(self, ctx):
                raise ToolFailure("could not open the door", {"attempts": [{"n": 1, "error": "key did not fit"}]})

        r, tid = self.run_one(Honest())
        rep = build_report(r.store, r.world, tid)
        self.assertTrue(rep["verdict"].startswith("NOT SOLVED"))
        self.assertIn("could not open the door", rep["verdict"])
        text = report_text(rep)
        self.assertIn("attempt 1: rejected before testing: key did not fit", text)

    def test_unknown_tool_in_a_plan_fails_cleanly(self):
        r = Rig(planner=FixedPlanner([PlanStep(1, "x", "does_not_exist")]))
        self.addCleanup(r.close)
        tid = r.engine.submit("x")
        r.run()
        self.assertEqual(r.store.get_task(tid)["status"], "failed")
        self.assertIn("no tool named", r.store.steps(tid)[0]["error"])


if __name__ == "__main__":
    unittest.main()
