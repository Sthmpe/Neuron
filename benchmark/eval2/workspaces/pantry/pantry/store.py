from datetime import date, timedelta

from .items import Item


class Pantry:
    def __init__(self):
        self.items = {}

    def add(self, name, quantity, expires, minimum=1):
        if name in self.items:
            self.items[name].quantity += quantity
        else:
            self.items[name] = Item(name, quantity, expires, minimum)
        return self.items[name]

    def use(self, name, quantity):
        item = self.items[name]
        if quantity > item.quantity:
            raise ValueError(f"only {item.quantity} {name} left")
        item.quantity -= quantity
        return item.quantity

    def expiring_within(self, days, today):
        limit = today + timedelta(days=days)
        return sorted(i.name for i in self.items.values() if i.expires <= limit)

    def low_stock(self):
        return sorted(i.name for i in self.items.values() if i.is_low())
