#include "account.h"

bool Account::withdraw(long amount) {
    if (amount + fee() > balance_) return false;
    balance_ -= amount + fee();
    return true;
}
