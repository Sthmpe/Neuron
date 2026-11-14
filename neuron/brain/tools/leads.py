"""The step-1 'find leads' actions, exposed through the common tool interface.

They are recipe-internal (not offered to the model planner) and still read
`actions.ACTIONS` at call time."""
from .. import actions
from .base import Tool, ToolResult

ONLINE = {"search_directory", "fetch_profiles", "verify_emails", "send_message", "crm_sync"}


class LegacyActionTool(Tool):
    planner_visible = False

    def __init__(self, name):
        self.name = name
        self.description = (actions.ACTIONS[name].__doc__ or f"find-leads recipe step: {name}").strip()
        self.needs_internet = name in ONLINE
        self.sensitive = name == "send_message"

    def check_inputs(self, params):
        return []

    def run(self, ctx):
        result, summary, evidence = actions.ACTIONS[self.name](ctx)
        has_record = "receipt" in evidence or "sha256" in evidence
        return ToolResult(result, summary, evidence, verified=has_record,
                          verification="outside-world receipt / file hash recorded" if has_record
                          else "counts recorded by the step itself")


TOOLS = [LegacyActionTool(name) for name in actions.ACTIONS]
