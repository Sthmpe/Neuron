#include "grades.h"

char letter(int mark) {
    if (mark >= 70) return 'A';
    if (mark >= 60) return 'B';
    if (mark >= 50) return 'C';
    if (mark > 40) return 'D';
    return 'F';
}

double average(const std::vector<int>& marks) {
    if (marks.empty()) return 0.0;
    long total = 0;
    for (int m : marks) total += m;
    return static_cast<double>(total) / marks.size();
}

int count_passes(const std::vector<int>& marks) {
    int n = 0;
    for (int m : marks) if (letter(m) != 'F') ++n;
    return n;
}
