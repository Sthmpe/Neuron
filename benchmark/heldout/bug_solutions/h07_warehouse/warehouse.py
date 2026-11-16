"""Moves stock on and off shelves."""
from shelf import Shelf


class OutOfStock(Exception):
    pass


class Warehouse:
    def __init__(self):
        self.shelves = {}

    def add_shelf(self, name, capacity):
        self.shelves[name] = Shelf(name, capacity)

    def store(self, name, quantity):
        shelf = self.shelves[name]
        if quantity > shelf.free_space():
            raise ValueError("not enough space")
        shelf.stock += quantity

    def take(self, name, quantity):
        """Remove stock. Raises OutOfStock if the shelf holds less than `quantity`."""
        shelf = self.shelves[name]
        if quantity > shelf.stock:
            raise OutOfStock(f"{name} has only {shelf.stock}")
        shelf.stock -= quantity

    def total_stock(self):
        return sum(s.stock for s in self.shelves.values())
