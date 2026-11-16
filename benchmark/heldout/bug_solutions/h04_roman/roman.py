"""Roman numerals."""

VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
PAIRS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
         (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def to_roman(number):
    if not 0 < number < 4000:
        raise ValueError("out of range")
    out = ""
    for value, symbol in PAIRS:
        while number >= value:
            out += symbol
            number -= value
    return out


def from_roman(text):
    """'XIV' -> 14. A smaller symbol before a larger one is subtracted."""
    total = 0
    for i, ch in enumerate(text):
        value = VALUES[ch]
        if i + 1 < len(text) and VALUES[text[i + 1]] > value:
            total -= value
        else:
            total += value
    return total
