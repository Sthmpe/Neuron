package pay

import "math"

// Gross pay for a week, rounded to whole naira.
func Gross(hours, rate float64) float64 {
	regular := math.Min(hours, StandardWeek)
	over := math.Max(0, hours-StandardWeek)
	return math.Round(regular*rate + over*rate*OvertimeRate)
}
