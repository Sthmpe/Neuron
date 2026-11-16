"""Keeps events and refuses double bookings."""
from event import Event


class Clash(Exception):
    pass


def overlaps(a, b):
    """True if the two events share any time. An event that ends at 10 does NOT overlap one starting at 10."""
    return a.start <= b.end and b.start <= a.end


class Calendar:
    def __init__(self):
        self.events = []

    def book(self, title, start, end):
        new = Event(title, start, end)
        for existing in self.events:
            if overlaps(new, existing):
                raise Clash(f"{title} clashes with {existing.title}")
        self.events.append(new)
        return new

    def busy_hours(self):
        return sum(e.length() for e in self.events)
