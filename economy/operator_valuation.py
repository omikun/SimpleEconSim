"""One source for operator return arithmetic and its explanation."""
from typing import Callable
from dataclasses import dataclass
from goods import Goods


@dataclass(frozen=True)
class ExplainedReturn:
    evaluation: Callable

    def __call__(self, agent, region, shadow_cash):
        return self.evaluation(agent, region, shadow_cash)[0]



def generic_return(operator, agent, region, shadow_cash):
    from abundance import enabled, funded_demand
    from economy.transformation_graph import TransformationGraph
    commercial = enabled(region) and operator.category in ('enclosure', 'corvee', 'artisan', 'capitalist')
    outputs, inputs, gross = [], [], 0.0
    for good, quantity in operator.output_goods.items():
        if commercial:
            quantity = min(quantity, funded_demand(region, good))
        price = TransformationGraph.compute_expected_price(region, good)
        spec = TransformationGraph.get_commodity_spec(good)
        prestige = spec.prestige_rating if spec else 0.0
        prestige_valued = prestige > 0 and not commercial
        contribution = prestige * quantity if prestige_valued else price * quantity * shadow_cash
        gross += contribution
        outputs.append({'good': getattr(good, 'name', str(good)), 'quantity': float(quantity),
                        'expected_unit_price': price, 'prestige_rating': float(prestige),
                        'value_basis': 'prestige' if prestige_valued else 'expected_price_times_shadow_cash',
                        'value_contribution': contribution})
    cost = operator.cash_cost * shadow_cash
    for good, quantity in operator.input_goods.items():
        price = float(getattr(region, 'recipes', {}).get(good, {}).get('price', 1.0))
        contribution = price * quantity * shadow_cash
        cost += contribution
        inputs.append({'good': getattr(good, 'name', str(good)), 'quantity': float(quantity),
                       'unit_price': price, 'cost_contribution': contribution})
    return gross - cost, {
        'formula': 'sum(output contributions) - shadow_cash * (cash_cost + input costs)',
        'shadow_price_cash': float(shadow_cash), 'cash_cost': float(operator.cash_cost),
        'cash_cost_contribution': operator.cash_cost * shadow_cash,
        'outputs': outputs, 'inputs': inputs}


def construction_return(agent, region, shadow_cash):
    value = 35.0
    return value * shadow_cash, {'formula': '35 * shadow_price_cash', 'fixed_return': value}


def repair_return(agent, region, shadow_cash):
    value = 40.0
    return value * shadow_cash, {'formula': '40 * shadow_price_cash', 'fixed_return': value}


def conquest_return(agent, region, shadow_cash):
    from economy.transformation_graph import TransformationGraph
    price = TransformationGraph.compute_expected_price(region, Goods.cotton)
    units, cost, bonus = 10.0, 50.0, 20.0
    return price * units * shadow_cash - cost * shadow_cash + bonus, {
        'formula': '(expected_cotton_price * 10 - 50) * shadow_price_cash + 20',
        'commodity': Goods.cotton.name, 'expected_unit_price': price,
        'valued_output_units': units, 'cash_cost': cost, 'fixed_utility_bonus': bonus}


def procurement_return(agent, region, shadow_cash):
    from economy.transformation_graph import TransformationGraph
    estates = getattr(agent, 'frontier_estates', [])
    if not estates:
        return 0.0, {'reason': 'no_frontier_estates'}
    estate = min(estates, key=lambda row: row.get('captive_labor', 0))
    good = getattr(Goods, estate.get('primary_commodity', 'cotton'), Goods.cotton)
    price = TransformationGraph.compute_expected_price(region, good)
    units, cost = 30.0, 25.0
    return price * units * shadow_cash - cost * shadow_cash, {
        'formula': '(expected_unit_price * 15 * 2 - 25) * shadow_price_cash',
        'commodity': good.name, 'expected_unit_price': price,
        'valued_output_units': units, 'cash_cost': cost}


def plantation_return(agent, region, shadow_cash):
    from economy.transformation_graph import TransformationGraph
    estate = next((e for e in getattr(agent, 'frontier_estates', [])
                   if e.get('captive_labor', 0) >= 3), None)
    if estate is None:
        return 0.0, {'reason': 'no_viable_frontier_estate'}
    good = getattr(Goods, estate.get('primary_commodity', 'cotton'), Goods.cotton)
    base = float(getattr(region, 'recipes', {}).get(good, {}).get('price', 4.0))
    price = TransformationGraph.compute_expected_price(region, good)
    effective, units, cost = max(price, base * .5), 15.0, 10.0
    return effective * units * shadow_cash - cost * shadow_cash, {
        'formula': '(effective_unit_price * 15 - 10) * shadow_price_cash',
        'commodity': good.name, 'expected_unit_price': price,
        'recipe_price_floor_basis': base, 'effective_unit_price': effective,
        'valued_output_units': units, 'cash_cost': cost}


def return_basis(operator, agent, region, shadow_cash):
    hook = getattr(operator, 'estimate_return_hook', None)
    if isinstance(hook, ExplainedReturn):
        return hook.evaluation(agent, region, shadow_cash)[1]
    if hook is not None:
        return {'estimator_hook': getattr(hook, '__name__', type(hook).__name__),
                'formula': 'specialized operator return hook'}
    return generic_return(operator, agent, region, shadow_cash)[1]
