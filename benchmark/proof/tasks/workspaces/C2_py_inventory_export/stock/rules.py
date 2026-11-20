def needs_reorder(item):
    """An item is reordered when what is left is at or below its reorder level."""
    return item.on_hand <= item.reorder_level
