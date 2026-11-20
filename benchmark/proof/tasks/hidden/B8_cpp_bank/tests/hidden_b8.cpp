#include <iostream>
#include "account.h"
#include "ledger.h"
int main() {
    Account a(200); Ledger l; int bad = 0;
    if (!l.withdraw(a, 150)) bad++;
    if (a.balance() != 0) bad++;
    Account b(500);
    if (l.withdraw(b, 451)) bad++;
    if (b.balance() != 500) bad++;
    std::cout << (bad ? "hidden failed" : "hidden ok") << "\n";
    return bad;
}
