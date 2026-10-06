# Commonweal

*How a commons becomes an economy — and what each step costs the people living in it.*

A small agent-based simulation of one valley (~160 named people, 1 tick = 1 season, ~150 years).
Nobody presses an "enclose" button. Capitalism emerges from ordinary choices under pressure:
harvest luck, debt, foreclosure, population pressure on land, competition between owners and
the substitution of bought goods for crafts. The UI keeps **two ledgers** side by side: what the
state measures (GDP, capital) and what people live (health, free time, ties, culture, commons).

Name: *commonweal* = the public welfare, and the thing a *commons* is for. It is the ideal the
economy keeps claiming to serve.

## Run
```bash
source ../venv/bin/activate          # or any python 3.10+; stdlib only, no dependencies
python server.py                     # http://127.0.0.1:8765  (localhost only)
python run_sim.py 150 1 endogenous   # headless table: years, seed, preset
python -m unittest discover -s tests # conservation, determinism, baseline, dials, emergence
```

## Design choices (from the planning doc)
- **C3** Python simulation core (`sim/`) + thin web UI (`web/`, `server.py`).
- **A5** observer/terrarium first (policy dials, follow any life, money trail); full "possess one
  person" play is the next phase.
- **D1** one tick per season; ~600 ticks.
- Presets (B): `endogenous` (harvest + lending only), `merchant` (outside cash buyers, year 30),
  `tax` (merchant + a cash-only state tax, year 30).

## The causal loops (all in `sim/world.py`)
1. Harvest variance (weather + household luck) → short stores → mutual aid, then loans.
2. Unpaid debt → foreclosure → land concentrates; ties cut, grudges inherited.
3. Landless people sell hours; owners hire while marginal product beats the wage.
4. Competition ratchet: owners with thin margins lengthen the working day; laggards imitate
   machinery purchases (cash flows to artisans).
5. Time squeeze: less community time → culture and ties decay → less mutual aid.
6. Commodity substitution: machine cloth makes weaving obsolete and creates a cash need.
7. Commons and soil wear, pollution from machinery throughput → health.

## Honesty rules
- Money and food are conserved; `World.audit()` raises on any leak every tick.
- The model lets markets deliver real gains (trade smooths shortages, wages feed the landless).
  The claim to test is that costs grow faster and fall on different people.
- Tuning constants live in `sim/config.py` and a few inline coefficients; they are
  **game quantities, not measurements**.

## Provenance
`sim/ledger.py` is copied from the SimpleEconSim project (destruction ledger). The conserved-money
audit, per-agent memory/grudges, conservation-first workflow and "no scripted crises" rule come from
`../gdd.md` and `../agent.md`. No other code was reused; the old hex/FX/bond/provinces stack is
intentionally left behind.

## Roadmap
Phase 8 possession mode (play one person/family); richer tenancy/rent; culture-by-practice
carriers (elders); merchant/tax debrief screen; calibrate presets against historical cases.
