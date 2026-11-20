#pragma once
#include <string>
#include <vector>
#include "account.h"
// Records every operation on an account.
struct Ledger {
    std::vector<std::string> lines;
    bool withdraw(Account& a, long amount);
    void deposit(Account& a, long amount);
};
