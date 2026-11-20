from .tax import vat


def subtotal(lines):
    return sum(line.amount() for line in lines)


def total(lines):
    s = subtotal(lines)
    return s + vat(s)
