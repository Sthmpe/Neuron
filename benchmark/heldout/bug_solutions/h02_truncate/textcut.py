"""Shorten text for display."""


def truncate(text, limit):
    """Return text unchanged if it fits in `limit` characters. Otherwise cut it and end with
    "..." so that the result is exactly `limit` characters long."""
    if limit < 3:
        raise ValueError("limit must be at least 3")
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


def initials(name):
    """'ada lovelace' -> 'AL'"""
    return "".join(part[0].upper() for part in name.split())


def title_case(text):
    return " ".join(w.capitalize() for w in text.split())
