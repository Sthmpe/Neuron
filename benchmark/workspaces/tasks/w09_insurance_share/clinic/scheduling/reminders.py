"""Text-message reminders the day before."""
import datetime


def day_before(date):
    return (datetime.date.fromisoformat(date) - datetime.timedelta(days=1)).isoformat()


def reminders_for(book, patients, doctors, today):
    """Messages to send today: one per booked appointment tomorrow, sorted by time."""
    out = []
    for a in sorted(book.appointments, key=lambda a: (a.date, a.start)):
        if a.status != "booked" or day_before(a.date) != today:
            continue
        p, d = patients[a.patient], doctors[a.doctor]
        out.append((p.phone, f"Hello {p.name.split()[0]}, a reminder of your appointment with {d.name} "
                             f"tomorrow at {a.start}."))
    return out
