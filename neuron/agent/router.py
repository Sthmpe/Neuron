"""Understand: what kind of job is this? Rules first (words in the request, attached file types, what the
workspace contains); the model only chooses from a short list when the rules cannot tell."""
import re
from pathlib import Path

KINDS = {
    "excel": "a spreadsheet or Excel workbook",
    "word": "a Word document (letter, memo, proposal, report)",
    "pptx": "a PowerPoint presentation",
    "pdf_qa": "answers to questions from attached documents",
    "fix_bug": "fixing a bug in an existing project so its tests pass",
    "document_code": "adding documentation (docstrings, comments) to existing code without changing behaviour",
    "build_program": "writing a new command-line program in a compiled or scripting language",
    "web_app": "building a website or web app",
    "upgrade_packages": "updating an existing project's packages or dependencies to newer versions, safely",
    "add_feature": "adding new behaviour or a new feature to an existing project's code",
    "answer": "answering a question or explaining something",
}
RULES = [
    ("excel", r"\bexcel\b|spreadsheet|workbook|\.xlsx\b"),
    ("pptx", r"powerpoint|presentation|slide deck|\bslides?\b|\.pptx\b|\bdeck\b"),
    ("word", r"word document|\.docx\b|\bmemo\b|\bproposal\b|\bletter\b(?! of)"),
    ("upgrade_packages", r"\b(update|upgrade|bump)\b.{0,30}\b(packages?|dependenc(y|ies)|libraries|requirements)\b|outdated (packages|dependencies)"),
    ("document_code", r"docstring|add comments|document (the|this|every) (code|function)|type hints"),
    ("fix_bug", r"\bfix\b|\bbug\b|failing tests?|tests? (are )?fail|broken|doesn't work|does not work"),
    ("build_program", r"command[- ]line|\bcli\b|\bc\+\+|\brust\b|\bgolang\b|\bgo program|\bjava program|makefile"),
    ("web_app", r"website|web app|landing page|\bweb page\b|app (where|that|for) (i|my|we)|dashboard|log in first"),
    # only decides when there is a project to change (see rule_guess): new behaviour in existing code
    ("add_feature", r"^\s*(please\s+)?(add|implement|extend|support|introduce|create|make)\b|\b(add|implement) (a |an |the )?(new )?\w+|"
                    r"\bcreate [\w/-]+\.(py|js|ts|go|cpp|cc|h|hpp|rs|java)\b|\bnew (command|function|option|field|feature|method|endpoint)\b"),
]


CODE_GLOBS = ("*.py", "*.cpp", "*.go", "*.rs", "*.java", "*.js")


def project_has_code(workspace):
    """True if the folder holds a code project of the owner's. An app NEURON built (its kit, pages and schema) is not
    one: a follow-up like "Add a contact page" there belongs to the app builder, not to the code-feature step."""
    ws = Path(workspace)
    built_apps = {p.parent.parent for p in ws.rglob("kit/web.py")}      # the app folder that holds the kit
    for pattern in CODE_GLOBS:
        for f in ws.rglob(pattern):
            rel = f.relative_to(ws)
            if ".neuron" in rel.parts or "__pycache__" in rel.parts or any(f.is_relative_to(a) for a in built_apps):
                continue
            return True
    return False


def rule_guess(request, attachments=(), workspace=None):
    text = request.lower()
    hits = [k for k, pattern in RULES if re.search(pattern, text)]
    exts = {Path(a).suffix.lower() for a in attachments}
    if ".pdf" in exts and not hits:
        hits.append("pdf_qa")
    if ".csv" in exts or ".xlsx" in exts:
        hits = ["excel"] + [h for h in hits if h != "excel"] if "excel" in hits or not hits else hits
    # any(...) over the generators themselves was always True (a generator object is truthy), so a request containing
    # "fix" went to the bug fixer even in an empty folder (core proof A8: "fix charging ports" on a website request)
    has_code = workspace is not None and project_has_code(workspace)
    if not has_code:                          # "add"/"make" means new behaviour only when there is a project to change
        hits = [h for h in hits if h != "add_feature"]
    if has_code and "fix_bug" in hits and "document_code" not in hits:
        return "fix_bug", hits
    if has_code and "add_feature" in hits and "document_code" not in hits and "upgrade_packages" not in hits:
        return "add_feature", hits
    if "document_code" in hits and has_code:
        return "document_code", hits
    if "upgrade_packages" in hits and workspace is not None and \
            any((Path(workspace) / f).exists() for f in ("requirements.txt", "package.json")):
        return "upgrade_packages", hits
    order = ["excel", "pptx", "word", "pdf_qa", "build_program", "web_app", "fix_bug", "document_code"]
    for k in order:
        if k in hits:
            return k, hits
    return ("answer", hits) if re.search(r"\?\s*$|^(what|why|how|who|when|where|which|explain)\b", text.strip()) else (None, hits)


SIMPLE_MAX_CHARS = 500


def is_simple(request, attachments=(), workspace=None):
    """A single question or a simple task (a short request, no files, no project to work on, nothing the rules
    recognise as a document, program, app or bug fix): it goes straight to the model, with no classification call,
    no plan and no planning overhead, so NEURON is never meaningfully slower than the bare model on easy work."""
    import os
    text = (request or "").strip()
    if os.environ.get("NEURON_FAST") == "0" or not text or len(text) > SIMPLE_MAX_CHARS or attachments:
        return False
    if workspace is not None:
        ws = Path(workspace)
        if any(p for p in ws.rglob("*") if p.is_file() and ".neuron" not in p.relative_to(ws).parts):
            return False                          # there is something to work on: not a simple question
    kind, hits = rule_guess(text, attachments, workspace)
    if kind in (None, "answer") and not hits:
        return True
    # "Explain what a spreadsheet is" is a question about a topic, not a request to make one: a question form with no
    # verb of making stays simple (the internal easy set sent it to the spreadsheet builder)
    asks = re.match(r"\s*(what|why|how|who|when|where|which|explain|describe|define|tell me|is|are|can|does|do)\b", text, re.I)
    makes = re.search(r"\b(make|create|build|write|generate|draft|produce|prepare|fix|repair|debug|design)\b|\.(xlsx|docx|pptx|pdf|csv)\b",
                      text, re.I)
    return bool(asks) and not makes and kind != "fix_bug"


def understand(job, request, attachments=()):
    kind, hits = rule_guess(request, attachments, job.workspace)
    how = "rules"
    named = re.search(r"\b[\w-]+\.(xlsx|docx|pptx)\b", request, re.I)
    if named:                  # the owner named the file to make: that decides ("write letter.docx ... fix the roof" is a letter)
        return {"xlsx": "excel", "docx": "word", "pptx": "pptx"}[named.group(1).lower()], "rules (named output file)"
    if kind is None or len(set(hits)) > 1 and kind not in ("fix_bug", "document_code", "excel", "add_feature"):
        options = sorted(KINDS)
        data = job.ask_json("planner", "You classify a request into exactly one kind of job.",
                            "Request:\n" + request + "\n\nKinds:\n" + "\n".join(f"- {k}: {v}" for k, v in KINDS.items()),
                            {"type": "object", "required": ["kind"], "properties": {"kind": {"type": "string", "enum": options}}})
        if data and data.get("kind") in KINDS:
            kind, how = data["kind"], "model chose from rule candidates" if hits else "model"
        elif kind is None:
            kind, how = "answer", "default"
    return kind, how
