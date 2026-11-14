"""Calendar helpers."""

DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def is_leap_year(year):
    return year % 4 == 0 and year % 100 != 0


def days_in_month(year, month):
    if not 1 <= month <= 12:
        raise ValueError("month must be 1..12")
    if month == 2 and is_leap_year(year):
        return 29
    return DAYS[month - 1]


def day_of_year(year, month, day):
    """1 for 1 January, 365 or 366 for 31 December."""
    if not 1 <= day <= days_in_month(year, month):
        raise ValueError("no such day")
    return sum(days_in_month(year, m) for m in range(1, month)) + day


def days_in_year(year):
    return 366 if is_leap_year(year) else 365
