"""Layered settings: defaults overridden by user choices."""


def merge(defaults, overrides):
    """Return a new dict: `defaults` with `overrides` applied. Nested dicts are merged key by key,
    so overriding one nested value keeps its sibling values."""
    result = dict(defaults)
    for key, value in overrides.items():
        result[key] = value
    return result


def get_path(settings, path, default=None):
    """get_path(s, "screen.width") -> s["screen"]["width"]"""
    node = settings
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
