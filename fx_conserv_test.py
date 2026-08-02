"""Pure FX conservation unit test — no agents, no region step, no deaths.

Runs sell_fx / buy_fx / repatriate / death-inheritance in isolation and
verifies each currency's global total is exactly conserved.  This separates
FX-specific leaks from the pre-existing core home-currency leak (death debt
write-downs) seen in fx_debug_turn.py.

Phase 2: wallets are LAZY (None unless a balance exists).  This test
verifies that and proves a check that non-traders carry no allocation.

All holders of each currency are tracked EXHAUSTIVELY:
  * bank equity (total_deposits - total_liabilities)          [home only]
  * bank fx_pool                                              [home only]
  * bank foreign_reserves                                     [foreign]
  * trader cash                                               [home]
  * all agent wallets (traders, heirs, gov agent)             [any]
"""
from agent import Agent
import econsim_trade_money as tm
import forex as fx
import econsim_live as live

# ---- Two banks, two currencies ----
bA = tm.Bank()
bB = tm.Bank()
CUR_A = "Region_A"
CUR_B = "Region_B"

# Seed FX desk state exactly as ForexDesk would
deskA = fx.ForexDesk(CUR_A, CUR_B, bank=bA)
deskB = fx.ForexDesk(CUR_B, CUR_A, bank=bB)

# ---- Minimal traders around Agent ----
ta = Agent(0); ta.is_trader = True; ta.home_currency = CUR_A
tb = Agent(0); tb.is_trader = True; tb.home_currency = CUR_B
# Phase 2: seed via fx_add (lazy materialization) — mirrors buy working capital
fx.fx_add(ta, CUR_B, 100.0)
fx.fx_add(tb, CUR_A, 75.0)

# ---- Death-inheritance subjects ----
td = Agent(0); td.is_trader = True; td.home_currency = CUR_A
fx.fx_add(td, CUR_B, 250.0)
te = Agent(0); te.is_trader = True; te.home_currency = CUR_A
fx.fx_add(te, CUR_B, 90.0)

# ---- Heirs + government agent (start with wallets=None!) ----
heir1 = Agent(0); heir2 = Agent(0)
gov_agent = Agent(0)
gov_agent.is_government = True

# Complete tracked set of agents (ALL cash + wallets holders except gov bank)
AGENTS = [ta, tb, td, te, heir1, heir2, gov_agent]

# ---- Phase 2 proof: non-traders carry NO wallet allocation ----
assert heir1.wallets is None and heir2.wallets is None, "non-trader wallets must default to None"
assert gov_agent.wallets is None, "gov agent wallet must default to None"

def audit(cur):
    total = 0.0
    for b, home in ((bA, CUR_A), (bB, CUR_B)):
        if home == cur:
            total += b.total_deposits - b.total_liabilities
            total += b.fx_pool
        total += b.foreign_reserves.get(cur, 0.0)
    for a in AGENTS:
        if a.home_currency == cur:
            total += a.cash
        total += fx.fx_balance(a, cur)
    return total

baseA = audit(CUR_A)
baseB = audit(CUR_B)
print(f"baselines: A={baseA:.4f} B={baseB:.4f}")

def check(tag):
    dA = audit(CUR_A) - baseA
    dB = audit(CUR_B) - baseB
    ok = abs(dA) < 1e-9 and abs(dB) < 1e-9
    print(f"{tag:>55}  dA={dA:+.6f} dB={dB:+.6f}  {'OK' if ok else 'LEAK'}")
    return ok

results = []

# 0. Phase 2: working-capital buy (trader pays home for foreign float)
bought0 = fx.buy_fx_from_bank(bA, ta, CUR_B, 10.0, deskA.sell_rate())
results.append(check(f"A-trader buys 10 B working cap (got {bought0:.2f} B)"))

# 1. Trader A sells 100 B-currency to bank A (gets home A money)
home = fx.sell_fx_to_bank(bA, ta, CUR_B, 100.0, deskA.buy_rate())
results.append(check(f"A-trader sells 100 B (got {home:.2f} A)"))

# 2. B-trader sells 75 A-currency at bank B (gets home B money)
home = fx.sell_fx_to_bank(bB, tb, CUR_A, 75.0, deskB.buy_rate())
results.append(check(f"B-trader sells 75 A (got {home:.2f} B)"))

# 3. Repatriate trader A fully (wallet -> home cash at home desk)
class FakeRegionA:
    forex = deskA
    bank = bA
val = fx.repatriate_trader(ta, FakeRegionA(), 1)
results.append(check(f"A-trader repatriate (got {val:.2f} A)"))

# 4. Repatriate trader B fully
class FakeRegionB:
    forex = deskB
    bank = bB
val = fx.repatriate_trader(tb, FakeRegionB(), 1)
results.append(check(f"B-trader repatriate (got {val:.2f} B)"))

# 5. Death with living heirs: trader D dies holding 250 B -> heirs keep currency
ctx = live.LiveContext.__new__(live.LiveContext)
ctx.bank = bA
ctx.default_gov = None
live._handle_wealth_inheritance(ctx, 5, td, [heir1, heir2])
live._zero_out_dead_agent(ctx, td)
results.append(check("D dies w/ heirs: 250 B -> heirs"))
print(f"      D wallet[B]={fx.fx_balance(td, CUR_B):.4f} "
      f"| heir1={fx.fx_balance(heir1, CUR_B):.2f} "
      f"heir2={fx.fx_balance(heir2, CUR_B):.2f}")
# Phase 2: heirs got a lazy dict materialized by fx_add — still conserve
assert heir1.wallets is not None and heir2.wallets is not None, "heirs should have materialized wallets"

# 6. Death with NO heirs: trader E dies holding 90 B -> government agent
gov_bank = tm.Bank()
ctx2 = live.LiveContext.__new__(live.LiveContext)
ctx2.bank = gov_bank
ctx2.default_gov = type('G', (), {'agent': gov_agent})()
baseA6 = audit(CUR_A); baseB6 = audit(CUR_B)

# Note: gov-bank is separate; E's home-currency cash stays outside the audit.
live._handle_wealth_inheritance(ctx2, 6, te, [])
live._zero_out_dead_agent(ctx2, te)
dA6 = audit(CUR_A) - baseA6
dB6 = audit(CUR_B) - baseB6
ok6 = abs(dA6) < 1e-9 and abs(dB6) < 1e-9
results.append(ok6)
print(f"E dies w/o heirs: 90 B -> gov           "
      f"dA={dA6:+.6f} dB={dB6:+.6f}  {'OK' if ok6 else 'LEAK'}")
print(f"      gov wallet[B]={fx.fx_balance(gov_agent, CUR_B):.2f} "
      f"| E wallet[B]={fx.fx_balance(te, CUR_B):.4f}")

print()
if all(results):
    print("ALL FX CONSERVATION CHECKS PASS")
else:
    print("FX CONSERVATION LEAKS FOUND")