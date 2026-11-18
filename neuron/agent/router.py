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
]


def rule_guess(request, attachments=(), workspace=None):
    text = request.lower()
    hits = [k for k, pattern in RULES if re.search(pattern, text)]
    exts = {Path(a).suffix.lower() for a in attachments}
    if ".pdf" in exts and not hits:
        hits.append("pdf_qa")
    if ".csv" in exts or ".xlsx" in exts:
        hits = ["excel"] + [h for h in hits if h != "excel"] if "excel" in hits or not hits else hits
    has_code = workspace is not None and any(Path(workspace).rglob(p) for p in ("*.py", "*.cpp", "*.go", "*.rs", "*.java", "*.js"))
    if has_code and "fix_bug" in hits and "document_code" not in hits:
        return "fix_bug", hits
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


def understand(job, request, attachments=()):
    kind, hits = rule_guess(request, attachments, job.workspace)
    how = "rules"
    named = re.search(r"\b[\w-]+\.(xlsx|docx|pptx)\b", request, re.I)
    if named:                  # the owner named the file to make: that decides ("write letter.docx ... fix the roof" is a letter)
        return {"xlsx": "excel", "docx": "word", "pptx": "pptx"}[named.group(1).lower()], "rules (named output file)"
    if kind is None or len(set(hits)) > 1 and kind not in ("fix_bug", "document_code", "excel"):
        options = sorted(KINDS)
        data = job.ask_json("planner", "You classify a request into exactly one kind of job.",
                            "Request:\n" + request + "\n\nKinds:\n" + "\n".join(f"- {k}: {v}" for k, v in KINDS.items()),
                            {"type": "object", "required": ["kind"], "properties": {"kind": {"type": "string", "enum": options}}})
        if data and data.get("kind") in KINDS:
            kind, how = data["kind"], "model chose from rule candidates" if hits else "model"
        elif kind is None:
            kind, how = "answer", "default"
    return kind, how
