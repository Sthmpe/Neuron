"""Split a bill. All amounts are whole cents."""


def split(total_cents, people):
    """Share the bill as evenly as possible. The shares must add up to exactly the total;
    when it does not divide evenly, the first people pay one cent more."""
    if people <= 0:
        raise ValueError("need at least one person")
    share = total_cents // people
    extra = total_cents % people
    return [share + 1 if i < extra else share for i in range(people)]


def with_tip(total_cents, percent):
    return total_cents + round(total_cents * percent / 100)


def format_cents(cents):
    return f"{cents // 100}.{cents % 100:02d}"
