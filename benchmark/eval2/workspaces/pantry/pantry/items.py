from dataclasses import dataclass
from datetime import date


@dataclass
class Item:
    name: str
    quantity: int
    expires: date
    minimum: int = 1

    def is_low(self):
        return self.quantity < self.minimum
