// Package ledger keeps accounts and converts currencies. Amounts are whole cents.
package ledger

import "fmt"

// RoundDiv divides a by b and rounds to the nearest whole number; halves round away from zero.
func RoundDiv(a, b int64) int64 {
	if b == 0 {
		panic("division by zero")
	}
	q, r := a/b, a%b
	if 2*abs(r) > abs(b) {
		if (a < 0) != (b < 0) {
			q--
		} else {
			q++
		}
	}
	return q
}

func abs(x int64) int64 {
	if x < 0 {
		return -x
	}
	return x
}

// Format shows cents as "1,234.56" (with a leading minus sign for negative amounts).
func Format(cents int64) string {
	sign := ""
	if cents < 0 {
		sign, cents = "-", -cents
	}
	whole, frac := cents/100, cents%100
	s := fmt.Sprintf("%d", whole)
	out := ""
	for i, c := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			out += ","
		}
		out += string(c)
	}
	return fmt.Sprintf("%s%s.%02d", sign, out, frac)
}
