package stock

// NeedsReorder: an item is reordered when what is left is at or below its reorder level.
func NeedsReorder(left, level int) bool {
	return left <= level
}

// ReorderQty is how many to order to bring the item back up to its target (0 if no order is needed).
func ReorderQty(left, level, target int) int {
	if !NeedsReorder(left, level) {
		return 0
	}
	return target + left
}
