"""Helpers for nested lists."""


def flatten(items):
    """[1, [2, [3, 4]], 5] -> [1, 2, 3, 4, 5], at any depth."""
    out = []
    for item in items:
        if isinstance(item, list):
            out.append(flatten(item))
        else:
            out.append(item)
    return out


def depth(items):
    """[] and [1, 2] have depth 1; [1, [2]] has depth 2."""
    if not isinstance(items, list):
        return 0
    return 1 + max((depth(i) for i in items), default=0)


def count_leaves(items):
    return len(flatten(items))
