"""Free appointment slots in a doctor's day."""
from ..core.times import overlaps, to_minutes, to_text


def day_slots(doctor, length=30):
    """All slots of `length` minutes between day start and end, skipping lunch."""
    start, end = to_minutes(doctor.day_start), to_minutes(doctor.day_end)
    lunch_start, lunch_end = (to_minutes(t) for t in doctor.lunch)
    slots = []
    t = start
    while t + length <= end:
        if not (lunch_start < t < lunch_end):
            slots.append(to_text(t))
        t += length
    return slots


def free_slots(doctor, booked, length=30):
    """Slots not overlapping any booked (start, minutes) appointment."""
    taken = [(to_minutes(s), to_minutes(s) + m) for s, m in booked]
    out = []
    for slot in day_slots(doctor, length):
        s = to_minutes(slot)
        if not any(overlaps(s, s + length, a, b) for a, b in taken):
            out.append(slot)
    return out


def first_free(doctor, booked, after="00:00", length=30):
    after_m = to_minutes(after)
    for slot in free_slots(doctor, booked, length):
        if to_minutes(slot) >= after_m:
            return slot
    return None
