#include <iostream>
#include "account.h"
#include "ledger.h"
static int failures = 0;
#define CHECK(c) do { if (!(c)) { ++failures; std::cerr << "FAIL line " << __LINE__ << ": " #c "\n"; } } while (0)
int main() {
    Account a(10000); Ledger l;
    CHECK(l.withdraw(a, 1000));
    CHECK(a.balance() == 8950);
    l.deposit(a, 50);
    CHECK(a.balance() == 9000);
    CHECK(!l.withdraw(a, 9000));
    CHECK(l.lines.size() == 3);
    if (!failures) std::cout << "all tests passed\n";
    return failures;
}
