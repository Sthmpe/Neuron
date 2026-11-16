"""One shelf in the warehouse."""


class Shelf:
    def __init__(self, name, capacity):
        self.name = name
        self.capacity = capacity
        self.stock = 0

    def free_space(self):
        return self.capacity - self.stock
