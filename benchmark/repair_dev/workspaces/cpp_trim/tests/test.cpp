#include <iostream>
#include "text.h"
static int failures = 0;
#define CHECK(c) do { if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\n"; } } while (0)
int main() {
    CHECK(trim("  Ada  ") == "Ada");
    CHECK(trim("\tAda\r\n") == "Ada");
    CHECK(trim(" \t ") == "");
    CHECK(clean_name("  Ada \t  Obi ") == "Ada Obi");
    CHECK(clean_name("\tNgozi\n") == "Ngozi");
    if (!failures) std::cout << "all tests passed\n";
    return failures;
}
