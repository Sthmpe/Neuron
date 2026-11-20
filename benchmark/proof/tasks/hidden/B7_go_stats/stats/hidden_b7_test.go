package stats

import "testing"

func TestHiddenMedian(t *testing.T) {
	cases := map[float64][]float64{2.5: {1, 2, 3, 4}, 7: {7}, 0: {}, 4: {9, 1, 4}}
	for want, xs := range cases {
		if got := Median(xs); got != want {
			t.Errorf("Median(%v) = %v, want %v", xs, got, want)
		}
	}
}
