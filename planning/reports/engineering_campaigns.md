# Commercial deployment and engineering acceptance

Recorded 2026-10-28. All runs use seed 4243 and 100 canonical game turns. Each
strategy was repeated in a fresh process and its JSON output matched byte for
byte. No sales, production, learning or recurring income were injected.

| Strategy | Final capability | Public engineering spend | Private engineering spend | Tracked factory installation spend | Tracked factory steam design |
|---|---:|---:|---:|---:|---|
| Commercial pioneer | 38.24 / tier 2 | 0 | 116.66 | 800.00 | Tier 1 |
| Public engineering challenger | 68.22 / tier 3 | 1,146.11 | 0 | 1,116.82 | Tier 2 |
| Weak demand | 1.00 / tier 1 | 0 | 0 | 0 | None |
| Control without autonomous adoption | 1.00 / tier 1 | 0 | 0 | 0 | None |

All four runs reported zero currency-audit violations. This is the engine's
existing audit, with its five-unit reporting threshold; dedicated construction
tests additionally check exact cash conservation and physical inventory use.

The commercial firm commissioned tier-1 equipment on turn 11. Productive use
and paid private engineering reached tier 2 on turn 55. The old installation
remained tier 1, demonstrating that learning does not upgrade equipment for free.
Its generation-1 manufacturing maturity reached 47.77%. New tier-2 designs
inherited only 16.72% maturity.

The public strategy began without steam knowledge, demonstrated a prototype on
turn 10, reached tier 2 on turn 15 and tier 3 on turn 64. Its firm independently
funded an installation on turn 11 and a 316.82 retrofit on turn 17. The final
equipment remained tier 2 although national capability was tier 3. Current
tier-3 maturity was 7.96%; further public work was constrained by iron supplies.

The weak-demand firm had enough opening capital to afford an installation but
never commissioned one. On turn 20, its estimated payback was 34.65 turns and
discounted return was negative. Idle knowledge remained at tier 1 without
manufacturing maturity or free refinement.

## Test conditions and limits

These are authored strategy checks, not identical-economy causal comparisons.
Commercial/public worlds start with 75 households and 250 cash per household;
weak demand starts with 18 and 40 respectively. Firms begin with the same 2,500
capital and four employees. The land is commons, forestry is deliberately
abundant, and suppliers have finite opening physical stock. The ordinary
production, labor, consumption, market, finance and innovation phases run.
Unrelated elite planning is disabled by the scenario's owner policy; autonomous
technology investment is explicitly enabled. Public funding is renewed at each
performance milestone, up to a ceiling of 100 per turn, with actual spending
limited by labor, supplies and treasury cash.

All three tracked strategy firms lost their remaining employees by turn 100, and hunger
remained present. The control without adoption also lost its workforce and
ceased being a corporation. This supports investigating broader workforce and
economic stability; it does not establish the cause. The runs validate the
technology decision paths and their different outcomes, not balanced long-run
prosperity. Estimates of future returns remain conditional on recent sales.

## Follow-up: national economy and workforce diagnosis

A read-only replay now records all 101 turn boundaries, other firms' investments,
prices, births/deaths, health, pollution, politics, banking and actual staffing
changes. All four replays match the original acceptance snapshots exactly after
JSON normalization. See [the detailed account](engineering_campaign_narrative.md).

The table above follows the originally named factory, not all national capital
spending. Another furniture firm installed steam equipment on turn 16. Total
private installation/retrofit spending was **1,570.50 commercial** and **1,909.65
public**. Both nations ended with two steam installations. The commercial
secondary firm still employed one worker on turn 100, allowing national learning
to continue after the tracked factory stopped. Both public installations were
tier 2, while the nation's blueprint capability was tier 3.

The replay establishes why the tracked factories lost staff: every departure was
a registered death, predominantly starvation. Unfilled positions were repeatedly
refused because the fixed 2.5 wage was below reservation wages. The authored
owner policy disables ordinary wage adjustment and elite planning; the nation
has no general policy AI. These restrictions materially limit what this test
establishes about the unrestricted game's long-run stability. Pollution-related
work withholding, disease, food-price inflation and repeated coups were also
active. None of these runs establishes that technology alone sustains prosperity.

## Reproduction

Run each variant in a fresh process because engine registries are process-global:

```sh
venv/bin/python scripts/audit_engineering_campaigns.py --variant commercial --output /tmp/commercial.json
venv/bin/python scripts/audit_engineering_campaigns.py --variant public --output /tmp/public.json
venv/bin/python scripts/audit_engineering_campaigns.py --variant low_demand --output /tmp/low_demand.json
venv/bin/python scripts/audit_engineering_campaigns.py --variant control --output /tmp/control.json
```

The saved report files contain turn-20/50/100 snapshots, investments,
capability milestones, local construction quotes and audit outcomes:

- [Commercial](engineering_commercial_seed4243_100.json)
- [Public](engineering_public_seed4243_100.json)
- [Weak demand](engineering_low_demand_seed4243_100.json)
- [Control](engineering_control_seed4243_100.json)

The focused regression command passed 87 tests, including private financing,
reserves, frozen credit, ownership, physical construction, upgrade cancellation,
duplicate prevention, traced decision estimates, engineering objectives and API
parity. Four full checkpoint tests passed separately. Desktop/mobile browser
checks cover previews, funding, stopping, operation-driven learning, constrained
spending and the private investment explanation.

The broader metric-catalog check currently fails on three existing, unregistered
pollution metrics: `politics.pollution_illness_rate`, `politics.pollution_petition`
and `politics.pollution_revolt`. New commercial and engineering metrics are
registered. This unrelated catalog gap is outside this change's acceptance.
