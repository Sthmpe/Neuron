"""Answers from documents, with sources. Pages are indexed by code (no model); the model answers from the
retrieved pages; every citation is checked: the quoted sentence must really be on the cited page."""
import json
import math
import re
from collections import Counter
from pathlib import Path

from ...kit_next.copy import clean
from ..capability import Capability, Outcome, Verdict
from ..document_facts import document_proof, facts_backed, legacy_identity

WORD = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*")
STOP = set("the a an of to in and or is are was were for on at by with from that this it as be what how which who when where much many does do".split())


def tokens(text):
    return [w for w in WORD.findall(text.lower()) if w not in STOP]


class Index:
    def __init__(self, pages):
        self.pages = pages                    # [{"doc", "page", "text"}]
        self.tf = [Counter(tokens(p["text"])) for p in pages]
        self.df = Counter(w for tf in self.tf for w in tf)
        self.avg = sum(sum(tf.values()) for tf in self.tf) / max(1, len(self.tf))

    def search(self, query, k=3):
        q = tokens(query)
        n = len(self.pages)
        scores = []
        for i, tf in enumerate(self.tf):
            L = sum(tf.values())
            s = sum(math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5)) * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * L / self.avg))
                    for w in q if w in tf)
            scores.append((s, i))
        return [self.pages[i] for s, i in sorted(scores, reverse=True)[:k] if s > 0]


def questions_from(request):
    qs = [l.strip(" -*\t") for l in request.splitlines() if l.strip().endswith("?")]
    qs = [re.sub(r"^\d+[.)]\s*", "", q) for q in qs]
    return qs or [request]


class IndexDocuments(Capability):
    name = "index_documents"
    purpose = "Read attached PDFs page by page and build a search index"
    requires = {"binaries": [], "modules": ["pypdf"]}
    verification = "every page's text extracted"
    domains = ("research", "documents")

    def run(self, job, params):
        from pypdf import PdfReader
        pages = []
        for a in job.state.goal().get("attachments", []):
            if Path(a).suffix.lower() == ".pdf":
                for i, pg in enumerate(PdfReader(a).pages, 1):
                    pages.append({"doc": Path(a).stem, "page": i, "text": pg.extract_text() or ""})
        if not pages:
            return Outcome(False, "no PDF is attached", evidence={"no_retry": True})
        (job.state.dir / "index.json").write_text(json.dumps(pages))
        docs = sorted({p["doc"] for p in pages})
        for d in docs:
            job.state.learn(f"document {d}: {sum(p['doc'] == d for p in pages)} pages", d)
        return Outcome(True, f"indexed {len(pages)} pages from {len(docs)} documents", {"pages": len(pages), "docs": docs})

    def verify(self, job, params, outcome):
        pages = json.loads((job.state.dir / "index.json").read_text())
        empty = [f"{p['doc']} p{p['page']}" for p in pages if not p["text"].strip()]
        return Verdict(not empty, [{"id": "text_on_every_page", "pass": not empty, "detail": empty[:5]}], "pypdf extraction")


def indexed_pages(rows):
    pages = {}
    for row in rows:
        key = (row["doc"], row["page"])
        text = row["text"]
        pages[key] = text if key not in pages or pages[key] == text else None
    return pages


def render_answers(answers):
    lines = ["# Answers", ""]
    for i, answer in enumerate(answers, 1):
        lines.append(f"{i}. **{answer['question']}**  ")
        lines.append(answer["answer"])
        if answer.get("verified"):
            lines[-1] += f" ({answer['doc']}, page {answer['page']})  "
            lines.append("> " + answer["quote"])
    return "\n".join(lines) + "\n"


class AnswerFromDocuments(Capability):
    name = "answer_from_documents"
    purpose = "Answer questions from the indexed documents, each with document, page and a supporting quote"
    permissions = ("use_model", "write_workspace")
    resources = {"ram_mb": 60, "uses_model": True}
    verification = "the cited page and quote give the same unique answer to the requested fact"
    domains = ("research",)
    strategies = ("answer the failed questions again with more pages",)

    def run(self, job, params):
        idx = Index(json.loads((job.state.dir / "index.json").read_text()))
        qs = questions_from(job.state.goal()["request"])
        pages = indexed_pages(idx.pages)
        prev = {a["question"]: a for a in (job.state.task("answer").get("result") or {}).get("answers", [])}
        retry = set(params.get("retry_questions") or [])
        answers = []
        for q in qs:
            prior = prev.get(q, {})
            if q not in retry and prior.get("verified") and document_proof(prior, pages.get((prior.get("doc"), prior.get("page")))):
                answers.append(prev[q])
                continue
            hits = idx.search(q, k=4 if params.get("strategy") else 3)
            ctx = "\n\n".join(f"[{h['doc']}, page {h['page']}]\n{h['text'][:1800]}" for h in hits)
            data = job.ask_json("builder", "You answer only from the given pages. If the pages do not say, answer 'not found'.",
                                f"Question: {q}\n\nPages:\n{ctx}\n\nGive a short answer, the document and page it comes from, and a short quote copied exactly from that page.",
                                {"type": "object", "required": ["answer", "doc", "page", "quote"],
                                 "properties": {"answer": {"type": "string"}, "doc": {"type": "string", "enum": sorted({h['doc'] for h in hits}) or ["none"]},
                                                "page": {"type": "integer"}, "quote": {"type": "string"}}}, max_tokens=300)
            if not data:
                answers.append({"question": q, "answer": "not found", "verified": False})
                continue
            row = {k: data.get(k) for k in ("doc", "page", "quote")}
            row.update(question=q, answer=data["answer"].strip() if isinstance(data.get("answer"), str) else "")
            page_text = pages.get((row["doc"], row["page"])) if isinstance(row["doc"], str) and type(row["page"]) is int else None
            row["verified"] = document_proof(row, page_text) is not None
            if not row["verified"]:
                row["answer"] = "not found" if str(row["answer"]).strip().lower() == "not found" else "Not confirmed by the cited page."
            answers.append(row)
        (job.workspace / "answers.md").write_text(render_answers(answers))
        (job.workspace / "answers.json").write_text(json.dumps(answers, indent=1))
        ok = sum(a["verified"] for a in answers)
        return Outcome(True, f"{ok} of {len(answers)} answers supported by their cited facts", {"answers": answers},
                       ["answers.md", "answers.json"], made_by="model")

    def verify(self, job, params, outcome):
        pages = indexed_pages(json.loads((job.state.dir / "index.json").read_text()))
        answers = outcome.result["answers"]
        try:
            intact = (json.loads((job.workspace / "answers.json").read_text()) == answers
                      and (job.workspace / "answers.md").read_text() == render_answers(answers))
        except (OSError, ValueError):
            intact = False
        notes, checks = [], []
        for i, a in enumerate(answers, 1):
            proof = document_proof(a, pages.get((a.get("doc"), a.get("page")))) if a.get("verified") else None
            passed = bool(proof and intact)
            checks.append({"id": f"q{i}_fact_on_cited_page", "pass": passed,
                           "detail": f"{a['question'][:60]} -> {a.get('doc')} p{a.get('page')}"})
            if passed:
                text, source = legacy_identity(a)
                notes.append({"kind":"finding", "text":text, "source":source, "verified":True, "tags":[a["doc"]],
                              "meta":{"document_fact":proof}})
        outcome.result["memory_notes"] = notes
        if not all(c["pass"] for c in checks):
            job.state.update_task("answer", params={"retry_questions": [a["question"] for a in outcome.result["answers"] if not a["verified"]]})
        return Verdict(all(c["pass"] for c in checks), checks, "the question, answer and cited page agree on a unique fact")


COMPUTE = re.compile(r"\d|\b(calculate|compute|how (much|many)|percent|average|total|sum|probability|solve)\b", re.I)


class AnswerQuestion(Capability):
    name = "answer_question"
    purpose = "Answer a general question and state which results have independent evidence"
    permissions = ("use_model", "write_workspace")
    resources = {"ram_mb": 40, "uses_model": True}
    verification = "exact arithmetic checked against the delivered answer; other answers marked unverified"
    domains = ("research",)

    def run(self, job, params):
        from ..arithmetic import exact_answer
        from ..capability import NeedsOwnerInput
        from ..owner_input import METHOD, prepare
        q = job.state.goal()["request"]
        exact = exact_answer(q)
        if exact is not None:
            expression, text = exact
            (job.workspace / "answer.md").write_text(text + "\n")
            return Outcome(True, text, {"answer": text, "expression": expression}, ["answer.md"])

        turns = params.get("owner_inputs", [])
        q, supplied = prepare(job, q, turns)
        text = supplied.text if supplied else None
        method = supplied.basis if supplied else ""
        result = {}
        if text is None and COMPUTE.search(q) and not METHOD.search(q):
            from ..thinking import solve
            s = solve(lambda m, n: job.chat("builder", m, max_tokens=n, temperature=0.1), job.sandbox, q)
            text = s["answer"]
            result["tool_runs"] = s["tool_runs"]
            result["computed"] = s["computed"]
            method = (f"The answer is the output of {s['tool_runs']} Python run(s). The program was written by the model."
                      if s["computed"] else "The model used a second pass.")
            if s["computed"]:
                result["review_answer"] = s["review_answer"]
        elif text is None:
            mem = job.memory_context() if hasattr(job, "memory_context") else ""
            text = job.ask_text("builder", "You are NEURON, an offline assistant. Answer clearly. If a specific input only the owner "
                                "can provide is missing, reply with NEED_INPUT followed by one question asking for that fact. "
                                "For a formula or method, explain with variables. Say so if you are not sure. No em dashes."
                                + (f"\n\n{mem}" if mem else ""), q, max_tokens=700)
            method = "The local model supplied this answer."
            missing = re.fullmatch(r"NEED_INPUT\s*:?\s*(.{4,220}\?)", text or "", re.I)
            if missing:
                raise NeedsOwnerInput(missing[1])
        answer = text if result.get("computed") else (text if supplied and supplied.made_by == "owner" else clean(text or "")).strip()
        if not answer:
            return Outcome(False, "the local model did not supply a final answer")
        (job.workspace / "answer.md").write_text(f"{answer}\n\nUnverified. {method}\n")
        return Outcome(True, answer[:300], {**result, "answer": answer}, ["answer.md"], made_by=supplied.made_by if supplied else "model")

    def verify(self, job, params, outcome):
        from ..arithmetic import exact_answer
        path = job.workspace / "answer.md"
        delivered = path.read_bytes().decode("utf-8") if path.is_file() else ""
        exact = exact_answer(job.state.goal()["request"])
        if exact is not None:
            expression, expected = exact
            ok = delivered.strip() == expected
            return Verdict(ok, [{"id": "exact_arithmetic", "pass": ok, "detail": f"{expression} = {expected}"}],
                           "exact rational arithmetic checked against answer.md")
        answer = outcome.result.get("answer", "")
        ok = bool(answer) and delivered.startswith(answer + "\n\nUnverified.")
        return Verdict(ok, [{"id": "answer_delivered", "pass": ok, "detail": "The answer carries an unverified label."}],
                       "unverified")


CAPABILITIES = [IndexDocuments(), AnswerFromDocuments(), AnswerQuestion()]
