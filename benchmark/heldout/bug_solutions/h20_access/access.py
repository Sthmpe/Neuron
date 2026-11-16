"""Decide whether a user may do something."""
from roles import permissions_of


class User:
    def __init__(self, name, role):
        self.name, self.role = name, role


def can(user, *needed):
    """True only if the user's role has EVERY one of the needed permissions."""
    have = permissions_of(user.role)
    return all(p in have for p in needed)


def require(user, *needed):
    if not can(user, *needed):
        raise PermissionError(f"{user.name} may not {' + '.join(needed)}")


def visible_actions(user, actions):
    """actions: {name: [permissions it needs]} -> names the user may use, sorted."""
    return sorted(name for name, needs in actions.items() if can(user, *needs))
