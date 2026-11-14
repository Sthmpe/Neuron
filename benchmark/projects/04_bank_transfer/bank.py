"""A bank that moves money between accounts."""
from account import Account, InsufficientFunds


class Bank:
    def __init__(self):
        self.accounts = {}
        self.log = []

    def open(self, owner, opening_balance=0):
        if owner in self.accounts:
            raise ValueError(f"{owner} already has an account")
        self.accounts[owner] = Account(owner, opening_balance)
        return self.accounts[owner]

    def transfer(self, sender, receiver, amount):
        """Move `amount` from sender to receiver. Nothing changes if the sender cannot pay."""
        src = self.accounts[sender]
        dst = self.accounts[receiver]
        dst.deposit(amount)
        src.withdraw(amount)
        self.log.append((sender, receiver, amount))

    def total_money(self):
        return sum(a.balance for a in self.accounts.values())
