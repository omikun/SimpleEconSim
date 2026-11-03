# Career transitions with profession-level departure budgets

Date: 2026-10-31. Status: implemented and validated.
This replaces the earlier proposal for heterogeneous beliefs, social learning
and detailed transition frictions. Implementation and results: [acceptance report](reports/career_recovery_implementation_20261031.md).

## Core rule

Each profession in each region has a shared maximum number of voluntary
career departures per turn. The allowance rises when another profession is
more lucrative and falls as the source profession approaches its protected
minimum. Start with a configurable minimum of **four adult workers**.

For source profession A:

```text
surplus_workers = max(0, workers_at_turn_start[A] - minimum_workers)
gain = max(0, (best_feasible_new_return - current_return)
              / max(abs(current_return), normal_meal_cost, epsilon))
transition_rate = min(max_transition_rate, gain_sensitivity * gain)
allowance = surplus_workers * transition_rate + fractional_carry[A]
max_departures = min(surplus_workers, floor(allowance))
```

Initial tuning values:

- `minimum_workers = 4`
- `gain_sensitivity = 0.10`
- `max_transition_rate = 0.25`

Thus a 100% improvement, when the denominator is the current positive return,
permits 10% of workers above the protected minimum to depart that turn. A
250% improvement reaches the initial 25% maximum. These are game parameters,
not empirical constants, and remain configurable.

Use the existing consistent livelihood-return estimates, including food
retained for the household and necessary costs. Compare feasible alternatives
and funded offers; a posted selling price alone does not establish a return.
The source profession's most attractive feasible proposed move determines
its rate, and its strongest proposed moves receive the available slots first.
A source with no beneficial feasible move has no departures.

## Integer handling

Carry only the fractional remainder, always below one, into the next turn.
Unused whole departure slots expire; they cannot accumulate into a later
mass exodus. Reset the carry when there are no beneficial proposals or the
profession is at or below its minimum.

This matters for small professions: rounding every turn downward without
fractional carry would strand them above the chosen floor.

At a steady 10% rate and minimum four:

| Starting workers | Workers above minimum | Departure allowance |
| --- | ---: | --- |
| 50 | 46 | 4 this turn, with 0.6 carried forward |
| 10 | 6 | 0 this turn, with 0.6 carried forward |
| 5 | 1 | Approximately one departure after ten qualifying turns |
| 4 or fewer | 0 | No voluntary career departures |

The five-worker example assumes unchanged membership and rate throughout.

## Counting and enforcement

- Count living adult people by the profession of their actual work. For an
  employee, use the employer's production profession; for an independent
  worker, use the committed occupation. Exclude corporations, government
  entities and children carrying a default occupation label.
- Use a common pre-production decision/commit phase and one departure ledger.
  Hiring into another profession, independent career changes, and ordinary
  demographic switching all consume that source profession's budget.
- Changing employers within the same profession does not consume a departure
  slot. Quitting an employer while retaining the same profession does not
  itself constitute a profession change; it also does not grant a free second
  occupation change later in the turn.
- Freeze the budget's population basis at turn start. Arrivals do not refill
  that turn's allowance. Recheck live membership at commitment so voluntary
  changes cannot push the source below four after other events.
- Existing land, skill, input, cash, funded vacancy and legal requirements still
  apply. New professions can gain entrants even when they have fewer than four
  members; the minimum protects existing members from further voluntary exit.
- Death, closure, compulsory reassignment and physical displacement are separate
  events. They may reduce membership below four; this rule does not create
  replacement workers or make people immortal. Record such events separately
  from quota-controlled voluntary departures.

## Decision system

Keep a single career-decision path so the cap cannot be bypassed through a
second hiring or fallback subsystem. Every eligible adult can be considered,
including a person with cash but inadequate food. Use simple comparable returns
and existing feasibility checks, rank the proposed moves, then commit within
source budgets and destination capacities.

Remove the overlapping career mutations and the cash-based exclusion identified
in the mobility diagnosis. This simplified design does not require a new
personality model, information network, multi-period household optimizer or
special collection of emergency switching exceptions.

The hard protected minimum is an intentional gameplay rule requested by the
user. It replaces the earlier design's rejection of profession floors.

## Validation

- More lucrative feasible alternatives increase the source's allowed rate.
- Smaller source professions have fewer available departure slots.
- Voluntary exits stop at four, including attempts from all hiring/career paths.
- Fractional carry permits gradual movement down to four rather than locking
  a profession at seven or another accidental rounding threshold.
- Unused whole capacity never accumulates; arrivals cannot reset the budget.
- Adult work membership is counted consistently; children and firms cannot
  inflate the protected population.
- Failed job attachment or another failed commitment does not consume a slot.
- Save/restore preserves the current turn's ledger and fractional carry without
  resetting either. Seeded reruns remain reproducible.
- Rerun the existing three-seed campaign matrix, measuring adult farmers,
  departures, harvests, wages/prices, calories and deaths. Keep food access and
  stale-price repairs as separately inspectable mechanisms.
