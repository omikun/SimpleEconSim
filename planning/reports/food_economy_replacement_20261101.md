# Food economy replacement — implementation and verification

Implemented 2026-11-01 in the existing checkout. No commit or deployment was requested.

## Result

Food production now comes from persistent crops on finite lawful farm operations.
Pantries do not switch a planted crop off. Households share actual grain and
prepared meals, and each person receives one ordinary nutrition update per turn.
Commons gathering is finite and consumes work that cannot also be used for crops,
industry, engineering, or travel. Established workers keep viable livelihoods;
better quotes alone do not make them change professions.

The temporary universal steam multiplier is removed. Installed seed drills and
harvest machinery reduce their specified farm work requirements; yield technologies
improve potential. Operating-company ownership is respected. Soil degradation
retains the earlier tenfold slowdown. Aging and the separate ten-turn agricultural
calendar are unchanged.

## Authoritative rules

- Food wallets use integer thousandths internally, including export and foreign
  inventories. Ordinary getters, slices, copying and pickling expose normal units.
  Public institutions hold separate stocks at named physical sites.
- Each operation retains its plot, area, seed reserve, standing crop, delivered
  work, harvest, and storage. Commons acreage is reallocated at sowing among
  eligible cultivators; neither entrants nor population growth create land or silos.
  Standing crops and their grain survive a career change or operator succession.
- The calendar is sowing at phases 0–1, tending at 2–5, harvesting at 6–7, and
  fallow at 8–9. Default generated openings start after a declared prior harvest.
  Authored Egypt stocks are preserved. Missing legacy crop history creates no free crop.
- Sowing requires owned seed. The ordinary turn buys productive inputs before
  production, pays wages and obligations, then clears household food orders.
  Late food clearing does not repeat the credit, wage, or career phases.
- Work is bounded per real adult. Gathering and engineering reduce the remainder.
  An employed person can gather. Paid seasonal jobs draw on the same remaining
  work; a person does not acquire a second full workday by taking one.
- Recovery intake is bounded above basic need. Wealth does not multiply staple
  calories. Prepared meals substitute for raw food, and processing cannot create
  additional food calories. Storage overflow and spoilage are real losses.
- Search starts after persistent uncovered necessities, actual meal failure,
  loss of livelihood, or first entry into adult work. Executable permanent moves
  still share the profession departure budget and protected minimum of four.
- Households may plan a move to neighboring usable commons when local subsistence
  fails. People and their inventories arrive together at the next boundary, with
  travel reducing available work. Cash without reachable food does not prevent
  subsistence migration. Explicit enforced movement policies can deter it.
- Existing gathering restrictions retain their usable-rights effects. Refreshing
  customary-right records cannot silently restore an enforced closure.
- Public programmes reserve an actual budget, begin next turn, require deliveries
  or work, and expire. Unspent cash returns. Productive advances create repayment
  claims. Neither public orders nor the needs view assigns people a profession.

## Player and AI controls

The web district inspector’s **Citizens → Labor** view now shows primary farmers,
effective crop work, the latest production/consumption/seed/loss flows, stock change,
and farm support relative to farmers and other residents. Ten-turn support capacity
is withheld until a complete observed window exists. The native government panel
shows the corresponding food-support figures and opens **Economic Needs / Funded
Support**.

Both clients provide a commodity needs table and bounded controls for public
procurement, productive loans, seasonal farm work, and purchased meal relief.
Quantity, budget, expiry, delivered amount, spending, completion and refund are
observable. The web form preserves edits across updates. Authored rivalry games
retain their existing scenario-decision restriction; the general funding form
respects that restriction. Normal sandbox games permit these programmes.

Enabled national policy AI reads the same needs information, waits for persistent
pressure, and uses a bounded treasury appropriation. Isolated engineering test
campaigns do not implicitly acquire a national AI or unlimited relief.

The stock outlook distinguishes committed crop receipts from conditional future
planting, splits the two harvest windows, ages known children, and shows an adverse
path and a separate potential-commons path. A stock gap before harvest is visible
even if a later crop could cover the full cycle. Physical supply and household
purchasing access remain separate diagnoses.

## Conservation and trace coverage

The world audit includes people, corporations, located public/charity grain,
operating stores and seed, legacy queued food, bankless estates, commercial cargo,
and provincial shipments. Its opening precedes spoilage, movement and freight
arrival. It reconciles harvests, gathering, seed, meals, processing loss, storage,
failed-birth provisions, engineering inputs and military rations. Internal transfers
are not sources or sinks. Every audit exposes its unexplained residual.

Soldiers consume local public grain; neighboring stocks do not become instant
rations. Scenario purchases, crew provisioning, relief and looting also respect
located ownership. Army abstract personnel and civilian ordinary nutrition remain
separate existing model abstractions.

The historical trace readers remain available. New gathering and crop arithmetic
have versioned formulas. Household allocation records exact inventory legs, and
sector-inventory traces include corporate stocks while demographic counts exclude
corporations. A closed company remains a corporate entity.

## Verification

The final simulation source fingerprint is
`0e694b15dbd478043ae164c34d69ec4c90090e5b1a7a3a19950cabbc9f8b73f8`.
All campaign artifacts report an unchanged source at completion.

| Check | Result |
|---|---|
| Focused food, career, market, engineering and trace regressions | 213 passed, including 32 replacement-model causal tests |
| Authored scenario, institutional transfer and enclosure regressions | 80 passed |
| Server and native fresh-process checkpoint regressions | 5 passed; full-state/RNG continuation and supported trace formulas agree |
| Three-person renewable farm fixture | 300 turns; no unmet basic meals or unexplained food |
| Policy/seed matrix | 18 × 100-turn campaigns; zero currency violations and zero unexplained food |
| Growing stress economy | 300 turns; zero currency violations and zero unexplained food; severe famine remains |
| Default multi-nation world | 3 turns; contiguous food-account balances and successful complete UI serialization |
| Native Egypt | 10 advances; zero food residuals and currency violations, including scenario actions after the core turn |
| Web/native interface | Desktop and phone browser checks plus native modal rendering, paging, and funded submission |

Artifacts: [campaign summary](food_economy_release_20261101/summary.json),
[balanced 300-turn fixture](food_economy_release_20261101/balanced_300.json),
[300-turn stress run](food_economy_release_20261101/responsive_4243_300.json),
[default-world check](food_economy_release_20261101/default_3.json), and
[Egypt check](food_economy_release_20261101/egypt_10.json).
Test logs and UI captures: [QA evidence](food_economy_release_20261101/qa/).
Earlier probes are retained in the separately named intermediate directories;
they are not the final-source acceptance evidence. JavaScript syntax and diff
whitespace checks pass. No additional package dependency is introduced.

### What the stress runs establish

These are isolated engineering-test economies, with no adjacent migration
escape and no implicit national policy AI. Their variants exercise frozen or
responsive labour, commercial adoption/control, and bounded relief. The
18 runs record **90–141 human starvation deaths** each by turn 100. Low final
underfeeding in a nearly depopulated region is not evidence of success.

For example, responsive seed 4243 records these complete ten-turn windows:

| Turns | Farm harvest | Commons food | Ordinary meal need | Delivered crop work | Closing food stocks |
|---|---:|---:|---:|---:|---:|
| 1–10 | 175 | 131 | 3,022 | 4.7 | 2,902.5 |
| 11–20 | 3,919 | 415 | 3,430 | 101.7 | 3,620.4 |
| 21–30 | 3,655 | 483 | 4,242 | 124.5 | 3,297.1 |
| 31–40 | 3,652 | 480 | 5,028 | 133.9 | 2,969.0 |
| 41–50 | 2,541 | 480 | 5,762 | 127.5 | 1,886.4 |
| 51–60 | 448 | 480 | 6,282 | 44.1 | 374.5 |

Quantities are rounded here; the underlying records retain thousandths. Opening
carryover explains why the first low-harvest window can feed people. Subsequent
demand outgrows replenishment, then harvests and delivered work deteriorate.
The archived rows include seed use, storage losses, adult professions, prices,
soil, water pollution, and final crop commitments for diagnosis. This is a
within-run observation, not an isolated causal estimate for any one policy.
The 300-turn stress continuation ends with two residents and 142 starvation
deaths. **Accounting and mechanism checks pass; long-run welfare balance does
not.** Further demographic, health, land/productivity and policy calibration
should be evaluated explicitly, without restoring infinite foraging, compulsory
career changes, free rations, or universal steam productivity.

## Practical limits

This replacement does not promise that every economy survives. The authored
stress campaigns still develop severe food crises as demand grows and delivered
crop work deteriorates. Balanced subsistence and full demographic campaigns test
different things; a three-person fixed-population farm fixture is not a claim
about the survival of a growing industrial nation.

The model still uses one aggregate crop and gameplay parameters for acreage,
yields, seasons and work. It does not add detailed crop species or a demographic
rebalance. Conditional future planting is not a guaranteed harvest; future births,
new prices, strikes, disease and new policies can change the outcome. Potential
commons is explicitly not food already in a pantry. Commercial grain must still
arrive and clear its market before a household can eat it.

The support estimate deducts seed and all observed local food-storage losses,
so it is a conservative regional net-support measure, not a provenance claim
that every spoiled unit was grown by local farms. The needs table is diagnostic:
a labour or productivity gap is not proof that assigning extra workers alone
would solve it. Procurement can build a public reserve; a downstream input
shortage also requires reachable upstream supply.

Existing trusted checkpoints retain the repository’s strict source/runtime
validation. The food schema translates legacy inventory and missing agricultural
facts when a trusted state reaches the new model, records its assumptions, and
shows a legacy-outlook notice. This does not waive the checkpoint loader’s
cross-source compatibility rejection.

## Commit preparation verification — 2026-11-03

Review of an isolated copy of the staged files exposed two additional physical
inventory boundaries. Ordinary child relief now requires a complete ration in
local public stock. Imported market offers are capped by the whole units still
present in the trader's cargo or parked stock when each offer settles, including
when multiple offers draw on the same wallet. These guards prevent overdrafts;
they do not create replacement grain or change the archived campaign outcomes.
Regression tests cover fractional public stocks and duplicate import offers.

Older integration fixtures were aligned with household career inertia, dated
harvest receipts, the explicit agricultural calendar, and corporate identity
after business closure. The staged snapshot passes 224 focused tests and 107
shorter integration tests. The separate 30-turn default-world regression also
passes. Five checkpoint tests passed during commit preparation before these
two inventory guards; browser and long campaign evidence above remains the
dated release evidence, rather than a rerun of every campaign for this commit.
