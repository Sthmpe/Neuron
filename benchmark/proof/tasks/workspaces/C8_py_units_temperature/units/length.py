FACTORS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0}


def convert_length(value, from_unit, to_unit):
    return value * FACTORS[from_unit] / FACTORS[to_unit]
