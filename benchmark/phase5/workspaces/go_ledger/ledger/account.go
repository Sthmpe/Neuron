package ledger

import (
	"errors"
	"sort"
)

var ErrInsufficient = errors.New("insufficient funds")

// Account is a balance in one currency with a history of entries.
type Account struct {
	Name     string
	Currency string
	balance  int64
	history  []int64
}

func (a *Account) Balance() int64 { return a.balance }

func (a *Account) Deposit(cents int64) {
	a.balance += cents
	a.history = append(a.history, cents)
}

// Withdraw takes money out; it fails and changes nothing if the balance is too small.
func (a *Account) Withdraw(cents int64) error {
	if cents > a.balance {
		return ErrInsufficient
	}
	a.balance -= cents
	a.history = append(a.history, -cents)
	return nil
}

// Transfer moves money between accounts, converting currency if needed. All or nothing.
func Transfer(from, to *Account, cents int64, rates *Rates) error {
	converted, err := rates.Convert(cents, from.Currency, to.Currency)
	if err != nil {
		return err
	}
	if err := from.Withdraw(cents); err != nil {
		return err
	}
	to.Deposit(converted)
	return nil
}

// Largest returns the n biggest deposits, largest first.
func (a *Account) Largest(n int) []int64 {
	var deps []int64
	for _, h := range a.history {
		if h > 0 {
			deps = append(deps, h)
		}
	}
	sort.Slice(deps, func(i, j int) bool { return deps[i] > deps[j] })
	if len(deps) > n {
		deps = deps[:n]
	}
	return deps
}
