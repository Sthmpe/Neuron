package shifts

import "testing"

func TestOvertime(t *testing.T) {
	if got := Overtime(46); got != 6 {
		t.Fatalf("Overtime(46)=%v want 6", got)
	}
	if got := Overtime(38); got != 0 {
		t.Fatalf("Overtime(38)=%v want 0", got)
	}
}

func TestWeeklyPay(t *testing.T) {
	if got := WeeklyPay(46, 1000); got != 49000 {
		t.Fatalf("WeeklyPay(46,1000)=%v want 49000", got)
	}
	if got := WeeklyPay(30, 1000); got != 30000 {
		t.Fatalf("WeeklyPay(30,1000)=%v want 30000", got)
	}
}

func TestTeamPay(t *testing.T) {
	if got := TeamPay([]float64{40, 44}, 500); got != 43000 {
		t.Fatalf("TeamPay=%v want 43000", got)
	}
}
