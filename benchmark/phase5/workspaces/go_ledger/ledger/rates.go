package ledger

import "fmt"

// Scale is the fixed-point scale for rates: a rate of 1.0 is stored as Scale.
const Scale int64 = 1_000_000_000

// Rates holds exchange rates as fixed-point numbers: target cents per source cent, times Scale.
type Rates struct {
	scaled map[string]int64
}

func NewRates() *Rates { return &Rates{scaled: map[string]int64{}} }

func key(from, to string) string { return from + ">" + to }

// Set records that one unit of `from` buys rate/Scale units of `to`, and the reverse rate too.
func (r *Rates) Set(from, to string, rate int64) {
	r.scaled[key(from, to)] = rate
	r.scaled[key(to, from)] = RoundDiv(Scale*Scale, rate)
}

// Convert turns an amount in `from` cents into `to` cents, rounded to the nearest cent.
func (r *Rates) Convert(amount int64, from, to string) (int64, error) {
	if from == to {
		return amount, nil
	}
	rate, ok := r.scaled[key(from, to)]
	if !ok {
		return 0, fmt.Errorf("no rate for %s to %s", from, to)
	}
	return RoundDiv(amount*rate, Scale), nil
}
