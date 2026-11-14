"""Data model for the to-do app."""


class Task:
    def __init__(self, title, tags=[]):
        if not title.strip():
            raise ValueError("a task needs a title")
        self.title = title.strip()
        self.tags = tags
        self.done = False

    def add_tag(self, tag):
        tag = tag.strip().lower()
        if tag and tag not in self.tags:
            self.tags.append(tag)

    def complete(self):
        self.done = True

    def __repr__(self):
        return f"Task({self.title!r}, tags={self.tags}, done={self.done})"
