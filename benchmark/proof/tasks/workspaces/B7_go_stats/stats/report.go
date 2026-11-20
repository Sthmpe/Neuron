package stats

import "fmt"

// Summary line for a list of daily sales.
func Summary(xs []float64) string {
	total := 0.0
	for _, x := range xs {
		total += x
	}
	return fmt.Sprintf("days %d, total %.0f, median %.1f", len(xs), total, Median(xs))
}
