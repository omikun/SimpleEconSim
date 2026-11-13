"""Pure market/production phase forecasts; forecasts never settle live assets."""
from dataclasses import replace
from math import comb
from economy.production_math import active_slots, output_units


def purchase(state, quantity, *, reserve=True):
    if quantity < 0 or quantity != int(quantity) or state.phase != 'opening':
        return None
    # Old stock can sell in this auction; new production cannot.
    sold = min(state.outputs, state.demand)
    if state.buyer_budget is not None:
        sold = min(sold, max(0, state.buyer_budget) / state.output_price)
    cash = state.cash + sold * state.output_price
    spent = quantity * state.input_price
    buffer = state.payroll + state.liabilities if reserve else 0
    # Input orders cannot spend proceeds from a later output clearing.
    if quantity > state.supply or spent > max(0, state.cash - buffer):
        return None
    return replace(state, phase='inputs', cash=cash - spent, inputs=state.inputs + quantity,
                   outputs=state.outputs - sold, supply=state.supply - quantity,
                   demand=state.demand - sold,
                   buyer_budget=None if state.buyer_budget is None else state.buyer_budget - sold * state.output_price)


def finish_turn(state, *, allow_unfunded=False):
    due = (sum(amount for turn, amount in state.due_schedule if turn <= state.turn)
           if state.due_schedule else state.liabilities)
    if state.phase != 'inputs' or (not allow_unfunded and state.cash < state.payroll + due):
        return None
    slots = active_slots(state.slots, state.inputs, state.input_per_slot)
    chance = min(1, max(0, state.chance * max(0, 1 - state.outputs / state.max_inventory)))
    expected = sum(comb(slots, k) * chance ** k * (1 - chance) ** (slots - k)
                   * output_units(k, state.output_per_slot) for k in range(slots + 1))
    # Match live production: failed/zero-output slots do not consume materials.
    used = sum(comb(slots, k) * chance ** k * (1 - chance) ** (slots - k)
               * k * state.input_per_slot for k in range(slots + 1)
               if output_units(k, state.output_per_slot) > 0)
    demand = state.demand if state.demand_per_turn is None else state.demand_per_turn
    if state.buyer_budget is not None:
        demand = min(demand, max(0, state.buyer_budget) / state.output_price)
    return replace(state, turn=state.turn + 1, phase='opening', inputs=state.inputs - used,
                   outputs=state.outputs + expected, cash=state.cash - state.payroll - due,
                   liabilities=max(0, state.liabilities - due),
                   due_schedule=tuple((t, amount) for t, amount in state.due_schedule if t > state.turn),
                   demand=demand)


def score_terminal(state):
    # Unsold output is valued only to the extent funded observed demand remains.
    return (state.cash + state.inputs * state.input_price
            + min(state.outputs, state.demand) * state.output_price - state.liabilities)


def baseline(state, turns):
    for _ in range(turns):
        quantity = int(min(state.supply, max(0, state.cash) // state.input_price,
                           max(0, state.input_per_slot * 2 * (1 + state.slots) - state.inputs)))
        state = purchase(state, quantity, reserve=False)
        state = finish_turn(state) if state is not None else None
        if state is None:
            return None
    return state


def idle_baseline(state, turns):
    """Normal work with no new inputs; negative cash denotes a financing deficit.

    This comparison is not an executable credit facility. Search successors
    always use the funded finish_turn path.
    """
    for _ in range(turns):
        state = finish_turn(purchase(state, 0), allow_unfunded=True)
    return state
