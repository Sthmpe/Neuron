def to_minutes(text):
    """'09:30' -> 570 minutes after midnight."""
    text = text.strip()
    return int(text[0]) * 60 + int(text[3:5])


def from_minutes(m):
    return f"{m // 60:02d}:{m % 60:02d}"
