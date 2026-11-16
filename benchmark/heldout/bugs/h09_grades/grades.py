"""Turn marks into letter grades."""

BOUNDARIES = [(90, "A"), (80, "B"), (70, "C"), (60, "D")]


def letter(mark):
    """90 and above is an A, 80-89 a B, 70-79 a C, 60-69 a D, anything lower an F."""
    for lowest, grade in BOUNDARIES:
        if mark > lowest:
            return grade
    return "F"


def summary(marks):
    """How many of each letter, e.g. {"A": 2, "C": 1}."""
    counts = {}
    for m in marks:
        counts[letter(m)] = counts.get(letter(m), 0) + 1
    return counts


def passed(mark):
    return letter(mark) != "F"
