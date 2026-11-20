package pay

import "testing"

func TestGross(t *testing.T) {
	if g := Gross(38, 1000); g != 38000 {
		t.Errorf("Gross(38, 1000) = %v, want 38000", g)
	}
	if g := Gross(44, 1000); g != 46000 {
		t.Errorf("Gross(44, 1000) = %v, want 46000", g)
	}
}
