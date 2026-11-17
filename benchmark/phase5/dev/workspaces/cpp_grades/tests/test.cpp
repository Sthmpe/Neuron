#include <iostream>
#include "grades.h"
static int failures = 0;
#define CHECK(c) do { if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\n"; } } while (0)
int main() {
    CHECK(letter(75) == 'A');
    CHECK(letter(60) == 'B');
    CHECK(letter(40) == 'D');
    CHECK(letter(39) == 'F');
    CHECK(average({50, 60, 70}) == 60.0);
    CHECK(count_passes({40, 39, 80}) == 2);
    if (!failures) std::cout << "all tests passed\n";
    return failures;
}
