from .length import FACTORS as LENGTH, convert_length


def convert(value, from_unit, to_unit):
    """Convert value between units of the same kind."""
    if from_unit in LENGTH and to_unit in LENGTH:
        return convert_length(value, from_unit, to_unit)
    raise ValueError(f"cannot convert {from_unit} to {to_unit}")
