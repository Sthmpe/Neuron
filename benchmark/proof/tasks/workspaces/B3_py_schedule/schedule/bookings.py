from .timeutil import to_minutes


def overlaps(a, b):
    """a and b are (start, end) strings like ('10:00', '11:30'); touching ends do not overlap."""
    return to_minutes(a[0]) < to_minutes(b[1]) and to_minutes(b[0]) < to_minutes(a[1])


def clashes(bookings):
    """Pairs of booking names that overlap, in the order given."""
    out = []
    for i, (n1, t1) in enumerate(bookings):
        for n2, t2 in bookings[i + 1:]:
            if overlaps(t1, t2):
                out.append((n1, n2))
    return out
