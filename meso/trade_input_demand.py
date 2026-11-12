"""Funded producer input requests used to rank profitable trade routes."""

from goods import Goods


def input_requests(destination, good, price, *, trace=False):
    """Return requested units plus optional trace diagnostics and producer rows."""
    requested = 0
    requesters = [] if trace else None
    demand_diagnostics = ({'eligible_corporation_count': 0,
                           'eligible_independent_count': 0,
                           'zero_shortfall_count': 0,
                           'cash_limited_below_one_unit_count': 0}
                          if trace else None)
    from world_config import gameplay_flags_for
    allow_independent_requests = gameplay_flags_for(
        destination).independent_input_requests
    for company in getattr(destination, 'agents', ()):
        corporate = getattr(company, 'is_corporation', False)
        independent = (
            allow_independent_requests
            and not corporate
            and not getattr(company, 'is_government', False)
            and not getattr(company, 'is_trader', False)
            and not getattr(company, 'military_unit_id', None)
            and getattr(company, 'employer', None) is None
            and not (getattr(company, 'is_native_child', False)
                     and company.age(getattr(destination, '_last_turn', 0)) < 14))
        if not getattr(company, 'alive', True) or not (corporate or independent):
            continue
        recipe = destination.recipes.get(company.output, {})
        if recipe.get('input') != good:
            continue
        workforce = 1 + len(getattr(company, 'employees', ())) if corporate else 1
        target = float(recipe.get('numInput', 0)) * 2 * workforce
        shortfall = max(0.0, target - company.inv_get(good, 0))
        food_cash_reserve = 0.0
        if independent:
            from nutrition import appetite_units
            food_gap = max(0, appetite_units(company) - company.inv_get(Goods.food, 0))
            food_cash_reserve = food_gap * destination.recipes.get(Goods.food, {}).get('price', 1.0)
        spendable = max(0.0, company.cash - food_cash_reserve)
        affordable = (spendable / max(0.05, price)
                      if price > 0 else 0.0)
        requested_units = int(min(shortfall, affordable))
        requested += requested_units
        if trace:
            demand_diagnostics['eligible_corporation_count' if corporate
                               else 'eligible_independent_count'] += 1
            if shortfall <= 0:
                demand_diagnostics['zero_shortfall_count'] += 1
            elif requested_units <= 0:
                demand_diagnostics[
                    'cash_limited_below_one_unit_count'] += 1
            if requested_units > 0:
                requesters.append({
                    'producer_id': str(getattr(company, 'id', 'unknown')),
                    'producer_role': 'corporation' if corporate else 'independent',
                    'input_target': target,
                    'inventory': float(company.inv_get(good, 0)),
                    'shortfall': shortfall,
                    'cash': float(company.cash),
                    'food_cash_reserve': food_cash_reserve,
                    'spendable_cash': spendable,
                    'cash_affordable_units': affordable,
                    'requested_units': requested_units})
    return requested, demand_diagnostics, requesters
