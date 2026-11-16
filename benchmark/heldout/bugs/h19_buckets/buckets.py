"""Group numbers into equal-width buckets for a histogram."""


def bucket_start(value, width):
    """Start of the bucket a value falls in. With width 10: 0-9 -> 0, 10-19 -> 10, 20-29 -> 20."""
    return round(value / width) * width


def histogram(values, width):
    """{bucket start: how many values fall in that bucket}"""
    counts = {}
    for v in values:
        start = bucket_start(v, width)
        counts[start] = counts.get(start, 0) + 1
    return counts


def fullest(values, width):
    """Start of the bucket holding the most values (lowest start wins a tie)."""
    h = histogram(values, width)
    return min(h, key=lambda start: (-h[start], start))
