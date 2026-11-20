from dataclasses import dataclass


@dataclass
class Line:
    """One line of an invoice. Amounts are in kobo."""
    description: str
    quantity: int
    unit_price: int

    def amount(self):
        return self.quantity * self.unit_price
