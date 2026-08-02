"""Pure FX conservation unit test — no agents, no region step, no deaths.

Runs sell_fx / buy_fx / repatriate / death-inheritance in isolation and
verifies each currency's global total is exactly conserved.  This separates
FX-specific leaks from the pre-existing core home-currency leak (death debt
write-downs) seen in fx_debug_turn.py.

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
ta.wallets[CUR_B] = 100.0
tb.wallets[CUR_A] = 75.0

# ---- Death-inheritance subjects ----
td = Agent(0); td.is_trader = True; td.home_currency = CUR_A
td.wallets[CUR_B] = 250.0
te = Agent(0); te.is_trader = True; te.home_currency = CUR_A
te.wallets[CUR_B] = 90.0

# ---- Heirs + government agent ----
heir1 = Agent(0); heir2 = Agent(0)
gov_agent = Agent(0)
gov_agent.is_government = True

# Complete tracked set of agents (ALL cash + wallets holders except gov bank)
AGENTS = [ta, tb, td, te, heir1, heir2, gov_agent]

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
        total += a.wallets.get(cur, 0.0)
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

# 1. Trader A sells 100 B-currency to bank A (gets home A money)
home = fx.sell_fx_to_bank(bA, ta, CUR_B, 100.0, deskA.buy_rate())
results.append(check(f"A-trader sells 100 B (got {home:.2f} A)"))

# 2. Trader A buys 10 B-currency back from bank A (pays home A money)
bought = fx.buy_fx_from_bank(bA, ta, CUR_B, 10.0, deskA.sell_rate())
results.append(check(f"A-trader buys 10 B back (got {bought:.2f} B)"))

# 3. Trader B sells 75 A-currency at bank B (gets home B money)
home = fx.sell_fx_to_bank(bB, tb, CUR_A, 75.0, deskB.buy_rate())
results.append(check(f"B-trader sells 75 A (got {home:.2f} B)"))

# 4. Repatriate trader A fully (wallet -> home cash at home desk)
class FakeRegionA:
    forex = deskA
    bank = bA
val = fx.repatriate_trader(ta, FakeRegionA(), 1)
results.append(check(f"A-trader repatriate (got {val:.2f} A)"))

# 5. Repatriate trader B fully
class FakeRegionB:
    forex = deskB
    bank = bB
val = fx.repatriate_trader(tb, FakeRegionB(), 1)
results.append(check(f"B-trader repatriate (got {val:.2f} B)"))

# 6. Death with living heirs: trader D dies holding 250 B -> heirs keep currency
ctx = live.LiveContext.__new__(live.LiveContext)
ctx.bank = bA
ctx.default_gov = None
live._handle_wealth_inheritance(ctx, 5, td, [heir1, heir2])
live._zero_out_dead_agent(ctx, td)
results.append(check("D dies w/ heirs: 250 B -> heirs"))
print(f"      D wallet[B]={td.wallets.get(CUR_B, 0.0):.4f} "
      f"| heir1={heir1.wallets.get(CUR_B, 0.0):.2f} heir2={heir2.wallets.get(CUR_B, 0.0):.2f}")

# 7. Death with NO heirs: trader E dies holding 90 B -> government agent
gov_bank = tm.Bank()
ctx2 = live.LiveContext.__new__(live.LiveContext)
ctx2.bank = gov_bank
ctx2.default_gov = type('G', (), {'agent': gov_agent})()
baseA7 = audit(CUR_A); baseB7 = audit(CUR_B)

# Note: gov-bank is separate; E's home-currency cash stays outside the audit.
live._handle_wealth_inheritance(ctx2, 6, te, [])
live._zero_out_dead_agent(ctx2, te)
dA7 = audit(CUR_A) - baseA7
dB7 = audit(CUR_B) - baseB7
ok7 = abs(dA7) < 1e-9 and abs(dB7) < 1e-9
results.append(ok7)
print(f"E dies w/o heirs: 90 B -> gov           "
      f"dA={dA7:+.6f} dB={dB7:+.6f}  {'OK' if ok7 else 'LEAK'}")
print(f"      gov wallet[B]={gov_agent.wallets.get(CUR_B, 0.0):.2f} "
      f"| E wallet[B]={te.wallets.get(CUR_B, 0.0):.4f}")

print()
if all(results):
    print("ALL FX CONSERVATION CHECKS PASS")
else:
    print("FX CONSERVATION LEAKS FOUND")