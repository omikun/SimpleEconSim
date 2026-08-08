# REGNUM — Priority Action Items

Per-phase, prioritized task list. Work items are ordered top-to-bottom within each phase.
Every item has an acceptance check. The standing invariant for ALL phases:

> **No conservation violation.** After any change, run the relevant sim and confirm
> `0 LEAK` / `0 SUPPLY SHIFT` and no `BANK INSOLVENCY` traceback.

Proposed cadence: 1 turn = 1 season (3 turns/year) — revisit in §14 of gdd.md.

---

## M0 — Nation & Tiles  *(priority 1: foundation)*

- [ ] **M0.1** Add `nation.py` — `Nation` wraps one sovereign `Government` +
      `tiles` list + `legitimacy` (0–1) + `regime_type` + treasury accessor.
      - Acceptance: `Nation` init over 1–3 `Region`s; gov.regions populated;
        `legitimacy` baseline 0.6; importable without touching existing sims.
- [ ] **M0.2** Terrain on `Region` — `terrain` dict + recipe modifier hook
      (`_produce_independent` / `_produce_corporation` scale production;
      cost-of-living hook for cold tiles).
      - Acceptance: fertile tile produces ~1.5x food vs plain; audits green
        (goods are not created — production is the *legitimate* good-creation
        point, modifiers adjust the existing recipe output).
- [ ] **M0.3** Adjacency graph + multi-route — replace single `destination_region`
      with `neighbors` list; wire one `Route` per neighbor; traders pick
      best-margin destination.
      - Acceptance: 3-tile ring sim (A–B–C–A) runs 300t, each pair trades,
        0 LEAK / 0 SUPPLY SHIFT.
- [ ] **M0.4** Ownership — `tile.owner_nation` / `claims`; Nation claims tiles.
      - Acceptance: ownership set/get + transfer between Nations exposes all
        citizen/agent reparenting in one call.
- [ ] **M0.5** 3-nation smoke test — new `sim_nation.py`: 3 Nations × 2 tiles,
      run 300t, print per-nation GDP/trade/food-price summary.
      - Acceptance: no exceptions; per-currency audit conserved across all
        nation currencies.

**M0 exit criteria:** a "govern one province" sandbox runs headless; all 9 legacy
conservation checks still pass on `econsim_two_region.py 300`.

---

## M1 — People: traits, memory, learning  *(priority 2)*

- [ ] **M1.1** Traits — add to `Agent.__slots__`: `ambition`, `loyalty`,
      `charisma`, `risk_tolerance`, `bigotry` (dict), `productivity`,
      `fertility`, `religiousness`; seeded at birth; **heritable with
      mutation** in `_handle_reproduction`.
      - Acceptance: newborn inherits parent's traits ± noise; no
        conservation impact (pure state).
- [ ] **M1.2** Identity sets — ethnicity / religion / political-identity tags
      on Agent (→ M2 faction membership).
      - Acceptance: 3-tile sim shows identity mix per tile in state archive.
- [ ] **M1.3** Memory — bounded ring buffers: `mem_prices`, `mem_hunger`,
      `mem_taxes`, `mem_promises`, `mem_casualties`, `mem_wages`.
      - Acceptance: each buffer capped (e.g. 32 entries); no unbounded growth.
- [ ] **M1.4** Learning 1 — personalize career-switch weights using
      `mem_hunger` + `demand_ratio` history (`_handle_career_switching`).
      - Acceptance: survival rates by profession shift measurably vs M0
        (compare 3 seeds); 0 LEAK.
- [ ] **M1.5** Learning 2 — migration intent from `mem_wages` + price
      differentials (feeds M4; stub produces intent score only).
      - Acceptance: intent score logged per tile; no agents move yet.

**M1 exit criteria:** agents demonstrably differ in behavior by trait/memory;
behavior-drift validation script (`tmp/`) shows no conservation drift over 300t.

---

## M2 — Factions & Unrest  *(priority 3)*

- [ ] **M2.1** `faction.py` — `Faction` (kind, membership, demands, grievances,
      influence). Overlapping membership allowed.
      - Acceptance: one agent simultaneously in 2+ factions; overlaps visible.
- [ ] **M2.2** Demand satisfaction — policy → demand matching (tax cut,
      welfare, tariff, native rights, immigration).
      - Acceptance: faction support = weighted demand-satisfaction; support
        plotted per faction per turn.
- [ ] **M2.3** Grievance accumulation — per-faction grievance from hunger,
      gini, tax, unemployment, repression, broken promises.
      - Acceptance: famine (kill food production) drives grievance up;
        food aid drives it down.
- [ ] **M2.4** Protest energy per tile — aggregate agent grievance into
      `tile.protest_energy`.
      - Acceptance: protest energy > 0 correlated with hungry + gini;
        logged per turn.
- [ ] **M2.5** Escalation ladder — unrest → protest → mob → forced
      compromise → takeover. All destruction/looting = **transfers**
      (looted food moves; burned goods counted as consumption; funds to
      fundraiser agents).
      - Acceptance: ladder triggers at thresholds; takeover reuses coup
        machinery (M3 stub hook); 0 LEAK through every stage.
- [ ] **M2.6** Repression — costs legitimacy + popularity; writes
      `mem_promises`/`mem_casualties` seeds.
      - Acceptance: repression quells current protest but raises future
        grievance (2-turn delayed effect).

**M2 exit criteria:** a scripted famine → protest → forced-compromise cycle
runs end-to-end with conservation intact.

---

## M3 — Regimes  *(priority 4)*

- [ ] **M3.1** `election.py` — candidates from trait.charisma + faction
      membership; platforms from faction demands.
      - Acceptance: candidate pool generated per election cycle.
- [ ] **M3.2** Campaign finance — treasury → candidate popularity at
      charisma-diluted rate (conserved transfer).
      - Acceptance: $10k spent on low-charisma candidate yields less
        popularity than on high-charisma; audit shows the transfer.
- [ ] **M3.3** Faction-weighted voting — adults vote by faction influence +
      memory (broken-promise betrayal).
      - Acceptance: election outcome flips when big faction betrayed.
- [ ] **M3.4** Legitimacy tracking + election cadence (fixed interval or
      legitimacy collapse).
      - Acceptance: losing coalition takes over; policy set flips.
- [ ] **M3.5** `coup.py` — generals (agents with popularity/loyalty/ambition);
      trigger check each turn; coup = treasury seizure (transfer), regime
      switch, possible purge.
      - Acceptance: engineered coup (low legitimacy + popular general)
        fires; treasury conserved; old elite's portable wealth becomes
        refugee capital (M4 hook).
- [ ] **M3.6** Player-faction continuity — if player's faction loses, they
      may continue as opposition.
      - Acceptance: opposition-mode UI stub exposes agitate/unrest actions.

**M3 exit criteria:** a full election cycle and a full coup each run with
conserved transitions; state archive shows the money trail for both.

---

## M4 — Territory & Migration  *(priority 5)*

- [ ] **M4.1** Settlers — recruit agents → claim unclaimed tiles (carrying
      portable wealth — conserved).
      - Acceptance: settler tile gets agents + inventory; no money created.
- [ ] **M4.2** Natives — `native_population` init + `native_ratio` stat.
      - Acceptance: tile reports native ratio; natives join factions.
- [ ] **M4.3** Assimilation — welfare/education spend lowers `native_ratio`.
      - Acceptance: $X spent → ratio falls; faction animosity falls.
- [ ] **M4.4** Eviction — army-driven; estates escheat per inheritance rules
      (conserved); expelled become refugees with portable wealth.
      - Acceptance: eviction run shows 0 LEAK; refugee population appears in
        neighbor tiles; diaspora faction + war-crimes grievance created.
- [ ] **M4.5** `army.py` — units from unemployed agents (drains protest
      energy); upkeep food/tools (consumed); equipment recipe (weapons
      consume wood/furniture); strength = soldiers × morale × equipment.
      - Acceptance: recruiting during unrest lowers protest energy; unpaid
        wages lower morale → desertion/mutiny risk; 0 LEAK.
- [ ] **M4.6** Legal migration — policy open/quota/points-based/closed;
      reuses `spawn_immigrants`; immigrants become citizens.
      - Acceptance: each policy produces measurable immigrant inflow;
        citizenship granted (faction membership + vote).
- [ ] **M4.7** Illegal migration — spontaneous movement by wage/price
      differential + risk_tolerance + chain-memory; undocumented =
      non-citizen (no aid/welfare/vote).
      - Acceptance: rich tile gains undocumented; poor tile sheds; protest
        energy in rich tile rises from undocumented hunger.
- [ ] **M4.8** Enforcement — patrols (treasury payroll), deportation events;
      anti-immigration faction grows with undocumented population.
      - Acceptance: enforcement reduces undocumented; faction responds;
        0 LEAK.

**M4 exit criteria:** a full expansion arc (settle → assimilate-or-evict →
refugees → migration waves) runs against an AI neighbor with conservation
intact.

---

## M5 — Worlds: AI, Diplomacy, Alliances  *(priority 6)*

- [ ] **M5.1** `ai_nation.py` — terrain value scoring from `production_log` +
      recipe modifiers; bottleneck relief from `demand_ratio_log` /
      `price_spread_log`.
      - Acceptance: AI picks the fertile tile over the barren one (greedy
        claim test).
- [ ] **M5.2** Vulnerability — tile vulnerable if adjacent to hostile/
      expansionist neighbor and weak local military; AI fortifies or secures
      peace.
      - Acceptance: AI moves army to threatened tile / signs treaty.
- [ ] **M5.3** Expansion drive — claim high-value adjacent tiles; weigh
      assimilate vs evict vs settle vs diplomatic fallout.
      - Acceptance: AI chooses cheapest acceptable path; player-visible
        reason string.
- [ ] **M5.4** `diplomacy.py` — bilateral relations from ideology, shared
      threats, trade intimacy, betrayal memory.
      - Acceptance: trade-pact tariff cut flows into
        `get_trade_fee_multiplier`; betrayal lowers relations.
- [ ] **M5.5** Alliance formation — common-threat counterbalancing;
      military coordination + trade pact + defensive commitment.
      - Acceptance: two weak nations ally against a strong expansionist.
- [ ] **M5.6** Ideological blocs — ideology distance + grievance →
      polarization; AI-vs-AI and player-vs-AI wars.
      - Acceptance: bloc war outbreak traceable to faction grievance
        (state archive).
- [ ] **M5.7** Betrayal — AI re-evaluates when threat rating shifts;
      backstab stores memory for all parties.
      - Acceptance: betrayed nation shows grievance rise; alliance
        formation post-betrayal is slower.

**M5 exit criteria:** N AI nations run a full sandbox (300–600t) with wars,
alliances, betrayals, and migrations; every outcome traces to agents/factions;
0 conservation violations.

---

## Cross-cutting (any phase)

- [ ] **C.1** State archive UI — expose `wealth_lineage`, `trade_dashboard`,
      money-trail views as an in-game ledger panel (matplotlib-based).
- [ ] **C.2** Perf pass — reuse SoA (`region_core.pyx`) / cython for agent
      count > 2000; profile with `profile_current.py`.
- [ ] **C.3** Repo hygiene — keep `tmp/` diagnostics out of commits; revert
      regenerated PNGs before committing (existing repo rule).
- [ ] **C.4** Client contract — define JSON **world-state schema** (tiles,
      nations, agent summaries, factions, protest energy, treasury, event
      log) + **intent schema** (set policy X, spend $Y, army move,
      eviction). This is the contract any engine can render against.
      - Acceptance: a sample 3-tile run dumps a complete world-state JSON.
- [ ] **C.5** `sim_server.py` — headless wrapper: load scenario, run one
      turn on request, return world-state diff; reuse the existing audit
      code to reject any conservation-breaking intent.
      - Acceptance: reject-a-bad-intent test passes (e.g. negative spend
        refused); 0 LEAK after 300t through the server.
- [ ] **C.6** Determinism pin — set `PYTHONHASHSEED`; replace per-process
      `hash((trader.id, good))` (region.py `_import_ask_price`) with a
      stable deterministic mix before multiplayer.
      - Acceptance: two fresh processes with same seed produce identical
        turn-by-turn world-state.
- [ ] **C.7** Feasibility client (engine decision) — Godot 4 2D tile map OR
      web (React + ECharts + canvas map) wired to `sim_server.py`. Goal:
      *feel* the election / protest / coup loop on a 3–5 tile map.
      - Acceptance: live run shows treasury, protest bars, event log; a
        policy intent visibly changes tile state next turn.
- [ ] **C.8** Rendering spec — density rendering (tile population heat),
      hero agents (candidates/generals/faction leaders as named portraits),
      engine-native charts replacing matplotlib for in-game panels.
      - Acceptance: 2,000-agent sim renders as tile-level stats with zero
        per-agent sprites; hero roster lists ≤ 40 named agents.
- [ ] **C.9** Asset pack selection — Kenney CC0 tile/UI packs, OpenGameArt /
      itch CC0/MIT sets, Google Fonts (serif display + UI face), Kenney
      audio + Freesound CC0 SFX.
      - Acceptance: an `assets/` dir with licenses documented; no
        non-CC0/MIT assets in the repo.

---

## Suggested first sprint

1. **M0.1** `nation.py` (small, unlocks everything)
2. **M0.2** terrain hooks (touches `region.py` core)
3. **M0.3** adjacency + multi-route (biggest M0 risk — do early)
4. Then M0.4 → M0.5, validating each with `econsim_two_region.py 300` +
   the new `sim_nation.py 300`.
</｜｜DSML｜｜>
</｜｜DSML｜｜>