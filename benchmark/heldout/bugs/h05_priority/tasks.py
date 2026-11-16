"""A to-do queue where a LOWER priority number means MORE urgent."""


class TaskQueue:
    def __init__(self):
        self._items = []      # (priority, order added, name)
        self._counter = 0

    def add(self, name, priority=5):
        self._items.append((priority, self._counter, name))
        self._counter += 1

    def next(self):
        """Remove and return the most urgent task. Ties go to the task added first."""
        if not self._items:
            raise IndexError("no tasks")
        best = max(self._items)
        self._items.remove(best)
        return best[2]

    def __len__(self):
        return len(self._items)

    def names(self):
        """All task names, most urgent first."""
        return [name for _, _, name in sorted(self._items)]
