# Corporations and lords over 100 turns

**Decision quality is not consistently good.** Most commercial company entities
are not operating, the experimental planner barely runs, and its one intervention
in this campaign coordinates inputs and staffing badly. Lords have mixed outcomes:
some estate entities retain substantial wealth from rent/tribute, while eight of
the nineteen original lord actors die. Financial success here is not proof of
successful planning.

## Run and comparison

Both campaigns reached turn 100: seed/terrain/nation seed 4243, normal 81-tile hex
world, three nations, all 46 gameplay flags enabled, standard national autoplay
off. The experimental production planner is active in one run and off in the
comparison; the existing elite policies run in both. No opening endowments,
recipes, actors or cash were edited to manufacture opportunities. The world
starts with nineteen lords and no corporations.

The native recorder was off for practicality. Read-only wrappers retained actual
elite decisions, source economic events and complete-turn actor observations.
Each run used a fresh process, took approximately sixteen minutes and reported
unchanged source. The audit source is `f6cbaa8`; gameplay remains the preceding
`77d3211` implementation. Initial tracked actors match exactly, and the first
recorded elite-state difference occurs at turn 45. Later paths diverge; this is
one illustrative seed, not a statistical estimate of the experiment's effect.

[summary.json](summary.json) contains the extracted figures, configuration,
examples, input checksums and raw file locations. Raw observations remain under
`/private/tmp/elite-100-active` and `/private/tmp/elite-100-off`.

## Operating outcomes

| End-of-turn-100 measure | Planner active | Planner off |
| --- | ---: | ---: |
| Commercial corporation entities | 249 | 252 |
| With employees | 30 | 29 |
| Produced anything during turns 91–100 | 14 | 20 |
| Original lord actors still alive/present | 11 / 19 | 16 / 19 |
| Of those survivors, also marked as corporations | 7 | 7 |
| Total human residents | 1,443 | 1,418 |

Commercial excludes lord/corporation hybrids. There are another seven such estate
entities in each run. Company records remain legal entities after business
closure, so entity presence is not a business-survival statistic; closure flags
were not collected. Actual production is the stronger operating measure. Some
firms are agricultural and employment/harvest timing differs from factory work.
These qualifications do not change the finding that most company records are not
currently producing.

Commercial firms' active-run liquid positions, in each model currency separately:

| Currency | Cash | Bank principal | Cash + deposits − bank principal |
| --- | ---: | ---: | ---: |
| CNY | 3,504.22 | 5,923.60 | −2,419.38 |
| JPY | 6,202.06 | 10,391.81 | −4,189.75 |
| USD | 2,482.75 | 7,603.71 | −5,120.96 |

These figures exclude inventory, property, equity, foreign wallets and scrip
obligations; they are **not net worth or insolvency findings**. Positive balances
at the estate/corporation hybrids otherwise mask much of this funding weakness.
The three currencies are never summed or treated as interchangeable.

## What the new planner actually did

There were 2,902 requests reaching its search integration:

- 2,679 returned `world_budget_exhausted` before search.
- 213 rejected unsupported production/financing contexts.
- 9 rejected unsupported workforce/crop contexts.
- One actually expanded states: corporation 1768 on turn 45, using its full
  200-state allowance and returning a best-known candidate with status
  `budget_exhausted` and reason `higher_terminal_value`.

No `PRODUCTION_PLAN` was executed. The caller selected `DECLINE_INPUT` instead,
via the separate `nonpositive_material_contribution` hold rule. The observer did
not capture that returned candidate's complete valuation, so foregone profit
cannot be quantified. It does expose a conflict between the multi-step search
result and the one-period hold heuristic.

The allocator in [elite_plan_execution.py](../../../economy/elite_plan_execution.py)
reserves 200-state shares in advance for corporation IDs, including unsupported,
unstaffed and not-currently-planning firms. Unused reservations are not reassigned
to the requests that actually reach the stage. Only 200 states were expanded in
all 100 turns, despite the nominal 2,000-state world allowance per turn. Thus most
budget rejections are reservation failures, not evidence of computational load.
The eligibility/cadence interaction also needs a fairness test against actual
requesting firms rather than the allocator's roster alone.

## Concrete decision examples

### Decline inputs but keep hiring and paying

At turn 45, furniture company **1768**, owned by actor 195 in `r0c4`, had 169.16 USD,
five workers, a nominal 10.60 payroll and no wood for its next batch. Active mode
chose `DECLINE_INPUT`; the ordinary policy chose `REDUCE_OR_PAUSE_OUTPUT` and
released the existing workers. Other owner/hiring decisions then continued in
both runs.

Across turns 45–50, the active firm paid **46.74 USD cash wages and produced zero**.
The same firm in the off run paid **15.56 USD and produced four units**. The active
firm ended turn 50 with 12.76 cash versus 29.44 in off mode. Those cash changes
also contain transfers and other expenses, so the entire difference is not
attributed to wages. The observable coordination failure is that input refusal
is not integrated with staffing, owner expansion and pause decisions.

### Sell materials needed for current work

On turn 35, furniture company **1554** in `r6c1` held six wood units, had one worker
and needed two units for a nominal round. With 99.59 CNY cash and a nominal 1.98
payroll, it liquidated **all six wood units for 11.21 CNY**. Its input gap rose
from zero to two. There were seven active-run commercial decisions liquidating
an input while staffed and worsening the nominal shortage.

This is a warning, not proof every liquidation loses money: high input prices
can justify selling stock. But the liquidation rule in
[elite_liquidation.py](../../../economy/elite_liquidation.py) does not reserve
productive inputs or evaluate a sell/rebuy plan. More seriously, it transfers
goods to the first live buyer who can afford them, without checking buyer demand
or consent to that particular purchase. Such receipts cannot establish smart
market-demand forecasting.

### Keep injecting capital into dormant targets

There were 108 expansion injections into companies at least five turns old that
had no employees and no recorded production during the preceding five turns.
106 have five-turn follow-up; **77 had no staff at that endpoint and no
recorded output in the follow-up interval**. These are decisions, not 108 distinct companies.

For example, company 965 received another 50 USD at turn 15 and still had no
staff or output through turn 20. The expansion policy raises the wage and worker
cap automatically; it does not establish whether the bottleneck is staffing,
inputs, demand or an unprofitable recipe. Seasonal enterprises can legitimately
wait for output, so the counts are an operational warning rather than a measured
loss on every injection.

## Lords

The nineteen initial lord actors split into twelve ordinary lord actors and seven
estate/syndicate actors also flagged as corporations. At turn 100, four ordinary
lords and all seven hybrid estate entities remain alive/present in active mode;
nine ordinary lords plus the same seven hybrids remain in the off run. Death
causes were not captured, and this difference should not be attributed wholly to
the experimental policy from one path-dependent seed.

The initial lord cohort receives approximately **12,701.56 CNY and 12,187.72 JPY
in gross rent** during the active run, plus in-kind tribute and sales. No USD rent
is recorded, although the USD lords receive substantial tribute. Some estate
entities accumulate cash and deposits; these protected income streams and
institutional role changes are not demonstrations of better planning. We did not
value land, tenancy claims or family/company equity.

Their discretionary actions include converting actual wool to cloth, liquidating
stock and petitioning labor law. Material transformations consume their declared
inputs, which is mechanically sound. The same forced-buyer liquidation problem
still undermines the interpretation of their sales as good commercial decisions.
The available evidence does not justify calling the lords uniformly successful:
eight original actors die and wealth is unevenly concentrated among survivors.

## Confidence and next priorities

No world-level currency violation was reported. However, the active campaign has
**106 nonzero actor cash-statement residuals out of 19,672 statements**, the largest
453 units; off mode has 96 out of 19,835. There are therefore existing posting or
statement-boundary gaps, and this report makes no fully reconciled profit claim.
Company scrip payroll also remains separate from cash wages and bank principal.

The strongest conclusions concern directly observed actions and physical activity:
poor planner access, almost no multi-step execution, uncoordinated input/staffing
choices, unchecked liquidation demand and repeated expansion without operating
response. Fix those before treating nominal wealth as evidence of intelligent AI.
Priority order: allocate work to actual supported requests; unify search and hold
valuation; couple purchasing with staffing/pause; require a real buyer/order for
liquidation; make expansion depend on a measured bottleneck and expected return.

Reproduce each campaign in a fresh process:

```sh
PYTHONPATH=. MPLCONFIGDIR=/private/tmp/engineering-mpl SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
venv/bin/python scripts/audit_elite_long_run.py --mode active --turns 100 --seed 4243 --output /private/tmp/elite-100-active
# Repeat with --mode off and a different output directory.
python3 scripts/analyze_elite_long_run.py --active /private/tmp/elite-100-active \
  --off /private/tmp/elite-100-off --output planning/reports/elite_100_turn_20261112/summary.json
```

Use a fresh output directory for each run. This worktree's interpreter is
`/Users/sli/Code/venv/bin/python`. No gameplay rules were changed for the audit;
the experiment remains off by default outside the explicitly active campaign.
