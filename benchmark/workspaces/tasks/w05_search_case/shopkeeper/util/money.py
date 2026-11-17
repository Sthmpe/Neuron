"""Money is always kept in whole kobo (1 naira = 100 kobo) to avoid rounding errors."""


def to_kobo(naira):
    """'1,250.50' or 1250.5 -> 125050"""
    if isinstance(naira, str):
        naira = naira.replace(",", "").replace("₦", "").strip()
    return int(round(float(naira) * 100))


def format_naira(kobo):
    """125050 -> '₦1,250.50'"""
    sign = "-" if kobo < 0 else ""
    kobo = abs(kobo)
    return f"{sign}₦{kobo // 100:,}.{kobo % 100:02d}"


def percent_of(kobo, percent):
    """percent% of an amount, rounded to the nearest kobo (halves round up)."""
    return (kobo * percent * 2 + 100) // 200


def split_evenly(kobo, parts):
    """Split an amount into `parts` shares that add up exactly; earlier shares get the extra kobo."""
    if parts <= 0:
        raise ValueError("parts must be positive")
    base, extra = divmod(kobo, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]
