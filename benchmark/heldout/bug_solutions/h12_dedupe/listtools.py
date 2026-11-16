"""Small list helpers."""


def dedupe(items):
    """Remove repeated items, keeping the FIRST occurrence of each, in the original order."""
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def chunk(items, size):
    """[1,2,3,4,5] with size 2 -> [[1,2],[3,4],[5]]"""
    if size <= 0:
        raise ValueError("size must be positive")
    return [items[i:i + size] for i in range(0, len(items), size)]


def most_common(items):
    """The item that appears most often; on a tie, the one seen first."""
    best, best_count = None, 0
    for item in dedupe(items):
        n = items.count(item)
        if n > best_count:
            best, best_count = item, n
    return best
