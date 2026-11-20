package stats

import "testing"

func TestSummary(t *testing.T) {
	if s := Summary([]float64{40, 10, 30, 20}); s != "days 4, total 100, median 25.0" {
		t.Errorf("got %q", s)
	}
	if s := Summary([]float64{5, 1, 3}); s != "days 3, total 9, median 3.0" {
		t.Errorf("got %q", s)
	}
}
