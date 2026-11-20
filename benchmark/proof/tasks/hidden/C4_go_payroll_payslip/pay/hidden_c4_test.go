package pay

import "testing"

func TestHiddenPayslip(t *testing.T) {
	if v := Tax(25000); v != 0 {
		t.Errorf("Tax(25000) = %v", v)
	}
	if v := Tax(46000); v != 1600 {
		t.Errorf("Tax(46000) = %v", v)
	}
	if s := Payslip("Ada", 44, 1000); s != "Ada: gross 46000, tax 1600, net 44400" {
		t.Errorf("got %q", s)
	}
	if s := Payslip("Bo", 20, 1000); s != "Bo: gross 20000, tax 0, net 20000" {
		t.Errorf("got %q", s)
	}
}
