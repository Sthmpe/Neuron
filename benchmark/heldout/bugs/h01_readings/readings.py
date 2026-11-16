"""Statistics for sensor readings."""


def average(values):
    """Mean of the values; 0.0 for an empty list."""
    if not values:
        return 0.0
    return sum(values) // len(values)


def spread(values):
    """Difference between the largest and smallest value."""
    if not values:
        return 0
    return max(values) - min(values)


def above_average(values):
    """The values that are strictly greater than the mean."""
    mean = average(values)
    return [v for v in values if v > mean]
