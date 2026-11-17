#include "csv.h"
#include <stdexcept>

std::vector<std::string> split_csv(const std::string& line) {
    std::vector<std::string> out;
    std::string cur;
    bool quoted = false;
    for (size_t i = 0; i < line.size(); ++i) {
        char c = line[i];
        if (quoted) {
            if (c == '"') {
                if (i + 1 < line.size() && line[i + 1] == '"') { cur += '"'; ++i; }
                else quoted = false;
            } else cur += c;
        } else if (c == '"') quoted = true;
        else if (c == ',') { out.push_back(cur); cur.clear(); }
        else cur += c;
    }
    out.push_back(cur);
    return out;
}

long parse_cents(const std::string& text) {
    size_t dot = text.find('.');
    std::string whole = text.substr(0, dot);
    std::string frac = dot == std::string::npos ? "" : text.substr(dot + 1);
    if (frac.size() > 2) throw std::invalid_argument("too many decimals: " + text);
    while (frac.size() < 2) frac += '0';
    return std::stol(whole.empty() ? "0" : whole) * 100 + std::stol(frac);
}
