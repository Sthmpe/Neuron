#include "pricing.h"
#include <cstdio>

int discount_percent(int total_units) {
    if (total_units >= 50) return 10;
    if (total_units > 10) return 5;
    return 0;
}

long order_total(const std::vector<Line>& lines) {
    long subtotal = 0;
    int units = 0;
    for (const auto& l : lines) {
        subtotal += l.unit_cents * l.quantity;
        units += l.quantity;
    }
    long discount = (subtotal * discount_percent(units) * 2 + 100) / 200;
    return subtotal - discount;
}

std::string money(long cents) {
    char buf[32];
    std::snprintf(buf, sizeof buf, "%ld.%02ld", cents / 100, cents % 100);
    return buf;
}
