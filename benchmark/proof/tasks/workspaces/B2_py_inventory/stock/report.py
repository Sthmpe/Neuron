from .rules import needs_reorder


def reorder_list(items):
    """Names of the items to reorder, in alphabetical order."""
    return sorted(i.name for i in items if needs_reorder(i))


def summary(items):
    names = reorder_list(items)
    return f"{len(names)} to reorder: " + ", ".join(names) if names else "nothing to reorder"
