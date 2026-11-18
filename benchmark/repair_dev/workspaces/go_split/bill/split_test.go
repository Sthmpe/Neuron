package bill

import "testing"

func TestSplit(t *testing.T) {
	got := Split(1000, 3)
	want := []int{334, 333, 333}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("Split(1000, 3) = %v, want %v", got, want)
		}
	}
	sum := 0
	for _, s := range Split(1001, 4) {
		sum += s
	}
	if sum != 1001 {
		t.Errorf("Split(1001, 4) adds up to %d, want 1001", sum)
	}
}
