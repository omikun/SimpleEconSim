"""Finite regional commons food, gathered using the shared work budget."""
from goods import Goods
from food_inventory import milli

BASE_FORAGE_YIELD = 8


def commons_access(region):
    if getattr(region, 'wilderness', False):
        return 1.0
    return max(0, min(1, getattr(getattr(region, 'tenure', None), 'commons_access', 0)))


def can_forage(agent, region):
    from households import human
    from labor_choice import career_lifecycle_age
    rights = [r for r in getattr(region, 'access_rights', {}).get(agent.id, ())
              if r.resource == 'commons_food']
    usable = not rights or any(r.usable_share > 0 for r in rights)
    return (usable and human(agent) and career_lifecycle_age(agent, int(getattr(region, '_last_turn', 0))) >= 14
            and not getattr(agent, 'in_workhouse', False) and not getattr(agent, 'military_unit_id', None)
            and commons_access(region) > 0)


def capacity(region, turn=None):
    from agriculture import phase
    import math
    seasonal = max(.4, .8 + .2 * math.sin(2 * math.pi * phase(region, turn) / 10))
    background_use = getattr(region, 'wilderness_pop', 0) * 4 if getattr(region, 'wilderness', False) else 0
    return max(0, float(getattr(region, 'commons_capacity', 0)) - background_use) * commons_access(region) * seasonal


def potential(agent, region):
    from nutrition import basic_food_units
    if not can_forage(agent, region):
        return 0.0
    users = sum(can_forage(a, region) for a in region.agents)
    return min(basic_food_units(agent), capacity(region) / max(1, users), BASE_FORAGE_YIELD)


def forage_tile(region, t):
    from households import demand, buyer
    from food_accounts import create
    from work_allocation import begin, assign
    if getattr(region, '_commons_food_turn', None) == t:
        return getattr(region, 'food_foraged_this_turn', 0)
    region._commons_food_turn = t
    begin(region, t)
    if getattr(region, 'is_ocean', False) or getattr(region, 'elevation', 0) < 0:
        return 0
    maximum = max(0, float(getattr(region, 'commons_capacity', 0))) * 2
    stock = min(maximum, max(0, getattr(region, 'commons_food_stock', 0)) + capacity(region, t))
    total = 0.0
    # Most deprived households receive the first opportunity, not list shuffle.
    people = sorted((a for a in region.agents if can_forage(a, region) and buyer(a, region)),
                    key=lambda a: (a.energy_reserve_kcal, a.id))
    for person in people:
        need = demand(person, region, reserve_turns=0)['meal_gap']
        from work_allocation import remaining
        available_work = remaining(region, person)
        stock_before = stock
        work = assign(region, person, 'commons', min(need, stock) / BASE_FORAGE_YIELD)
        units = min(stock, milli(work * BASE_FORAGE_YIELD) / 1000)
        if units <= 0:
            continue
        create(region, person, units, kind='commons_gathering', work=work,
               capacity=capacity(region, t))
        stock -= units
        total += units
        person.food_foraged += units
        person.last_forage_turn = t
        person.temporary_work_share = work
        _record_activity(region, person, t, units, requested_food=need,
                         stock_before=stock_before, available_work=available_work)
    region.commons_food_stock = max(0, milli(stock) / 1000)
    region.food_foraged_this_turn = total
    return total


def _record_activity(region, agent, turn, food_units, *, requested_food,
                     stock_before, available_work):
    from run_trace import emit
    event_id = emit(region, kind='commons_foraging', record_class='outcome',
         subject={'type': 'agent', 'id': agent.id, 'tile': region.name},
         metric_id='labor.temporary_activity', unit='turn_share',
         after=agent.temporary_work_share,
         formula_id='commons.forage_activity.v2',
         inputs={'food_units': food_units, 'good': Goods.food.name,
                 'requested_food': requested_food, 'commons_stock_before': stock_before,
                 'available_work': available_work, 'yield_per_work_turn': BASE_FORAGE_YIELD,
                 'access': round(commons_access(region), 4),
                 'turn': turn})
    if event_id is not None:
        receipt_id = emit(
            region, kind='foraged_food_receipt', record_class='outcome',
            subject={'type': 'tile', 'id': region.name, 'good': Goods.food.name},
            metric_id='goods.foraged_receipt', unit='units', after=food_units,
            inputs={'agent_id': agent.id, 'turn': turn},
            cause_event_ids=[event_id])
        receipts = getattr(region, '_trace_forage_receipts', [])
        receipts.append({'agent_id': agent.id, 'units': food_units,
                         'event_id': receipt_id})
        region._trace_forage_receipts = receipts
