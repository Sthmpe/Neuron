#include <cmath>
#include <iostream>
#include <stdexcept>
#include "shapes.h"
int main() {
    int bad = 0;
    Triangle t(3, 4, 5);
    if (std::fabs(t.area() - 6) > 1e-9) bad++;
    if (t.perimeter() != 12) bad++;
    std::vector<std::unique_ptr<Shape>> v;
    v.push_back(std::make_unique<Triangle>(3, 4, 5));
    v.push_back(std::make_unique<Rectangle>(2, 2));
    if (std::fabs(total_area(v) - 10) > 1e-9) bad++;
    try { Triangle x(1, 2, 3); bad++; } catch (const std::invalid_argument&) {}
    try { Triangle x(0, 2, 2); bad++; } catch (const std::invalid_argument&) {}
    std::cout << (bad ? "hidden failed" : "hidden ok") << "\n";
    return bad;
}
