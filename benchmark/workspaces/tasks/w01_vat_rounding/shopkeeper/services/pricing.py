"""How much an order costs: loyalty discount first, then VAT on what is taxable."""
from ..util.money import percent_of

VAT_PERCENT = 7.5


def line_discount(line_total, discount_percent):
    return percent_of(line_total, discount_percent)


def vat_for(amount):
    """VAT at 7.5%, rounded to the nearest kobo."""
    return int(amount * VAT_PERCENT / 100)


def price_order(order, customer):
    """Returns a breakdown dict, all amounts in kobo."""
    discount_percent = customer.discount_percent()
    subtotal = discount = taxable = 0
    for line in order.lines:
        total = line.total()
        d = line_discount(total, discount_percent)
        subtotal += total
        discount += d
        if not line.vat_exempt:
            taxable += total - d
    vat = vat_for(taxable)
    return {"subtotal": subtotal, "discount": discount, "vat": vat, "total": subtotal - discount + vat}
