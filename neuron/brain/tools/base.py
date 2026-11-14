"""The one interface every capability plugs into.

A tool says what it is (name, description, inputs), whether it needs internet,
and whether it is sensitive (needs host approval). The engine knows nothing
about any particular tool: it looks the tool up in the registry by name, runs
it, and stores what comes back. Image, audio, messaging or app tools are added
by writing another `Tool` - the engine does not change.

A tool must return a `ToolResult` WITH evidence. No evidence = the engine marks
the step failed. A tool that cannot do its job raises `ToolFailure` and says
what it tried.
"""
from dataclasses import dataclass, field

TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "path": str}


@dataclass
class ToolResult:
    result: dict                 # data for later steps
    summary: str                 # one plain sentence: what happened
    evidence: dict               # the proof (hashes, receipts, test output, timings ...)
    verified: bool = False       # True only if the outcome was checked by something other than the model
    verification: str = "not independently verified"


class ToolFailure(Exception):
    """The tool could not do the job. `evidence` records what was tried."""

    def __init__(self, summary, evidence=None):
        super().__init__(summary)
        self.summary, self.evidence = summary, evidence or {}


class Tool:
    name = ""
    description = ""
    inputs = {}              # {"question": {"type": "string", "description": "...", "required": True}}
    needs_internet = False
    sensitive = False
    planner_visible = True   # may a model planner choose this tool?

    def run(self, ctx) -> ToolResult:
        raise NotImplementedError

    def spec(self):
        return {"name": self.name, "description": self.description, "inputs": self.inputs,
                "needs_internet": self.needs_internet, "sensitive": self.sensitive}

    def check_inputs(self, params):
        """Return a list of problems with `params` (empty list = fine)."""
        if not isinstance(params, dict):
            return ["inputs must be an object"]
        problems = []
        for key, rule in self.inputs.items():
            if key not in params or params[key] in (None, ""):
                if rule.get("required"):
                    problems.append(f"missing input '{key}'")
                continue
            want = TYPES.get(rule.get("type", "string"), str)
            if isinstance(params[key], bool) and want is not bool or not isinstance(params[key], want):
                problems.append(f"input '{key}' must be {rule.get('type', 'string')}")
        for key in params:
            if key not in self.inputs:
                problems.append(f"unknown input '{key}'")
        return problems
