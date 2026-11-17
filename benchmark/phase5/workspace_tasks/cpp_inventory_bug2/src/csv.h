#pragma once
#include <string>
#include <vector>

// Splits one CSV line on commas. A field in double quotes may contain commas; "" inside quotes is one quote.
std::vector<std::string> split_csv(const std::string& line);
// Parses "12.5" or "12" or "12.05" into cents (1250, 1200, 1205).
long parse_cents(const std::string& text);
