"""Phase 3: make Bank.Borrow return the actual amount lent and use it.

Bank.Borrow clamps the loan to borrowable capacity but returns None, so
callers like Region._incorporate assume the full request was funded:
    shortfall = max(0, startup_target - equity)
    self.bank.Borrow(t, company, shortfall)
    company.cash = equity + shortfall      # can exceed actual loan!

If the bank has less borrowable capacity, company.cash > equity + actual_loan,
which is money created from nothing (the phantom never hit total_liabilities).
Fix: Borrow returns the amount actually lent; _incorporate uses it.
"""
p = "/Users/sli/Code/econsim_trade_money.py"
src = open(p).read()

old = """    def Borrow(self, t, agent, amount):
        borrowable_amount = (self.total_deposits * (1 - self.reserve_fraction)
                             - self.total_liabilities)
        amount = clamp(amount, 0, borrowable_amount)
        loginfo(t, "borrowing from bank with $", self.total_deposits,
                " deposit and $", self.total_liabilities,
                "borrowable: $", borrowable_amount, " lending: $", amount)
        if amount <= 0:
            return
        loan = Loan(self, agent, amount, self.interest_rate)
        agent.cash += amount
        agent.loans.append(loan)
        self.loans.append(loan)
        self.total_liabilities += amount"""
new = """    def Borrow(self, t, agent, amount):
        borrowable_amount = (self.total_deposits * (1 - self.reserve_fraction)
                             - self.total_liabilities)
        amount = clamp(amount, 0, borrowable_amount)
        loginfo(t, "borrowing from bank with $", self.total_deposits,
                " deposit and $", self.total_liabilities,
                "borrowable: $", borrowable_amount, " lending: $", amount)
        if amount <= 0:
            return amount
        loan = Loan(self, agent, amount, self.interest_rate)
        agent.cash += amount
        agent.loans.append(loan)
        self.loans.append(loan)
        self.total_liabilities += amount
        return amount"""
assert old in src, "borrow-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("Bank.Borrow now returns actual amount lent")

# ---- 2. _incorporate uses actual lent amount ----
p2 = "/Users/sli/Code/region.py"
src2 = open(p2).read()

old2 = """            shortfall = max(0, startup_target - equity)
            if shortfall > 0:
                self.bank.Borrow(t, company, shortfall)
            a.cash -= equity
            company.cash = equity + shortfall"""
new2 = """            shortfall = max(0, startup_target - equity)
            loaned = 0.0
            if shortfall > 0:
                loaned = self.bank.Borrow(t, company, shortfall)
            a.cash -= equity
            company.cash = equity + loaned"""
assert old2 in src2, "incorporate-anchor"
src2 = src2.replace(old2, new2)

open(p2, "w").write(src2)
print("_incorporate now funds company.cash from actual loan only")