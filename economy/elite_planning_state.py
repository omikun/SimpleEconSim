"""Immutable, local-currency firm planning contracts; no live actor references."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningState:
    firm_id: int
    region: str
    currency: str
    turn: int
    phase: str
    input_good: str
    output_good: str
    cash: float
    inputs: float
    outputs: float
    payroll: float
    liabilities: float
    slots: int
    input_per_slot: float
    output_per_slot: float
    chance: float
    max_inventory: float
    input_price: float
    output_price: float
    supply: float
    demand: float
    baseline_quantity: int
    signature: tuple = ()
    due_schedule: tuple = ()
    demand_per_turn: float | None = None
    buyer_budget: float | None = None


@dataclass(frozen=True)
class PlanningGoal:
    kind: str
    minimum: float
    deadline: int
    deadline_phase: str = 'inputs'

    def satisfied(self, state):
        value = state.inputs if self.kind == 'input_stock' else state.cash
        on_time = (state.turn <= self.deadline if self.kind == 'input_stock'
                   else state.turn == self.deadline)
        return (on_time and state.phase == self.deadline_phase and value >= self.minimum
                and state.cash >= state.payroll + state.liabilities)


@dataclass(frozen=True)
class CandidateStep:
    quantity: int
    limit_price: float
    turn: int


@dataclass(frozen=True)
class SearchResult:
    status: str
    steps: tuple
    baseline_value: float
    candidate_value: float
    expanded: int
    reason: str


def derive_goal(state):
    missing = max(0, state.input_per_slot * state.slots - state.inputs)
    if missing <= 0 or state.slots <= 0:
        return None
    return PlanningGoal('input_stock', state.input_per_slot * state.slots, state.turn)


def _production_parameters(firm, region, turn):
    from goods import Goods
    from labor_contract import preview_labor_agreement, calculate_work_effort
    from region_production import terrain_bonus
    from work_allocation import main_work, available_work
    from economy.production_math import production_per_slot
    from abundance import enabled, proficiency
    from engineering import production_work_share
    recipe = region.recipes.get(getattr(firm, 'output', None), {})
    good, output = recipe.get('input'), getattr(firm, 'output', None)
    if (not getattr(firm, 'is_corporation', False) or not getattr(firm, 'alive', True)
            or output in (Goods.food, Goods.prepared_food, Goods.wood, Goods.cotton, Goods.sugar, Goods.tobacco)
            or not isinstance(good, Goods) or good in (Goods.food, Goods.prepared_food)
            or recipe.get('numInput', 0) <= 0 or recipe.get('production', 0) <= 0
            or (enabled(region) and recipe.get('setup_good'))
            or getattr(firm, 'loans', ()) or getattr(firm, 'pay_mode', 'cash') != 'cash'
            or any(c.get('lender_id') == firm.id and c.get('status') == 'active'
                   for c in getattr(region, 'offtake_contracts', ()))):
        raise ValueError('unsupported_production_or_financing')
    workers = [w for w in firm.employees if getattr(w, 'alive', True)
               and not w.is_striking and not w.in_revolt
               and w.id not in getattr(region, 'pollution_revolt_ids', ())]
    participant_ids = {firm.id, *(w.id for w in workers)}
    if not workers or any(f.get('operator_id') in participant_ids or f.get('employer_id') == firm.id
                          for f in getattr(region, 'farms', {}).values()):
        raise ValueError('unsupported_workforce_or_crop_work')
    efforts = []
    for worker in workers:
        agreement = preview_labor_agreement(worker, firm, turn)
        work = main_work(region, worker, turn, default=max(0, available_work(region, worker, turn)
                                                        - production_work_share(worker, turn)))
        efforts.append(calculate_work_effort(agreement.hours, agreement.pace, 1,
                                           getattr(worker, 'work_fatigue', 0)) * work)
    machinery = max(0, getattr(firm, 'machinery_level', 1) - getattr(firm, 'broken_machinery', 0))
    practice = sum(proficiency(w, output) for w in workers) / len(workers) if enabled(region) else 1
    units = production_per_slot(recipe['production'], len(workers),
        terrain_bonus(region, output, producer=firm), sum(efforts) / len(efforts), practice, machinery)
    if units <= 0:
        raise ValueError('no_productive_work')
    payroll = sum(max(0, preview_labor_agreement(w, firm, turn).pay_rate) for w in workers)
    return recipe, good, output, len(workers), units, payroll


def _market_parameters(firm, region, turn, recipe, good, output):
    from economy.market_math import ask_terms
    ref = float(region.recipes[good]['price'])
    if ref <= 0:
        raise ValueError('invalid_input_quote')
    suppliers = [a for a in region.agents if a is not firm and getattr(a, 'alive', True)
                 and not getattr(a, 'is_trader', False) and a.output == good and a.inv_get(good, 0) > 0]
    supply = sum(a.inv_get(good, 0) for a in suppliers)
    asks = [ask_terms(ref, a.inv_get(good, 0), region.recipes[good]['maxinv'],
                     a.hungry_steps, region.ASK_URGENCY_MIN, region.ASK_URGENCY_MAX)[0] for a in suppliers]
    input_price = max([ref, *asks])
    output_price = float(recipe['price']) * region.ASK_URGENCY_MIN
    if output_price <= 0:
        raise ValueError('invalid_output_quote')
    # One recent turn's realized demand, capped by the same buyers' present cash.
    recent = [e for e in getattr(region, 'economic_events', ()) if e['kind'] == 'spot_sale'
              and e['good'] == output.name and turn - 4 <= e['turn'] < turn]
    latest = max((e['turn'] for e in recent), default=-1)
    buyers = {a.id: a for a in region.agents if a is not firm and getattr(a, 'alive', True)}
    quantities = {}
    for event in recent:
        if event['turn'] == latest:
            ident = event['payer_id']
            quantities[ident] = quantities.get(ident, 0) + event['quantity']
    demand = sum(min(q, max(0, buyers[i].cash) // output_price)
                 for i, q in quantities.items() if i in buyers) if output_price > 0 else 0
    budget = sum(max(0, buyers[i].cash) for i in quantities if i in buyers)
    return input_price, output_price, supply, demand, budget


def capture_planning_state(firm, region, turn, settings=None):
    """Read supported firms only; historical fills are estimates, never assets."""
    recipe, good, output, slots, units, payroll = _production_parameters(firm, region, turn)
    input_price, output_price, supply, demand, buyer_budget = _market_parameters(firm, region, turn, recipe, good, output)
    from economy.elite_plan_orders import current_signature, cash_reserve, scheduled_obligations
    liabilities = max(0, cash_reserve(firm, region) - payroll)
    due_schedule = scheduled_obligations(firm, region, turn)
    arrears = max(0, float(getattr(firm, 'wage_arrears_balance', 0)))
    if arrears:
        due_schedule += ((turn, arrears),)
    signature = current_signature(firm, region)
    return PlanningState(firm.id, region.name, region.home_currency, turn, 'opening',
        good.name, output.name, float(firm.cash), firm.inv_get(good, 0), firm.inv_get(output, 0),
        payroll, liabilities, slots, recipe['numInput'],
        units, 1 / (1 + max(0, firm.hungry_steps) * .2),
        recipe['maxinv'] * (1 + len(firm.employees)), input_price, output_price, supply, demand,
        int(max(0, recipe['numInput'] * 2 * (1 + len(firm.employees)) - firm.inv_get(good, 0))),
        signature, due_schedule, demand, buyer_budget)
