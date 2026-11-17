"""Keeps everything in memory, with a JSON save/load so data survives a restart."""
import json
from dataclasses import asdict

from ..models import Customer, Order, OrderLine, Product


class NotFound(KeyError):
    pass


class Repository:
    def __init__(self):
        self.products, self.customers, self.orders = {}, {}, {}
        self._next_order = 1

    # products
    def add_product(self, product):
        if product.sku in self.products:
            raise ValueError(f"duplicate sku {product.sku}")
        self.products[product.sku] = product

    def product(self, sku):
        try:
            return self.products[sku]
        except KeyError:
            raise NotFound(sku) from None

    def search_products(self, text):
        """Products whose name contains `text` (any case), sorted by name."""
        text = text.lower()
        return sorted((p for p in self.products.values() if text in p.name.lower()), key=lambda p: p.name)

    # customers
    def add_customer(self, customer):
        self.customers[customer.code] = customer

    def customer(self, code):
        try:
            return self.customers[code]
        except KeyError:
            raise NotFound(code) from None

    # orders
    def new_order_number(self):
        number = f"ORD-{self._next_order:05d}"
        self._next_order += 1
        return number

    def add_order(self, order):
        self.orders[order.number] = order

    def order(self, number):
        try:
            return self.orders[number]
        except KeyError:
            raise NotFound(number) from None

    def orders_for(self, customer_code):
        return [o for o in self.orders.values() if o.customer_code == customer_code]

    # persistence
    def save(self, path):
        data = {"products": [asdict(p) for p in self.products.values()],
                "customers": [asdict(c) for c in self.customers.values()],
                "orders": [asdict(o) for o in self.orders.values()],
                "next_order": self._next_order}
        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        repo = cls()
        for p in data["products"]:
            repo.add_product(Product(**p))
        for c in data["customers"]:
            repo.add_customer(Customer(**c))
        for o in data["orders"]:
            lines = [OrderLine(**l) for l in o.pop("lines")]
            repo.add_order(Order(lines=lines, **o))
        repo._next_order = data["next_order"]
        return repo
