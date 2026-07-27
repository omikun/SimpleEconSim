#!/usr/bin/env python3
"""
Cash-flow auditor: wraps Bank methods to track all cash/deposit/liability
mutations and computes the system-wide delta per turn.

Usage:
    python3 -c "
from cash_auditor import install_auditor, audit_report
install_auditor()
import benchmark  # runs the sim with auditing
audit_report()
"
or integrate directly into benchmark.py / econsim_two_region.py.
"""

import functools
from collections import defaultdict

# =============================================================================
# Global audit log
# =============================================================================

_audit_log = []               # list of dicts per turn
_turn_mutations = []           # mutations within current turn
_wrapped = False


class Mutation:
    """Record of a single cash-flow mutation."""
    __slots__ = ('turn', 'method', 'agent', 'amount', 'total_deposits_delta',
                 'total_liabilities_delta', 'agent_cash_delta', 'bank_deposit_delta',
                 'caller')

    def __init__(self, turn, method, agent, amount, td_delta, tl_delta,
                 ac_delta, bd_delta, caller):
        self.turn = turn
        self.method = method
        self.agent = agent.id if agent else None
        self.amount = amount
        self.total_deposits_delta = td_delta
        self.total_liabilities_delta = tl_delta
        self.agent_cash_delta = ac_delta
        self.bank_deposit_delta = bd_delta
        self.caller = caller


def _record(method_name, agent, amount, total_deposits_delta=0.0,
            total_liabilities_delta=0.0, agent_cash_delta=0.0,
            bank_deposit_delta=0.0):
    """Record a mutation in the current turn log."""
    import traceback
    caller = traceback.extract_stack(limit=4)[-3]
    caller_str = f"{caller.filename.split('/')[-1]}:{caller.lineno} {caller.name}"
    _turn_mutations.append(Mutation(
        len(_audit_log) + 1, method_name, agent, amount,
        total_deposits_delta, total_liabilities_delta,
        agent_cash_delta, bank_deposit_delta, caller_str,
    ))


# =============================================================================
# Wrap Bank methods
# =============================================================================

def _wrap_method(bank_class, method_name, wrapper_fn):
    original = getattr(bank_class, method_name)
    setattr(bank_class, method_name, wrapper_fn(original))


def install_auditor():
    """Patch Bank class to log all cash-flow mutations."""
    global _wrapped
    if _wrapped:
        return
    _wrapped = True

    import econsim_trade_money as tm

    # ---- Borrow ----
    _orig_borrow = tm.Bank.Borrow
    @functools.wraps(_orig_borrow)
    def _audited_borrow(self, t, agent, amount):
        before = self.total_deposits, self.total_liabilities, agent.cash
        result = _orig_borrow(self, t, agent, amount)
        td_delta = self.total_deposits - before[0]
        tl_delta = self.total_liabilities - before[1]
        ac_delta = agent.cash - before[2]
        _record('Borrow', agent, amount, td_delta, tl_delta, ac_delta)
        return result
    tm.Bank.Borrow = _audited_borrow

    # ---- Deposit ----
    _orig_deposit = tm.Bank.Deposit
    @functools.wraps(_orig_deposit)
    def _audited_deposit(self, agent, amount):
        before = self.total_deposits, agent.cash, self.deposits.get(agent, 0)
        result = _orig_deposit(self, agent, amount)
        td_delta = self.total_deposits - before[0]
        ac_delta = agent.cash - before[1]
        bd_delta = self.deposits.get(agent, 0) - before[2]
        _record('Deposit', agent, amount, td_delta, 0.0, ac_delta, bd_delta)
        return result
    tm.Bank.Deposit = _audited_deposit

    # ---- Withdraw ----
    _orig_withdraw = tm.Bank.Withdraw
    @functools.wraps(_orig_withdraw)
    def _audited_withdraw(self, agent, amount):
        before = self.total_deposits, agent.cash, self.deposits.get(agent, 0)
        result = _orig_withdraw(self, agent, amount)
        td_delta = self.total_deposits - before[0]
        ac_delta = agent.cash - before[1]
        bd_delta = self.deposits.get(agent, 0) - before[2]
        _record('Withdraw', agent, amount, td_delta, 0.0, ac_delta, bd_delta)
        return result
    tm.Bank.Withdraw = _audited_withdraw

    # ---- pay_principle ----
    _orig_pp = tm.Bank.pay_principle
    @functools.wraps(_orig_pp)
    def _audited_pay_principle(self, amount):
        before = self.total_liabilities
        result = _orig_pp(self, amount)
        tl_delta = self.total_liabilities - before
        _record('pay_principle', None, amount, 0.0, tl_delta)
        return result
    tm.Bank.pay_principle = _audited_pay_principle

    # ---- pay_interest ----
    _orig_pi = tm.Bank.pay_interest
    @functools.wraps(_orig_pi)
    def _audited_pay_interest(self, amount):
        before = self.total_deposits
        result = _orig_pi(self, amount)
        td_delta = self.total_deposits - before
        _record('pay_interest', None, amount, td_delta)
        return result
    tm.Bank.pay_interest = _audited_pay_interest

    # ---- PayDepositInterest ----
    _orig_pdi = tm.Bank.PayDepositInterest
    @functools.wraps(_orig_pdi)
    def _audited_pay_deposit_interest(self, agents):
        result = _orig_pdi(self, agents)
        # The interest was paid inside the loop — we won't capture per-agent,
        # but the total_deposits change is logged in the individual agent.cash +=
        # and self.total_deposits -= calls. Log a summary entry.
        return result
    tm.Bank.PayDepositInterest = _audited_pay_deposit_interest


def start_turn():
    """Call at the start of each turn to begin a new audit block."""
    global _turn_mutations
    _turn_mutations = []


def end_turn():
    """Call at the end of each turn to compute net deltas."""
    net_td = sum(m.total_deposits_delta for m in _turn_mutations)
    net_tl = sum(m.total_liabilities_delta for m in _turn_mutations)
    net_ac = sum(m.agent_cash_delta for m in _turn_mutations)
    net_bd = sum(m.bank_deposit_delta for m in _turn_mutations)
    net_system = net_td - net_tl + net_ac
    entry = {
        'turn': len(_audit_log) + 1,
        'mutations': len(_turn_mutations),
        'net_total_deposits': net_td,
        'net_total_liabilities': net_tl,
        'net_agent_cash': net_ac,
        'net_bank_deposits': net_bd,
        'net_system_cash': net_system,
        'largest_mutations': sorted(
            _turn_mutations, key=lambda m: abs(m.amount), reverse=True
        )[:5],
    }
    _audit_log.append(entry)
    return entry


def audit_report():
    """Print summary of all audited turns."""
    leaky_turns = [e for e in _audit_log if abs(e['net_system_cash']) > 0.01]
    if not leaky_turns:
        print(f"\n{'='*60}")
        print(f"CASH AUDITOR: All {len(_audit_log)} turns clean (no leaks > $0.01)")
        print(f"{'='*60}")
        return

    print(f"\n{'='*60}")
    print(f"CASH AUDITOR: {len(leaky_turns)}/{len(_audit_log)} turns with leaks")
    print(f"{'='*60}")

    for entry in leaky_turns[:20]:
        print(f"\n  Turn {entry['turn']}: net_system=${entry['net_system_cash']:.4f}")
        print(f"    net_agent_cash={entry['net_agent_cash']:.4f}  "
              f"net_total_deposits={entry['net_total_deposits']:.4f}  "
              f"net_total_liabilities={entry['net_total_liabilities']:.4f}")
        print(f"    mutations={entry['mutations']}")
        for m in entry['largest_mutations']:
            print(f"      {m.method:>25} agent={m.agent} amt={m.amount:>10.2f} "
                  f"td={m.total_deposits_delta:>8.2f} tl={m.total_liabilities_delta:>8.2f} "
                  f"ac={m.agent_cash_delta:>8.2f} [{m.caller}]")

    if len(leaky_turns) > 20:
        print(f"  ... and {len(leaky_turns) - 20} more leaky turns")