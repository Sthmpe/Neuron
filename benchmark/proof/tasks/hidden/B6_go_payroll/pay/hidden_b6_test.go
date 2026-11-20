package pay

import "testing"

func TestHiddenOvertime(t *testing.T) {
	if g := Gross(50, 800); g != 44000 {
		t.Errorf("Gross(50, 800) = %v, want 44000", g)
	}
	if g := Gross(40, 1200); g != 48000 {
		t.Errorf("Gross(40, 1200) = %v, want 48000", g)
	}
}
