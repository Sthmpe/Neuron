#pragma once
#include <string>
#include <vector>

struct Line { long unit_cents; int quantity; };

// Bulk discount: 5% off the order when it has 10 or more units in total, 10% off at 50 or more.
int discount_percent(int total_units);
// Order total in cents after the bulk discount, rounded to the nearest cent (halves round up).
long order_total(const std::vector<Line>& lines);
// Format cents as "12.34".
std::string money(long cents);
