"""Invoices and payment terms."""
from ..util.dates import add_days, days_between, next_working_day
from ..util.money import format_naira
from .pricing import price_order

TERMS_DAYS = 14


def due_date(order_date):
    """Payment is due 14 days after the order; if that falls on a weekend, the next working day."""
    return add_days(order_date, TERMS_DAYS)


def days_overdue(order_date, today):
    """0 if not overdue yet."""
    return max(0, days_between(due_date(order_date), today))


def late_fee(amount, overdue_days):
    """1% of the amount for each full week overdue, at most 10%."""
    weeks = overdue_days // 7
    return amount * min(weeks, 10) // 100


def invoice_lines(order, repo):
    customer = repo.customer(order.customer_code)
    bill = price_order(order, customer)
    out = [f"Invoice {order.number} for {customer.name}"]
    for line in order.lines:
        name = repo.product(line.sku).name
        out.append(f"{line.quantity} x {name} @ {format_naira(line.unit_price)} = {format_naira(line.total())}")
    out.append(f"Subtotal {format_naira(bill['subtotal'])}")
    if bill["discount"]:
        out.append(f"Loyalty discount -{format_naira(bill['discount'])}")
    out.append(f"VAT {format_naira(bill['vat'])}")
    out.append(f"Total {format_naira(bill['total'])}")
    out.append(f"Due {due_date(order.date)}")
    return out
