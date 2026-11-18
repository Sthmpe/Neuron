#include <iostream>
#include "tickets.h"
static int failures = 0;
#define CHECK(c) do { if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\n"; } } while (0)
int main() {
    CHECK(fare(8) == 150);
    CHECK(fare(30) == 300);
    CHECK(fare(65) == 0);
    CHECK(fare(70) == 0);
    CHECK(day_total({8, 30, 65}) == 450);
    CHECK(free_riders({65, 64, 80}) == 2);
    if (!failures) std::cout << "all tests passed\n";
    return failures;
}
