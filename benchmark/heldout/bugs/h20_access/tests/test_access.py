import unittest

from access import User, can, require, visible_actions


class Tests(unittest.TestCase):
    def test_single_permission(self):
        self.assertTrue(can(User("vi", "viewer"), "read"))
        self.assertFalse(can(User("vi", "viewer"), "write"))

    def test_all_permissions_are_needed(self):
        self.assertFalse(can(User("ed", "editor"), "write", "delete"))
        self.assertTrue(can(User("ad", "admin"), "write", "delete"))

    def test_require(self):
        with self.assertRaises(PermissionError):
            require(User("ed", "editor"), "read", "manage_users")

    def test_unknown_role(self):
        self.assertFalse(can(User("x", "guest"), "read"))

    def test_visible_actions(self):
        actions = {"open": ["read"], "save": ["read", "write"], "purge": ["write", "delete"]}
        self.assertEqual(visible_actions(User("ed", "editor"), actions), ["open", "save"])
