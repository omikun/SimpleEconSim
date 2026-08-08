# REGNUM — Game Design Document

**Working title:** REGNUM — *a dynasty-and-regime economics game built on the conserved-money engine*

**Engine basis:** SimpleEconSim (`econsim*.py`, `region.py`, `forex.py`, `government.py`, `wealth_lineage.py`).
Each region is a living economy of individual agents (cash, deposits, loans, inventory, parent,
descendants, birth/death). Goods flow through priced transport pipelines. Two+ currencies trade
via central-bank desks with reserve-capped convertibility. Every mechanic is a *conserved
transfer* enforced by per-turn cash audits and per-currency totals.

---

## 1. Concept pitch

You don't build cities. You **rule a state built out of living tiles** — each tile is a region
full of individual agents who eat, breed, work, trade, bank, protest, migrate, and die. You win
by growing your nation's wealth, legitimacy, and power without being deposed or conquered.

The game's promise: **every macroscopic strategy outcome (election, coup, famine, currency
crisis, treaty, war, annexation) is legible all the way down to the specific agent, family,
faction, and transfer that caused it.**

## 2. Design pillars

1. **Legibility** — every system effect must be traceable to agents. The existing
   `wealth_lineage.py` family/genogram plots and `trade_dashboard.py` panels become in-game
   "state archives" the player can open.
2. **Conserved money = trust** — no mechanic may create or destroy currency/goods. Elections,
   coups, war, eviction, annexation all *transfer*. The audit is a feature: the game can prove
   where money went.
3. **Power flows from people, not tiles** — legitimacy, unrest, elections, and coups emerge
   from agent state (hunger, wealth, memory, faction grievances), not event scripts.
4. **Consequences persist across generations** — agents have memory, traits, and descendants.
   A general you humiliate becomes a faction leader whose descendants still resent you.

---

## 3. The world: tiles

Each region becomes a Civ-like tile. The existing `Region` class is ~90% of a tile already
(agents, bank, gov, currency, recipes, logs, charity).

### 3.1 Additions to `Region`
- `terrain`: fertility, forest, minerals, altitude, climate — *as recipe modifiers*
  (fertile tile → food production ×1.5; mineral tile → unlocks new `ore` good or boosts
  furniture; cold tile → higher food consumption).
- `adjacency`: a graph of neighbor tiles, replacing the single `destination_region`.
  Multiple `Route` objects per tile (one per neighbor) — `transporter.py` already supports
  per-route wiring and congestion.
- `native_population`: initial agents with distinct faction identities (see §6) and a
  `native_ratio` statistic.
- `owner_nation` / `claims`: which nation controls / claims the tile.

### 3.2 Nation superstructure
A `Nation` wraps one sovereign `Government` (the class already supports `gov.regions = []`)
plus: treasury, legitimacy, regime type, borders, diplomacy state. Tiles are provinces of a
nation; a tile's local governor is a `Government` subordinate to the Nation.

### 3.3 Scarcity & trade
Tiles differ by terrain → different cost structures → the existing arbitrage/import machinery
(`_calculate_bid` margin gates, `_import_ask_price`, tariff pass-through, FX conversion)
naturally produces inter-tile trade, tariffs, and FX flows. The first thing an AI or player
does is read the price map between tiles (`price_spread_log`).

---

## 4. Regimes: democracy and the gun-barrel exit

The player controls the **Nation**, not individual agents. Two access modes.

### 4a. Democracy path — elections & campaign finance
- **Candidates** are agents with `trait.charisma`, faction membership, and a policy platform
  drawn from their faction's demands (tax cuts, welfare, war, tariffs, native rights,
  immigration stance).
- Player **chooses a candidate and throws money at the campaign**: allocate treasury funds
  (conserved transfer) that convert to `popularity` at a rate diluted by charisma and
  scandals (low traits → money wasted).
- Elections run on a cadence or when legitimacy collapses. Voters = all adult citizens;
  **voting is weighted by faction** and by agent memory (a remembered broken promise =
  betrayal grievance).
- Win → keep the policy levers. Lose → opposition coalition takes over; policy set flips
  toward their agenda. If the player's faction is in opposition, they may keep playing as
  that faction agitating from outside.

### 4b. Military path — coup
- **Generals** are agents with `traits: popularity, loyalty, ambition`. Popularity comes from
  winning wars, public spending, charisma.
- Coup triggers when: general popularity high **and** regime legitimacy low **and** general
  loyalty low, checked probabilistically each turn.
- On coup: a new government takes over. The treasury is **seized (a transfer)**; the old elite
  may flee with portable wealth → refugee wealth abroad, feeding migration/immigration
  pressure and capital flight.
- "Start anew": regime change resets legitimacy to a fresh baseline, swaps faction power, and
  may purge. Purged/promoted/paid-off agents carry memories that flavor future faction
  relations.
- Player can *be* the general (play the coup) or face it as a threat and preempt it (pay
  off, promote, purge — each with memory/grievance consequences).

---

## 5. Agents: traits, memory, learning

### 5.1 Traits (static, birth-seeded, heritable with mutation)
- `ambition`, `loyalty`, `charisma`, `risk_tolerance`, `bigotry` (per-faction animosity
  vector), `productivity`, `fertility`, `religiousness`
- Ethnicity / religion / political-identity sets (→ faction membership)
- Trait effects: ambition → more career switching; charisma → elections; bigotry → faction
  conflict; risk_tolerance → emigration/illegal migration propensity; religiousness → faction
  cohesion.

### 5.2 Memory (bounded ring buffers)
- `mem_prices` — learned price expectations → smarter bidding (less panic)
- `mem_hunger` — hunger history → grievance + protest participation
- `mem_taxes`, `mem_promises` — broken-promise events → betrayal grievance
- `mem_casualties` — war/famine deaths of kin → hatred toward the responsible nation/faction
- `mem_wages` — expected wage → labor-market behavior / strike propensity

### 5.3 Learning (bounded parameter drift)
- If a profession starved an agent last winter (`mem_hunger`), raise career-switch weight
  toward sectors with high `demand_ratio` history (the engine already computes `most_demand`
  and `_compute_bottleneck_weights`; learning personalizes the weights).
- If wages are falling, raise migration intent toward tiles with better price/wage
  differentials.
- Learning is stochastic and bounded so behavior stays alive without destabilizing
  conservation.

---

## 6. Factions

New `Faction` class (per nation, or spanning nations for diaspora/religious blocs):
- `kind`: ethnicity | religion | political | class | regional
- `membership`: set of agent ids (**overlapping** — an agent can be Catholic, Basque,
  socialist, farmer, and veteran simultaneously)
- `demands`: ranked policy vectors (lower grain tax, more welfare, native rights, war with X,
  open borders)
- `grievance_growth` from: hunger, inequality (gini per faction), taxation, unemployment,
  repression, broken promises
- `influence` in government: elected seats or coup-cell strength

**Overlapping interests in practice:** the player's coalition = sum of factions backing the
regime; support decays as demands are ignored, spikes on concessions (a policy = a transfer
into their members' pockets and food). Cross-cutting memberships mean alienating one faction
bleeds into others — the "overlapping interests" mechanic.

---

## 7. Hungry masses: protest, compromise, takeover

Built on existing `hungry_steps`, starvation deaths, and gini tracking.

**Protest energy per tile** = aggregate agent grievance:
`f(hunger, gini, tax, unemployment, repression_memory, faction influence)`.

**Escalation ladder** (energy thresholds):
1. *Unrest* — production efficiency drops (generalize the existing
   `chance *= 1/(1+hungry_steps*0.2)` pattern to strikers withholding labor).
2. *Protests* — agents withhold production (strike); export pipeline slows.
3. *Mob / riots* — looted food moves to protestors; goods burned counted as "consumption";
   funds move to fundraiser agents — **nothing created, everything moves.**
4. *Forced compromise* — the government must adopt the largest faction's top demand (policy
   flip) or lose legitimacy sharply.
5. *Takeover* — if the mob outnumbers the army/gov forces and legitimacy is collapsed, a
   *popular front* replaces the regime (same regime-change machinery as coup, initiated by
   faction grievance instead of a general's ambition).

**Player responses:** food aid (exists), welfare (exists), concessions (new), repression
(costs popularity + writes memory that fuels *future* grievance — the long-game tradeoff).

---

## 8. Expansion: settlers, natives, and the army

### 8.1 Tile acquisition
- Claim unclaimed tiles via expedition — settlers are recruited agents who migrate out
  (carrying portable wealth — conserved).
- **Absorb natives:** tiles have native populations. Options:
  - *Assimilation*: invest in native welfare/education (conserved transfers) → natives
    integrate into citizen factions; `native_ratio` falls.
  - *Settler friction*: settlers and natives compete in the same market (the engine handles
    competition naturally); friction manifests as faction animosity and raid events
    (production hits).
  - *Forcible eviction*: army action — natives killed (estates escheat per existing
    inheritance rules — conserved) or expelled as **refugees** (migrate across borders,
    feeding legal/illegal migration pressure and international grievance).
- Eviction has permanent consequences: refugee diaspora factions abroad hostile to the
  player's nation, and a "war crimes" grievance that poisons diplomacy.

### 8.2 Army (new)
A `Military` structure:
- **Units** tied to tiles; each unit = paid soldiers recruited from unemployed agents —
  this drains protest energy (a strategic lever, not just an expense).
- **Upkeep**: food + tools per unit per turn (conserved; consumed as the existing luxury
  consumption consumes goods).
- **Equipment**: weapons/armor good chain (new recipe) that consumes wood/furniture — gives
  the industrial sector a strategic demand sink.
- **Strength**: soldier count × morale × equipment quality. Morale falls with unpaid wages
  (memory seeds for desertion/mutiny → potential military coup source).
- Used for: eviction, defense of vulnerable tiles, offensive war (see §10).

---

## 9. Migration and immigration policy

The engine already has `spawn_immigrants` (legal, interval-based, cash + inventory). Extend:

### 9.1 Legal migration
Per-nation policy: **open / quota / points-based / closed**. Points reuse the existing
points-style thinking — profession scarcity, wealth, age, family ties. Legal immigrants
become citizens (faction membership, voting rights).

### 9.2 Illegal migration (spontaneous movement)
- Driven by wage/price/opulence differentials between adjacent tiles and agent traits
  (`risk_tolerance`, `ambition`) and memory (chain migration — someone they know made it).
- Undocumented entrants exist in the tile but are **non-citizens**: no food aid, no welfare,
  no vote, higher hunger vulnerability — they show up in the protest pool as unrepresented
  hungry masses.
- **Enforcement**: costs treasury (patrols, border posts — conserved payroll); deportation
  events (expellees return or become refugees elsewhere); anti-immigration factions grow
  with undocumented population.

### 9.3 Migration as the population-pressure valve
Poor tiles shed hungry agents (reducing local protest) into rich tiles (raising theirs).
`hungry_log` per tile becomes the real geopolitical signal — migration is how unrest is
exported and imported between nations.

---

## 10. AI governments: terrain sense, vulnerability, resources, alliances

**AI brain (`NationPolicyAI` per AI nation):**

1. **Terrain & resources:** per-tile value = production potential (recipe modifiers × current
   production from `production_log`), defensibility (neighbor hostility), and bottleneck
   relief (does a neighbor produce the input I'm importing? — read `demand_ratio_log` /
   `price_spread_log`). Gives the AI a natural resources map.
2. **Vulnerability:** a tile is vulnerable if adjacent to a hostile/expansionist nation and
   military presence is weak vs neighbor strength. AI fortifies (moves army units) or secures
   peace.
3. **Expansion drive:** claims high-value tiles adjacent to its borders; weighs
   native-absorption cost vs eviction cost vs diplomatic fallout — the player's own four
   options (settle cheaper, evict faster, assimilate cleaner).
4. **Cooperation & alliances (diplomacy layer):**
   - Bilateral relations matrix from: ideology vectors (dominant faction of each nation),
     shared threats, trade intimacy (`export_val`/`import_val` history), past betrayals
     (memory).
   - **Alliance formation heuristic:** detect a common threat (a neighbor with high military
     expansion score and adjacent borders) → sign an alliance with counterbalancing nations.
     Alliance = military coordination (joint war if jointly threatened), trade pact (mutual
     tariff cut — wired directly into `get_trade_fee_multiplier`), and defensive commitment.
   - **Ideological wars:** if ideology distance crosses a threshold and grievance (per-faction
     memory) is hot, alliances polarize into blocs and war becomes likely — the classic
     "two-nation standoff over resources or ideology" emerges from faction memory, not a script.
   - Betrayal is possible: if a partner's threat rating shifts, AI re-evaluates — backstabbing
     stores memory for everyone involved.

---

## 11. The trust layer: conserved money as the signature feature

Every new system obeys the engine's existing invariants:
- Currency totals per nation are conserved (per-currency audit from `forex.audit_currency_total`
  extended to all nation currencies).
- Goods move or are *consumed*; they are never created or destroyed invisibly.
- Regime change = treasury seizure (transfer), not free money.
- Eviction = estates escheat per inheritance rules; refugees carry portable wealth with them
  — a real international capital-flow mechanic: **refugee flight = capital flight**.

The game can therefore show the player, at any moment, a **"money trail"** view: *"your 3%
tariff on furniture from the mineral province flowed $12,040 into the treasury, $2,800 of which
you spent suppressing the Eastern Grand Coalition's protests — here are the receipts."*
No competitor does this. It is the hook.

---

## 12. Existing code → game component map

| Game feature | Existing engine piece | Work needed |
|---|---|---|
| Tile | `Region` (agents, bank, gov, recipes, logs) | terrain modifiers, adjacency graph, multi-route |
| Nation | `Government` (regions list, policy knobs) | legitimacy, regime type, diplomacy state |
| Economy | `Region.step()`, `_trade`, `_produce`, `bank`, `forex` | mostly reuse; scenery-aware recipe tweaks |
| Transport/trade routes | `Route`, `transporter.py` | wire N routes per tile |
| Dynasty/UI archive | `wealth_lineage.py` | expose as in-game ledger |
| Fiscal/welfare levers | `Government` policy suite (baby bonus, UBI, parental leave, mortality multiplier, tariff, drawback, probate) | reuse directly as "policies" |
| Governments of tiles | `govmod.find_government_for_agent` | extend to Nation sovereignty |
| Migration | `spawn_immigrants` | illegal spontaneous migration, enforcement |
| Conservation audit | cash audits, per-currency totals, insolvency guard | extend to all new systems |

**New modules:** `nation.py`, `tile.py`, `faction.py`, `unrest.py`, `election.py`, `coup.py`,
`army.py`, `migration.py`, `diplomacy.py`, `ai_nation.py`, `memory.py` (agent trait/memory
fields + learning), plus a minimal map/UI shell (turn-based strategic view of tiles + event
log; reuse matplotlib as the "state archive").

---

## 13. Phased roadmap

- **M0 — Nation & Tiles:** Nation wrapper, adjacency graph, 2–3 tiles wired with routes,
  terrain price modifiers, keep all audits green, 30–150 turn test.
- **M1 — People:** traits, memory, learning; verify behavior drift without breaking
  conservation.
- **M2 — Factions & Unrest:** factions, grievances, protest escalation ladder, compromise,
  mob takeover.
- **M3 — Regimes:** elections, campaign finance, candidates; generals, coup path, purges.
- **M4 — Territory & Migration:** settlers, natives, eviction/assimilation, army units,
  legal/illegal migration, enforcement.
- **M5 — Worlds:** AI brain (terrain-value, vulnerability, expansion), diplomacy, alliances,
  ideological blocs, AI-vs-AI and player-vs-AI wars.

Each phase ships playable: M0–M1 is a "govern one province" sandbox; M2–M3 adds the political
game on the same loop; M4–M5 expands to the geopolitical game.

Priority action items per phase live in **`priority_tasks.md`**.

---

## 14. Open questions to steer iteration

1. **Cadence** — each turn = a month? a season? a quarter? (Affects age/lifespan tuning.)
2. **Scale** — how many tiles/nations at full release? (Perf: the SoA/cython path exists for
   large agent counts.)
3. **Play style** — single-player with AI nations (assumed) vs hot-seat/async multiplayer?
4. **Failure tone** — when your regime falls, do you *continue as the successor
   regime/opposition faction* (assumed — persistent world) or game over?
5. **Victory conditions** — score-based (wealth × legitimacy × power), objective-driven, or
   open-ended sandbox with "survive the timeline"?
</｜｜DSML｜｜>
</｜｜DSML｜｜>