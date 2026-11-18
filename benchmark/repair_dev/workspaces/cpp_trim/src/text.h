#pragma once
#include <string>
// trim removes spaces, tabs and line breaks at both ends of a line read from a customer file.
std::string trim(const std::string& s);
// clean_name trims a name and turns every run of inner spaces or tabs into one space.
std::string clean_name(const std::string& s);
