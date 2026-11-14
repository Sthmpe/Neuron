"""A tiny shopping cart."""


class Cart:
    def __init__(self):
        self.items = []          # list of (name, unit_price, quantity)
        self.discount_percent = 0

    def add(self, name, unit_price, quantity=1):
        if unit_price < 0 or quantity <= 0:
            raise ValueError("bad price or quantity")
        self.items.append((name, unit_price, quantity))

    def set_discount(self, percent):
        if not 0 <= percent <= 100:
            raise ValueError("discount must be between 0 and 100")
        self.discount_percent = percent

    def subtotal(self):
        return sum(price * qty for _, price, qty in self.items)

    def total(self):
        """Subtotal minus the percentage discount, rounded to 2 decimals."""
        return round(self.subtotal() * self.discount_percent / 100, 2)
