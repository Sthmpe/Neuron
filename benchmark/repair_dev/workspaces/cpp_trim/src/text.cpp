#include "text.h"

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(' ');
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(' ');
    return s.substr(a, b - a + 1);
}

std::string clean_name(const std::string& s) {
    std::string t = trim(s), out;
    bool gap = false;
    for (char c : t) {
        if (c == ' ' || c == '\t') { gap = true; continue; }
        if (gap && !out.empty()) out += ' ';
        gap = false;
        out += c;
    }
    return out;
}
