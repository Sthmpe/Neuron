package parking

// Fee is what a car pays in naira: the first 30 minutes are free, then 200 per started hour, at most 2000 a day.
func Fee(minutes int) int {
	if minutes < 30 {
		return 0
	}
	hours := (minutes + 59) / 60
	fee := hours * 200
	if fee > 2000 {
		fee = 2000
	}
	return fee
}

// DayTakings adds up the fees for every car of the day.
func DayTakings(stays []int) int {
	total := 0
	for _, m := range stays {
		total += Fee(m)
	}
	return total
}
