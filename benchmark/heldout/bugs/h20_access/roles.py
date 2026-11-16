"""Which permissions each role has."""

ROLE_PERMISSIONS = {
    "viewer": {"read"},
    "editor": {"read", "write"},
    "admin": {"read", "write", "delete", "manage_users"},
}


def permissions_of(role):
    return ROLE_PERMISSIONS.get(role, set())
