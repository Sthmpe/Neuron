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


STOP = set("how many much what which who whom whose when where why is are was were be been the a an of in on at to for from by "
           "with there their this that these those does do did per each any some all it its they them you your our we "
           "can could should would will may might about into than then also only just not no yes".split())
CLAUSE = re.compile(r"[;.!?]\s+|,\s*|\s+(?:and|but|while|whereas)\s+", re.I)    # "Yellow chairs: 3" stays one clause


def _words(text):
    return [w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in STOP and len(w) > 2]


def tied_numbers(question, quote):
    """The numbers in the quote that belong to what the question asks about, or None if the quote leaves no doubt.
    "There are 16 blue chairs and 3 yellow chairs" for "How many yellow chairs?" gives {"3"}: the clause that holds
    the question's distinguishing word (one the quote uses only once, here "yellow") holds the number that answers it.
    Astra's review of main d54bf4d found "16 yellow chairs" accepted because 16 was somewhere in the quote."""
    if len(numbers_in(quote)) < 2:
        return None                                       # only one number: nothing to confuse
    stem = lambda w: w[:5]
    counts = Counter(stem(w) for w in _words(quote))
    wanted = {stem(w) for w in _words(question)}
    distinct = {w for w in wanted if counts.get(w) == 1}   # appears exactly once in the quote: it pins the clause
    if not distinct:
        return None
    tied = set()
    for clause in CLAUSE.split(quote):
        toks = re.findall(r"[a-z]+|\d[\d,]*(?:\.\d+)?", clause.lower())
        nums = [(i, t.replace(",", "")) for i, t in enumerate(toks) if t[0].isdigit()]
        for i, t in enumerate(toks):
            if nums and not t[0].isdigit() and t not in STOP and len(t) > 2 and stem(t) in distinct:
                tied.add(min(nums, key=lambda n: abs(n[0] - i))[1])        # the number closest to that word
    return tied or None


def facts_backed(question, answer, quote):
    """An answer counts as backed only if every number it states is in the quote AND belongs to what was asked, a
    question that asks for a number gets one, and an answer without numbers shares words with its quote.
    (The locked run found 'half the fare' where the page gives the amount; Astra's review found '16 yellow chairs'
    where the page said 16 blue and 3 yellow.)"""
    said, quoted = numbers_in(answer), numbers_in(quote)
    if said - quoted:
        return False
    if said:
        tied = tied_numbers(question, quote)
        return tied is None or bool(said & tied)
    if NUMBER_QUESTION.search(question or ""):
        return False
    own = set(_words(answer)) - set(_words(question))      # what the answer adds must come from the quote
    return not own or bool(own & set(_words(quote)))


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
            quote_n = norm(data["quote"] or "")
            if len(quote_n) > 8 and (page is None or quote_n not in norm(page["text"])):
                # the quote is copied exactly but the page number is wrong (core proof D8, 2 GB: "The clinic employs 6
                # nurses" quoted from page 1, cited as page 2): cite the page where the quote really is, if it is on
                # exactly one page of the documents
                where = [p for p in idx.pages if quote_n in norm(p["text"])]
                if len(where) == 1:
                    job.state.decide("answer", "citation", f"{q[:60]}: quote found on {where[0]['doc']} page {where[0]['page']}, "
                                                           f"not page {data['page']}; cited where it is")
                    page, data["doc"], data["page"] = where[0], where[0]["doc"], where[0]["page"]
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
                  "source": f"{a['doc']} page {a['page']}", "verified": True, "tags": [a["doc"]],
                  "meta": {"question": a["question"], "answer": a["answer"], "quote": a["quote"], "rule": "doc-facts-2"}}
                 for a in answers if a["verified"]]
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
    purpose = "Answer a general question and state which results have independent evidence"
    permissions = ("use_model", "write_workspace")
    resources = {"ram_mb": 40, "uses_model": True}
    verification = "exact arithmetic checked against the delivered answer; other answers marked unverified"
    domains = ("research",)

    def run(self, job, params):
        # Exact arithmetic, the owner-input questions and the "Unverified." label are Astra's design (research/astra
        # 6847ef3); the require-code solver, the empty-answer failure and the computed-result protection are Claude's.
        from ..arithmetic import exact_answer
        from ..capability import NeedsOwnerInput
        from ..owner_input import METHOD, prepare
        q = job.state.goal()["request"]
        exact = exact_answer(q)
        if exact is not None:                      # a pure calculation: exact, no model, independently checked below
            expression, text = exact
            (job.workspace / "answer.md").write_text(text + "\n")
            return Outcome(True, text, {"answer": text, "expression": expression}, ["answer.md"])
        turns = params.get("owner_inputs", [])
        if getattr(job, "fast", False) and not turns:
            done = self._fast(job, q)              # easy work: one model call, like the bare model
            if done is not None:
                return done
        q, supplied = prepare(job, q, turns)       # may pause the step with a question for the owner
        text = supplied.text if supplied else None
        method = supplied.basis if supplied else ""
        result, extra = {}, ""
        if text is None and COMPUTE.search(q) and not METHOD.search(q):
            from ..thinking import solve
            s = solve(lambda m, n: job.chat("builder", m, max_tokens=n, temperature=0.1), job.sandbox, q, require_code=True)
            text = s["answer"]
            result["tool_runs"] = s["tool_runs"]
            method = (f"The model wrote a program that ran {s['tool_runs']} time(s) in the sandbox, then a second pass checked it."
                      if s["tool_runs"] else "The model answered and a second pass checked it.")
            if s.get("check_disagreed"):
                extra = f" A second pass said {s['check_disagreed']}; the result the program printed is kept."
            if not (text or "").strip():
                return Outcome(False, "the local model produced no answer" + (f" (its program printed: {s['printed'][:120]})" if s.get("printed") else ""))
        elif text is None:
            mem = job.memory_context() if hasattr(job, "memory_context") else ""
            text = job.ask_text("builder", "You are NEURON, an offline assistant. Answer clearly. If a specific input only the owner "
                                "can provide is missing, reply with NEED_INPUT followed by one question asking for that fact. "
                                "For a formula or method, explain with variables. Say so if you are not sure. No em dashes."
                                + (f"\n\n{mem}" if mem else ""), q, max_tokens=700)
            method = "The local model supplied this answer."
            missing = re.fullmatch(r"NEED_INPUT\s*:?\s*(.{4,220}\?)", (text or "").strip(), re.I)
            if missing:
                raise NeedsOwnerInput(missing[1])
        answer = (text if supplied and supplied.made_by == "owner" else clean(text or "")).strip()
        if not answer:
            return Outcome(False, "the local model did not supply a final answer")
        (job.workspace / "answer.md").write_text(f"{answer}\n\nUnverified. {method}{extra}\n")
        return Outcome(True, answer[:300], {**result, "answer": answer}, ["answer.md"], made_by=supplied.made_by if supplied else "model")

    FAST_SYSTEM = ("You are NEURON, an offline assistant. Answer the request directly and clearly. If it needs a calculation, "
                   "write one short Python program in a ```python block that computes the answer from the numbers given and "
                   "prints only the result. No em dashes.")
    # offered only for personal requests: told it may ask, the 2 GB model asked instead of answering "Who wrote Things
    # Fall Apart?" (internal easy set, first run)
    ASK_RULE = " If a fact only the owner can know is missing, reply only: NEED_INPUT: <one question>."
    @staticmethod
    def _allowed_numbers(q):
        """Numbers a program may use although the request does not state them: 0, 1 and 2 always; 100 and the values a
        stated percentage implies (15% -> 0.15, 0.85, 1.15) only with a percentage; time constants only with time words;
        1000 only with metric units. Anything else is an input the model made up (eval: '100 - 7' for 'how much is
        left' when the starting amount was never given)."""
        from ..owner_input import numbers
        allowed = {0.0, 1.0, 2.0}
        given = [float(n) for n in numbers(q)]
        allowed |= set(given)
        if re.search(r"%|percent", q, re.I):
            allowed.add(100.0)
            for n in given:
                allowed |= {round(n / 100, 6), round(1 - n / 100, 6), round(1 + n / 100, 6)}
        def units(family):                  # distinct units of one kind named in the request
            return {m.lower()[:4] for m in re.findall(family, q, re.I)}
        # a conversion factor only makes sense when two different units of the same kind appear (minutes and hours)
        if len(units(r"\b(second|minute|hour|day|week|month|year)s?\b")) >= 2:
            allowed |= {7.0, 12.0, 24.0, 30.0, 31.0, 52.0, 60.0, 365.0, 3600.0, 86400.0}
        if len(units(r"\b(km|kilomet\w*|mm|millimet\w*|cm|centimet\w*|metres?|meters?|kg|kilogram\w*|grams?|ml|millilit\w*|litres?|liters?)\b")) >= 2:
            allowed |= {10.0, 100.0, 1000.0}
        return allowed

    def _fast(self, job, q):
        """One model call. Questions get the model's answer; calculations get a program run in the sandbox, so the number
        comes from code, not from the model's head. Returns None to fall back to the careful path when the shortcut is
        not safe: the program failed or used a number that is not in the request (an input the model invented)."""
        from ..capability import NeedsOwnerInput
        from ..owner_input import DECLARED_MISSING, PERSONAL_EVENT, QUANTITY, direct_question, numbers
        from ..thinking import final_answer, python_block
        missing = DECLARED_MISSING.search(q)
        if missing and q[:missing.start()].strip():                    # "I have not given the opening balance"
            raise NeedsOwnerInput(f"What is the {missing[1].strip()}?", {"end_of_question": missing.start()})
        if PERSONAL_EVENT.fullmatch(q.strip()) and not QUANTITY.search(q) and not numbers(q):
            raise NeedsOwnerInput(direct_question(q.strip()), {"direct": True})
        from ..owner_input import PERSONAL
        personal = bool(PERSONAL.search(q))
        mem = job.memory_context() if hasattr(job, "memory_context") else ""
        text = job.ask_text("builder", self.FAST_SYSTEM + (self.ASK_RULE if personal else "") + (f"\n\n{mem}" if mem else ""),
                            q, max_tokens=700)
        if not text:
            return Outcome(False, "the local model did not supply an answer")
        need = re.search(r"NEED_INPUT\s*:?\s*(.{4,220}\?)", text, re.I)
        if need and not python_block(text):
            if personal:
                raise NeedsOwnerInput(need[1].strip())
            return None                            # asked about something it should know: the careful path decides
        code = python_block(text)
        if code:
            ok = self._allowed_numbers(q)
            invented = sorted({n.lstrip("-") for n in numbers(code) if not any(abs(abs(float(n)) - a) < 1e-9 for a in ok)})
            if invented:
                job.log(f"  fast path: the program uses numbers not in the request ({invented[:4]}); taking the careful path")
                return None
            import tempfile
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / "calc.py").write_text(code)
                res = job.sandbox.run(["python3", "calc.py"], d, timeout=20) if job.sandbox else None
            printed = (res.output or "").strip() if res is not None and res.ok else ""
            if not printed or len(printed.splitlines()) > 3:
                return None
            answer = printed if len(printed.splitlines()) == 1 else final_answer(text) or printed
            method = "The model wrote a program that computed this; it ran once in the sandbox."
        else:
            if QUANTITY.search(q) and not numbers(text):
                return None                        # asked for a number, got none: the careful path decides
            answer = clean(final_answer(text) or text).strip()
            method = "The local model supplied this answer."
        if not answer:
            return Outcome(False, "the local model did not supply a final answer")
        (job.workspace / "answer.md").write_text(f"{clean(answer)}\n\nUnverified. {method}\n")
        return Outcome(True, clean(answer)[:300], {"answer": clean(answer), "fast": True, "tool_runs": 1 if code else 0},
                       ["answer.md"], made_by="model")

    def verify(self, job, params, outcome):
        from ..arithmetic import exact_answer
        path = job.workspace / "answer.md"
        delivered = path.read_text().strip() if path.is_file() else ""
        exact = exact_answer(job.state.goal()["request"])
        if exact is not None:                      # the only answers here that are really checked
            expression, expected = exact
            ok = delivered == expected
            return Verdict(ok, [{"id": "exact_arithmetic", "pass": ok, "detail": f"{expression} = {expected}"}],
                           "exact rational arithmetic checked against answer.md")
        answer = outcome.result.get("answer", "")
        ok = bool(answer) and delivered.startswith(answer + "\n\nUnverified.")
        # eval2 found jobs that said VERIFIED for a wrong number: an unchecked answer is UNVERIFIED, never VERIFIED
        return Verdict(ok, [{"id": "answer_delivered", "pass": ok, "detail": "UNVERIFIED: a model answer, not checked against a source"}],
                       "unverified", unverified=True)


CAPABILITIES = [IndexDocuments(), AnswerFromDocuments(), AnswerQuestion()]
