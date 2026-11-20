#include <cmath>
#include <iostream>
#include "shapes.h"
static int failures = 0;
#define CHECK(c) do { if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\n"; } } while (0)
int main() {
    std::vector<std::unique_ptr<Shape>> v;
    v.push_back(std::make_unique<Rectangle>(3, 4));
    v.push_back(std::make_unique<Circle>(1));
    CHECK(std::fabs(total_area(v) - (12 + M_PI)) < 1e-9);
    CHECK(Rectangle(3, 4).perimeter() == 14);
    if (!failures) std::cout << "all tests passed\n";
    return failures;
}
