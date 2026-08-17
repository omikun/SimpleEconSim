# REGNUM — Session Progress

**Topic (2026-08-17):** Provinces (shared gov/bank/charity across tiles), random seeding, per-tile vs per-nation sidebar stats, province highlight.
Agreement: **commit after each phase** (no push), refactor-first, every milestone gated on 0 SUPPLY SHIFT.

---

## Why this is complex

The engine assumes **one tile = one full institution set**. That invariant is load-bearing in:
1. `Region.__init__` — builds its own bank / gov / charity per tile.
2. `Region.step()` — ONE method interleaves per-tile economy (production/prices/auction) with institutional flows (charity collect/distribute mid-auction, gov tax/food-buy/borrow, bank deposit interest) running once per tile.
3. `forex.audit_currency_total` — sums `bank.equity`, `bank.fx_pool`, `charity.agent.cash` **per tile**. Sharing one bank across tiles without dedup ⇒ double-count ⇒ phantom SUPPLY SHIFT.
Plus ~40 read sites of `region.bank/.gov/.charity` across region.py, world_trade.py, forex.py, econsim_live.py, claims.py, viewers, drivers.

## Refactor-first ordering (each phase committed + green before next)

### Milestone D — zero-behavior-change extraction (commit 1)
- New `InstitutionBundle` holder (bank/government/charity) in province.py-style module.
- `Region` keeps `self.bank/.gov/.charity` as **properties** forwarding to the bundle → all ~40 read sites compile unchanged.
- Extract institutional chunks of `Region.step()` into named helpers called in the SAME order → byte-identical behavior.
- GATE: full regression (sim_nation/ring/behavior_drift/probe_hex/probe_worldview) + 40-turn world = 0 SHIFT.

### Milestone E — Province + shared institutions + audit dedupe (commit 2)
- `Province` owns ONE bundle; several Regions point at it (economy still per-tile).
- Institutional steps move from "per-tile inside step" to "once per province per turn".
- `forex.audit_currency_total` dedupes shared bank/charity (id()-seen set).
- `claims.py`: fresh claim → NEW single-tile province (existing per-claim institutions become the province's).
- `Nation`: add `provinces` list; treasury/stats aggregate via provinces (legacy Nation.government unchanged; sim_nation/sim_ring NOT converted).
- GATE: 40-turn AND 120-turn world = 0 SHIFT.

### Milestone F — seeding + viewer UX (commit 3)
- Random seed: `--seed N` launch arg (`sim_world` + `worldview`); default entropy (remove `random.seed(42)` hardcodes).
- Sidebar: per-tile ⇄ per-nation toggle (new key, e.g. V); per-region CoL line; tile CoL + climate display.
- Selecting a tile highlights its whole province on the hex map.
- Update `tmp/probe_worldview.py` (contiguity, highlight render, seed determinism, both panels).
- GATE: probe PASS + 40-turn 0 SHIFT.

---

## Progress
- [x] Milestone D — InstitutionBundle extraction DONE:
      province.py InstitutionBundle (bank/gov/charity); Region.bank/.gov/.charity
      now forwarding properties; construction via make_bundle (wilderness = all
      None); step() untouched (byte-identical).  Gate: sim_nation 100, sim_ring
      300, behavior_drift GATE, probe_m2/m3/hex/worldview all PASS +
      verify_hex_adj 10t 0 SUPPLY SHIFT.  **Committed (no push).**
- [ ] Milestone E — Province + shared bundle + audit dedupe + claims (commit 2)
- [ ] Milestone F — seeding + viewer province-highlight + tile/nation stats (commit 3)
