"""Planner: turns a task into numbered steps, each marked online or offline.

`Planner` is the interface. `RuleBasedPlanner` is the simple version used now.
`LlamaCppPlanner` shows where a local language model plugs in later.
"""
import json
import os
import re
from dataclasses import dataclass, field


@dataclass
class PlanStep:
    no: int
    title: str
    action: str
    needs_internet: bool = False
    sensitive: bool = False
    depends_on: list = field(default_factory=list)
    params: dict = field(default_factory=dict)


class Plan(list):
    """A list of PlanStep that also remembers which planner really produced it."""

    def __init__(self, steps, planner, note=""):
        super().__init__(steps)
        self.planner, self.note = planner, note


class Planner:
    name = "base"
    reflective = False   # True = the engine asks `review` after every finished step

    def plan(self, goal: str) -> list:
        """Return a list of PlanStep, numbered from 1."""
        raise NotImplementedError

    def review(self, goal, steps, finished_step, can_revise):
        """Look at a finished step. Return (decision, reason, new_steps) where decision is
        'continue', 'revise' (replace the steps not yet run with new_steps) or 'give_up'."""
        return "continue", "", []


# (title, action, needs_internet, sensitive, depends_on, params)
FIND_LEADS = [
    ("Read the brief and load the target customer criteria", "load_brief", 0, 0, [], {}),
    ("Load existing contacts from the local address book", "load_contacts", 0, 0, [], {}),
    ("Search the business directory, page 1", "search_directory", 1, 0, [1], {"page": 1}),
    ("Search the business directory, page 2", "search_directory", 1, 0, [1], {"page": 2}),
    ("Search the business directory, page 3", "search_directory", 1, 0, [1], {"page": 3}),
    ("Merge the search results into one list", "merge_results", 0, 0, [3, 4, 5], {}),
    ("Remove duplicates and companies we already know", "dedupe", 0, 0, [2, 6], {}),
    ("Fetch company profiles, batch 1", "fetch_profiles", 1, 0, [7], {"batch": 1}),
    ("Fetch company profiles, batch 2", "fetch_profiles", 1, 0, [7], {"batch": 2}),
    ("Score the leads in batch 1", "score_leads", 0, 0, [1, 8], {"batch": 1}),
    ("Score the leads in batch 2", "score_leads", 0, 0, [1, 9], {"batch": 2}),
    ("Draft the outreach message template", "draft_template", 0, 0, [1], {}),
    ("Save an interim leads file from batch 1", "save_interim", 0, 0, [10], {}),
    ("Verify contact emails for the best leads", "verify_emails", 1, 0, [10, 11], {}),
    ("Rank the final lead list", "rank_leads", 0, 0, [14], {}),
    ("Personalise messages for the top 3 leads", "personalise", 0, 0, [12, 15], {}),
    ("Write the final leads CSV file", "write_csv", 0, 0, [15], {}),
    ("Send the intro message to the top lead", "send_message", 1, 1, [16], {}),
    ("Sync the leads to the cloud CRM", "crm_sync", 1, 0, [17], {}),
    ("Write the final summary", "write_summary", 0, 0, [18, 19], {}),
]

ONLINE_WORDS = ("search", "fetch", "download", "send", "email", "message", "sync", "upload",
                "look up", "browse", "post", "call", "online", "web")
SENSITIVE_WORDS = ("send", "message", "email", "pay", "buy", "delete", "post", "call", "publish")


FIX_WORDS = re.compile(r"\b(fix|repair|debug)\b", re.I)
QUESTION_START = re.compile(r"(what|why|how|who|when|where|which|explain|define)\b", re.I)


def find_folder(goal):
    """The first existing folder path mentioned in the goal, or None."""
    for token in re.findall(r"[~./\w\-]*/[\w./\-]*", goal):
        path = os.path.expanduser(token.rstrip(".,;:!?"))
        if os.path.isdir(path):
            return path
    return None


class RuleBasedPlanner(Planner):
    """Keyword rules. Knows the 'find leads' recipe; splits anything else into simple steps."""
    name = "rule-based"

    def recipe(self, goal):
        """A built-in recipe for this goal, or None."""
        if "lead" in goal.lower():
            return Plan([PlanStep(i + 1, t, a, bool(n), bool(s), list(d), dict(p))
                         for i, (t, a, n, s, d, p) in enumerate(FIND_LEADS)], self.name)
        return None

    def plan(self, goal):
        known = self.recipe(goal)
        if known is not None:
            return known
        folder = find_folder(goal)
        if folder and FIX_WORDS.search(goal):
            return Plan([PlanStep(1, f"Fix the failing tests in {folder}", "fix_code",
                                  params={"project": folder})], self.name)
        if goal.strip().endswith("?") or QUESTION_START.match(goal.strip()):
            return Plan([PlanStep(1, "Answer the question with the local model", "answer",
                                  params={"question": goal.strip()})], self.name)
        parts = [p.strip() for p in re.split(r"\bthen\b|[;.\n]", goal) if p.strip()] or [goal]
        steps = []
        for i, part in enumerate(parts, 1):
            low = part.lower()
            steps.append(PlanStep(
                no=i, title=part[:120], action="generic",
                needs_internet=any(w in low for w in ONLINE_WORDS),
                sensitive=any(w in low for w in SENSITIVE_WORDS),
                depends_on=[i - 1] if i > 1 else []))
        return Plan(steps, self.name)


class LlamaCppPlanner(Planner):
    """Planner backed by a local model served by llama.cpp (`llama-server`).

    plan():   the model gets the task and the list of available tools and returns steps as JSON.
              The JSON is validated (known tool, correct inputs). One repair round is allowed.
              If the result is still unusable - or the model cannot be reached - the rule-based
              planner is used instead, and the plan says so.
    review(): after every finished step the model sees what happened and answers
              continue / revise / give_up. Its answer is validated the same way.

    Whether a step needs internet or is sensitive is taken from the TOOL, never from the model.
    """
    name = "llama.cpp"
    reflective = True
    PLAN_SYSTEM = (
        "You are the planner inside NEURON, a personal AI computer that works offline. "
        "Break the user's task into the fewest steps that complete it. Each step uses exactly one of the "
        "available tools. Copy file and folder paths exactly as written in the task. "
        'Reply with JSON only: {"steps": [{"tool": "<tool name>", "inputs": {...}, "why": "<short reason>"}]}')
    REVIEW_SYSTEM = (
        "You are the planner inside NEURON, a personal AI computer that works offline. A step of the plan "
        "just finished. Decide what happens next. Reply with JSON only: "
        '{"decision": "continue" | "revise" | "give_up", "reason": "<short>", "steps": [...]}.\n'
        "continue: the result is fine, or the remaining plan still makes sense.\n"
        "revise: the result shows a different approach is needed. Put the new steps in \"steps\" "
        "(same format as a plan). Never repeat a step that already ran with the same inputs.\n"
        "give_up: the task cannot be completed with the available tools. Say why.")

    def __init__(self, url="http://127.0.0.1:8080", fallback=None, timeout=600, registry=None,
                 client=None, max_steps=6):
        from .llm import LlamaClient
        from .tools import default_registry
        self.client = client or LlamaClient(url, timeout)
        self.fallback = fallback or RuleBasedPlanner()
        self.registry = registry or default_registry()
        self.max_steps = max_steps

    # ---- helpers ---------------------------------------------------------
    def _step_schema(self):
        names = [t["name"] for t in self.registry.specs()]
        return {"type": "object",
                "properties": {"tool": {"type": "string", "enum": names}, "inputs": {"type": "object"},
                               "why": {"type": "string"}},
                "required": ["tool", "inputs", "why"]}

    def _tools_text(self):
        return "Available tools:\n" + json.dumps(self.registry.specs(), indent=1)

    def _validate(self, items, first_no=1):
        """Turn the model's step list into PlanSteps. Returns (steps, problems)."""
        if not isinstance(items, list) or not items:
            return [], ["'steps' must be a non-empty list"]
        if len(items) > self.max_steps:
            return [], [f"too many steps ({len(items)}); the limit is {self.max_steps}"]
        steps, problems = [], []
        for i, it in enumerate(items):
            if not isinstance(it, dict) or not isinstance(it.get("tool"), str):
                problems.append(f"step {i + 1}: must be an object with a 'tool' name")
                continue
            if not self.registry.has(it["tool"]) or not self.registry.get(it["tool"]).planner_visible:
                problems.append(f"step {i + 1}: unknown tool '{it['tool']}'")
                continue
            tool = self.registry.get(it["tool"])
            inputs = it.get("inputs") if isinstance(it.get("inputs"), dict) else {}
            inputs = {k: v for k, v in inputs.items() if v not in (None, "")}
            bad = tool.check_inputs(inputs)
            if bad:
                problems.append(f"step {i + 1} ({tool.name}): " + "; ".join(bad))
                continue
            no = first_no + i
            steps.append(PlanStep(no, str(it.get("why") or tool.name)[:120], tool.name, tool.needs_internet,
                                  tool.sensitive, [no - 1] if i else [], inputs))
        return steps, problems

    def _ask_json(self, messages, schema, max_tokens=600):
        reply = self.client.chat(messages, max_tokens=max_tokens, temperature=0.1, json_schema=schema)
        text = reply.text.strip()
        try:
            return json.loads(text[text.index("{"): text.rindex("}") + 1]), text
        except ValueError:
            return None, text

    # ---- planning --------------------------------------------------------
    def plan(self, goal):
        from .llm import LLMUnavailable
        known = self.fallback.recipe(goal) if hasattr(self.fallback, "recipe") else None
        if known is not None:
            return Plan(known, f"{self.fallback.name} (built-in recipe)")
        schema = {"type": "object", "required": ["steps"],
                  "properties": {"steps": {"type": "array", "minItems": 1, "maxItems": self.max_steps,
                                           "items": self._step_schema()}}}
        messages = [{"role": "system", "content": self.PLAN_SYSTEM + "\n\n" + self._tools_text()},
                    {"role": "user", "content": "Task: " + goal}]
        why = ""
        try:
            for _ in range(2):   # first try + one repair round
                data, text = self._ask_json(messages, schema)
                steps, problems = self._validate(data.get("steps") if isinstance(data, dict) else None)
                if steps and not problems:
                    return Plan(steps, f"{self.name}:{self.client.model_name()}")
                why = "; ".join(problems) or "reply was not valid JSON"
                messages += [{"role": "assistant", "content": text},
                             {"role": "user", "content": f"That plan cannot be used: {why}. Send a corrected plan."}]
        except LLMUnavailable as e:
            why = f"model not reachable ({e})"
        plan = self.fallback.plan(goal)
        return Plan(plan, f"{self.fallback.name} (fallback: {why[:200]})", why)

    # ---- reviewing -------------------------------------------------------
    def review(self, goal, steps, finished_step, can_revise):
        lines = []
        for s in steps:
            line = f"{s['no']}. tool={s['action']} inputs={json.dumps(s['params'])} status={s['status']}"
            proof = s.get("proof") or {}
            if proof.get("summary"):
                line += f" result: {str(proof['summary'])[:300]}"
            if s["status"] == "done" and s["action"] == "answer":
                line += f" answer: {str((s.get('result') or {}).get('answer', ''))[:400]}"
            lines.append(line)
        last = max(s["no"] for s in steps)
        user = (f"Task: {goal}\n\nSteps so far:\n" + "\n".join(lines) +
                f"\n\nThe step that just finished is step {finished_step['no']} "
                f"(status: {finished_step['status']}).\n"
                + ("" if can_revise else "The plan may not be revised any more: choose continue or give_up.\n")
                + "What now?")
        schema = {"type": "object", "required": ["decision", "reason"],
                  "properties": {"decision": {"type": "string", "enum": ["continue", "revise", "give_up"]},
                                 "reason": {"type": "string"},
                                 "steps": {"type": "array", "maxItems": self.max_steps, "items": self._step_schema()}}}
        data, _ = self._ask_json([{"role": "system", "content": self.REVIEW_SYSTEM + "\n\n" + self._tools_text()},
                                  {"role": "user", "content": user}], schema, max_tokens=500)
        if not isinstance(data, dict) or data.get("decision") not in ("continue", "revise", "give_up"):
            return "continue", "the model's review was unusable, so the plan was left as it is", []
        reason = str(data.get("reason") or "")[:300]
        if data["decision"] != "revise":
            return data["decision"], reason, []
        new_steps, problems = self._validate(data.get("steps"), first_no=last + 1)
        if problems or not new_steps:
            return "continue", f"the model's revised plan was invalid ({'; '.join(problems)[:200]})", []
        return "revise", reason, new_steps
