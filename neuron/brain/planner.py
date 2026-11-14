"""Planner: turns a task into numbered steps, each marked online or offline.

`Planner` is the interface. `RuleBasedPlanner` is the simple version used now.
`LlamaCppPlanner` shows where a local language model plugs in later.
"""
import json
import re
import urllib.request
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


class Planner:
    name = "base"

    def plan(self, goal: str) -> list:
        """Return a list of PlanStep, numbered from 1."""
        raise NotImplementedError


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


class RuleBasedPlanner(Planner):
    """Keyword rules. Knows the 'find leads' recipe; splits anything else into simple steps."""
    name = "rule-based"

    def plan(self, goal):
        if "lead" in goal.lower():
            return [PlanStep(i + 1, t, a, bool(n), bool(s), list(d), dict(p))
                    for i, (t, a, n, s, d, p) in enumerate(FIND_LEADS)]
        parts = [p.strip() for p in re.split(r"\bthen\b|[;.\n]", goal) if p.strip()] or [goal]
        steps = []
        for i, part in enumerate(parts, 1):
            low = part.lower()
            steps.append(PlanStep(
                no=i, title=part[:120], action="generic",
                needs_internet=any(w in low for w in ONLINE_WORDS),
                sensitive=any(w in low for w in SENSITIVE_WORDS),
                depends_on=[i - 1] if i > 1 else []))
        return steps


class LlamaCppPlanner(Planner):
    """Plug-in point for a local model served by llama.cpp (`llama-server`).

    Not exercised in v0.1 (no model is installed). It asks the server for a JSON
    step list and falls back to the rule-based planner if anything goes wrong.
    """
    name = "llama.cpp"
    PROMPT = ("Break the task into numbered steps. Reply with only a JSON list of objects with keys "
              "title (string), needs_internet (bool), sensitive (bool).\nTask: {goal}\nJSON:")

    def __init__(self, url="http://127.0.0.1:8080", fallback=None, timeout=60):
        self.url, self.timeout = url.rstrip("/"), timeout
        self.fallback = fallback or RuleBasedPlanner()

    def plan(self, goal):
        try:
            body = json.dumps({"prompt": self.PROMPT.format(goal=goal), "n_predict": 1024,
                               "temperature": 0}).encode()
            req = urllib.request.Request(self.url + "/completion", body,
                                         {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                text = json.loads(r.read())["content"]
            items = json.loads(text[text.index("["): text.rindex("]") + 1])
            return [PlanStep(no=i, title=str(it["title"])[:120], action="generic",
                             needs_internet=bool(it.get("needs_internet")),
                             sensitive=bool(it.get("sensitive")),
                             depends_on=[i - 1] if i > 1 else [])
                    for i, it in enumerate(items, 1)]
        except Exception:
            return self.fallback.plan(goal)
