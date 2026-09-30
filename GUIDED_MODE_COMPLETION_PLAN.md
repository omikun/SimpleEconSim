# Guided Mode Completion Plan

## Goal

Deliver one complete, understandable Guided campaign based on Khedivate of Egypt under Khedive Ismail Pasha during the 1877 low-Nile and debt crisis. Guided mode should teach the crisis through a small set of choices and consequences while retaining Advanced mode and the shared simulation engine.

The historical setting supplies people, institutions, and places. The campaign's 20-turn duration, four-turn relief reserve, six-turn payment window, starting values, and scenario outcomes are explicit gameplay abstractions. Do not present them as documented historical events.

## Recommended decisions adopted

- Use Egypt in 1877 as the authored introductory scenario: Cairo, the Nile Delta, Upper Egypt, and Alexandria; Khedive Ismail Pasha, the Caisse de la Dette Publique, merchants/exporters, large landowners, and fellahin.
- Keep Guided/Advanced as an application setting independent of campaign selection. The existing Advanced composition remains available.
- Keep the first release to three headline pressures: household access to maize, the next debt-service window, and political support.
- Start paused and make **Next Turn** the deliberate step. Keep optional Play available.
- Model grain reserves as state-held inventory available for relief, and show coverage in turns at the configured relief rate. Show household food access separately from public stock.
- Use the existing economy and policy/decree seams where their effects are legible. Avoid adding commodities or a detailed historic economy unless a distinct player decision requires it.
- Replace the old commons-restoration action in this scenario with crop allocation, irrigation, and cultivator tax/relief decisions, which fit this setting more directly.
- Use a deterministic authored scenario setup rather than relying on a random world to happen to resemble Egypt. Keep setup data separate from rendering code.
- Use four debrief bands: relief and payment, creditor settlement, coercive extraction, and breakdown. Explain the causal path; do not reduce the result to a score.

## Phases and completion criteria

### Phase 0 — Scenario and product decisions

**Status: Complete**

- Replace the fictional Grain Compact setting with the Egypt 1877 scenario in the GDD.
- State which campaign numbers and timeline elements are abstractions.
- Align the Guided UI label and roadmap with the selected scenario.
- Record defaults and phase acceptance criteria in this plan.

**Acceptance:** GDD and interface labels consistently describe the same scenario; historical facts and tuned values are distinguishable.

### Phase 1 — Deterministic scenario setup

**Status: Complete**

- Add a scenario definition/data module for briefing, map/region roles, initial state, pressure definitions, available choices, and outcome predicates.
- Add a deterministic `--scenario egypt-1877` start path without changing the default sandbox or the saved Guided/Advanced preference.
- Give this scenario Egypt, Britain, and France identities; label Egypt's capital and selected regions with Cairo, Nile Delta, Upper Egypt, and Alexandria scenario roles.
- Use fixed scenario seeds while restoring the normal random-generator state after setup.
- Seed only scenario-relevant state; do not silently overwrite player progress when switching UI mode.
- Make scenario selection and scenario identity visible in the UI.

**Acceptance:** The scenario entry path builds the Egypt/Britain/France setup with stable place labels and initializes its briefing/state; ordinary sandbox startup and UI preference remain unchanged. Geography still uses the shared procedural map topology, so its generated outline should not be presented as a literal map of Egypt.

### Phase 2 — Playable crisis choices

**Status: Complete**

- Reuse household food inventories, public food reserves, local tax policy, export routes, unrest, legitimacy, and treasury transfers for public grain release, domestic food priority, tax relief, and the scheduled debt-service choice.
- Add the narrow missing hook for retaining part of food exports in regional granary stocks when domestic supply is prioritized.
- Record choices and their consequences in scenario state; enforce one major scenario choice per turn.
- Ensure scenario actions resolve through supported intents/decrees or an equally explicit domain action path; avoid UI-only state changes.
- Show eligibility, cost, delay, and expected direction of effect before confirmation.

**Acceptance:** The scenario action layer includes a resource-limited food release, a delayed food export change, tax relief with lower future revenue, and a payment/defer choice that changes treasury or creditor confidence. UI affordances are completed in Phase 3.

### Phase 3 — Guided briefing, pressure cards, and map focus

**Status: Complete**

- Replace generic nation diagnostics with three scenario pressures: household maize access, the debt-service window, and political support.
- Add a short opening briefing, objective/turn tracker, payment countdown, recommended first action, and stable place labels. Mark the shared generated geography as schematic.
- Connect decision buttons to scenario actions; keep detailed accounting and specialist panels in Analysis.
- Handle narrow panel widths, long text, unavailable actions, hover/focus, and keyboard/mouse interaction without clipping or dead links.
- Preserve the full Advanced composition and mode preference.

**Acceptance:** The Guided panel shows the crisis, three headline pressures, one suggested response, and legal action buttons without opening Analysis; the existing analysis panels remain available.

### Phase 4 — Campaign progression and debrief

**Status: Complete**

- Keep the campaign paused by default, stop autoplay when it ends, and track the turn-six payment window and turn-20 horizon.
- Apply the low-Nile yield shock in the Delta and Upper Egypt through turn eight; update household access, debt status, treasury transfers, and political support through the shared simulation.
- Implement breakdown precedence at legitimacy <= 10% or average unrest >= 0.85. Otherwise, tax extraction identifies the coercive band; protected food plus payment is relief/payment; protected food plus a concession is creditor settlement; remaining states end in breakdown.
- On completion, stop further scenario turns and show measured food/political outcomes, debt/autonomy status, and the player's recorded decisions.

**Acceptance:** The same opening can lead to at least two distinguishable endings, and the debrief attributes results to actual player choices and measured simulation state.

### Phase 5 — Integration and delivery polish

**Status: Complete**

- Confirm Guided/Advanced switching stays independent of campaign selection, scenario restart is deterministic, and ordinary sandbox startup/restart keeps its existing path.
- Confirm scenario entry bypasses sandbox save-slot/cache restoration so generated scenario state cannot overwrite a player's existing sandbox.
- Check all scenario links, action feedback, layout at supported window sizes, and history-versus-abstraction wording.
- Update the GDD and plan with delivered behavior, remaining limitations, and any changed decisions.
- Run focused checks and a complete scenario smoke playthrough where the local environment supports it.

**Delivery evidence:** Three deterministic 20-turn strategy paths reached relief/payment, creditor settlement, and coercive extraction respectively. The native Voronoi renderer drew the guided scenario on the Apple M3 Pro path (91,104 mesh vertices); it did not use the 2D renderer. The scenario restart and ordinary sandbox reload paths were checked; scenario restart rebuilds the same turn-one setup. All six UI render-cache unit tests passed, and touched Python modules compiled. The geographic-demographics test module still has two failures in generic-world occupation and biome assertions; those runs used the ordinary sandbox path, and the scenario changes do not alter that path. Pytest is unavailable in the local environment. Scenario startup skips prior saved-slot and generated-map cache loading so it cannot overwrite the sandbox's saved state. The scenario campaign itself does not yet serialize mid-run progress to a save slot; restarting begins the scenario again from turn one. Guided/Advanced remains a persistent UI setting, independent from campaign selection. The map is still shared procedural geography with scenario-role labels, not a literal Egypt map; food and financial quantities remain normalized abstractions.

**Acceptance:** The campaign can be started, played to a debrief, restarted deterministically, and exited to Advanced/sandbox use without losing unrelated state.

## Ambiguities to resolve by recommended default

These are not blockers; use the defaults below unless implementation reveals a concrete mismatch:

1. **Historical start date:** Use the 1877 low-Nile emergency with the Caisse already operating. Treat turn six as an abstracted next payment window, not a specific coupon date.
2. **Geographic representation:** Preserve the shared map topology and simulation model, but use authored scenario roles/names and a small playable focus. Do not claim every generated tile is a literal historical province.
3. **Maize and food goods:** Reuse the existing food commodity initially and name it “maize” in scenario-facing copy. Add a distinct maize good only if the existing commodity cannot support the intended price, stock, or trade decisions.
4. **Relief stock mechanics:** Prefer real inventory and transfer flows. If public stock is not represented by the engine, add the smallest explicit scenario stock ledger with turn-by-turn accounting and avoid implying it is household inventory.
5. **Crop and irrigation actions:** Prefer existing production, construction, and policy mechanisms. If direct crop allocation is absent, implement one narrow, delayed scenario action before adding broad agricultural simulation.
6. **Outcome precedence:** Breakdown takes precedence if government control/revolt ends the campaign; otherwise classify by food access and debt outcome, with coercive extraction identifying high repression or burdens. Record thresholds in the scenario definition and expose them in the debrief explanation.
7. **Currency presentation:** Treat scenario debt amounts and cross-border transfers as normalized simulation units. Do not display them as literal 1877 sterling values or imply a historical exchange rate.

## Commit policy

Complete and review each phase's changes as a coherent unit, then create one commit for that phase before starting the next. Keep unrelated pre-existing scratch files out of commits. If a phase cannot meet its acceptance criteria because of an engine limitation, document the exact blocker and the smallest viable next step in this file rather than marking it complete.
