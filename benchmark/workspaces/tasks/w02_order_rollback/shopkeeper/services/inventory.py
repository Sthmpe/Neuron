"""Stock movements."""


class OutOfStock(Exception):
    pass


class Inventory:
    def __init__(self, repo):
        self.repo = repo
        self.movements = []      # (sku, change, reason)

    def receive(self, sku, quantity):
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        self.repo.product(sku).stock += quantity
        self.movements.append((sku, quantity, "received"))

    def reserve(self, sku, quantity):
        """Take stock for an order. Nothing changes if there is not enough."""
        product = self.repo.product(sku)
        if quantity > product.stock:
            raise OutOfStock(f"{sku}: only {product.stock} left")
        product.stock -= quantity
        self.movements.append((sku, -quantity, "reserved"))

    def release(self, sku, quantity):
        """Give stock back (for example when an order is cancelled)."""
        self.repo.product(sku).stock += quantity
        self.movements.append((sku, quantity, "released"))

    def reorder_list(self):
        """SKUs that need reordering, lowest stock first."""
        low = [p for p in self.repo.products.values() if p.needs_reorder()]
        return [p.sku for p in sorted(low, key=lambda p: (p.stock, p.sku))]

    def total_value(self):
        return sum(p.stock_value() for p in self.repo.products.values())
