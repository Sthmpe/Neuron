#include "shapes.h"
#include <cmath>

double Rectangle::area() const { return w * h; }
double Rectangle::perimeter() const { return 2 * (w + h); }
double Circle::area() const { return M_PI * r * r; }
double Circle::perimeter() const { return 2 * M_PI * r; }

double total_area(const std::vector<std::unique_ptr<Shape>>& shapes) {
    double t = 0;
    for (const auto& s : shapes) t += s->area();
    return t;
}
