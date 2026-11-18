package stock

import "testing"

func TestReorder(t *testing.T) {
	if !NeedsReorder(10, 10) || NeedsReorder(11, 10) {
		t.Errorf("reorder level is wrong")
	}
	if got := ReorderQty(5, 10, 50); got != 45 {
		t.Errorf("ReorderQty(5, 10, 50) = %d, want 45", got)
	}
	if got := ReorderQty(20, 10, 50); got != 0 {
		t.Errorf("ReorderQty(20, 10, 50) = %d, want 0", got)
	}
}
