"""Pinpoint the core home-currency leak inside Region.step(13) using cash_auditor.

Wraps Bank methods (Borrow/Deposit/Withdraw/pay_principle/pay_interest) and
records every mutation in Region_A's step 13 so we can see exactly which
operation destroys currency.  The cash_auditor already computes net_system per
call; we aggregate by caller.
"""
import random
from collections import defaultdict
from goods import Goods
from region import Region
import econsim_trade_money as tm
import forex as fx
from cash_auditor import install_auditor, _turn_mutations, _audit_log, start_turn, end_turn

install_auditor()
random.seed(42)
ra = Region("Region_A", 0, 55, {Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rb = Region("Region_B", 0, 55, {Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
ra.recipes[Goods.food]['production'] *= 2
rb.recipes[Goods.wood]['production'] *= 2
ra.destination_region = rb
rb.destination_region = ra
for a in ra.agents + rb.agents:
    if getattr(a, 'is_trader', False):
        a.destination_region = rb if a in ra.agents else ra
fx.connect_regions(ra, rb, 0)

from econsim_two_region import foreign_sell, process_transport
import wealth_lineage, wealth_diagnostic
wealth_lineage.init_collectors()
wealth_diagnostic.init_collectors()

for t in range(1, 13):
    ra.step(t); rb.step(t)
    process_transport(t, ra, rb)
    foreign_sell(t, ra, rb); foreign_sell(t, rb, ra)
    wealth_lineage.record_turn(t, ra, rb); wealth_diagnostic.record_turn(t, ra, rb)
    for r in (ra, rb):
        r.forex.update(t, bank=r.bank, fx_regime='managed')
        r.forex.save_rate(r)

# Audit region A's step 13 mutations by caller
start_turn()
ra.step(13)
entry = end_turn()
print(f"Turn 13 Region_A net_system_cash = {entry['net_system_cash']:.4f}")
print(f"  mutations = {entry['mutations']}")

by_caller = defaultdict(lambda: {'td': 0.0, 'tl': 0.0, 'ac': 0.0})
for m in _turn_mutations:
    key = m.caller.split(' ')[0] + ':' + m.caller.split(':')[1]
    by_caller[key]['td'] += m.total_deposits_delta
    by_caller[key]['tl'] += m.total_liabilities_delta
    by_caller[key]['ac'] += m.agent_cash_delta

print("\nPer-caller deltas (td=total_deposits, tl=total_liabilities, ac=agent_cash):")
for caller, d in sorted(by_caller.items(), key=lambda kv: -abs(kv[1]['td'] - kv[1]['tl'] + kv[1]['ac'])):
    net = d['td'] - d['tl'] + d['ac']
    if abs(net) > 1e-6:
        print(f"  {caller:>38}  net={net:+.4f}  td={d['td']:+.4f} tl={d['tl']:+.4f} ac={d['ac']:+.4f}")