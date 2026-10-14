# Generic Scenario Framework & Template Interpreter

This folder contains the generic scenario engine and modular simulation dynamics designed to orchestrate historical and hypothetical economic crises in **SimpleEconSim / Call of Capital**.

---

## 1. Architecture Overview

```
                                  ┌───────────────────────────────┐
                                  │   Scenario Specification      │
                                  │   (*.scenario.json)           │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │      ScenarioInterpreter      │
                                  │   (scenarios/interpreter.py)  │
                                  └───────┬───────────────┬───────┘
                                          │               │
            ┌─────────────────────────────┼───────────────┼────────────────────────────┐
            ▼                             ▼               ▼                            ▼
    ┌───────────────┐             ┌───────────────┐ ┌───────────────┐          ┌───────────────┐
    │  Obligations  │             │   Coercion    │ │   Domestic    │          │   Resource    │
    │   & Claims    │             │  & Gunboats   │ │   Politics    │          │  & Logistics  │
    ├───────────────┤             ├───────────────┤ ├───────────────┤          ├───────────────┤
    │ modules/debt  │             │modules/coercion│ │modules/politics│         │modules/relief │
    │ Sovereign     │             │ Naval forces  │ │ Factions      │          │ Reserve stocks│
    │ Bonds, Caisse │             │ Ultimatums    │ │ Morale/Loyalty│          │ Retention     │
    │ Intercepts,   │             │ Blockades     │ │ Legitimacy    │          │ Export bans   │
    │ Debt windows  │             │ Bombardments  │ │ Coups/Cabinets│          │ Calorie shocks│
    └───────────────┘             └───────────────┘ └───────────────┘          └───────────────┘
```

---

## 2. Directory Structure

- [`schema.py`](schema.py): Data models (`ScenarioSpec`, `ActionSpec`, `ReactionSpec`) and schema validation for `coc.scenario.v2`.
- [`evaluator.py`](evaluator.py): AST-based sandboxed expression evaluator for preconditions, metrics, and triggers.
- [`effects.py`](effects.py): Effect dispatcher enforcing **strict conservation of cash and physical goods** while adjusting macro metrics.
- [`interpreter.py`](interpreter.py): The `ScenarioInterpreter` engine managing role bindings, turn stepping, action execution, delayed reactions, modals, and debrief classification.
- [`modules/`](modules/): Reusable simulation dynamic sub-systems:
  - [`modules/debt.py`](modules/debt.py): Sovereign bond obligations, revenue intercepts, and payment windows.
  - [`modules/coercion.py`](modules/coercion.py): Gunboat diplomacy, force ratios, blockades, and ultimatums.
  - [`modules/politics.py`](modules/politics.py): Factions, cabinet transitions, and translating granular agent protest energy into nation unrest.
  - [`modules/relief.py`](modules/relief.py): Public grain stocks, food distribution to hungry households, and harvest shocks.
- [`templates/`](templates/):
  - [`templates/egypt_1877.scenario.json`](templates/egypt_1877.scenario.json): Declarative scenario spec for Egypt's 1877 crisis.
  - [`templates/venezuela_1902.scenario.json`](templates/venezuela_1902.scenario.json): Declarative scenario spec for the 1902 Venezuela naval blockade and debt arbitration.
- [`test_interpreter.py`](test_interpreter.py): Unit test suite verifying loading, AST evaluation, cash conservation, branch reaction modals, and multi-scenario runs.

---

## 3. How to Orchestrate a Scenario with `ScenarioInterpreter`

```python
from scenarios import ScenarioInterpreter

# 1. Load declarative scenario spec
interpreter = ScenarioInterpreter.from_file('scenarios/templates/egypt_1877.scenario.json')

# 2. Initialize scenario state and bind roles ($player, $creditor_1, etc.)
interpreter.initialize_scenario(world)

# 3. Discover available actions
actions = interpreter.get_available_actions(world)

# 4. Apply a player decision (deducts costs, applies effects, queues delayed reaction)
ok, feedback = interpreter.apply_action(world, 'release_maize')

# 5. Advance turn lifecycle (steps dynamic modules, evaluates reactions, triggers modals)
interpreter.advance_turn(world, turn, ticker_push)

# 6. If an interactive modal is queued (e.g. creditor reaction or ultimatum):
if world.get('scenario_warning_modal'):
    interpreter.resolve_reaction_response(world, 'defend_food_priority')
```

---

## 4. Authoring a New Scenario in JSON

To create a new scenario, create a `*.scenario.json` file in `scenarios/templates/` with:
1. `meta`: Title, year, horizon turns, briefing, actor list.
2. `roles`: Map semantic roles (`$player`, `$creditor_1`, `$capital`, `$port`) to names or criteria.
3. `modules`: Configure parameters for `debt`, `naval_coercion`, `politics`, and `relief`.
4. `pressures`: Define the 3 headline metrics displayed in the HUD.
5. `actions`: Define player decisions with `precondition`, `requires_cash`, and `effects`.
6. `branches`: Define delayed actor responses (`delay_turns`, `headline`, `responses`).
7. `outcomes`: Define declarative outcome predicates (`when: "payment_status == 'paid'"`) and debrief summaries.
