VAT_RATE = 0.075          # Nigerian VAT: 7.5 percent


def vat(amount):
    """VAT on an amount in kobo, rounded to the nearest kobo."""
    return round(amount * VAT_RATE)
