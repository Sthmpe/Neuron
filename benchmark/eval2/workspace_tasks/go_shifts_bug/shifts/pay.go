package shifts

// Weekly pay: hours up to 40 at the base rate, hours above 40 at 1.5 times the base rate. Amounts in naira.

const StandardHours = 40.0

func Overtime(hours float64) float64 {
	if hours <= StandardHours {
		return 0
	}
	return hours - StandardHours
}

func WeeklyPay(hours, rate float64) float64 {
	ot := Overtime(hours)
	return hours*rate + ot*rate*1.5
}

func TeamPay(hours []float64, rate float64) float64 {
	total := 0.0
	for _, h := range hours {
		total += WeeklyPay(h, rate)
	}
	return total
}
