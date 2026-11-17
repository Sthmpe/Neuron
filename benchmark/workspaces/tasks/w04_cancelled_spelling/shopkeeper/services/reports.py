"""Simple reports for the owner."""
from collections import Counter


def best_sellers(repo, n=3):
    """The n SKUs sold most (by quantity, cancelled orders excluded); ties by SKU."""
    sold = Counter()
    for order in repo.orders.values():
        if order.status == "canceled":
            continue
        for line in order.lines:
            sold[line.sku] += line.quantity
    return [sku for sku, _ in sorted(sold.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def revenue_by_day(repo, pricing):
    """{date: total of paid or delivered orders that day}"""
    out = {}
    for order in repo.orders.values():
        if order.status in ("paid", "delivered"):
            customer = repo.customer(order.customer_code)
            out[order.date] = out.get(order.date, 0) + pricing(order, customer)["total"]
    return dict(sorted(out.items()))


def customers_by_tier(repo):
    out = {"gold": [], "silver": [], "bronze": []}
    for c in sorted(repo.customers.values(), key=lambda c: c.name):
        out[c.tier()].append(c.code)
    return out
