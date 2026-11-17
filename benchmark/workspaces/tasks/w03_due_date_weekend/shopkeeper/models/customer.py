"""A customer, and how loyal they are."""
from dataclasses import dataclass, field

TIERS = [(500_000_00, "gold"), (100_000_00, "silver"), (0, "bronze")]   # lifetime spend in kobo
TIER_DISCOUNT = {"gold": 10, "silver": 5, "bronze": 0}                  # percent


@dataclass
class Customer:
    code: str
    name: str
    phone: str = ""
    lifetime_spend: int = 0
    tags: list = field(default_factory=list)

    def tier(self):
        for threshold, name in TIERS:
            if self.lifetime_spend >= threshold:
                return name
        return "bronze"

    def discount_percent(self):
        return TIER_DISCOUNT[self.tier()]
