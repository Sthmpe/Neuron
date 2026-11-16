"""Convert 12-hour clock times to minutes after midnight."""


def to_minutes(text):
    """'7:30 am' -> 450, '12:15 am' -> 15, '12:00 pm' -> 720, '11:59 pm' -> 1439"""
    time_part, period = text.strip().lower().split()
    hours, minutes = (int(p) for p in time_part.split(":"))
    if not 1 <= hours <= 12 or not 0 <= minutes < 60 or period not in ("am", "pm"):
        raise ValueError("bad time")
    if hours == 12:
        hours = 0
    if period == "pm":
        hours += 12
    return hours * 60 + minutes


def duration(start, end):
    """Minutes from start to end on the same day."""
    return to_minutes(end) - to_minutes(start)
