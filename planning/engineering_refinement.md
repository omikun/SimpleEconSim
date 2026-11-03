# Operation, engineering and commercial maturity

Implemented 2026-10-27. Replaces the automatic refinement increments and fixed
state-subsidy XP multipliers in the original emergent-tech integration plan.

## Player decisions

The science tree shows capability (four tiers), commercial maturity of the current
design, operating installations and utilization. Engineering details let the player
preview a recurring budget, choose a host and a performance/economy/balanced
objective, then fund work until the next milestone. Stop cancels future public
spending without stopping industrial learning. The panel explains the current
staff, workshop, supply or supporting-technology constraint.

New construction quotes reflect manufacturing maturity. Pilot installations are
available for every discovered catalog technology. Existing installations retain
their commissioned design generation. A retrofit is a paid construction project;
the installation is offline until it completes. Adoption estimates use recent
production and prices and explicitly show **gross** output value and payback,
excluding changes to labor and input costs.

## Sources of progress

`macro/engineering.py` contains the common pure refinement rule, program lifecycle,
procurement and read-only forecasts. `InnovationSystem` delegates refinement to
this implementation. Production reports work performed and available capacity
against installed designs, with source production trace IDs. Neither owning a
blueprint nor maintaining an idle installation generates operational progress.

Routine learning scales with operating installations to the power 0.6, utilization
and supporting technical readiness. Capability difficulty grows with advancement
but never exhausts a lifetime learning allowance: sustained operation can reach
the next tier. High-performance applications require supporting technologies at
industrial-standard tier; loss of a prerequisite never erases existing knowledge.

An engineering/testing workshop supports three half-day artisan shifts per turn.
Existing guild workshops also qualify. Artisans must be living, independent,
skilled in a relevant craft, available and not on strike. They cannot be assigned
twice in one turn. Their reserved half day reduces ordinary production chances.
Repeated engineering develops expertise, capped at twice the initial effectiveness.
Supporting technologies also affect readiness.

Each delivered shift purchases a complete bundle of real inputs and pays a real
artisan. Experiment bundles use modeled wood, furniture, iron and coal as
appropriate. Imported inventory can substitute for domestic mineral/forest
deposits when developing a prototype. Deposits for resources without modeled
commodity equivalents remain catalog requirements. Budgets are spending ceilings;
unavailable labor, stock or treasury cash cannot purchase fictitious progress.

Firms using a technology can finance economy-focused engineering from a bounded
share of cash above payroll/input reserves. Public programs choose the allocation:
performance develops capability; economy develops manufacturing maturity; balanced
does both. Public experiments can demonstrate the first prototype without any
commercial installations. Existing organic discoveries and bounties remain.

## Design generations and costs

Maturity is recorded separately for each technology and design generation. Older
manufacturing knowledge transfers at 35% per generation gap. Repeated construction,
operation and economy-focused engineering develop the relevant generation.
The construction cost/material factor falls from 1.6 at zero maturity to 0.8 at
full maturity. Integer material quantities round up and never become zero.

Capability milestones are 1/25/60/90 XP. Those internal values remain for old
commands, espionage and trace compatibility; the UI uses capability names.
Legacy commercial/standard/crash commands now mean zero public funding, a 25-per-
turn balanced program, and a 100-per-turn performance program respectively.
They do not grant free refinement multipliers or reserve automatic bounties.

Programs remember their initial capability and design-cost targets, so crossing a
tier does not move the cost milestone to a different generation. Public funding
stops when the selected milestone(s) are met. Constraint changes, completed
programs, capability advances and mature manufacturing designs produce notices.

## Evidence and verification

Payments have paired account contracts and economic journal entries. Purchased
inputs have supplier inventory records and immediate consumption entries. Delivery
records identify paid workers, consumed supplies, spending and effective effort.
Refinement, prototype development and maturity have replayable calculations;
snapshots retain capability and generation-specific maturity. Simulation
checkpoints preserve the program and installed-design state through the existing
object graph.

The standalone tech simulator calls the same Python refinement rules through its
API, including for browser turn advancement. Its controlled scenario exposes
installation count, utilization, staff, experiment bundles and budget ceilings.
It uses a documented five-currency-unit bundle-plus-wage cost, whereas the live
game uses actual local prices and wages.

Forecasts are conditional projections using current operation, available workshop
staff/supplies, supporting capability and recent private engineering. They do not
predict future prices, firm entry, migration, public/private competition for staff,
or improved skills. Read-only program previews never spend money or advance XP.

Behavioral coverage: `tests/test_engineering.py`, `tests/test_tech_sim_server.py`,
science API tests in `tests/test_web_client_parity.py`, and the optional
`tests/test_engineering_browser.js` against disposable standard-game and simulator
servers. Existing construction, innovation trace, desktop interaction, trace,
state-coverage and checkpoint suites provide regression checks.

## Autonomous commercial deployment

Firms now compare paid installations, replacement and retrofits against eight
completed turns of actual production, settled sales and operating costs. Cash,
loans or unsold inventory do not count as demand. They evaluate opportunities
every three turns, retaining five turns of payroll, inputs and existing debt
payments plus a cash buffer. Accessible savings are used before new bank loans;
credit freezes, lending capacity, interest, debt service, risk tolerance and
upgrade downtime constrain the decision.

An accepted investment pays a real contractor from the firm's funds. Physical
materials and available construction workers are required. Private equipment
benefits its owner; public installations retain their existing regional scope.
New knowledge leaves existing machines unchanged. Replacement removes the old
asset, and a retrofit updates its installed generation after construction.
Cancelled upgrades restore the old equipment's operation. Only one investment
can be active per firm, and current equipment cannot be installed repeatedly to
stack the same design's bonus.

The science panels show each firm's dated decision, installed generation,
estimated cost, additional receipts, payback and construction constraints. These
are conditional estimates, not guaranteed profits. Decision traces retain the
market observations and economic inputs used in the comparison. Authored
scenarios with an owner policy preserve their existing behavior unless they
explicitly enable `commercial_technology_adoption`.

See [the 100-turn acceptance report](reports/engineering_campaigns.md) for live
campaign results and remaining economy-balancing limits. Commercial decision
coverage is in `tests/test_technology_adoption.py`; the replayable campaign entry
point is `scripts/audit_engineering_campaigns.py`.

## Production expansion, 2026-10-29

Steam now applies across production through installed equipment. Sixteen sector
technologies extend the catalog to 45 entries; all 17 domestically productive
professions have specific productivity routes. Sector output contributes domain
learning, and the science panels list the professions helped by each design.
Negative net soil-fertility changes now take ten times as long, with recovery
speed retained. See [the production-expansion report](reports/productivity_expansion_20261029.md)
for profession coverage, primary references, the revised four-case campaigns and
an additional paid regional steam-pilot experiment.
