# Food access repairs for the engineering campaigns

Date: 2026-10-30. Status: implemented; validation and remaining limitations linked below.

Implementation update (2026-10-30): the access repairs, fixture switches,
projections, and validation harness are implemented. See the
[acceptance report](reports/food_access_implementation_20261030.md) for tests,
18 campaign outcomes, and the unresolved collapse of farming in the responsive
labor stress case. The original plan below is preserved as the design record.

Evidence: [100-turn food-access investigation](reports/engineering_food_access_20261029.md).
This extends the existing [food security recovery implementation](food_security_recovery_implementation.md),
including its conserved emergency purchases, treasury funding, surplus levies,
and delayed provincial shipments. Those systems should be reused.

## Objective and design decisions

Make available food reachable through correct purchases, functioning employment
arrangements, and the relief policies actually selected. Productivity gains
must reach equipped farms and appear in food supply, but ownership, poverty,
seasonality, transport delays, and policy choices can still produce hunger.

- Separate a household's immediate meal, its desired reserve, and a business's
  food requirements. A company's employee count is not a household appetite.
- Use the existing nutrition model for age-dependent needs, appetite, and
  recovery. Do not hard-code every person to four units or lower physiological
  needs to conceal an access failure.
- Keep ordinary purchases price-based. Reserve demand must not reduce the
  same buyer's ability to purchase an affordable meal. Universal rationing or
  redistribution is a separate policy choice.
- Preserve named owners and conserved food/cash. Relief purchases spend actual
  budgets; compulsory collection uses the existing levy rule and grievance.
- Make ordinary and emergency relief behavior explicit. Player governments
  retain policy control; AI responses follow their existing authority.
- Keep the old authored frozen-wage campaign available as a stress case.
  Use a separately labeled responsive-economy case for the main technology
  experiment rather than silently changing what the control measures.

## 1. Correct affordable food orders

Primary files: `micro/region_market.py`, `micro/nutrition.py`,
`trace/price_trace.py`, and market trace producers.

1. Introduce one shared food-demand calculation returning immediate meal gap,
   reserve target, surplus, and affordable quantity. Count queued emergency
   meals and food already owned so a transfer does not trigger another order
   for the same need. Preserve dependent-household transfers and avoid counting
   a child's need in both a parent order and a separate funded child order.
2. Replace the output profession's recipe inventory limit with a household
   food target. Start with a configurable two-turn reserve above the current
   meal; treat that value as a tuning default, not a physiological constant.
   Wealth may affect existing appetite, but must not multiply an already
   affordable order into an unaffordable one.
3. Establish unit willingness to pay and spending limits before finalizing
   quantity. Reduce quantity to fit its budget. Protect the current meal's
   budget before adding reserve purchases or discretionary goods. If separate
   meal/reserve orders are needed, aggregate settlement by buyer and enforce
   one shared cash budget.
4. Preserve genuine below-ask rejection and competition for scarce food.
   A funded buyer can still lose to another buyer; an enlarged desired basket
   must not by itself make that buyer's smaller affordable meal impossible.
5. Trace demand components, reserved spending, submitted quantity and unit
   limit, filled units, and the actual reason an order remains unfilled.
   Version affected trace formulas and retain replay of older records.

Acceptance checks:

- Reproduce the recorded 197-cash/36-unit defect in an isolated market with
  enough stock. The buyer successfully purchases an affordable meal.
- Test partial purchasing with cash for only one or two units, plus true
  unaffordability, no stock, and below-ask willingness to pay.
- Changing a household's output profession alone does not change its food
  reserve target. Increasing desired reserves cannot reduce its funded meal
  order. Cash remains nonnegative across food and other goods.
- Extend `tests/test_market_auction.py`, food recovery tests, and trace replay
  checks with meaningful settlement cases.

## 2. Give business food stocks a purpose and a resale path

Primary files: `micro/region_market.py`, `micro/region_finance.py`,
`micro/labor_contract.py`, `economy/actor_accounts.py`.

1. Classify business demand as recipe inputs, contracted employee meals,
   company-store demand, or trading inventory. Nonfood firms with none of
   those purposes submit no household-style food demand.
2. Size company-store procurement from living workers' expected purchases and
   a bounded operating reserve. Keep food used as a production input covered
   by the input replenishment rule; do not bid twice for the same requirement.
3. Allow companies to sell surplus above their actual operating commitments.
   Employee departures and firm closure reduce those commitments and expose
   released stocks for sale. Existing saved inventories remain owned goods.
4. Let households offer excess food above their meal and chosen reserve,
   including employees. Protect quantities committed to dependents, and avoid
   a same-turn buy/sell loop in the same household's order book.
5. Add a normal cash purchase path at company stores. Preserve existing scrip
   tender, disclosed markup, and company-debt accounting. Optional advances
   should size against a meal gap and a bounded credit agreement; they must
   not become unlimited free employer food.

Acceptance checks:

- A firm with no food business or meal commitments does not accumulate food
  merely because it has employees or a large output inventory limit.
- A worker can spend cash on available company food; cash/scrip/debt payments
  reconcile with one physical transfer and no duplicate redemption.
- A firm losing its last employee offers surplus stocks. A food-input firm
  retains its required inputs. Producer and dependent meal reserves remain
  protected.
- Extend `tests/test_truck_system_and_scrip.py` and market/conservation tests.

## 3. Repair access between payday and consumption

Primary files: `micro/region/stepper.py`, `micro/region_market.py`,
`micro/region_finance.py`, `economy/econsim_live.py`, `agents/charity.py`.

1. Preserve the main market and its firm sales revenue, then add a bounded
   food-only purchase opportunity after payroll and company-store settlement.
   Newly paid workers can buy from remaining or newly offered stocks before
   eating. Do not repeat the whole borrowing, repayment, tax, donation, or
   nonfood trading pipeline.
2. Recompute the remaining meal gaps, available cash, and actual seller stock
   for that opportunity. Reconcile both food settlements in the turn's sale
   totals and update the reference-price rule once from their combined
   evidence; do not apply inflation twice because two settlements occurred.
3. Submit ordinary funded government/charity procurement through a functioning
   food purchasing path, with explicit institutional budgets and limits.
   They must be able to buy eligible corporate surplus, rather than only
   leftover farmer stock. Preserve policy restrictions on emergency collection.
4. Deliver government and charity food after purchasing and before dependent
   transfers, consumption, and mortality. Retain exactly one daily nutrition
   assessment and one mortality assessment. Ensure legacy regional and shared
   provincial charity paths do not distribute twice or give inconsistent timing.
5. Base emergency food-credit eligibility on actual access to production and
   employment. Keeping food-growing skills or `output=food` must not classify
   an employed factory worker as self-feeding.

Acceptance checks:

- The recorded cash-before-market/payday/store-threshold case gets an actual
  opportunity to purchase an affordable unit after being paid when stock is
  offered. No guarantee is made when cash or stock is insufficient.
- Same-turn charitable food affects intake before the death assessment;
  insufficient aid still leaves a measurable calorie deficit.
- No double payroll, interest, borrowing, donation collection, aid, consumption,
  or reference-price update. Test standalone regions and province-managed paths.
- Extend charity, food intake, government transfer, company store, and
  provincial food logistics tests; verify their causal traces.

## 4. Connect emergency granary release to actual distress

Primary files: `micro/region_production.py`, `micro/food_security.py`,
`macro/government.py`, `meso/food_logistics.py`.

1. Keep ordinary seasonal storage and release as a baseline policy. When an
   authorized emergency food policy is active, permit additional release on
   any turn, sized from the current funded/physically coverable meal gap,
   granary stock, and explicit handling capacity.
2. Count only stock that can actually be delivered before the meal. Compute
   the remaining gap after confirmed purchases and prior transfers, not a
   campaign average or all private inventories added together.
3. Release physical grain into the existing public food account and deliver
   through the established aid mechanism. Deduct the donor inventory once
   and record recipient transfers. Capacity should scale with population and
   handling resources rather than a permanent four-unit ceiling.
4. Reuse national funding and existing procurement/levy policies. A rich
   national treasury must transfer money before a local authority can spend
   it. Provincial transfers retain travel time and paid haulage.
5. Record why reserves remain unused: policy off, protected reserve,
   handling capacity, insufficient funds for procurement, or transit delay.

Acceptance checks:

- With emergency policy enabled, an accessible stocked granary can respond
  to hungry residents outside the ordinary release season.
- Policy-off ordinary behavior remains a valid scenario. Empty stores,
  limited handling capacity, and delayed shipments still constrain relief.
- Every release matches granary debit, public receipt, and subsequent meal
  transfers. Extend `tests/test_granary_stock_flow.py`,
  `tests/test_granary_relief_trace.py`, and food recovery tests.

## 5. Make the technology comparison interpretable

Primary files: `scripts/audit_engineering_campaigns.py`,
`scripts/inspect_engineering_food.py`, `economy/technology_adoption.py`,
and engineering acceptance tests.

1. Expose and record fixture settings for wage/owner behavior, relief policy,
   national AI, and private versus regional steam scope. Preserve archived
   baseline results; use new report names for changed rules.
2. Retain frozen-wage/no-emergency-relief cases as explicit stress tests.
   Add a responsive-economy case with normal wage adjustment and lawful labor
   mobility. Add an explicitly authorized automatic-relief case rather than
   silently enabling emergency policy in every comparison.
3. Keep private adoption ownership-specific. To test steam's effect on farming,
   use the existing regional pilot or a paid farm-owned installation. Record
   cost, completion, ownership, generation, and actual operating use.
4. Add a controlled production comparison with fixed workers, land, weather,
   inputs, and installed equipment as the variable. Then compare whole-campaign
   outcomes, where deaths and births can change labor and food demand.

Acceptance checks:

- Installed steam raises the equipped farm's physical productivity under
  otherwise equal conditions. An uninstalled discovery gives no machine bonus.
- Normal wages may rise or remain unaffordable according to firm finances;
  no universal wage floor or guaranteed employment is introduced by this plan.
- Reports distinguish the mechanical repairs from wage, relief, and equipment
  policy choices. Population changes are shown beside total food output.

## 6. Present food access clearly and rerun acceptance

Primary files: existing food-security projections and web/desktop panels,
`trace/metric_catalog.py`, food/market trace producers and replay code,
and campaign reporting scripts.

Show food security as a small set of connected quantities:

- Food produced and foraged this turn versus residents' meal needs.
- Food offered for sale, household reserves, company stocks, public stocks,
  and food still in transit. Stored food is not automatically accessible food.
- People short of a meal, the cost of a meal, wages and spendable cash.
- Public/charitable food actually delivered and the remaining calorie gap.
- A plain-language explanation such as “Households cannot afford meals,”
  “Food held in company stocks,” “Emergency release disabled,” or “Food in transit.”

Keep all transfers inspectable through the existing causal trace, including
who sold or released food, who paid, who received it, and what remained blocked.
Version changed formulas so historical replay still works. Confirm browser
and desktop presentation use the same quantities.

Validation sequence:

1. Before each implementation stage, retain its source signature and the
   preceding stage's evidence. Add focused regression tests for that stage's
   actual failure and conservation boundaries.
2. Run the 100-turn commercial, regional steam pilot, and control cases at
   seed 4243 after the market, timing/relief, and final fixture stages. Separate
   cumulative repair effects from alternate policies. Keep the original
   diagnosis as evidence, not a snapshot that new gameplay must match.
3. At final acceptance, repeat the meaningful scenario comparisons with seeds
   4242 and 4244. Use a fixed hash seed and record scenario options/source
   signatures so reruns are reproducible.
4. Run the existing default-world and multi-region food-security regressions
   to catch spillovers beyond the engineering fixture, including provincial
   shipment and legacy regional turn ordering.
5. Compare per-person intake, deficit severity, reserves, actual filled food
   orders, wages/meal costs, food ownership, aid deliveries, starvation deaths,
   and production. Require zero unexplained cash or goods discrepancies and
   valid causal replay for affected flows.

Success means the diagnosed purchasing and sequencing defects cannot recur,
available surplus has a functioning lawful route to buyers or authorized
relief, and equipped farms show their productivity gain. Whole campaigns may
still exhibit poverty or famine; remaining deaths must have inspectable supply,
affordability, ownership, policy, or transport causes. Zero starvation is not
an unconditional acceptance target.

## Delivery order

Implement and review stages 1–2 first. Follow with stage 3 timing and stage 4
emergency release; these depend on correct stock and budget accounting.
Then complete the scenario comparisons and player-facing explanations in
stages 5–6. Each stage should leave runnable evidence and a clearly scoped
change, so any improvement or regression has a traceable cause.
