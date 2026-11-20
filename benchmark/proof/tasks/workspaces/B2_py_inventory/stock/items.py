from dataclasses import dataclass


@dataclass
class Item:
    name: str
    on_hand: int
    reorder_level: int
