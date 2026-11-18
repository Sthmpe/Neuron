#include "tickets.h"

int fare(int age) {
    if (age < 12) return 150;
    if (age > 65) return 0;
    return 300;
}

int day_total(const std::vector<int>& ages) {
    int total = 0;
    for (int a : ages) total += fare(a);
    return total;
}

int free_riders(const std::vector<int>& ages) {
    int n = 0;
    for (int a : ages) if (fare(a) == 0) ++n;
    return n;
}
