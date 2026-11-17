package ledger

import "testing"

func TestRoundDiv(t *testing.T) {
	cases := [][3]int64{{10, 4, 3}, {9, 4, 2}, {-10, 4, -3}, {7, 2, 4}, {-7, 2, -4}, {100, 3, 33}}
	for _, c := range cases {
		if got := RoundDiv(c[0], c[1]); got != c[2] {
			t.Errorf("RoundDiv(%d,%d)=%d want %d", c[0], c[1], got, c[2])
		}
	}
}

func TestFormat(t *testing.T) {
	for in, want := range map[int64]string{123456789: "1,234,567.89", 5: "0.05", -150000: "-1,500.00", 99999: "999.99"} {
		if got := Format(in); got != want {
			t.Errorf("Format(%d)=%q want %q", in, got, want)
		}
	}
}

func TestRates(t *testing.T) {
	r := NewRates()
	r.Set("USD", "NGN", 1500*Scale) // 1 USD = 1500 NGN
	got, _ := r.Convert(1000, "USD", "NGN")
	if got != 1500000 {
		t.Errorf("10 USD = %d NGN cents, want 1500000", got)
	}
	back, _ := r.Convert(1500000, "NGN", "USD")
	if back != 1000 {
		t.Errorf("15000 NGN = %d USD cents, want 1000", back)
	}
	if _, err := r.Convert(1, "USD", "EUR"); err == nil {
		t.Error("expected an error for a missing rate")
	}
}

func TestTransfer(t *testing.T) {
	r := NewRates()
	r.Set("USD", "NGN", 1500*Scale)
	a := &Account{Name: "a", Currency: "USD"}
	b := &Account{Name: "b", Currency: "NGN"}
	a.Deposit(5000)
	if err := Transfer(a, b, 2000, r); err != nil {
		t.Fatal(err)
	}
	if a.Balance() != 3000 || b.Balance() != 3000000 {
		t.Errorf("balances %d %d", a.Balance(), b.Balance())
	}
	if err := Transfer(a, b, 9999, r); err != ErrInsufficient {
		t.Errorf("want ErrInsufficient, got %v", err)
	}
	if a.Balance() != 3000 || b.Balance() != 3000000 {
		t.Error("a failed transfer changed a balance")
	}
}

func TestLargest(t *testing.T) {
	a := &Account{}
	for _, d := range []int64{50, 300, 20, 300, 75} {
		a.Deposit(d)
	}
	_ = a.Withdraw(10)
	got := a.Largest(3)
	if len(got) != 3 || got[0] != 300 || got[1] != 300 || got[2] != 75 {
		t.Errorf("Largest = %v", got)
	}
}
