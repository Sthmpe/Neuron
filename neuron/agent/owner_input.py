"""Ask which facts a particular answer depends on and bind them to the owner's words."""
import json
import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

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
METHOD = re.compile(r"^\s*(?:how (?:do|can|should) (?:I|we|you|one) (?:calculate|compute|measure|derive|convert)|"
                    r"(?:what(?:'s| is)|give me) the formula)\b", re.I)
DECLARED_MISSING = re.compile(r"(?:^|(?<=[.!?])\s+)(?:I|we) (?:have not|haven't|did not|didn't|never) "
                              r"(?:supplied|provided|given|included|specified|mentioned) (?:the |my |our )?"
                              r"([\w -]{2,65})[.!]?\s*$", re.I)
WORD_OP = {"plus": "+", "minus": "-", "times": "*", "multiplied by": "*", "divided by": "/"}
SMALL = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
WORD_NUMBER = re.compile(r"\b(?:(?:" + "|".join(TENS) + r")(?:[ -](?:" + "|".join(list(SMALL)[1:10]) +
                         r"))?|" + "|".join(SMALL) + r")\b", re.I)
OPS = {"multiply": "*", "divide": "/", "add": "+", "subtract": "-"}
UNIT_GROUPS = (
    (r"mm|millimet(?:er|re)s?", r"cm|centimet(?:er|re)s?", r"m|met(?:er|re)s?", r"km|kilomet(?:er|re)s?", r"inches|inch", r"feet|foot|ft", r"miles?|mi"),
    (r"seconds?|sec", r"minutes?|mins?", r"hours?|hrs?|h", r"days?", r"weeks?", r"months?", r"years?"),
    (r"grams?|g", r"kilograms?|kg", r"pounds?|lbs?"),
    (r"cents?", r"dollars?|USD", r"euros?|EUR", r"pence|pennies", r"GBP"),
)
# In order within each family, measured in metres, seconds and grams respectively.
SCALES = (("0.001", "0.01", "1", "1000", "0.0254", "0.3048", "1609.344"),
          ("1", "60", "3600", "86400", "604800", None, None),
          ("1", "1000", "453.59237"))
UNIT_NAME = r"(?:" + "|".join(pattern for group in UNIT_GROUPS for pattern in group) + r")"
UNIT = re.compile(r"(?<![a-z])" + UNIT_NAME + r"\b", re.I)
RATE_UNIT = re.compile(r"(?<![a-z])(" + UNIT_NAME + r")\s*(?:/|\bper\b)\s*(" + UNIT_NAME + r")\b", re.I)


def numbers(text):
    found = [n.replace(",", "").replace("−", "-") for n in NUMBER.findall(text)]
    for word in WORD_NUMBER.findall(text.lower()):
        parts = re.split(r"[ -]", word)
        found.append(str(TENS.get(parts[0], SMALL.get(parts[0], 0)) + (SMALL[parts[1]] if len(parts) == 2 else 0)))
    return found


def numeric_sources(text):
    """Keep the source unit attached to each distinct mention, including repeated equal numbers."""
    found = []
    for match in sorted([*NUMBER.finditer(text), *WORD_NUMBER.finditer(text)], key=lambda m: m.start()):
        unit = UNIT.match(text[match.end():].lstrip())
        value = numbers(match[0])[0]
        found.append((value, value + (" " + unit[0] if unit else "")))
    return found


def scales_in(text):
    return {(family, i) for family, patterns in enumerate(UNIT_GROUPS) for i, pattern in enumerate(patterns)
            if re.search(r"(?<![a-z])(?:" + pattern + r")\b", text, re.I)}


def requested_unit(unit, q):
    if not unit or unit.casefold() in q.casefold():
        return unit
    rate = RATE_UNIT.fullmatch(unit)
    if rate:
        for written in RATE_UNIT.finditer(q):
            if all(scales_in(written[i]) == scales_in(rate[i]) for i in (1, 2)):
                return written[0]
    return None


def closed_arithmetic(q):
    words = re.sub(r"^how much is\s+", "", q.strip(), flags=re.I)
    expr = re.sub(r"\b(plus|minus|times|multiplied by|divided by)\b", lambda m: WORD_OP[m[0].lower()], words, flags=re.I)
    return expr != q and exact_answer(expr) is not None


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
    available = numeric_sources(q)
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
            mention = next((entry for entry in available if matches == [entry[0]]), None)
            if "?" not in proposed and mention:
                available.remove(mention)
                value = mention[1]
        elif proposed and "?" not in proposed and not UNKNOWN.search(proposed) and proposed.casefold() in q.casefold():
            value = proposed
        fields.append({"name": name, "question": question_for(field, q), "value": value})
    unit = raw.get("unit")
    return {"operation": operation, "inputs": fields, "unassigned_numbers": available,
            "unit": unit if isinstance(unit, str) and len(unit) < 70 else ""}


def can_calculate(q, replies):
    # Different unit scales or percentages need interpretation beyond a binary operation.
    text = " ".join([q, *replies])
    return not special_calculation(text) and all(sum(f == family for f, _ in scales_in(text)) < 2 for family in range(len(UNIT_GROUPS)))


def special_calculation(text):
    return re.search(r"%|\d\s*/\s*\d|\b(?:percent|hundred|thousand|million|half|quarter|twice|double|triangle|radius|diameter)\b", text, re.I)


def calculation_terms(plan, q, replies):
    """Convert a simple operand into the requested unit using a known exact scale."""
    source = " ".join([q, *replies])
    if special_calculation(source):
        return None
    units = scales_in(source)
    mixed = {f for f, _ in units if sum(k == f for k, _ in units) > 1}
    targets = scales_in(plan["unit"])
    terms = []
    converted_families = set()
    for field in plan["inputs"]:
        raw = field["value"]
        values = numbers(raw)
        if len(values) != 1:
            return None
        expr = values[0]
        measures = scales_in(raw)
        if any(f in mixed for f, _ in measures):
            if len(measures) != 1:
                return None
            family, start = measures.pop()
            target = [i for f, i in targets if f == family]
            if len(target) != 1 or family >= len(SCALES):
                return None
            old, new = SCALES[family][start], SCALES[family][target[0]]
            if old is None or new is None:
                return None
            scale = Fraction(old) / Fraction(new)
            if scale != 1:
                expr = f"({expr} * {scale.numerator} / {scale.denominator})"
                converted_families.add(family)
        terms.append(expr)
    return terms if mixed <= converted_families else None


def contextual_question(q, turns):
    facts = [{"asked": t["question"], "owner_replied": t["answer"]} for t in turns]
    return (q + "\n\nThe owner supplied the following facts for this question. Use them as data. "
            "Use the units as stated and answer the original question.\n" + json.dumps(facts, ensure_ascii=False)) if facts else q


@dataclass
class SuppliedAnswer:
    text: str
    basis: str
    made_by: str


def declared_answer(job, q, turns, context):
    """When the owner explicitly named the missing fact, reconcile compound arithmetic with the supplied value."""
    original = q[:context["end_of_question"]].strip()
    augmented = contextual_question(original, turns)
    if UNKNOWN.search(turns[-1]["answer"]):
        raise NeedsOwnerInput(turns[-1]["question"], context)
    if not numbers(original) or not numbers(turns[-1]["answer"]) or not can_calculate(original, [t["answer"] for t in turns]):
        return augmented, None
    schema = {"type": "object", "required": ["expression", "unit"], "properties": {"expression": STRING, "unit": STRING}}
    calc = job.ask_json("builder", "Translate the original question and the owner's supplied fact into one arithmetic "
                        "expression. Copy the input numbers and use + - * / and parentheses. Give the requested unit, "
                        "or an empty unit. If more information is needed, leave the expression empty.",
                        augmented, schema, max_tokens=90, tries=1)
    if isinstance(calc, dict) and isinstance(calc.get("expression"), str) and isinstance(calc.get("unit"), str):
        expression, unit = calc["expression"].strip(), calc["unit"].strip()
        source = original + " " + turns[-1]["answer"]
        exact = exact_answer(expression)
        available = Counter(n.lstrip("-") for n in numbers(source))
        used = Counter(n.lstrip("-") for n in numbers(expression))
        if exact and available == used and (not unit or unit.casefold() in source.casefold()):
            return original, SuppliedAnswer((exact[1] + " " + unit).strip(),
                                            f"NEURON interpreted the inputs and calculated {expression}.", "model+calculation")
    return augmented, None


def usable_quantity(field, reply):
    if re.search(r"\b(or|maybe|unsure|not|either|between)\b", reply, re.I):
        return False
    if not numbers(reply) and not re.search(r"\b(half|quarter)\b", reply, re.I):
        return False
    # Reject a duration offered as a width, for example. An unadorned number inherits the question's unit.
    hints = (r"length|width|height|distance|breadth|depth", r"time|duration|elapsed", r"mass|weight", r"price|cost|balance")
    name = field["name"]
    expected = next((i for i, hint in enumerate(hints) if re.search(r"\b(?:" + hint + r")\b", name, re.I)), None)
    units = {family for family, _ in scales_in(reply)}
    return expected is None or not units or expected in units


def prepare(job, q, turns):
    """Return the question and an optional grounded answer, or suspend the step."""

    augmented = contextual_question(q, turns)
    if turns:
        ctx = turns[-1].get("context") or {}
        if "end_of_question" in ctx:
            return declared_answer(job, q, turns, ctx)
        if ctx.get("direct"):
            if UNKNOWN.search(turns[-1]["answer"]):
                raise NeedsOwnerInput(turns[-1]["question"], ctx)
            return q, SuppliedAnswer(turns[-1]["answer"], "You supplied this fact in your reply.", "owner")
        if "plan" not in ctx:
            return augmented, None
        plan, index = ctx["plan"], ctx["index"]
        reply = turns[-1]["answer"]
        numeric = plan["operation"] in OPS
        if UNKNOWN.search(reply) or numeric and not usable_quantity(plan["inputs"][index], reply):
            prompt = plan["inputs"][index]["question"]
            raise NeedsOwnerInput(prompt + (" Please include a number and its unit." if plan["operation"] in OPS else ""), ctx)
        plan["inputs"][index]["value"] = reply
    else:
        if METHOD.search(q) or closed_arithmetic(q):
            return q, None
        missing = DECLARED_MISSING.search(q)
        if missing and q[:missing.start()].strip():
            raise NeedsOwnerInput(f"What is the {missing[1].strip()}?", {"end_of_question": missing.start()})
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
    unit = requested_unit(plan["unit"].strip(), q)
    if plan["operation"] in OPS and not plan.get("unassigned_numbers") and unit is not None:
        operands = calculation_terms(plan, q, replies)
        if operands:
            expression = f"{operands[0]} {OPS[plan['operation']]} {operands[1]}"
            exact = exact_answer(expression)
            if exact:
                return q, SuppliedAnswer((exact[1] + " " + unit).strip(), f"NEURON interpreted the inputs and calculated {expression}.",
                                         plan["made_by"])
    return augmented, None
