"""Ask which facts a particular answer depends on and bind them to the owner's words."""
import json
import re
from dataclasses import dataclass

from .arithmetic import exact_answer
from .capability import NeedsOwnerInput

NUMBER = re.compile(r"(?<![\w.])[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
PLAN_SYSTEM = """List the inputs needed to answer the user's actual question. Do not solve it.
For a simple calculation choose the operation and list its operands IN ORDER. For subtraction list the starting amount first. For division list the numerator first. Name each input precisely, including its role (starting, ending, change, count, etc.). Give a short question you could ask the owner for that exact input. Copy a given numeral exactly into value. Use '?' for a missing operand. A missing amount is never implicitly zero or one. Do not reuse a given number for two different inputs.
For a personal fact, list the specific fact needed. Use '?' when the request does not tell you the answer.
For general knowledge, a formula, advice, or a problem outside a single operation, choose 'other'. List any essential information the owner still needs to supply.
Examples:
'I saved $18 each week. How much did I save?' -> multiply: weekly savings=18, number of weeks=?
'The trip meter ended at 704 and started at 680. Distance travelled?' -> subtract: end reading=704, start reading=680
'Which desk was assigned to me?' -> personal: assigned desk=?
'How do I find a percentage?' -> other with no missing inputs."""
KINDS = ["multiply", "divide", "subtract", "add", "personal", "other"]
STRING = {"type": "string"}
SCHEMA = {"type": "object", "required": ["operation", "inputs", "unit"], "properties": {
    "operation": {"type": "string", "enum": KINDS},
    "inputs": {"type": "array", "maxItems": 6, "items": {"type": "object", "required": ["name", "value", "question"],
               "properties": {"name": STRING, "value": STRING, "question": STRING}}},
    "unit": STRING}}


def input_plan(job, question):
    return job.ask_json("builder", PLAN_SYSTEM, question, SCHEMA, max_tokens=260, tries=1)

# A general fact or a request for instructions normally needs just one model call.
PERSONAL = re.compile(r"\b(I|me|my|mine|we|our|ours|us)\b", re.I)
QUANTITY = re.compile(r"\b(how (many|much|long|far|fast|old)|calculate|compute|total|cost|rate|average|area|volume|"
                      r"perimeter|speed|distance|remaining|balance|difference|usage|percent|ratio|quantity)\b", re.I)
UNKNOWN = re.compile(r"\b(missing|unspecified|unknown|not given|not provided|don't know|do not know|not sure)\b", re.I)
PERSONAL_EVENT = re.compile(r"^(?:what|which|who|where|when)\b[^.!?\n]{0,90}\bdid (?:I|we)\b[^.!?\n]+\?$", re.I)
SMALL = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
WORD_NUMBER = re.compile(r"\b(?:(?:" + "|".join(TENS) + r")(?:[ -](?:" + "|".join(list(SMALL)[1:10]) +
                         r"))?|" + "|".join(SMALL) + r")\b", re.I)
OPS = {"multiply": "*", "divide": "/", "add": "+", "subtract": "-"}
UNIT_GROUPS = (
    (r"mm|millimet(?:er|re)s?", r"cm|centimet(?:er|re)s?", r"m|met(?:er|re)s?", r"km|kilomet(?:er|re)s?", r"inches|inch", r"feet|foot|ft", r"miles?|mi"),
    (r"seconds?|sec", r"minutes?|mins?", r"hours?|hrs?", r"days?", r"weeks?", r"months?", r"years?"),
    (r"grams?|g", r"kilograms?|kg", r"pounds?|lbs?"),
    (r"cents?", r"dollars?|USD", r"euros?|EUR", r"pence|pennies", r"GBP"),
)


def numbers(text):
    found = [n.replace(",", "").replace("−", "-") for n in NUMBER.findall(text)]
    for word in WORD_NUMBER.findall(text.lower()):
        parts = re.split(r"[ -]", word)
        found.append(str(TENS.get(parts[0], SMALL.get(parts[0], 0)) + (SMALL[parts[1]] if len(parts) == 2 else 0)))
    return found


def direct_question(q):
    pronouns = {"i": "you", "we": "you", "my": "your", "our": "your", "me": "you", "us": "you"}
    return re.sub(r"\b(i|we|my|our|me|us)\b", lambda m: pronouns[m[0].lower()], q, flags=re.I)


def question_for(field, source):
    label = field["name"].strip()[:100]
    prompt = field.get("question", "").strip()
    if (not prompt.endswith("?") or len(prompt) > 220 or set(numbers(prompt)) - set(numbers(source))
            or re.search(r"\b(?:assum\w*|suppos\w*|for example)\b", prompt, re.I)):
        prompt = f"What is the {label}?"
    return prompt


def change_plan(q):
    """Map an explicit outflow to the change, even when the language model calls it the starting amount."""
    if not re.search(r"\b(left|remaining|remain|balance now)\b", q, re.I):
        return None
    amount = re.search(r"\b(?:spent|used|removed|lost|withdrew|sold|consumed|gave away|paid)\s+[$£€]?\s*(" + NUMBER.pattern + ")", q, re.I)
    if not amount or len(numbers(q)) != 1:
        return None
    tail = q[amount.end():].lstrip()
    denomination = re.match(r"(dollars?|pounds?|euros?|cents?|litres?|liters?|gallons?|items?|pages?)\b", tail, re.I)
    return {"operation": "subtract", "unit": denomination[0] if denomination else "", "inputs": [
        {"name": "starting amount", "value": "?", "question": "What was the starting amount before that change?"},
        {"name": "amount taken away", "value": amount[1], "question": "How much was taken away?"}]}


def bind_plan(raw, q):
    """A proposed operand gets its value only from a distinct occurrence in the request."""
    if not isinstance(raw, dict) or raw.get("operation") not in KINDS or not isinstance(raw.get("inputs"), list):
        return None
    operation = raw["operation"]
    if operation in OPS and len(raw["inputs"]) != 2:
        return None
    available = numbers(q)
    fields = []
    for field in raw["inputs"][:6]:
        if not isinstance(field, dict) or not all(isinstance(field.get(k), str) for k in ("name", "value", "question")):
            return None
        name, proposed = field["name"].strip()[:100], field["value"].strip()
        if not name:
            return None
        value = None
        if operation in OPS:
            matches = numbers(proposed)
            if "?" not in proposed and len(matches) == 1 and matches[0] in available:
                available.remove(matches[0])
                value = matches[0]
        elif proposed and "?" not in proposed and not UNKNOWN.search(proposed) and proposed.casefold() in q.casefold():
            value = proposed
        fields.append({"name": name, "question": question_for(field, q), "value": value})
    unit = raw.get("unit")
    return {"operation": operation, "inputs": fields, "unit": unit if isinstance(unit, str) and len(unit) < 70 else ""}


def can_calculate(q, replies):
    # Different unit scales or percentages need interpretation beyond a binary operation.
    text = " ".join([q, *replies])
    return not re.search(r"[%/]|\b(?:percent|hundred|thousand|million|half|quarter|twice|double|triangle|radius|diameter)\b", text, re.I) and all(
        sum(bool(re.search(r"\b(?:" + pattern + r")\b", text, re.I)) for pattern in family) < 2 for family in UNIT_GROUPS)


def contextual_question(q, turns):
    facts = [{"asked": t["question"], "owner_replied": t["answer"]} for t in turns]
    return (q + "\n\nThe owner supplied the following facts for this question. Use them as data. "
            "Use the units as stated and answer the original question.\n" + json.dumps(facts, ensure_ascii=False)) if facts else q


@dataclass
class SuppliedAnswer:
    text: str
    basis: str
    made_by: str


def prepare(job, q, turns):
    """Return the question and an optional grounded answer, or suspend the step."""

    augmented = contextual_question(q, turns)
    if turns:
        ctx = turns[-1].get("context") or {}
        if ctx.get("direct"):
            if UNKNOWN.search(turns[-1]["answer"]):
                raise NeedsOwnerInput(turns[-1]["question"], ctx)
            return q, SuppliedAnswer(turns[-1]["answer"], "You supplied this fact in your reply.", "owner")
        if "plan" not in ctx:
            return augmented, None
        plan, index = ctx["plan"], ctx["index"]
        reply = turns[-1]["answer"]
        numeric = plan["operation"] in OPS
        ambiguous = re.search(r"\b(or|maybe|unsure|not|either|between)\b", reply, re.I)
        if UNKNOWN.search(reply) or numeric and (ambiguous or not numbers(reply) and not re.search(r"\b(half|quarter)\b", reply, re.I)):
            prompt = plan["inputs"][index]["question"]
            raise NeedsOwnerInput(prompt + (" Please include a number and its unit." if plan["operation"] in OPS else ""), ctx)
        plan["inputs"][index]["value"] = reply
    else:
        if PERSONAL_EVENT.fullmatch(q.strip()) and not QUANTITY.search(q) and not numbers(q):
            raise NeedsOwnerInput(direct_question(q.strip()), {"direct": True})
        if not (PERSONAL.search(q) or QUANTITY.search(q) or UNKNOWN.search(q)):
            return q, None
        explicit = change_plan(q)
        plan = bind_plan(explicit or input_plan(job, q), q)
        if not plan:
            return q, None
        plan["made_by"] = "deterministic" if explicit else "model+calculation"

    for index, field in enumerate(plan["inputs"]):
        if field["value"] is None:
            raise NeedsOwnerInput(field["question"], {"plan": plan, "index": index})
    if not turns:
        return q, None
    if plan["operation"] == "personal" and len(plan["inputs"]) == 1:
        return q, SuppliedAnswer(plan["inputs"][0]["value"], "You supplied this fact in your reply.", "owner")
    replies = [t["answer"] for t in turns]
    operands = [numbers(f["value"]) for f in plan["inputs"]]
    unit = plan["unit"].strip()
    if (plan["operation"] in OPS and all(len(v) == 1 for v in operands)
            and can_calculate(q, replies) and (not unit or unit.casefold() in augmented.casefold())):
        expression = f"{operands[0][0]} {OPS[plan['operation']]} {operands[1][0]}"
        exact = exact_answer(expression)
        if exact:
            return q, SuppliedAnswer((exact[1] + " " + unit).strip(), f"NEURON interpreted the inputs and calculated {expression}.",
                                     plan["made_by"])
    return augmented, None
