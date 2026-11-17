"""Times of day as minutes after midnight, written 'HH:MM'."""


def to_minutes(text):
    hours, minutes = text.split(":")
    h, m = int(hours), int(minutes)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"bad time {text}")
    return h * 60 + m


def to_text(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def overlaps(start_a, end_a, start_b, end_b):
    """Half-open ranges [start, end): touching ranges do not overlap."""
    return start_a < end_b and start_b < end_a
