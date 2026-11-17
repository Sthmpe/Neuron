"""Date helpers. Dates are ISO strings 'YYYY-MM-DD'."""
import datetime


def parse(text):
    return datetime.date.fromisoformat(text)


def add_days(text, days):
    return (parse(text) + datetime.timedelta(days=days)).isoformat()


def days_between(start, end):
    """Whole days from start to end (negative if end is earlier)."""
    return (parse(end) - parse(start)).days


def is_weekend(text):
    return parse(text).weekday() >= 5


def next_working_day(text):
    """The same day if it is a weekday, otherwise the following Monday."""
    day = parse(text)
    while day.weekday() >= 5:
        day += datetime.timedelta(days=1)
    return day.isoformat()
