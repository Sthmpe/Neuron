"""Split an arithmetic expression into tokens."""

SYMBOLS = "+-*/()"


def tokenize(text):
    """'12+3*(4-1)' -> ['12', '+', '3', '*', '(', '4', '-', '1', ')']"""
    tokens = []
    number = ""
    for ch in text:
        if ch.isdigit() or ch == ".":
            number += ch
            continue
        if number:
            tokens.append(number)
            number = ""
        if ch in SYMBOLS:
            tokens.append(ch)
        elif not ch.isspace():
            raise ValueError(f"unexpected character {ch!r}")
    return tokens


def count_numbers(text):
    return sum(1 for t in tokenize(text) if t[0].isdigit())
