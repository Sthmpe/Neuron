"""Answers from documents, with sources. Pages are indexed by code (no model); the model answers from the
retrieved pages; every citation is checked: the quoted sentence must really be on the cited page."""
import json
import math
import re
from collections import Counter
from pathlib import Path

from ...kit_next.copy import clean
from ..capability import Capability, Outcome, Verdict

WORD = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*")
STOP = set("the a an of to in and or is are was were for on at by with from that this it as be what how which who when where much many does do".split())


def tokens(text):
    return [w for w in WORD.findall(text.lower()) if w not in STOP]


def norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.,% ]", " ", text.lower())).strip()


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


NUMBER_QUESTION = re.compile(r"^\s*(how (much|many|long|far|old)|what (is|was) the (number|amount|price|cost|fare|percentage|share|total)|"
                             r"what percentage|in what year|when\b)", re.I)


def numbers_in(text):
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")}


NOT_FOUND = re.compile(r"^\W*(not found|not (stated|given|mentioned|in the (document|pages?))|unknown|no (answer|information)|"
                       r"the (document|pages?) (does|do) not (say|state|mention))\b", re.I)


def facts_backed(question, answer, quote):
    """An answer counts as backed only if every number it states is in the quote, and a question that asks for a
    number gets one. (The locked run found answers whose quote was on the page while the answer itself said
    something the quote does not, such as 'half the fare' where the page gives the amount.)"""
    said, quoted = numbers_in(answer), numbers_in(quote)
    if said - quoted:
        return False
    return bool(said) or not NUMBER_QUESTION.search(question or "")


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


class AnswerFromDocuments(Capability):
    name = "answer_from_documents"
    purpose = "Answer questions from the indexed documents, each with document, page and a supporting quote"
    permissions = ("use_model", "write_workspace")
    resources = {"ram_mb": 60, "uses_model": True}
    verification = "each quote is found on the cited page, and every number in the answer is in the quote"
    domains = ("research",)
    strategies = ("answer the failed questions again with more pages",)

    def run(self, job, params):
        idx = Index(json.loads((job.state.dir / "index.json").read_text()))
        qs = questions_from(job.state.goal()["request"])
        prev = {a["question"]: a for a in (job.state.task("answer").get("result") or {}).get("answers", [])}
        retry = set(params.get("retry_questions") or [])
        answers = []
        for q in qs:
            if q in prev and prev[q].get("verified") and q not in retry:
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
                answers.append({"question": q, "answer": "not found", "verified": False, "not_found": True})
                continue
            page = next((p for p in idx.pages if p["doc"] == data["doc"] and p["page"] == data["page"]), None)
            not_found = bool(NOT_FOUND.search(data["answer"] or ""))       # honest, but not an answer: never confirmed
            verified = not not_found and page is not None and len(norm(data["quote"])) > 8 and norm(data["quote"]) in norm(page["text"]) \
                and facts_backed(q, data["answer"], data["quote"])
            answers.append({"question": q, "answer": clean(data["answer"]), "doc": data["doc"], "page": data["page"], "quote": data["quote"],
                            "verified": verified, "not_found": not_found})
        md = ["# Answers", ""] + [f"{i}. **{a['question']}**  \n{a['answer']} ({a.get('doc', '?')}, page {a.get('page', '?')})"
                                  + (f"  \n> {a['quote']}" if a.get("quote") else "") + ("" if a["verified"] else "  \n_(not confirmed: the quote is not on that page, or the answer says more than the quote)_")
                                  for i, a in enumerate(answers, 1)]
        (job.workspace / "answers.md").write_text("\n".join(md) + "\n")
        (job.workspace / "answers.json").write_text(json.dumps(answers, indent=1))
        ok = sum(a["verified"] for a in answers)
        notes = [{"kind": "finding", "text": f"{a['question']} {a['answer']} (quote: \"{a['quote'][:200]}\")",
                  "source": f"{a['doc']} page {a['page']}", "verified": True, "tags": [a["doc"]]} for a in answers if a["verified"]]
        return Outcome(True, f"{ok} of {len(answers)} answers have a quote confirmed on the cited page", {"answers": answers, "memory_notes": notes},
                       ["answers.md", "answers.json"], made_by="model")

    def verify(self, job, params, outcome):
        retried = bool(params.get("strategy"))
        checks = []
        for i, a in enumerate(outcome.result["answers"], 1):
            if a.get("not_found") and retried:     # looked again with more pages and still nothing: say so, deliver the rest
                checks.append({"id": f"q{i}_answered", "pass": False, "gap": True,
                               "detail": f"not found in the documents: {a['question'][:80]}"})
            else:
                checks.append({"id": f"q{i}_quote_on_cited_page", "pass": a["verified"],
                               "detail": f"{a['question'][:60]} -> {a.get('doc')} p{a.get('page')}" + (" (answered 'not found')" if a.get("not_found") else "")})
        if not all(c["pass"] for c in checks):
            job.state.update_task("answer", params={"retry_questions": [a["question"] for a in outcome.result["answers"] if not a["verified"]]})
        return Verdict(all(c["pass"] for c in checks), checks, "quote found on the cited page and the answer's numbers in the quote (deterministic)")


COMPUTE = re.compile(r"\d|\b(calculate|compute|how (much|many)|percent|average|total|sum|probability|solve)\b", re.I)


class AnswerQuestion(Capability):
    name = "answer_question"
    purpose = "Answer a general question with the local model (not independently checkable)"
    permissions = ("use_model",)
    resources = {"ram_mb": 40, "uses_model": True}
    verification = "none possible offline: reported as unverified"
    domains = ("research",)

    def run(self, job, params):
        q = job.state.goal()["request"]
        if COMPUTE.search(q):                  # numbers involved: think, compute with real Python in the sandbox, check once
            from ..thinking import solve
            s = solve(lambda m, n: job.chat("builder", m, max_tokens=n, temperature=0.1), job.sandbox, q, require_code=True)
            if not s["answer"].strip():                 # only the note, no answer: that is a failure, never "answered"
                return Outcome(False, "the local model produced no answer" + (f" (its program printed: {s['printed'][:120]})" if s.get("printed") else ""))
            text = s["answer"] + (f"\n\n(Worked out with {s['tool_runs']} Python run(s) in the sandbox and checked once.)" if s["tool_runs"]
                                  else "\n\n(Checked once by a second pass.)")
            (job.workspace / "answer.md").write_text(clean(text) + "\n")
            return Outcome(True, clean(text)[:300], {"answer": clean(text), "tool_runs": s["tool_runs"]}, ["answer.md"], made_by="model")
        mem = job.memory_context() if hasattr(job, "memory_context") else ""
        text = job.ask_text("builder", "You are NEURON, an offline assistant. Answer clearly. Say so if you are not sure. No em dashes."
                            + (f"\n\n{mem}" if mem else ""), q, max_tokens=700)
        if not text:
            return Outcome(False, "no answer from the local model")
        (job.workspace / "answer.md").write_text(clean(text) + "\n")
        return Outcome(True, clean(text)[:300], {"answer": clean(text)}, ["answer.md"], made_by="model")

    def verify(self, job, params, outcome):
        # eval2 found two jobs that said VERIFIED for a wrong number: an answer nothing independent checked is reported as
        # "answered, not checked" (verdict UNVERIFIED), never as verified
        return Verdict(True, [{"id": "answered", "pass": True, "detail": "UNVERIFIED: a model answer, not checked against a source"}],
                       "unverified", unverified=True)


CAPABILITIES = [IndexDocuments(), AnswerFromDocuments(), AnswerQuestion()]
