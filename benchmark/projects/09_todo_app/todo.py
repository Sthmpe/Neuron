"""The to-do list itself."""
from models import Task


class TodoList:
    def __init__(self):
        self.tasks = []

    def add(self, title, *tags):
        task = Task(title)
        for tag in tags:
            task.add_tag(tag)
        self.tasks.append(task)
        return task

    def with_tag(self, tag):
        tag = tag.strip().lower()
        return [t for t in self.tasks if tag in t.tags]

    def open_tasks(self):
        return [t for t in self.tasks if not t.done]

    def all_tags(self):
        return sorted({tag for t in self.tasks for tag in t.tags})
