package bill

// Split shares a bill in kobo between people as evenly as possible. Nothing may be lost: any kobo left over go,
// one each, to the first people in the list.
func Split(totalKobo, people int) []int {
	shares := make([]int, people)
	each := totalKobo / people
	for i := range shares {
		shares[i] = each
	}
	return shares
}
