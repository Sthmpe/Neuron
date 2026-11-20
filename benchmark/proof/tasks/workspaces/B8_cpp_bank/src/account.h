#pragma once
// A savings account. Amounts in naira. Every withdrawal costs a fixed fee.
class Account {
public:
    explicit Account(long opening) : balance_(opening) {}
    long balance() const { return balance_; }
    static long fee() { return 50; }
    bool withdraw(long amount);           // false (and no change) if the balance cannot cover amount + fee
    void charge(long amount) { balance_ -= amount; }
    void deposit(long amount) { balance_ += amount; }
private:
    long balance_;
};
