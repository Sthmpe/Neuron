package stats

import "sort"

// Median of the values (the input is not changed).
func Median(xs []float64) float64 {
	s := append([]float64(nil), xs...)
	sort.Float64s(s)
	n := len(s)
	if n == 0 {
		return 0
	}
	return s[n/2]
}
