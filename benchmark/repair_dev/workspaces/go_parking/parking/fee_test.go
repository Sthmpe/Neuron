package parking

import "testing"

func TestFee(t *testing.T) {
	cases := map[int]int{0: 0, 29: 0, 30: 0, 31: 200, 60: 200, 61: 400, 600: 2000, 900: 2000}
	for m, want := range cases {
		if got := Fee(m); got != want {
			t.Errorf("Fee(%d) = %d, want %d", m, got, want)
		}
	}
}

func TestDayTakings(t *testing.T) {
	if got := DayTakings([]int{30, 45, 125}); got != 800 {
		t.Errorf("DayTakings = %d, want 800", got)
	}
}
