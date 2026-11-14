"""Binary search helpers for sorted lists."""


def index_of(items, target):
    """Index of target in the sorted list `items`, or -1 if it is not there."""
    lo, hi = 0, len(items) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def contains(items, target):
    return index_of(items, target) != -1


def insert_position(items, target):
    """Index at which target should be inserted to keep `items` sorted."""
    lo, hi = 0, len(items)
    while lo < hi:
        mid = (lo + hi) // 2
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo
