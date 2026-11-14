"""A least-recently-used cache."""


class LRUCache:
    """Keeps at most `capacity` entries. When full, the entry that was used
    (read or written) longest ago is thrown away."""

    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.data = {}
        self.order = []      # keys, least recently used first

    def _touch(self, key):
        if key in self.order:
            self.order.remove(key)
        self.order.append(key)

    def get(self, key, default=None):
        if key not in self.data:
            return default
        return self.data[key]

    def put(self, key, value):
        if key not in self.data and len(self.data) >= self.capacity:
            oldest = self.order.pop(0)
            del self.data[oldest]
        self.data[key] = value
        self._touch(key)

    def __len__(self):
        return len(self.data)

    def keys(self):
        """Keys from least to most recently used."""
        return list(self.order)
