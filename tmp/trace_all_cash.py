#!/usr/bin/env python3
"""
Trace ALL cash-related attribute changes by wrapping:
  1. Bank methods (Borrow, Deposit, Withdraw, pay_principle, pay_interest, PayDepositInterest)
  2. Bank property direct mutations (total_deposits, total_liabilities) via __setattr__
  3. Agent cash changes via __setattr__
  4. Charity cash changes via __setattr__
  5. Government agent cash changes

Then verify system cash conservation per turn.
"""
import sys
sys.path.insert(0, '.')

from region import Region, get_total_cash
from goods import Goods
from logger import logInit
from econsim_two_region import foreign_sell
import random

# =============================================================================
# Instrumentation
# =============================================================================

_turn = 0
_mutations = []

def reset():
    global _mutations
    _mutations = []

def log_mutation(source, attr, old_val, new_val, delta):
    global _mutations
    from traceback import extract_stack
    caller = extract_stack(limit=5)[-3]
    caller_str = f"{caller.filename.split('/')[-1]}:{caller.lineno} {caller.name}"
    _mutations.append({
        'source': source, 'attr': attr, 'old': old_val, 'new': new_val,
        'delta': delta, 'caller': caller_str,
    })

# Trace Bank.total_deposits / total_liabilities changes
def _instrument_bank_counts(bank, label):
    orig_class = type(bank)
    # Create a tracker wrapper for numeric attributes
    tracked_attrs = {}
    for attr in ['total_deposits', 'total_liabilities']:
        tracked_attrs[attr] = getattr(bank, attr)

    def _get(name):
        return tracked_attrs[name]

    def _set(name, val):
        old = tracked_attrs[name]
        if abs(old - val) > 1e-9:
            delta = val - old
            tracked_attrs[name] = val
            log_mutation(f"Bank({label})", name, old, val, delta)

    bank._tracked = tracked_attrs
    bank._get_tracked = lambda name: tracked_attrs[name]
    bank._set_tracked = lambda name, val: _set(name, val)

    # Wrap the bank methods
    _orig_borrow = bank.Borrow.__func__ if hasattr(bank.Borrow, '__func__') else bank.Borrow
    def _borrow(self, t, agent, amount):
        before = tracked_attrs['total_deposits'], tracked_attrs['total_liabilities'], agent.cash
        result = _orig_borrow(self, t, agent, amount)
        # Update our tracked values from the real ones (may have changed via direct mutation)
        td = self.total_deposits
        tl = self.total_liabilities
        ac = agent.cash
        if abs(td - tracked_attrs['total_deposits']) > 1e-9:
            log_mutation(f"Bank({label}) Borrow", 'total_deposits', tracked_attrs['total_deposits'], td, td - tracked_attrs['total_deposits'])
        if abs(tl - tracked_attrs['total_liabilities']) > 1e-9:
            log_mutation(f"Bank({label}) Borrow", 'total_liabilities', tracked_attrs['total_liabilities'], tl, tl - tracked_attrs['total_liabilities'])
        if abs(ac - agent.cash) > 1e-9:
            pass  # We track agent.cash separately
        tracked_attrs['total_deposits'] = td
        tracked_attrs['total_liabilities'] = tl
        return result
    bank.Borrow = _borrow.__get__(bank, type(bank))

    for method_name in ['Deposit', 'Withdraw', 'pay_principle', 'pay_interest']:
        orig = getattr(bank, method_name)
        def _make_wrapper(mname, orig_fn):
            def _wrapper(self, *args):
                before_td = tracked_attrs['total_deposits']
                before_tl = tracked_attrs['total_liabilities']
                result = orig_fn(self, *args)
                td = self.total_deposits
                tl = self.total_liabilities
                if abs(td - tracked_attrs['total_deposits']) > 1e-9:
                    log_mutation(f"Bank({label}) {mname}", 'total_deposits', tracked_attrs['total_deposits'], td, td - tracked_attrs['total_deposits'])
                if abs(tl - tracked_attrs['total_liabilities']) > 1e-9:
                    log_mutation(f"Bank({label}) {mname}", 'total_liabilities', tracked_attrs['total_liabilities'], tl, tl - tracked_attrs['total_liabilities'])
                tracked_attrs['total_deposits'] = td
                tracked_attrs['total_liabilities'] = tl
                return result
            return _wrapper
        setattr(bank, method_name, _make_wrapper(method_name, orig).__get__(bank, type(bank)))

    # Wrap PayDepositInterest specially (it loops agents)
    _orig_pdi = bank.PayDepositInterest.__func__ if hasattr(bank.PayDepositInterest, '__func__') else bank.PayDepositInterest
    def _pdi(self, agents):
        result = _orig_pdi(self, agents)
        td = self.total_deposits
        if abs(td - tracked_attrs['total_deposits']) > 1e-9:
            log_mutation(f"Bank({label}) PayDepositInterest", 'total_deposits', tracked_attrs['total_deposits'], td, td - tracked_attrs['total_deposits'])
        tracked_attrs['total_deposits'] = td
        return result
    bank.PayDepositInterest = _pdi.__get__(bank, type(bank))

    # Now sync real values at start of each turn
    return bank

# =============================================================================
# Main
# =============================================================================

time_steps = 10
logInit()
random.seed(42)

rA = Region('Region_A', t=0, number_of_agents=110,
            profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rB = Region('Region_B', t=0, number_of_agents=110,
            profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
rA.recipes[Goods.food]['production'] *= 2
rB.recipes[Goods.wood]['production'] *= 2
rA.destination_region = rB
rB.destination_region = rA
for trader in rA.agents:
    if trader.is_trader:
        trader.destination_region = rB
for trader in rB.agents:
    if trader.is_trader:
        trader.destination_region = rA

def process_transport(t, ra, rb):
    for trader in ra.agents:
        if trader.is_trader:
            trader._process_pipeline()
    for trader in rb.agents:
        if trader.is_trader:
            trader._process_pipeline()

for t in range(1, time_steps + 1):
    reset()
    
    # Snap all cash state
    cash_a_before = sum(a.cash for a in rA.agents)
    cash_b_before = sum(a.cash for a in rB.agents)
    td_a_before = rA.bank.total_deposits
    tl_a_before = rA.bank.total_liabilities
    td_b_before = rB.bank.total_deposits
    tl_b_before = rB.bank.total_liabilities
    ch_a_before = rA.charity.cash
    ch_b_before = rB.charity.cash
    
    total_before = cash_a_before + cash_b_before + (td_a_before - tl_a_before) + (td_b_before - tl_b_before) + ch_a_before + ch_b_before
    
    rA.step(t)
    rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB)
    foreign_sell(t, rB, rA)
    
    cash_a_after = sum(a.cash for a in rA.agents)
    cash_b_after = sum(a.cash for a in rB.agents)
    td_a_after = rA.bank.total_deposits
    tl_a_after = rA.bank.total_liabilities
    td_b_after = rB.bank.total_deposits
    tl_b_after = rB.bank.total_liabilities
    ch_a_after = rA.charity.cash
    ch_b_after = rB.charity.cash
    
    total_after = cash_a_after + cash_b_after + (td_a_after - tl_a_after) + (td_b_after - tl_b_after) + ch_a_after + ch_b_after
    
    leak = total_after - total_before
    
    # Categorize the tracked mutations
    bank_td = sum(m['delta'] for m in _mutations if 'total_deposits' in m.get('attr',''))
    bank_tl = sum(m['delta'] for m in _mutations if 'total_liabilities' in m.get('attr',''))
    
    print(f"\nT={t}: LEAK={leak:+.6f}")
    print(f"  Agent A cash: ${cash_a_before:.2f} -> ${cash_a_after:.2f} (d={cash_a_after-cash_a_before:+.2f})")
    print(f"  Agent B cash: ${cash_b_before:.2f} -> ${cash_b_after:.2f} (d={cash_b_after-cash_b_before:+.2f})")
    print(f"  Bank A equity: ${(td_a_before-tl_a_before):.2f} -> ${(td_a_after-tl_a_after):.2f} (d={(td_a_after-tl_a_after)-(td_a_before-tl_a_before):+.2f})")
    print(f"  Bank B equity: ${(td_b_before-tl_b_before):.2f} -> ${(td_b_after-tl_b_after):.2f} (d={(td_b_after-tl_b_after)-(td_b_before-tl_b_before):+.2f})")
    print(f"  Charity A: ${ch_a_before:.2f} -> ${ch_a_after:.2f} (d={ch_a_after-ch_a_before:+.2f})")
    print(f"  Charity B: ${ch_b_before:.2f} -> ${ch_b_after:.2f} (d={ch_b_after-ch_b_before:+.2f})")
    
    # Find direct mutations from code that bypasses bank methods
    direct_bank_ops = [m for m in _mutations if 'total_deposits' in m.get('attr','') or 'total_liabilities' in m.get('attr','')]
    if direct_bank_ops:
        print(f"\n  Bank attribute changes tracked:")
        for m in direct_bank_ops[:10]:
            print(f"    {m['attr']:>20} delta={m['delta']:+.2f} [{m['caller']}]")
    
    if abs(leak) > 0.01:
        total_agent_cash_delta = (cash_a_after - cash_a_before) + (cash_b_after - cash_b_before)
        total_bank_equity_delta = (td_a_after - tl_a_after) - (td_a_before - tl_a_before) + (td_b_after - tl_b_after) - (td_b_before - tl_b_before)
        total_charity_delta = (ch_a_after - ch_a_before) + (ch_b_after - ch_b_before)
        print(f"\n  Breakdown: agent_cash={total_agent_cash_delta:+.2f} bank_equity={total_bank_equity_delta:+.2f} charity={total_charity_delta:+.2f}")
        total_td = (td_a_after - td_a_before) + (td_b_after - td_b_before)
        total_tl = (tl_a_after - tl_a_before) + (tl_b_after - tl_b_before)
        print(f"  total_deposits_delta={total_td:+.2f} total_liabilities_delta={total_tl:+.2f}")
        if agent_a_before != agent_a_after:
            print(f"  Agents A: {len(rA.agents)}")
        if abs(leak) > 1:
            print(f"  *** LARGE LEAK — see caller trace above ***")