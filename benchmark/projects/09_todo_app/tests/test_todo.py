import unittest

from models import Task
from todo import TodoList


class TodoTests(unittest.TestCase):
    def test_add_and_complete(self):
        todo = TodoList()
        task = todo.add("Buy milk")
        task.complete()
        self.assertEqual(todo.open_tasks(), [])

    def test_tags_are_normalised(self):
        task = Task("Call Ada")
        task.add_tag("  Work ")
        task.add_tag("work")
        self.assertEqual(task.tags, ["work"])

    def test_new_task_has_no_tags(self):
        todo = TodoList()
        todo.add("Pay rent", "home", "money")
        second = todo.add("Write report")
        self.assertEqual(second.tags, [])

    def test_filter_by_tag(self):
        todo = TodoList()
        todo.add("Pay rent", "home")
        todo.add("Write report", "work")
        todo.add("Book flight")
        self.assertEqual([t.title for t in todo.with_tag("work")], ["Write report"])
        self.assertEqual([t.title for t in todo.with_tag("home")], ["Pay rent"])

    def test_all_tags(self):
        todo = TodoList()
        todo.add("A", "x")
        todo.add("B", "y")
        self.assertEqual(todo.all_tags(), ["x", "y"])

    def test_empty_title(self):
        with self.assertRaises(ValueError):
            Task("   ")
