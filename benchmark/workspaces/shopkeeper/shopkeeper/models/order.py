"""An order: lines of products with quantities."""
from dataclasses import dataclass, field


@dataclass
class OrderLine:
    sku: str
    quantity: int
    unit_price: int        # kobo, the price at the moment of ordering
    vat_exempt: bool = False

    def total(self):
        return self.quantity * self.unit_price


@dataclass
class Order:
    number: str
    customer_code: str
    date: str
    lines: list = field(default_factory=list)
    status: str = "open"        # open -> paid -> delivered, or cancelled

    def add(self, line):
        for existing in self.lines:
            if existing.sku == line.sku and existing.unit_price == line.unit_price:
                existing.quantity += line.quantity
                return
        self.lines.append(line)

    def subtotal(self):
        return sum(l.total() for l in self.lines)

    def item_count(self):
        return sum(l.quantity for l in self.lines)
