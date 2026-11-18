def shopping_list(pantry):
    lines = []
    for name in pantry.low_stock():
        item = pantry.items[name]
        lines.append(f"{name}: buy {item.minimum - item.quantity}")
    return lines


def summary(pantry, today):
    soon = pantry.expiring_within(3, today)
    return {"items": len(pantry.items), "low": len(pantry.low_stock()), "expiring_soon": soon}
