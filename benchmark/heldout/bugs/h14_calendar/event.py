"""A calendar event with a start and end hour."""


class Event:
    def __init__(self, title, start, end):
        if end <= start:
            raise ValueError("an event must end after it starts")
        self.title, self.start, self.end = title, start, end

    def length(self):
        return self.end - self.start
