"""Complete declared production/supply turns for paired economic acceptance."""
from collections import defaultdict
from economy.actor_accounts import begin_turn, seal_turn
from economy.elite_plan_execution import maintain_plans


def run_turn(region, firm, turn, accounts):
    from region_market import trade
    from region_production import produce_corporation
    from region_finance import pay_wages, settle_wage_arrears
    from livelihood_access import settle_obligations
    region._last_turn = turn
    begin_turn(region, turn)
    first_id = getattr(region, '_next_economic_event_id', 1)
    maintain_plans(region.elite_planner, region, turn)
    decision = region.elite_planner._execute_input_control(firm, region, turn)
    trade(region, turn)
    produce_corporation(region, firm, region.recipes[firm.output], firm.output,
                        {firm.output: 1}, defaultdict(float), turn=turn)
    pay_wages(region, turn)
    settle_wage_arrears(region, turn)
    settle_obligations(region, turn)
    events = [e for e in region.economic_events if e['id'] >= first_id]
    accounts.observe_turn(firm, events)
    statement = next(row for row in seal_turn(region, turn) if row['actor_id'] == firm.id)
    return {'decision': decision, 'events': events, 'statement': statement,
            'boundary': 'after_production_payroll_arrears_and_obligations', 'turn': turn}
