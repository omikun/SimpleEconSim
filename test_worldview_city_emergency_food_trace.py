import json
import unittest
from types import SimpleNamespace

from goods import Goods
from metric_catalog import METRICS, TRACE_INSTRUMENTED
from worldview_policies import _execute_policy_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Household:
    def __init__(self, agent_id, *, hungry_steps=2, corporation=False,
                 government=False, alive=True):
        self.id = agent_id
        self.is_corporation = corporation
        self.is_government = government
        self.hungry_steps = hungry_steps
        self.alive = alive
        self.inventory = {}

    def inv_get(self, good, default=0):
        return self.inventory.get(good, default)

    def inv_add(self, good, amount):
        self.inventory[good] = self.inventory.get(good, 0) + amount


def _fixture(*, municipal_cash=60.0, bank_capital=70.0,
             national_wallet=80.0, hungry_count=2, traced=True):
    households = [Household(f'household-{i}') for i in range(hungry_count)]
    city_government = SimpleNamespace(agent=SimpleNamespace(
        id='city-gov', cash=float(municipal_cash)))
    bank = SimpleNamespace(id='city-bank', capital=float(bank_capital))
    national_tile = SimpleNamespace(name='Capital', gov=SimpleNamespace(
        agent=SimpleNamespace(id='national-gov', cash=float(national_wallet))))
    nation = SimpleNamespace(name='Egypt', currency='EGP',
                             treasury=lambda: {'cash': float(national_wallet)},
                             tiles=[national_tile])
    city = SimpleNamespace(name='Alexandria', home_currency='EGP',
                            owner_nation=nation, gov=city_government,
                            bank=bank, agents=households)
    trace = MemoryTrace()
    if traced:
        city._run_trace = trace
        city._collective_trace_clock = {
            'turn': 3, 'phase': 'policy_action', 'next': 1}
    world = {'turn': 3, 'tiles': [city], 'policy_feedback': None}
    return world, city, households, trace


def _state(fixture):
    world, city, households, _trace = fixture
    national = city.owner_nation.tiles[0].gov.agent
    return (city.gov.agent.cash, city.bank.capital, national.cash,
            tuple((agent.hungry_steps, agent.inv_get(Goods.food, 0))
                  for agent in households), world.get('policy_feedback'))


class WorldviewCityEmergencyFoodTraceTests(unittest.TestCase):
    def test_municipal_source_priority_and_household_creation_match_untraced(self):
        plain = _fixture(municipal_cash=70, bank_capital=90,
                         national_wallet=100, hungry_count=32, traced=False)
        traced = _fixture(municipal_cash=70, bank_capital=90,
                          national_wallet=100, hungry_count=32, traced=True)
        traced[2].insert(0, Household('corporation', corporation=True))
        traced[2].insert(1, Household('public-office', government=True))
        plain[2].insert(0, Household('corporation', corporation=True))
        plain[2].insert(1, Household('public-office', government=True))

        _execute_policy_action(plain[0], 'city_emergency_food', plain[1])
        _execute_policy_action(traced[0], 'city_emergency_food', traced[1])

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[1].gov.agent.cash, 20.0)
        self.assertEqual(traced[1].bank.capital, 90.0)
        funding = next(row for row in traced[3].rows
                       if row.get('kind') == 'city_emergency_food_funding_decision')
        expense = next(row for row in traced[3].rows
                       if row.get('kind') == 'city_emergency_food_policy_expenditure')
        outcome = next(row for row in traced[3].rows
                       if row.get('kind') == 'city_emergency_food_policy_outcome')
        recipients = [row for row in traced[3].rows
                      if row.get('kind') == 'city_emergency_food_recipient_outcome']
        self.assertEqual(funding['inputs']['selected_source'], 'city_government_cash')
        self.assertEqual([row['source'] for row in funding['inputs']['candidate_sources']],
                         ['city_government_cash'])
        self.assertEqual(expense['after'], -50.0)
        self.assertEqual(expense['inputs']['transfer_contract']['payer_account'][
            'balance_after'], 20.0)
        self.assertEqual(len(recipients), 30)
        self.assertTrue(all(row['inputs']['source'] ==
                            'policy_action_created_food_without_stock_debit'
                            for row in recipients))
        self.assertTrue(all(row['cause_event_ids'] == [expense['event_id']]
                            for row in recipients))
        self.assertFalse(outcome['inputs']['stock_debit_recorded'])
        self.assertEqual(outcome['inputs']['recipient_count'], 30)
        self._assert_catalogued(traced[3].rows)

    def test_bank_capital_is_used_after_insufficient_city_treasury(self):
        fixture = _fixture(municipal_cash=20, bank_capital=60, national_wallet=100)

        _execute_policy_action(fixture[0], 'city_emergency_food', fixture[1])

        self.assertEqual(fixture[1].gov.agent.cash, 20.0)
        self.assertEqual(fixture[1].bank.capital, 10.0)
        decision = next(row for row in fixture[3].rows
                        if row.get('kind') == 'city_emergency_food_funding_decision')
        self.assertEqual(decision['inputs']['selected_source'], 'tile_bank_capital')
        self.assertEqual([row['source'] for row in decision['inputs']['candidate_sources']],
                         ['city_government_cash', 'tile_bank_capital'])
        expense = next(row for row in fixture[3].rows
                       if row.get('kind') == 'city_emergency_food_policy_expenditure')
        self.assertEqual(expense['inputs']['transfer_contract'][
            'payer_account']['balance_scope'], 'bank.capital')

    def test_national_treasury_is_used_after_local_sources_fail(self):
        fixture = _fixture(municipal_cash=20, bank_capital=30, national_wallet=80)

        _execute_policy_action(fixture[0], 'city_emergency_food', fixture[1])

        self.assertEqual(fixture[1].gov.agent.cash, 20.0)
        self.assertEqual(fixture[1].bank.capital, 30.0)
        self.assertEqual(fixture[1].owner_nation.tiles[0].gov.agent.cash, 30.0)
        decision = next(row for row in fixture[3].rows
                        if row.get('kind') == 'city_emergency_food_funding_decision')
        self.assertEqual(decision['inputs']['selected_source'], 'owner_national_treasury')
        self.assertEqual(decision['inputs']['candidate_sources'][-1]['available_cash'], 80.0)
        expense = next(row for row in fixture[3].rows
                       if row.get('kind') == 'city_emergency_food_policy_expenditure')
        account = expense['inputs']['transfer_contract']['payer_account']
        self.assertEqual(account['id'], 'national-gov')
        self.assertEqual(account['balance_before'], 80.0)
        self.assertEqual(account['balance_after'], 30.0)

    def test_unfunded_action_still_creates_food_and_records_cash_shortfall(self):
        fixture = _fixture(municipal_cash=20, bank_capital=30, national_wallet=40)

        _execute_policy_action(fixture[0], 'city_emergency_food', fixture[1])

        self.assertEqual(fixture[1].gov.agent.cash, 20.0)
        self.assertEqual(fixture[1].bank.capital, 30.0)
        self.assertEqual(fixture[1].owner_nation.tiles[0].gov.agent.cash, 40.0)
        decision = next(row for row in fixture[3].rows
                        if row.get('kind') == 'city_emergency_food_funding_decision')
        self.assertFalse(decision['inputs']['funded'])
        self.assertEqual(decision['inputs']['cash_shortfall'], 10.0)
        self.assertTrue(decision['inputs']['food_distribution_occurs_without_funding'])
        self.assertFalse(any(row.get('kind') == 'city_emergency_food_policy_expenditure'
                             for row in fixture[3].rows))
        outcome = next(row for row in fixture[3].rows
                       if row.get('kind') == 'city_emergency_food_policy_outcome')
        self.assertEqual(outcome['inputs']['food_units_created'], 2)
        self.assertTrue(all(row['inputs']['cash_expenditure_event_id'] is None
                            for row in fixture[3].rows
                            if row.get('kind') == 'city_emergency_food_recipient_outcome'))

    def test_funded_action_spends_even_when_no_household_qualifies(self):
        fixture = _fixture(municipal_cash=60, hungry_count=0)

        _execute_policy_action(fixture[0], 'city_emergency_food', fixture[1])

        self.assertEqual(fixture[1].gov.agent.cash, 10.0)
        outcome = next(row for row in fixture[3].rows
                       if row.get('kind') == 'city_emergency_food_policy_outcome')
        self.assertEqual(outcome['inputs']['recipient_count'], 0)
        self.assertEqual(outcome['inputs']['cash_paid'], 50.0)
        self.assertEqual(outcome['inputs']['food_units_created'], 0)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
