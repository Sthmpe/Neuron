"""A reverse Polish notation calculator: "3 4 +" means 3 + 4."""

OPERATORS = {"+", "-", "*", "/"}


def evaluate(expression):
    stack = []
    for token in expression.split():
        if token in OPERATORS:
            if len(stack) < 2:
                raise ValueError("not enough numbers")
            right = stack.pop()
            left = stack.pop()
            stack.append(apply(token, left, right))
        else:
            stack.append(float(token))
    if len(stack) != 1:
        raise ValueError("malformed expression")
    return stack[0]


def apply(operator, a, b):
    """a <operator> b"""
    if operator == "+":
        return a + b
    if operator == "-":
        return a - b
    if operator == "*":
        return a * b
    return a / b
