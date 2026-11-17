"""A product on the shelf."""
from dataclasses import dataclass


@dataclass
class Product:
    sku: str
    name: str
    price: int            # kobo
    stock: int = 0
    reorder_level: int = 5
    vat_exempt: bool = False

    def needs_reorder(self):
        """True when stock has fallen to the reorder level or below."""
        return self.stock <= self.reorder_level

    def stock_value(self):
        return self.price * self.stock
