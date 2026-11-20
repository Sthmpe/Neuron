"""Exact answers for requests consisting entirely of a small arithmetic expression."""
# Written by Astra (Codex) on research/astra (6847ef3); adopted unchanged by Claude on research/claude.

import ast
import operator
import re
from decimal import Decimal, localcontext
from fractions import Fraction

PREFIX = re.compile(r"^(?:what is|what's|calculate|compute|evaluate)\s+", re.I)
FRACTION_SUFFIX = re.compile(r"(?:[?.]\s*(?:give|return|provide)\s+(?:the|an?)\s+|\s+as\s+(?:an?|the)\s+)"
                             r"(?:exact\s+)?fraction[.!?]?\s*$", re.I)
OPERATIONS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
SIGNS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _value(node, expression):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Fraction(ast.get_source_segment(expression, node))
    if isinstance(node, ast.UnaryOp) and type(node.op) in SIGNS:
        return SIGNS[type(node.op)](_value(node.operand, expression))
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATIONS:
        return OPERATIONS[type(node.op)](_value(node.left, expression), _value(node.right, expression))
    raise ValueError("unsupported arithmetic")


def exact_answer(request):
    """Return (expression, exact answer text), or None if any part of the request is outside the grammar."""
    if len(request) > 256:
        return None
    text = PREFIX.sub("", request.strip(), count=1)
    suffix = FRACTION_SUFFIX.search(text)
    expression = (text[:suffix.start()] if suffix else text).strip().removesuffix("?").strip()
    expression = expression.translate(str.maketrans({"×": "*", "÷": "/", "−": "-"}))
    if not re.fullmatch(r"[0-9.()+*/\s-]+", expression, re.ASCII):
        return None
    try:
        tree = ast.parse(expression, mode="eval")
        if not any(isinstance(node, ast.BinOp) for node in ast.walk(tree)):
            return None
        value = _value(tree.body, expression)
    except (ValueError, SyntaxError, ZeroDivisionError, RecursionError):
        return None
    if suffix or value.denominator == 1:
        return expression, str(value)
    # A terminating decimal needs at most this many places. A repeating result stays a fraction.
    with localcontext() as ctx:
        ctx.prec = len(str(abs(value.numerator))) + value.denominator.bit_length() + 1
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return expression, format(decimal, "f") if Fraction(decimal) == value else str(value)
