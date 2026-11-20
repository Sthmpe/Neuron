#include "ledger.h"

bool Ledger::withdraw(Account& a, long amount) {
    if (!a.withdraw(amount)) { lines.push_back("refused " + std::to_string(amount)); return false; }
    a.charge(Account::fee());
    lines.push_back("withdrew " + std::to_string(amount));
    return true;
}

void Ledger::deposit(Account& a, long amount) {
    a.deposit(amount);
    lines.push_back("deposited " + std::to_string(amount));
}
