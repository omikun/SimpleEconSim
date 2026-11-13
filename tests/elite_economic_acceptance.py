"""Paired complete-turn observations; test accounting never changes live assets."""
import io
import copy
import pickle
import random
from dataclasses import asdict
import numpy as np
from goods import Goods
from world_config import ElitePlanningConfig
from economy.capitalist_planner import EliteCapitalistPlanner
from tests.elite_economic_accounts import FirmAccounts
from tests.elite_economic_turn import run_turn


def freeze_case(region, firm):
    from simulation_checkpoint import capture_globals, CheckpointPickler
    globals_state, _ = capture_globals()
    buffer = io.BytesIO()
    CheckpointPickler(buffer).dump((region, firm.id, globals_state, random.getstate(), np.random.get_state()))
    return buffer.getvalue()


def restore_case(frozen):
    from simulation_checkpoint import _restore_globals
    region, firm_id, globals_state, rng, numpy_rng = pickle.loads(frozen)
    _restore_globals(globals_state)
    random.setstate(rng)
    np.random.set_state(numpy_rng)
    return region, next(a for a in region.agents if a.id == firm_id)


def observe_case(case, frozen, mode):
    from micro.region.helpers import get_total_cash
    region, firm = restore_case(frozen)
    region._elite_planning_config = ElitePlanningConfig(mode=mode, horizon=case.turns)
    region.elite_planner = EliteCapitalistPlanner()
    accounts = FirmAccounts(firm)
    from economy.elite_planning_state import capture_planning_state
    initial_projection = capture_planning_state(firm, region, 1)
    prices = {Goods.wood:case.input_price, Goods.furniture:case.output_price}
    opening = accounts.balance_sheet(firm, region, prices)
    total = get_total_cash(region.agents, region.bank)
    observations, events, first_forecast = [], [], None
    for turn in range(1, case.turns+1):
        row = run_turn(region, firm, turn, accounts)
        observations.append(row)
        events.extend(row['events'])
        if turn == 1:
            first_forecast = copy.deepcopy(region.elite_planner._active_plans.get(firm.id, {}).get('forecast'))
    initial = observations[0]['decision']
    def owned(kind, side):
        return [e for e in events if e['kind'] == kind and e[side] == firm.id]
    purchases = [e for e in owned('spot_sale', 'payer_id') if e['good'] == 'wood']
    sales = [e for e in owned('spot_sale', 'recipient_id') if e['good'] == 'furniture']
    sheet = accounts.balance_sheet(firm, region, prices)
    result = dict(mode=mode, first_decision=initial, opening=opening, closing=sheet,
        boundary=observations[-1]['boundary'], measured_turns=case.turns,
        forecast=first_forecast,
        opening_projection=asdict(initial_projection),
        first_input_quantity=sum(e['quantity'] for e in purchases if e['turn'] == 1),
        input_quantity=sum(e['quantity'] for e in purchases), input_spend=sum(e['amount'] for e in purchases),
        output_produced=sum(e['quantity'] for e in owned('production', 'recipient_id')),
        output_sold=sum(e['quantity'] for e in sales), sale_receipts=sum(e['amount'] for e in sales),
        wages_paid=sum(e['amount'] for e in owned('wage', 'payer_id')),
        obligations_paid=sum(e['amount'] for e in owned('obligation_payment', 'payer_id')),
        interest_paid=sum(e['detail'].get('interest_paid', 0) for e in owned('bank_loan_repayment', 'payer_id')),
        unposted_cash_change=[row['statement']['unposted_cash_change'] for row in observations],
        aggregate_cash_change=get_total_cash(region.agents, region.bank)-total,
        turns=[{'turn':row['turn'], 'boundary':row['boundary'], 'decision':row['decision']} for row in observations])
    if first_forecast:
        financial = sheet['cash'] + sheet['deposits'] - sheet['bank_principal'] - sheet['cash_obligations'] - sheet['wage_arrears']
        buyer_ids = {e['payer_id'] for e in region.economic_events if e['turn'] == 0 and e['good'] == 'furniture'}
        available = sum(max(0, a.cash) for a in region.agents if a.id in buyer_ids)
        funded = min(initial_projection.demand_per_turn, available / initial_projection.output_price)
        comparable = (financial + firm.inv_get(Goods.wood) * initial_projection.input_price
                      + min(firm.inv_get(Goods.furniture), funded) * initial_projection.output_price)
        result['forecast_comparable_terminal_value'] = comparable
        result['forecast_error'] = comparable - first_forecast['candidate_value']
    return region, firm, result


def compare_case(case):
    from tests.elite_economic_cases import build_case
    region, firm = build_case(case)
    for good in (Goods.wood, Goods.furniture):
        if region.recipes[good]['price'] != region._price_ref[good]:
            raise AssertionError('Fixture quote and internal anchor disagree')
    frozen = freeze_case(region, firm)
    _, _, active = observe_case(case, frozen, 'active')
    _, _, baseline = observe_case(case, frozen, 'off')
    delta = active['closing']['net_assets_at_manufacturing_cost'] - baseline['closing']['net_assets_at_manufacturing_cost']
    common_delta = active['closing']['net_assets_at_common_prices'] - baseline['closing']['net_assets_at_common_prices']
    return dict(case=asdict(case), active=active, baseline=baseline, net_assets_delta=delta,
                common_price_net_assets_delta=common_delta,
                outcome='tie' if abs(delta)<1e-8 else 'higher' if delta>0 else 'lower')
