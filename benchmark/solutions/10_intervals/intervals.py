"""Working with closed intervals given as (start, end) pairs."""


def merge(intervals):
    """Merge overlapping or touching intervals. Returns a sorted list of (start, end)."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def total_length(intervals):
    """Total length covered, counting overlaps only once."""
    return sum(end - start for start, end in merge(intervals))


def covers(intervals, point):
    return any(start <= point <= end for start, end in merge(intervals))


def gaps(intervals):
    """The uncovered stretches between the merged intervals."""
    merged = merge(intervals)
    return [(a[1], b[0]) for a, b in zip(merged, merged[1:])]
