"""Causal trace contract and live mutation probes."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from goods import Goods
from region_market import update_price_ref, price_decay
from run_trace import RunTrace, verify
from price_trace import replay_event
from trace_report import report, render, diff_snapshots


class RunTraceTests(unittest.TestCase):

    def test_current_turn_tile_production_event_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'production-index.ctr',
                             'production-index')
            clock = {'next': 1, 'turn': 3, 'phase': 'production'}
            event_id = trace.emit(
                clock, kind='tile_production_total', record_class='calculation',
                subject={'type': 'tile', 'id': 'Nile Delta', 'good': 'food'},
                metric_id='goods.production', unit='units_per_turn', after=12,
                inputs={'producer_count': 4})

            self.assertEqual(
                trace.turn_tile_production_event_id('Nile Delta', 'food'), event_id)
            trace.emit(clock, kind='later_turn_event', record_class='observation')
            clock['turn'] = 4
            trace.emit(clock, kind='turn_marker', record_class='observation')
            self.assertIsNone(
                trace.turn_tile_production_event_id('Nile Delta', 'food'))

    def test_bank_balance_sheet_is_snapshotted(self):
        from econsim_trade_money import Bank
        from trace_snapshots import sample

        bank = Bank()
        bank.total_deposits = 37.0
        bank.total_liabilities = 12.0
        bank.cumulative_writedowns = 8.0
        tile = SimpleNamespace(
            name='Delta', recipes={}, agents=[], total_population=[],
            protest_energy_log=[], unrest_log=[], construction_projects=[],
            gdp_log=[], cost_of_living=1.0, bank=bank)

        values = sample([tile], [])
        self.assertEqual(values[('finance.bank_capital', 'Delta')][2], 2000.0)
        self.assertEqual(values[('finance.bank_equity', 'Delta')][2], 2025.0)
        self.assertEqual(values[('finance.bank_deposits', 'Delta')][2], 37.0)
        self.assertEqual(values[('finance.bank_liabilities', 'Delta')][2], 12.0)
        self.assertEqual(values[('finance.bank_cumulative_writedowns', 'Delta')][2], 8.0)

    def test_collective_action_withheld_hours_link_to_zero_firm_output(self):
        from collective_action import _event
        from labor_resistance import record_workforce_availability
        from region import Region
        from region_production import produce_corporation

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'labor-output.ctr', 'labor-output')
            clock = {'next': 1, 'turn': 4, 'phase': 'local'}
            region = Region('Delta', 0, 1)
            region._collective_trace_clock = clock
            region._run_trace = trace
            firm = Agent(0)
            initialize_agent(firm, Goods.cloth, 0, 0, 50.0)
            firm.is_corporation = True
            firm.output = Goods.cloth
            firm.company_name = 'Delta Mill'
            worker = Agent(0)
            initialize_agent(worker, Goods.food, 0, 0, 10.0)
            worker.employer = firm
            worker.is_striking = True
            firm.employees = [worker]
            region.agents = [firm, worker]

            strike = _event(region, 4, 'strike_started', firm,
                            strike_id='delta-strike', participant_ids=[worker.id])
            collective_event = trace.recent[-1]
            self.assertEqual(collective_event['metric_id'],
                             'labor.collective_action')
            self.assertEqual(collective_event['value_after'], 'strike_started')
            self.assertEqual(collective_event['inputs']['collective_kind'],
                             'strike_started')
            self.assertEqual(collective_event['subject']['tile'], 'Delta')
            self.assertEqual(strike['trace_event_id'],
                             collective_event['event_id'])
            query = trace.query(metric_id='labor.collective_action', turn=4)
            self.assertEqual(query['total'], 1)
            self.assertEqual(query['events'][0]['event_id'],
                             collective_event['event_id'])
            workforce_ids = record_workforce_availability(region, 4)
            workforce = trace.recent[-1]
            receipt_ids = []
            produce_corporation(region, firm, region.recipes[Goods.cloth],
                                Goods.cloth, {Goods.cloth: 1}, {}, receipt_ids)
            zero_output = trace.recent[-1]

            self.assertEqual(workforce['metric_id'], 'labor.available_worker_hours')
            self.assertEqual(workforce['value_after'], 0.0)
            self.assertEqual(workforce['cause_event_ids'], [strike['trace_event_id']])
            self.assertEqual(zero_output['kind'], 'firm_production_zero')
            self.assertEqual(zero_output['inputs']['reason'],
                             'all_employees_withheld_or_revolting')
            self.assertEqual(zero_output['cause_event_ids'],
                             [workforce_ids[firm.id]])
            self.assertIn(zero_output['event_id'], receipt_ids)

            clock.update(turn=5, phase='local')
            worker.is_striking = False
            firm.inv_add(Goods.wool, 4)
            available_ids = record_workforce_availability(region, 5)
            with patch('region_production.rand.random_n', return_value=[0.0]):
                produce_corporation(region, firm, region.recipes[Goods.cloth],
                                    Goods.cloth, {Goods.cloth: 1}, {})
            production = next(row for row in reversed(trace.recent)
                              if row['kind'] == 'firm_production')
            self.assertEqual(production['kind'], 'firm_production')
            self.assertEqual(production['cause_event_ids'],
                             [available_ids[firm.id]])
            surplus = next(row for row in reversed(trace.recent)
                           if row['kind'] == 'firm_surplus_value_calculation')
            self.assertEqual(surplus['turn'], 5)
            self.assertEqual(surplus['inputs']['turn'], 5)

    def test_commons_work_share_explains_failed_independent_production_roll(self):
        from region import Region
        from region_production import produce_independent

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'subsistence-output.ctr', 'subsistence-output')
            clock = {'next': 1, 'turn': 5, 'phase': 'local'}
            region = Region('Delta', 0, 1)
            region._collective_trace_clock = clock
            region._run_trace = trace
            person = Agent(0)
            initialize_agent(person, Goods.wood, 0, 0, 10.0)
            person.output = Goods.wood
            person.temporary_work_share = 0.25
            activity_id = trace.emit(
                clock, kind='commons_foraging', record_class='outcome',
                subject={'type': 'agent', 'id': person.id, 'tile': region.name},
                metric_id='labor.temporary_activity', after=0.25,
                unit='turn_share', inputs={'food_units': 4})

            with patch('region_production.rand.random', return_value=0.99):
                produce_independent(
                    region, person,
                    {'maxinv': 10, 'numInput': 0, 'production': 2,
                     'maxtotalprod': 100},
                    Goods.wood, {Goods.wood: 1}, {})

            zero_output = trace.recent[-1]
            self.assertEqual(zero_output['kind'], 'independent_production_zero')
            self.assertEqual(zero_output['cause_event_ids'], [activity_id])
            self.assertEqual(zero_output['inputs']['temporary_work_share'], 0.25)

    def test_national_basket_change_separates_territory_mix(self):
        from trace_snapshots import _territorial_mix_evidence

        previous = {
            ('living.cost_of_living', 'Meridian'): (None, None, 15.0),
            ('living.cost_of_living', 'A'): (None, None, 10.0),
            ('living.cost_of_living', 'B'): (None, None, 20.0),
        }
        current = {
            ('living.cost_of_living', 'Meridian'): (None, None, 21.0),
            ('living.cost_of_living', 'A'): (None, None, 12.0),
            ('living.cost_of_living', 'C'): (None, None, 30.0),
        }
        currencies = {'A': 'D', 'B': 'D', 'C': 'D'}
        evidence = _territorial_mix_evidence(
            'living.cost_of_living', 'Meridian', None, ['A', 'C'], ['A', 'B'],
            previous, current, currencies, currencies, 'D', 'D')
        self.assertEqual(evidence['added_member_tiles'], ['C'])
        self.assertEqual(evidence['removed_member_tiles'], ['B'])
        self.assertEqual(evidence['continuing_member_mean_change'], 2.0)
        self.assertEqual(evidence['territorial_composition_residual'], 4.0)
        self.assertEqual(evidence['delta_decomposition_status'],
                         'arithmetic_decomposition_available')

        mixed_currencies = dict(currencies, C='E')
        mixed = _territorial_mix_evidence(
            'living.cost_of_living', 'Meridian', None, ['A', 'C'], ['A', 'B'],
            previous, current, currencies, mixed_currencies, 'D', 'D')
        self.assertIsNone(mixed['territorial_composition_residual'])
        self.assertEqual(mixed['delta_decomposition_status'],
                         'mixed_or_changed_currency')

        previous_food = {
            **previous,
            ('goods.national_food_price', 'Meridian'): (None, None, 15.0),
            ('goods.price', 'A', 'food'): (None, None, 10.0),
            ('goods.price', 'B', 'food'): (None, None, 20.0),
        }
        current_food = {
            **current,
            ('goods.national_food_price', 'Meridian'): (None, None, 21.0),
            ('goods.price', 'A', 'food'): (None, None, 12.0),
            ('goods.price', 'C', 'food'): (None, None, 30.0),
        }
        food_evidence = _territorial_mix_evidence(
            'goods.national_food_price', 'Meridian', 'food', ['A', 'C'],
            ['A', 'B'], previous_food, current_food, currencies, currencies,
            'D', 'D')
        self.assertEqual(food_evidence['continuing_member_mean_change'], 2.0)
        self.assertEqual(food_evidence['territorial_composition_residual'], 4.0)

    def test_starvation_death_uses_region_trace_and_snapshot_counter(self):
        from demographics_estate import handle_death

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'deaths.ctr', 'deaths')
            clock = {'next': 1, 'turn': 7, 'phase': 'local'}
            region = SimpleNamespace(name='Delta', deaths_this_turn=0,
                                     deaths_by_cause_this_turn={},
                                     _collective_trace_clock=clock, _run_trace=trace)
            context = SimpleNamespace(source_region=region)
            person = Agent(0)
            initialize_agent(person, Goods.food, 0, 0, 0)
            person.calorie_deficit_kcal = 2000.0
            person.energy_reserve_kcal = 0.0
            with ExitStack() as patches:
                patches.enter_context(patch('demographics_estate.rand.random', return_value=0.0))
                for helper in ('cleanup_dead_agent_links', 'handle_company_inheritance',
                               'reclaim_dead_route_cargo', 'escheat_dead_parked_goods',
                               'handle_debt_inheritance', 'handle_wealth_inheritance',
                               'zero_out_dead_agent'):
                    patches.enter_context(patch(f'demographics_estate.{helper}'))
                patches.enter_context(patch('demographics_estate.living_descendants_recursive',
                                            return_value=[]))
                self.assertTrue(handle_death(context, 7, person, [person]))

            self.assertEqual(region.deaths_this_turn, 1)
            self.assertEqual(region.deaths_by_cause_this_turn, {'starvation': 1})
            rows = trace.query(turn=7)['events']
            self.assertEqual([row['kind'] for row in rows],
                             ['starvation_death_assessment', 'person_died'])
            self.assertEqual(rows[0]['subject']['id'], 'Delta')
            self.assertIn('metabolic_need_factor', rows[0]['inputs'])
            self.assertIn('effective_calorie_need_kcal', rows[0]['inputs'])
            self.assertIn('food_inventory', rows[0]['inputs'])
            self.assertEqual(rows[1]['inputs']['tile'], 'Delta')
            self.assertEqual(rows[1]['inputs']['death_cause'], 'starvation')

    def test_disease_fatality_requires_disease_to_cross_death_threshold(self):
        from demographics_estate import handle_death

        def resolve(death_draw, run_id):
            with tempfile.TemporaryDirectory() as tmp:
                trace = RunTrace(Path(tmp) / 'deaths.ctr', run_id)
                clock = {'next': 1, 'turn': 7, 'phase': 'local'}
                region = SimpleNamespace(
                    name='Delta', agents=[], deaths_this_turn=0,
                    deaths_by_cause_this_turn={}, disease_fatalities_this_turn=0,
                    _collective_trace_clock=clock, _run_trace=trace)
                person = Agent(-23)
                initialize_agent(person, Goods.food, 0, 0, 0)
                person.diseases = ['respiratory']
                region.agents.append(person)
                context = SimpleNamespace(
                    source_region=region, cost_of_living=1.0,
                    carrying_capacity=100, default_gov=None,
                    bank=SimpleNamespace(deposits={}))
                with ExitStack() as patches:
                    patches.enter_context(patch(
                        'demographics_estate.rand.random', return_value=death_draw))
                    patches.enter_context(patch(
                        'demographics_estate.is_last_of_profession', return_value=False))
                    patches.enter_context(patch(
                        'government.find_government_for_agent', return_value=None))
                    patches.enter_context(patch(
                        'nutrition.starvation_hazard', return_value=0.0))
                    for helper in ('cleanup_dead_agent_links', 'handle_company_inheritance',
                                   'reclaim_dead_route_cargo', 'escheat_dead_parked_goods',
                                   'handle_debt_inheritance', 'handle_wealth_inheritance',
                                   'handle_wage_claim_inheritance', 'zero_out_dead_agent'):
                        patches.enter_context(patch(f'demographics_estate.{helper}'))
                    patches.enter_context(patch(
                        'demographics_estate.living_descendants_recursive',
                        return_value=[]))
                    self.assertTrue(handle_death(context, 7, person, [person]))
                rows = trace.query(turn=7)['events']
                assessment = next(row for row in rows
                                  if row['kind'] == 'mortality_assessment')
                death = next(row for row in rows if row['kind'] == 'person_died')
                return (person, region, assessment, death)

        # At age 30 the pre-disease risk is 0.0007; respiratory disease raises
        # it by 45%. The same draw below the baseline is not disease-attributable.
        crossed = resolve(0.0009, 'disease-crossing')
        baseline = resolve(0.0005, 'disease-present')
        self.assertTrue(crossed[0].died_of_starvation is False)
        self.assertEqual(crossed[1].disease_fatalities_this_turn, 1)
        pending = crossed[1]._trace_pending_disease_fatalities
        self.assertEqual([crossed[2]['event_id']], [row['event_id'] for row in pending])
        self.assertEqual(7, pending[0]['mortality_turn'])
        self.assertEqual(crossed[3]['inputs']['death_cause'], 'disease')
        self.assertTrue(crossed[2]['inputs']['disease_attributed_by_threshold_crossing'])
        self.assertEqual(baseline[1].disease_fatalities_this_turn, 0)
        self.assertEqual(baseline[3]['inputs']['death_cause'], 'age_or_health')
        self.assertFalse(baseline[2]['inputs']['disease_attributed_by_threshold_crossing'])

    def test_resident_population_bridge_reconciles_lifecycle_and_migration(self):
        from trace_snapshots import resident_population_bridges

        nation = SimpleNamespace(name='A')
        departed = SimpleNamespace(id=1, alive=True, is_corporation=False,
                                   is_government=False, region='Beta')
        dead = SimpleNamespace(id=2, alive=False, is_corporation=False,
                               is_government=False, death_region='Alpha',
                               death_cause='combat')
        converted = SimpleNamespace(id=3, alive=True, is_corporation=True,
                                    is_government=False, region='Alpha')
        newborn = SimpleNamespace(id=4, alive=True, is_corporation=False,
                                  is_government=False, is_native_child=True,
                                  birth_round=9, parent=None)
        alpha = SimpleNamespace(name='Alpha', owner_nation=nation,
                                agents=[converted])
        beta = SimpleNamespace(name='Beta', owner_nation=nation,
                               agents=[departed, newborn])
        previous = {
            1: {'agent': departed, 'tile': 'Alpha', 'nation': 'A'},
            2: {'agent': dead, 'tile': 'Alpha', 'nation': 'A'},
            3: {'agent': converted, 'tile': 'Alpha', 'nation': 'A'},
        }
        current = {
            1: {'agent': departed, 'tile': 'Beta', 'nation': 'A'},
            4: {'agent': newborn, 'tile': 'Beta', 'nation': 'A'},
        }
        bridges = resident_population_bridges(
            previous, current,
            {1: 'person', 2: 'person', 3: 'person'},
            [alpha, beta], 9,
            {'1': ['run:10'], '2': ['run:11'], '4': ['run:12']})
        tile_bridges = {row['id']: row for row in bridges if row['scope'] == 'tile'}
        self.assertEqual(tile_bridges['Alpha']['before'], 3)
        self.assertEqual(tile_bridges['Alpha']['after'], 0)
        self.assertEqual(tile_bridges['Alpha']['inputs']['flow_counts'], {
            'departures': 1, 'deaths': 1, 'role_conversions_out': 1})
        self.assertTrue(tile_bridges['Alpha']['inputs']['reconciled'])
        self.assertEqual(tile_bridges['Beta']['before'], 0)
        self.assertEqual(tile_bridges['Beta']['after'], 2)
        self.assertEqual(tile_bridges['Beta']['inputs']['flow_counts'], {
            'arrivals': 1, 'births': 1})
        self.assertEqual(tile_bridges['Beta']['cause_event_ids'], ['run:10', 'run:12'])
        national = next(row for row in bridges if row['scope'] == 'nation')
        self.assertEqual(national['before'], 3)
        self.assertEqual(national['after'], 2)
        self.assertTrue(national['inputs']['reconciled'])

    def test_resident_population_bridge_separates_territorial_membership(self):
        from trace_snapshots import resident_population_bridges

        resident = SimpleNamespace(id=7, alive=True, is_corporation=False,
                                   is_government=False)
        tile = SimpleNamespace(name='Delta', owner_nation=SimpleNamespace(name='B'),
                               agents=[resident])
        previous = {7: {'agent': resident, 'tile': 'Delta', 'nation': 'A'}}
        current = {7: {'agent': resident, 'tile': 'Delta', 'nation': 'B'}}
        bridges = resident_population_bridges(
            previous, current, {7: 'person'}, [tile], 10)
        national = {row['id']: row for row in bridges if row['scope'] == 'nation'}
        self.assertEqual(national['A']['inputs']['flow_counts'], {'departures': 1})
        self.assertEqual(national['B']['inputs']['flow_counts'], {'arrivals': 1})
        self.assertEqual(
            national['B']['inputs']['flows']['arrivals'][0]['basis'],
            'territorial_membership_change')
        self.assertTrue(all(row['inputs']['reconciled'] for row in national.values()))

    def test_resident_population_bridge_downgrades_unknown_exit(self):
        from trace_snapshots import resident_population_bridges

        resident = SimpleNamespace(id=8, alive=True, is_corporation=False,
                                   is_government=False)
        tile = SimpleNamespace(name='Delta', owner_nation=SimpleNamespace(name='A'),
                               agents=[])
        previous = {8: {'agent': resident, 'tile': 'Delta', 'nation': 'A'}}
        bridges = resident_population_bridges(
            previous, {}, {8: 'person'}, [tile], 11)
        row = next(row for row in bridges
                   if row['scope'] == 'tile' and row['id'] == 'Delta')
        self.assertTrue(row['inputs']['reconciled'])
        self.assertFalse(row['inputs']['explanation_complete'])
        self.assertEqual(row['inputs']['flow_counts'], {'unknown_exits': 1})

    def test_profession_population_changes_link_death_and_career_events(self):
        from micro.region.stepper import _trace_profession_population

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'profession.ctr', 'profession')
            clock = {'next': 1, 'turn': 4, 'phase': 'local'}
            dead = SimpleNamespace(id=1, alive=False, is_corporation=False,
                                   is_government=False, is_trader=False,
                                   death_cause='combat', output=Goods.food)
            switcher = SimpleNamespace(id=2, alive=True, is_corporation=False,
                                       is_government=False, is_trader=False,
                                       output=Goods.wood)
            wood_worker = SimpleNamespace(id=3, alive=True, is_corporation=False,
                                          is_government=False, is_trader=False,
                                          output=Goods.wood)
            trace.emit(clock, kind='person_died', record_class='outcome',
                       subject={'type': 'tile/agent', 'id': '1'},
                       inputs={'agent_id': '1'})
            trace.emit(clock, kind='demographic_career_switch',
                       record_class='outcome',
                       subject={'type': 'agent', 'id': 2},
                       metric_id='labor.occupation_change', before='food', after='wood',
                       inputs={'agent_id': 2})
            region = SimpleNamespace(
                name='Delta', _run_trace=trace, _collective_trace_clock=clock,
                population_log={Goods.food: [2], Goods.wood: [1], 'trader': [0]},
                _trace_profession_members={
                    'food': {1: dead, 2: switcher}, 'wood': {3: wood_worker},
                    'trader': {}},
            )
            _trace_profession_population(region, {
                Goods.food: [], Goods.wood: [switcher, wood_worker],
                'trader': []})
            food = trace.query(metric_id='people.profession_population',
                               subject={'type': 'tile', 'profession': 'food'})['events']
            wood = trace.query(metric_id='people.profession_population',
                               subject={'type': 'tile', 'profession': 'wood'})['events']
            self.assertEqual(len(food), 1)
            self.assertEqual((food[0]['value_before'], food[0]['value_after']), (2, 0))
            self.assertEqual(food[0]['inputs']['removed_agent_ids'], ['1', '2'])
            self.assertIn('profession:1', food[0]['cause_event_ids'])
            self.assertIn('profession:2', food[0]['cause_event_ids'])
            self.assertEqual(len(wood), 1)
            self.assertEqual((wood[0]['value_before'], wood[0]['value_after']), (1, 2))
            self.assertEqual(wood[0]['inputs']['added_agent_ids'], ['2'])
            self.assertIn('profession:2', wood[0]['cause_event_ids'])

    def test_snapshots_include_profession_and_trader_population_series(self):
        from trace_snapshots import sample

        tile = SimpleNamespace(
            name='Delta', recipes={}, population_log={
                Goods.food: [3], Goods.wood: [0], 'trader': [1]},
            total_population=[4], agents=[], protest_energy_log=[], unrest_log=[],
            gdp_log=[], cost_of_living=1.0, construction_projects=[])
        values = sample([tile], [])
        self.assertEqual(values[
            ('people.profession_population', 'Delta', 'food')][2], 3)
        self.assertEqual(values[
            ('people.profession_population', 'Delta', 'trader')][2], 1)
        self.assertNotIn(('people.profession_population', 'Delta', 'wood'), values)

    def test_price_formula_replays_from_recorded_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'run.ctr', 'fixture', seed=1)
            clock = {'next': 1, 'turn': 7, 'phase': 'local'}
            producer = SimpleNamespace(output=Goods.food, is_trader=False,
                                       inv_get=lambda _good, _fallback: 2.0)
            region = SimpleNamespace(name='Delta', _price_ref={Goods.food: 2.0},
                                     _trade_prices={Goods.food: [2.2, 2.4]},
                                     agents=[producer], recipes={Goods.food: {'maxinv': 10, 'price': 2.0}},
                                     _collective_trace_clock=clock, _run_trace=trace)
            update_price_ref(region, Goods.food, 1.5,
                             local_asks=8, imported_asks=2, bids=15)
            rows = trace.query(turn=7, subject={'type': 'tile', 'id': 'Delta'},
                               metric_id='goods.price')['events']
            self.assertEqual(len(rows), 1)
            row = rows[0]
            terms = row['inputs']
            self.assertEqual((terms['local_asks'], terms['imported_asks'], terms['bids']),
                             (8, 2, 15))
            expected = min(50.0, max(0.1, terms['input_cost_floor'], terms['after_vwap']))
            self.assertAlmostEqual(row['value_after'], expected)
            self.assertAlmostEqual(region._price_ref[Goods.food], expected)
            self.assertTrue(replay_event(row)['matches'])
            self.assertTrue(row['formula_replay']['matches'])
            self.assertEqual(terms['recent_sample_mean'], 2.3)
            self.assertEqual(row['sequence'], 1)
            self.assertIn('prior_reference', render(row))
            self.assertEqual(trace.query(event_id=row['event_id'])['events'], [row])
            self.assertEqual(len(report(trace.path, turn=7, entity='tile:Delta',
                                        metric='goods.price')), 1)
            self.assertEqual(report(trace.path, event_id=row['event_id']), [row])
            self.assertEqual(len(report(trace.path, turn=7, entity='tile:Delta',
                                        metric='goods.price', good='wood')), 0)

    def test_standalone_price_formulas_replay_without_changing_results(self):
        from copy import deepcopy
        from econsim_trade_money import _price_default_decay, set_market_price

        recipe_fixture = {
            Goods.food: {'price': 2.0, 'production': 4},
            Goods.wood: {'price': 10.0, 'input': Goods.food,
                         'numInput': 2, 'production': 2},
        }
        producer = SimpleNamespace(output=Goods.wood, cash=5.0, hungry_steps=2)
        untraced_recipes = deepcopy(recipe_fixture)
        traced_recipes = deepcopy(recipe_fixture)
        expected = set_market_price(0.1, Goods.wood, untraced_recipes, [producer])

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'econsim.ctr', 'econsim', scenario='econsim')
            clock = {'next': 1, 'turn': 0, 'phase': 'market'}
            context = SimpleNamespace(name='econsim', _run_trace=trace,
                                      _collective_trace_clock=clock)
            actual = set_market_price(0.1, Goods.wood, traced_recipes,
                                      [producer], trace_context=context)
            self.assertEqual(actual, expected)
            update = trace.query(metric_id='goods.price')['events'][0]
            self.assertEqual(update['subject']['type'], 'simulation')
            self.assertTrue(update['formula_replay']['matches'])
            self.assertEqual(update['inputs']['producers'][0]['hungry_steps'], 2)

            decay_recipes = deepcopy(recipe_fixture)
            decay_recipes[Goods.wood]['price'] = 10.0
            _price_default_decay(Goods.wood, decay_recipes, trace_context=context)
            decay = trace.query(metric_id='goods.price')['events'][1]
            self.assertEqual(decay['formula_id'], 'econsim.price_decay.v1')
            self.assertEqual(decay['value_after'], 9.5)
            self.assertTrue(decay['formula_replay']['matches'])

    def test_pagination_and_typed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'run.ctr', 'fixture')
            clock = {'next': 1, 'turn': 1, 'phase': 'test'}
            for value in range(3):
                trace.emit(clock, kind='snapshot', subject={'type': 'tile', 'id': 'A'},
                           metric_id='people.population', after=value)
            page = trace.query(metric_id='people.population', offset=1, limit=1)
            self.assertEqual(page['total'], 3)
            self.assertEqual(page['events'][0]['value_after'], 1)
            self.assertEqual(page['events'][0]['event_id'], 'fixture:2')
            trace.emit(clock, kind='tax', record_class='transfer',
                       subject={'type': 'nation', 'id': 'A'},
                       metric_id='finance.treasury_flow', after=5.0)
            self.assertEqual(trace._treasury_flows['A'][0]['amount'], 5.0)
            trace.checkpoint(clock)
            self.assertEqual(verify(trace.path)['checkpoints'], 1)
            left = [{'kind': 'metric_snapshot', 'turn': 1,
                     'subject': {'type': 'tile', 'id': 'A'},
                     'metric_id': 'goods.price', 'value_after': 2.0}]
            right = [{**left[0], 'value_after': 2.5}]
            self.assertEqual(diff_snapshots(left, right)[0]['difference'], 0.5)

    def test_person_flow_event_ids_are_indexed_per_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'people.ctr', 'people')
            clock = {'next': 1, 'turn': 1, 'phase': 'demographics'}
            trace.emit(clock, kind='birth', record_class='outcome',
                       subject={'type': 'tile', 'id': 'Delta'},
                       inputs={'new_agent_id': 12})
            trace.emit(clock, kind='person_died', record_class='outcome',
                       subject={'type': 'tile/agent', 'id': '13'},
                       inputs={'agent_id': '13'})
            self.assertEqual(trace._person_flow_events,
                             {'12': ['people:1'], '13': ['people:2']})
            clock['turn'] = 2
            trace.emit(clock, kind='migration_arrival', record_class='outcome',
                       subject={'type': 'tile', 'id': 'Delta'},
                       inputs={'agent_id': 12})
            self.assertEqual(trace._person_flow_events, {'12': ['people:3']})

    def test_current_turn_food_intake_event_is_retrievable_by_person(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'food-intake.ctr', 'food-intake')
            clock = {'next': 1, 'turn': 1, 'phase': 'demographics'}
            event_id = trace.emit(
                clock, kind='household_food_intake', record_class='calculation',
                subject={'type': 'tile/agent', 'id': '52'},
                metric_id='health.calorie_deficit', before=0.0, after=500.0,
                inputs={'agent_id': 52})
            self.assertEqual(trace.food_intake_event_id(52), event_id)
            clock['turn'] = 2
            trace.emit(clock, kind='metric_snapshot',
                       subject={'type': 'tile', 'id': 'Delta'})
            self.assertIsNone(trace.food_intake_event_id(52))

    def test_price_bridge_tracks_order_and_exposes_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'bridge.ctr', 'bridge')
            clock = {'next': 1, 'turn': 1, 'phase': 'local'}
            subject = {'type': 'tile', 'id': 'Delta', 'good': 'food'}
            trace.emit(clock, kind='market_price_update', record_class='calculation',
                       subject=subject, metric_id='goods.price', before=2, after=3)
            trace.emit(clock, kind='market_price_decay', record_class='calculation',
                       subject=subject, metric_id='goods.price', before=3, after=2.5)
            trace.price_bridge(clock, subject=subject, before=2, after=2.5,
                               unit='local_currency_per_unit')
            bridge = trace.query(subject=subject, metric_id='goods.price')['events'][-1]
            self.assertEqual([step['difference'] for step in bridge['inputs']['steps']],
                             [1, -0.5])
            self.assertEqual(bridge['explanation_status'], 'ordered_writes_reconciled')
            trace.price_bridge(clock, subject=subject, before=1, after=2.5,
                               unit='local_currency_per_unit')
            gap = trace.query(subject=subject, metric_id='goods.price')['events'][-1]
            self.assertEqual(gap['explanation_status'], 'mutation_chain_incomplete')

    def test_formula_mismatch_cannot_receive_exact_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'mismatch.ctr', 'mismatch')
            clock = {'next': 1, 'turn': 1, 'phase': 'local'}
            subject = {'type': 'tile', 'id': 'Delta', 'good': 'food'}
            trace.emit(clock, kind='market_price_decay', record_class='calculation',
                       subject=subject, metric_id='goods.price', before=2, after=9,
                       formula_id='market.decay.v1',
                       inputs={'prior_display_price': 2, 'input_cost_floor': 1,
                               'input_quantity': 0, 'production_quantity': 0})
            row = trace.query(metric_id='goods.price')['events'][0]
            self.assertFalse(row['formula_replay']['matches'])
            self.assertEqual(row['confidence'], 'unknown')
            trace.price_bridge(clock, subject=subject, before=2, after=9,
                               unit='local_currency_per_unit')
            bridge = trace.query(metric_id='goods.price')['events'][-1]
            self.assertEqual(bridge['explanation_status'], 'mutation_chain_incomplete')

    def test_no_order_decay_and_furniture_input_floor_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'floors.ctr', 'floors')
            clock = {'next': 1, 'turn': 2, 'phase': 'local'}
            recipes = {Goods.food: {'price': 3.0, 'maxinv': 10},
                       Goods.furniture: {'price': 1.0, 'maxinv': 10,
                                         'input': Goods.food, 'numInput': 2,
                                         'production': 1}}
            producer = SimpleNamespace(output=Goods.furniture, is_trader=False,
                                       inv_get=lambda _good, _fallback: 10.0)
            region = SimpleNamespace(name='Delta', recipes=recipes,
                                     _price_ref={Goods.food: 3.0,
                                                 Goods.furniture: 1.0},
                                     _trade_prices={}, agents=[producer],
                                     _collective_trace_clock=clock, _run_trace=trace,
                                     home_currency='D')
            price_decay(region, Goods.food)
            self.assertAlmostEqual(recipes[Goods.food]['price'], 2.85)
            update_price_ref(region, Goods.furniture, 0.1,
                             local_asks=10, imported_asks=0, bids=1)
            self.assertAlmostEqual(recipes[Goods.furniture]['price'], 5.7)
            rows = trace.query(metric_id='goods.price')['events']
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(replay_event(row)['matches'] for row in rows))
            self.assertTrue(all(row['formula_replay']['matches'] for row in rows))
            self.assertAlmostEqual(rows[1]['constraints']['active_floor'], 5.7)

    def test_food_rise_and_fall_replay_on_separate_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'food.ctr', 'food')
            clock = {'next': 1, 'turn': 1, 'phase': 'local'}
            producer = SimpleNamespace(output=Goods.food, is_trader=False,
                                       inv_get=lambda _good, _fallback: 10.0)
            region = SimpleNamespace(name='Delta', recipes={Goods.food: {
                'price': 2.0, 'maxinv': 10}}, _price_ref={Goods.food: 2.0},
                _trade_prices={}, agents=[producer], _collective_trace_clock=clock,
                _run_trace=trace, home_currency='D')
            update_price_ref(region, Goods.food, 5.0,
                             local_asks=1, imported_asks=0, bids=5)
            rise = trace.query(turn=1, metric_id='goods.price')['events'][0]
            self.assertGreater(rise['value_after'], rise['value_before'])
            self.assertTrue(replay_event(rise)['matches'])
            clock['turn'] = 2
            update_price_ref(region, Goods.food, 0.0,
                             local_asks=1, imported_asks=0, bids=0)
            fall = trace.query(turn=2, metric_id='goods.price')['events'][0]
            self.assertLess(fall['value_after'], fall['value_before'])
            self.assertTrue(replay_event(fall)['matches'])

    def test_cloth_quote_change_is_queryable_at_each_turn(self):
        from labor_frontier_market import _cloth_ask
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'cloth.ctr', 'cloth')
            clock = {'next': 1, 'turn': 1, 'phase': 'scenario_market'}
            region = SimpleNamespace(name='Mill', recipes={
                Goods.cloth: {'production': 3}, Goods.cotton: {'price': 3.0}},
                neighbors={}, home_currency='D', _collective_trace_clock=clock,
                _run_trace=trace)
            firm = SimpleNamespace(id='mill-1', wage=2.0, machinery_level=1,
                                   broken_machinery=0,
                                   cost_get=lambda _good, _fallback: 3.0)
            first = _cloth_ask(region, firm)
            clock['turn'] = 2
            firm.wage = 4.0
            second = _cloth_ask(region, firm)
            self.assertGreater(second, first)
            old_row = trace.query(turn=1, subject={'type': 'tile', 'id': 'Mill',
                                                    'good': 'cloth'},
                                  metric_id='goods.seller_ask')['events'][0]
            new_row = trace.query(turn=2, subject={'type': 'tile', 'id': 'Mill',
                                                    'good': 'cloth'},
                                  metric_id='goods.seller_ask')['events'][0]
            self.assertEqual((old_row['value_after'], new_row['value_after']),
                             (first, second))
            self.assertTrue(replay_event(old_row)['matches'])
            self.assertTrue(replay_event(new_row)['matches'])

    def test_dynamic_price_snapshot_and_read_only_death_sample(self):
        from trace_snapshots import sample
        tile = SimpleNamespace(name='Delta', recipes={Goods.cotton: {'price': 3.0}},
                               total_population=[4], deaths_this_turn=2,
                               deaths_by_cause_this_turn={'disease': 2},
                               protest_energy_log=[], unrest_log=[], agents=[],
                               construction_projects=[], cost_of_living=1.0,
                               surplus_value_log=[8.5])
        first = sample([tile], [])
        second = sample([tile], [])
        self.assertEqual(first, second)
        self.assertEqual(first[('goods.price', 'Delta', 'cotton')][2], 3.0)
        self.assertEqual(first[('labor.surplus_value', 'Delta')][2], 8.5)
        self.assertEqual(first[('labor.hungry_adults', 'Delta')][2], 0)
        self.assertEqual(first[('labor.temporary_work_share', 'Delta')][2], 0.0)
        self.assertEqual(tile.deaths_this_turn, 2)

    def test_nation_chart_aggregation_replays_current_tile_histories(self):
        from trace_snapshots import nation_chart_aggregation_rows

        def tile(name, serf, commons, gini, shift, accidents):
            return SimpleNamespace(
                name=name,
                home_currency='NRC' if name == 'North' else 'SRC',
                social_class_log=[{'serf': serf, 'proletarian': serf + 1}],
                food_foraged_log=[serf * 2], food_purchased_log=[serf],
                hungry_log={Goods.food: [serf], Goods.wood: [0],
                            Goods.furniture: [0], 'trader': [0]},
                tenure_log=[commons], rent_collected_log=[serf * 3],
                rent_arrears_log=[serf], gini_log={Goods.food: [gini]},
                protest_energy_log=[float(serf)], avg_shift_hours_log=[shift],
                rate_of_exploitation_log=[0.5], workday_cap_log=[10.0],
                avg_alienation_log=[0.2], avg_health_attrition_log=[0.1],
                workplace_accidents_log=[accidents], avg_consciousness_log=[0.4],
                entertainment_log=[0.3], strikers_log=[serf],
                broken_machinery_log=[1], sabotage_log=[1],
                export_value_log=[serf * 10], import_value_log=[serf * 4],
                net_trade_value_log=[serf * 6],
                market_chart_goods={Goods.wool},
                production_log={Goods.wool: [serf * 0.5]},
                inventory_log={Goods.wool: [serf * 2.0]},
                market_demand_ratio_chart_log={Goods.wool: [{
                    'turn': 1 if name == 'North' else 0,
                    'value': 2.25 if name == 'North' else 9.0,
                    'event_id': 10 if name == 'North' else 9}]},
                soil_fertility_log=[0.8 if name == 'North' else 1.0],
                nutrition_density_log=[0.6 if name == 'North' else 0.8],
                pollution_air_log=[4.0 if name == 'North' else 8.0],
                pollution_water_log=[3.0 if name == 'North' else 5.0],
                pollution_soil_log=[7.0 if name == 'North' else 9.0],
                disease_cases_log=[{
                    'malnutrition': serf, 'waterborne': serf + 1,
                    'respiratory': 0, 'chemical': 2}],
                untreated_cases_log=[serf],
                disease_fatalities_log=[serf // 2],
                medical_spending_private_log=[serf * 3],
                medical_spending_public_log=[serf * 2])

        nation = SimpleNamespace(name='Republic', tiles=[
            tile('North', 2, 0.5, 0.2, 8.0, 1),
            tile('South', 4, 1.0, 0.4, 10.0, 2)])
        shared_government = SimpleNamespace(
            name='Shared Provincial Government',
            income_log=[{'turn': 1, 'tax': 10.0, 'tariff': 2.0,
                         'inheritance': 1.0}])
        for member in nation.tiles:
            member.gov = shared_government
        rows = nation_chart_aggregation_rows(nation, turn=1)
        by_series = {(row['inputs']['chart_family'],
                      row['inputs']['chart_series']): row for row in rows}
        self.assertEqual(by_series[('citizen', 'serf')]['after'], 6.0)
        self.assertEqual(by_series[('citizen', 'hungry')]['after'], 6.0)
        self.assertEqual(by_series[('citizen', 'avg commons %')]['after'], 0.75)
        self.assertAlmostEqual(by_series[('citizen', 'avg gini (x100)')]['after'],
                               0.3)
        self.assertEqual(by_series[('labor', 'avg shift hrs')]['after'], 9.0)
        self.assertEqual(by_series[('labor', 'accidents')]['after'], 3.0)
        self.assertEqual(by_series[('trade', 'exports')]['after'], 60.0)
        self.assertEqual(by_series[('trade', 'imports')]['after'], 24.0)
        self.assertEqual(by_series[('trade', 'net')]['after'], 36.0)
        self.assertEqual(
            by_series[('market_production', 'wool')]['after'], 3.0)
        self.assertEqual(
            by_series[('market_inventory', 'wool')]['after'], 12.0)
        wool_ratio = by_series[('market_demand_ratio', 'wool')]
        self.assertEqual(wool_ratio['after'], 2.25)
        self.assertEqual(wool_ratio['inputs']['reducer'], 'mean')
        self.assertEqual(wool_ratio['inputs']['coverage_count'], 1)
        self.assertEqual(
            [row['value'] for row in wool_ratio['inputs']['member_contributions']],
            [2.25, None])
        self.assertAlmostEqual(by_series[('ecology', 'soil')]['after'], 0.9)
        self.assertAlmostEqual(
            by_series[('ecology', 'nutrition')]['after'], 0.7)
        self.assertEqual(by_series[('ecology', 'smog')]['after'], 6.0)
        self.assertEqual(
            by_series[('health', 'malnutrition cases')]['after'], 6.0)
        self.assertEqual(by_series[('health', 'untreated')]['after'], 6.0)
        self.assertEqual(by_series[('health', 'fatalities')]['after'], 3.0)
        outlays = by_series[('health', 'outlays')]
        self.assertEqual(outlays['after'], 30.0)
        self.assertTrue(outlays['inputs']['unconverted_mixed_currency'])
        self.assertFalse(outlays['inputs']['currency_conversion_applied'])
        government_income = by_series[('government', 'income')]
        self.assertEqual(government_income['after'], 13.0)
        self.assertEqual(government_income['inputs']['government_count'], 1)
        self.assertEqual(
            [row['government_income_contribution'] for row in
             government_income['inputs']['member_contributions']],
            ['counted_once', 'duplicate_shared_government_snapshot'])
        self.assertIn('no FX conversion',
                      government_income['inputs']['contribution_policy'])
        net_trade = by_series[('trade', 'net')]
        self.assertEqual(net_trade['inputs']['member_currencies'], ['NRC', 'SRC'])
        self.assertTrue(net_trade['inputs']['unconverted_mixed_currency'])
        self.assertEqual(
            net_trade['inputs']['currency_semantics'],
            'raw member-tile local-currency sum without conversion')
        self.assertEqual(
            by_series[('citizen', 'rent ($)')]['inputs']['currency_conversion_applied'],
            False)

    def test_latest_metric_calculation_link_is_turn_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'metric-link.ctr', 'metric-link')
            clock = {'turn': 1, 'phase': 'local', 'next': 1}
            subject = {'type': 'tile', 'id': 'North'}
            event_id = trace.emit(
                clock, kind='sample_calculation', record_class='calculation',
                subject=subject, metric_id='people.hungry', after=4)
            self.assertEqual(trace.latest_metric_calculation_event_id(
                'people.hungry', subject), event_id)
            clock.update(turn=2, next=2)
            trace.emit(clock, kind='sample_calculation',
                       record_class='calculation', subject=subject,
                       metric_id='people.hungry', after=3)
            self.assertNotEqual(trace.latest_metric_calculation_event_id(
                'people.hungry', subject), event_id)
            clock.update(turn=3, next=3)
            observation_id = trace.emit(
                clock, kind='metric_snapshot', record_class='observation',
                subject=subject, metric_id='health.fatalities', after=0)
            self.assertEqual(trace.latest_metric_event_id(
                'health.fatalities', subject), observation_id)
            self.assertIsNone(trace.latest_metric_calculation_event_id(
                'health.fatalities', subject))

    def test_scenario_quote_replays_and_paid_price_is_separate(self):
        from sim_server.sim_server import SimServer
        server = SimServer(seed=613, terrain_seed=613, nation_seed=613,
                           scenario_id='labor_frontier_rivalry')
        server.step()
        asks = server.run_trace.query(turn=1, metric_id='goods.seller_ask',
                                      limit=10000)['events']
        self.assertTrue(any(row['subject']['good'] == 'cloth' for row in asks))
        self.assertTrue(any(row['subject']['good'] == 'cotton' for row in asks))
        self.assertTrue(all(replay_event(row)['matches'] for row in asks))
        delivered = server.run_trace.query(turn=1, metric_id='goods.delivered_quote',
                                           limit=10000)['events']
        self.assertTrue(all(replay_event(row)['matches'] for row in delivered))
        paid = server.run_trace.query(turn=1, metric_id='goods.transaction_price',
                                      limit=10000)['events']
        self.assertTrue(paid)
        self.assertTrue(all(row['value_after'] > 0 for row in paid))
        all_rows = server.run_trace.query(limit=100000)['events']
        rows_by_id = {row['event_id']: row for row in all_rows}
        tiles_by_name = {tile.name: tile for tile in server.tiles}
        scenario_delivered = [row for row in delivered
                              if row['kind'] in (
                                  'scenario_cotton_delivered_quote',
                                  'scenario_cloth_delivered_quote')]
        scenario_paid = [row for row in paid
                         if row['kind'] in ('scenario_cotton_paid_price',
                                            'scenario_cloth_paid_price')]
        self.assertTrue(scenario_delivered)
        self.assertTrue(scenario_paid)
        for quote in scenario_delivered:
            self.assertEqual(quote['turn'], 1)
            inputs = quote['inputs']
            self.assertFalse(inputs['currency_conversion_applied'])
            self.assertIn('currency', inputs)
            origin = tiles_by_name[inputs['origin_tile']]
            destination = tiles_by_name[inputs['destination_tile']]
            self.assertEqual(inputs['seller_nation_at_quote'],
                             origin.owner_nation.name)
            self.assertEqual(inputs['buyer_nation_at_quote'],
                             destination.owner_nation.name)
            self.assertEqual(inputs['seller_currency'], origin.home_currency)
            self.assertEqual(inputs['buyer_currency'], destination.home_currency)
            self.assertEqual(inputs['counterparty_currency_mismatch'],
                             origin.home_currency != destination.home_currency)
            self.assertEqual(len(quote['cause_event_ids']), 1)
            ask = rows_by_id[quote['cause_event_ids'][0]]
            self.assertEqual(ask['metric_id'], 'goods.seller_ask')
            self.assertEqual(ask['subject']['good'], quote['subject']['good'])
            self.assertEqual(ask['turn'], quote['turn'])
            self.assertEqual(ask['inputs']['currency'], quote['inputs']['currency'])
            self.assertEqual(ask['inputs']['seller_nation_at_quote'],
                             inputs['seller_nation_at_quote'])
        self.assertTrue(all(row.get('inputs', {}).get('selected_quote_event_id')
                            for row in scenario_paid))
        for transaction in scenario_paid:
            quote_id = transaction['inputs']['selected_quote_event_id']
            self.assertEqual(transaction['cause_event_ids'], [quote_id])
            quote = rows_by_id[quote_id]
            self.assertEqual(quote['metric_id'], 'goods.delivered_quote')
            self.assertEqual(quote['subject']['good'], transaction['subject']['good'])
            self.assertEqual(quote['subject']['seller_id'],
                             transaction['subject']['seller_id'])
            self.assertEqual(quote['subject']['buyer_id'],
                             transaction['subject']['buyer_id'])
            self.assertLess(quote['sequence'], transaction['sequence'])
            self.assertEqual(quote['turn'], transaction['turn'])
            self.assertEqual(transaction['inputs']['quote_turn'], transaction['turn'])
            self.assertEqual(quote['inputs']['currency'],
                             transaction['inputs']['currency'])
            self.assertEqual(quote['value_after'], transaction['value_after'])
            self.assertFalse(transaction['inputs']['currency_conversion_applied'])
            origin = tiles_by_name[transaction['inputs']['origin_tile']]
            destination = tiles_by_name[transaction['inputs']['destination_tile']]
            self.assertEqual(transaction['inputs']['seller_nation_at_quote'],
                             origin.owner_nation.name)
            self.assertEqual(transaction['inputs']['buyer_nation_at_quote'],
                             destination.owner_nation.name)
            self.assertEqual(transaction['inputs']['seller_currency'],
                             origin.home_currency)
            self.assertEqual(transaction['inputs']['buyer_currency'],
                             destination.home_currency)
            for field in ('origin_tile', 'destination_tile',
                          'seller_nation_at_quote', 'buyer_nation_at_quote',
                          'seller_currency', 'buyer_currency',
                          'counterparty_currency_mismatch',
                          'currency_conversion_applied'):
                self.assertEqual(transaction['inputs'][field],
                                 quote['inputs'][field])

    def test_scenario_market_histories_replay_paid_prices_and_keep_mix(self):
        from sim_server.sim_server import SimServer

        server = SimServer(seed=619, terrain_seed=619, nation_seed=619,
                           scenario_id='labor_frontier_rivalry')
        server.step()
        server.step()
        coverage = server.run_trace.query(
            turn=1, metric_id='goods.scenario_market_coverage',
            limit=10000)['events']
        self.assertEqual(len(coverage), len(server.nations) * 2)
        self.assertTrue(all(replay_event(row)['matches'] for row in coverage))
        coverage_by_market = {
            (row['subject']['id'], row['subject']['good']): row
            for row in coverage}

        prices = server.run_trace.query(
            turn=1, metric_id='goods.scenario_transaction_vwap',
            limit=10000)['events']
        all_events = server.run_trace.query(limit=100000)['events']
        by_id = {row['event_id']: row for row in all_events}
        for row in prices:
            self.assertTrue(replay_event(row)['matches'])
            inputs = row['inputs']
            key = (row['subject']['id'], row['subject']['good'])
            coverage_row = coverage_by_market[key]
            self.assertIn(coverage_row['event_id'], row['cause_event_ids'])
            self.assertFalse(inputs['currency_conversion_applied'])
            nation = next(n for n in server.nations if n.name == key[0])
            self.assertEqual(inputs['destination_territory_membership'],
                             sorted(tile.name for tile in nation.tiles))
            self.assertEqual(inputs['quantity'], coverage_row['value_after'])
            paid_rows = [by_id[trade['event_id']]
                         for trade in inputs['transactions']]
            self.assertTrue(all(event['kind'] in (
                'scenario_cotton_paid_price', 'scenario_cloth_paid_price')
                for event in paid_rows))
            self.assertTrue(all(event_id in row['cause_event_ids']
                                for event_id in (e['event_id'] for e in paid_rows)))
            self.assertEqual(inputs['total_paid'], sum(
                event['value_after'] * trade['quantity']
                for event, trade in zip(paid_rows, inputs['transactions'])))

        scenario_info = server.serialize_world()['scenario_info']
        self.assertEqual(len(scenario_info['market_history']), len(server.nations))
        for market in scenario_info['market_history']:
            self.assertIn(market['nation'], {n.name for n in server.nations})
            self.assertEqual(set(market['markets']), {'cotton', 'cloth'})
            for points in market['markets'].values():
                self.assertEqual([point['turn'] for point in points], [1, 2])
                for point in points:
                    self.assertEqual(point['currency_conversion_applied'], False)
                    if point['quantity']:
                        self.assertIsNotNone(point['price'])
                        self.assertEqual(point['trace_metric_id'],
                                         'goods.scenario_transaction_vwap')
                    else:
                        self.assertIsNone(point['price'])
                        self.assertEqual(point['trace_metric_id'],
                                         'goods.scenario_market_coverage')
                previous, current = points
                if (previous['price'] is not None and current['price'] is not None
                        and current['currency_membership_stable']):
                    self.assertIsNotNone(current['national_market_price_change'])
                    self.assertEqual(
                        current['territory_membership_changed'],
                        current['territory_membership']
                        != previous['territory_membership'])

    def test_scenario_market_history_does_not_depend_on_trace_recorder(self):
        from labor_frontier_market import _record_scenario_market_prices

        tile = SimpleNamespace(name='Mill District', _run_trace=None,
                               _collective_trace_clock=None)
        nation = SimpleNamespace(name='Meridian', currency='MRC', tiles=[tile])
        tile.owner_nation = nation
        world = {'scenario_state': {}, 'currencies': ['MRC'],
                 'nations': [nation], 'tiles': [tile]}
        purchases = [{
            'destination_nation': 'Meridian', 'trace_event_id': None,
            'paid_price': 3.5, 'quantity': 1, 'origin': 'Cotton District',
            'mill': 'Mill District', 'seller_nation': 'Meridian',
            'currency': 'MRC'}]

        _record_scenario_market_prices(world, 1, purchases, [])

        point = world['scenario_state']['market_price_history'][
            'Meridian']['cotton'][0]
        self.assertEqual(point['price'], 3.5)
        self.assertEqual(point['quantity'], 1)
        self.assertEqual(point['trace_event_id'], None)
        self.assertEqual(point['trace_metric_id'],
                         'goods.scenario_transaction_vwap')
    def test_fx_formula_records_reserves_and_ppp(self):
        from forex import ForexDesk
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'run.ctr', 'fx-fixture')
            clock = {'next': 1, 'turn': 4, 'phase': 'forex'}
            region = SimpleNamespace(name='Delta', _collective_trace_clock=clock,
                                     _run_trace=trace)
            bank = SimpleNamespace(total_deposits=100.0, fx_pool=20.0,
                                   foreign_reserves={'B': 10.0})
            desk = ForexDesk('A', 'B', bank=bank, seed_reserves=False,
                             target_reserves=20.0)
            desk.update(4, bank=bank, ppp_target=1.1, trace_region=region)
            row = trace.query(metric_id='fx.bilateral_mid')['events'][0]
            self.assertEqual(row['inputs']['reserve_ratio'], 0.5)
            self.assertEqual(row['turn'], 4)
            self.assertAlmostEqual(row['value_after'], desk.mid)

    def test_live_server_records_price_and_unrest(self):
        from sim_server.sim_server import SimServer
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           scenario_id='labor_frontier_rivalry')
        from metric_catalog import inventory_region_histories
        inventory = {row['field']: row for row in inventory_region_histories(server.tiles[0])}
        self.assertEqual(inventory['gdp_log']['coverage'], 'instrumented')
        for field in ('bank_cash_log', 'total_cash_log', 'demand_ratio_log',
                      'market_demand_ratio_chart_log', 'population_log',
                      'collective_log', 'grievance_sources_log', 'trade_flow_log',
                      'pasture_fraction_log', 'population_change_rate_log',
                      'trader_cash_log', 'pipeline_depth_log'):
            self.assertEqual(inventory[field]['coverage'], 'instrumented', field)
        self.assertEqual(inventory['surplus_value_log']['coverage'], 'instrumented')
        server.step()
        rows = server.run_trace.query(turn=1, limit=10000)['events']
        kinds = {row['kind'] for row in rows}
        self.assertIn('market_price_update', kinds)
        self.assertIn('unrest_roll', kinds)
        self.assertTrue(all(row['turn'] == 1 for row in rows))
        rows_by_id = {row['event_id']: row for row in rows}
        firm_surplus = [row for row in rows
                        if row.get('kind') == 'firm_surplus_value_calculation']
        tile_surplus = [row for row in rows
                        if row.get('kind') == 'labor_surplus_value_calculation']
        self.assertTrue(firm_surplus)
        self.assertTrue(tile_surplus)
        self.assertTrue(all(row['formula_replay']['matches']
                            for row in firm_surplus + tile_surplus))
        for row in firm_surplus:
            self.assertTrue(row.get('cause_event_ids'))
            self.assertTrue(all(event_id in rows_by_id
                                for event_id in row['cause_event_ids']))
        self.assertTrue(all(row['inputs']['turn'] == 1
                            for row in firm_surplus))
        firm_surplus_ids = {row['event_id'] for row in firm_surplus}
        for row in tile_surplus:
            expected_causes = [firm['source_event_id']
                               for firm in row['inputs']['firms']
                               if firm.get('included_in_current_turn')
                               and firm.get('source_event_id') is not None]
            self.assertEqual(row.get('cause_event_ids', []), expected_causes)
            self.assertTrue(set(expected_causes).issubset(firm_surplus_ids))
        bank_equity_rows = [row for row in rows
                            if row.get('kind') == 'bank_equity_calculation']
        total_cash_rows = [row for row in rows
                           if row.get('kind') == 'total_cash_calculation']
        self.assertTrue(bank_equity_rows)
        self.assertTrue(total_cash_rows)
        self.assertTrue(all(row['formula_replay']['matches']
                            for row in bank_equity_rows + total_cash_rows))
        for row in bank_equity_rows:
            tile = next(tile for tile in server.tiles
                        if tile.name == row['subject']['id'])
            self.assertEqual(row['value_after'], tile.bank_cash_log[-1])
        for row in total_cash_rows:
            tile = next(tile for tile in server.tiles
                        if tile.name == row['subject']['id'])
            self.assertEqual(row['value_after'], tile.total_cash_log[-1])
        history_metrics = (
            ('land.pasture_fraction', 'pasture_fraction_log'),
            ('people.population_change_rate', 'population_change_rate_log'),
            ('trade.trader_cash', 'trader_cash_log'),
            ('trade.pipeline_depth', 'pipeline_depth_log'))
        for metric_id, field in history_metrics:
            metric_rows = [row for row in rows
                           if row.get('metric_id') == metric_id
                           and row.get('formula_id') is not None]
            self.assertTrue(metric_rows, metric_id)
            self.assertTrue(all(row['formula_replay']['matches']
                                for row in metric_rows), metric_id)
            for row in metric_rows:
                tile = next(tile for tile in server.tiles
                            if tile.name == row['subject']['id'])
                self.assertAlmostEqual(row['value_after'],
                                       float(getattr(tile, field)[-1]))
        from trace_snapshots import sample
        snapshot_values = sample(server.tiles, server.nations)
        from innovation import get_innovation_system
        innovation_system = get_innovation_system()
        learning_rows = [row for row in rows
                         if row.get('kind') == 'innovation_learning_calculation']
        self.assertEqual(len(learning_rows), len(server.nations) * 5)
        self.assertTrue(all(row['formula_replay']['matches'] for row in learning_rows))
        for row in learning_rows:
            nation_name = row['subject']['id']
            domain = row['subject']['domain']
            self.assertEqual(row['value_after'],
                             innovation_system.domain_experience[nation_name][domain])
            self.assertEqual(snapshot_values[(
                'innovation.domain_experience', nation_name, domain)][2], row['value_after'])
        for metric_id, field in history_metrics:
            for tile in server.tiles:
                history = getattr(tile, field, ())
                if history:
                    self.assertAlmostEqual(
                        snapshot_values[(metric_id, tile.name)][2],
                        float(history[-1]))
        buyer_orders = [row for row in rows
                        if row['kind'] == 'market_buyer_order_submitted']
        seller_orders = [row for row in rows
                         if row['kind'] == 'market_seller_order_submitted']
        pressure_rows = [row for row in rows
                         if row['kind'] == 'market_demand_supply_ratio']
        nation_chart_rows = [row for row in rows
                             if row['kind'] == 'nation_chart_history_aggregate']
        market_totals = [row for row in rows
                         if row['kind'] in ('market_demand_total',
                                            'market_supply_total',
                                            'market_demand_supply_ratio')]
        zero_order_summaries = [row for row in rows
                                if row['kind'] == 'market_zero_order_summary']
        self.assertTrue(buyer_orders)
        self.assertTrue(seller_orders)
        self.assertTrue(pressure_rows)
        self.assertTrue(nation_chart_rows)
        worker_aggregate = next(
            row for row in nation_chart_rows
            if row['metric_id'] == 'society.class_population'
            and row['subject'].get('class_group') == 'worker')
        self.assertEqual(worker_aggregate['formula_id'], 'aggregate.sum.v1')
        self.assertTrue(replay_event(worker_aggregate)['matches'])
        self.assertTrue(worker_aggregate['inputs']['member_values'])
        self.assertTrue(worker_aggregate['inputs']['member_contributions'])
        self.assertTrue(worker_aggregate['cause_event_ids'])
        self.assertTrue(zero_order_summaries)
        self.assertTrue(all(replay_event(row)['matches'] for row in pressure_rows))
        self.assertTrue(all(row['formula_replay']['matches']
                            for row in market_totals))
        labor_constrained_output = [row for row in rows
                                    if row['kind'] == 'firm_production_zero'
                                    and row.get('cause_event_ids')]
        self.assertTrue(labor_constrained_output)
        for production in labor_constrained_output:
            workforce = rows_by_id[production['cause_event_ids'][0]]
            self.assertEqual(workforce['metric_id'], 'labor.available_worker_hours')
        for summary in zero_order_summaries:
            inputs = summary['inputs']
            reasons = [group['reason'] for group in
                       inputs['buyers_by_reason'] + inputs['sellers_by_reason']]
            evidence = [order for groups in
                        (inputs['buyers_by_reason'], inputs['sellers_by_reason'])
                        for group in groups for order in group['orders']]
            self.assertNotIn('positive_quantity', reasons)
            self.assertTrue(all('agent_id' in order for order in evidence))
            self.assertEqual(
                sum(group['count'] for group in inputs['buyers_by_reason']),
                inputs['zero_buyer_count'])
            self.assertEqual(
                sum(group['count'] for group in inputs['sellers_by_reason']),
                inputs['zero_seller_count'])

            related = [row for row in rows
                       if row.get('subject') == summary.get('subject')]
            if inputs['zero_buyer_count']:
                demand_total = next(row for row in related
                                    if row['kind'] == 'market_demand_total')
                self.assertIn(summary['event_id'],
                              demand_total.get('cause_event_ids', []))
            if inputs['zero_seller_count']:
                supply_total = next(row for row in related
                                    if row['kind'] == 'market_supply_total')
                self.assertIn(summary['event_id'],
                              supply_total.get('cause_event_ids', []))
            for production_id in inputs.get('seller_production_event_ids', ()):
                self.assertIn(production_id, summary.get('cause_event_ids', []))
                self.assertEqual(rows_by_id[production_id]['metric_id'],
                                 'goods.production')
            for funding_event_id in inputs.get(
                    'buyer_cash_funding_event_ids', ()):
                self.assertIn(funding_event_id, summary.get('cause_event_ids', []))
                self.assertEqual(rows_by_id[funding_event_id]['kind'],
                                 'bank_withdrawal_posted')
            for group in inputs['buyers_by_reason']:
                for zero_order in group['orders']:
                    self.assertIn('cash_funding_event_ids', zero_order)
                    self.assertIn('cash_affordable_units_at_bid', zero_order)
                    self.assertIn('cash_affordability_formula_id', zero_order)
                    if zero_order['cash_affordability_basis'] == 'remainingCash':
                        self.assertEqual(
                            zero_order['cash_affordability_formula_id'],
                            'market.cash_affordability_ceiling.v1')
                    for funding_event_id in zero_order['cash_funding_event_ids']:
                        self.assertEqual(rows_by_id[funding_event_id]['kind'],
                                         'bank_withdrawal_posted')
        self.assertTrue(any(
            rows_by_id.get(production_id, {}).get('kind') == 'firm_production_zero'
            for summary in zero_order_summaries
            for production_id in summary['inputs'].get(
                'seller_production_event_ids', ())))
        for order in seller_orders + buyer_orders:
            self.assertEqual(order['confidence'], 'exact')
        for order in buyer_orders:
            funding_event_ids = order['inputs'].get('cash_funding_event_ids', [])
            for funding_event_id in funding_event_ids:
                self.assertIn(funding_event_id, order.get('cause_event_ids', []))
                self.assertEqual(rows_by_id[funding_event_id]['kind'],
                                 'bank_withdrawal_posted')
        self.assertTrue(any(
            order['inputs'].get('current_turn_production_event_id') in rows_by_id
            and order['inputs']['current_turn_production_event_id']
            in order.get('cause_event_ids', [])
            for order in seller_orders))
        self.assertTrue(any(
            any(rows_by_id.get(event_id, {}).get('kind') == 'market_demand_total'
                for event_id in row.get('cause_event_ids', []))
            and any(rows_by_id.get(event_id, {}).get('kind') == 'market_supply_total'
                    for event_id in row.get('cause_event_ids', []))
            for row in pressure_rows))
        self.assertTrue(any(
            rows_by_id.get(event_id, {}).get('kind') == 'market_demand_supply_ratio'
            for row in rows if row['kind'] == 'market_price_update'
            for event_id in row.get('cause_event_ids', [])))
        for _ in range(5):
            server.step()
        self.assertEqual(server.turn, 6)
        self.assertTrue(server.run_trace.query(turn=6, metric_id='goods.price')['events'])
        self.assertEqual(verify(server.run_trace.path)['checkpoints'], 6)
        all_rows = server.run_trace.query(limit=100000)['events']
        all_rows_by_id = {row['event_id']: row for row in all_rows}
        basket_calculations = [row for row in all_rows
                               if row['kind'] == 'cost_of_living_calculation']
        self.assertTrue(basket_calculations)
        self.assertTrue(all(replay_event(row)['matches']
                            for row in basket_calculations))
        self.assertTrue(all(row['inputs']['basket_component_prices']
                            and row['inputs']['currency']
                            for row in basket_calculations))
        second_turn_baskets = [row for row in basket_calculations
                               if row['turn'] == 2]
        self.assertTrue(second_turn_baskets)
        for basket in second_turn_baskets:
            component_event_ids = basket['inputs']['component_price_event_ids']
            self.assertEqual(set(component_event_ids),
                             {'food', 'wood', 'furniture'})
            for event_id in component_event_ids.values():
                self.assertIsNotNone(event_id)
                self.assertIn(event_id, basket.get('cause_event_ids', []))
                self.assertLess(all_rows_by_id[event_id]['turn'], basket['turn'])
        national_baskets = [row for row in all_rows
                            if row['kind'] == 'national_aggregate'
                            and row.get('metric_id') == 'living.cost_of_living']
        self.assertTrue(national_baskets)
        for aggregate in national_baskets:
            self.assertTrue(replay_event(aggregate)['matches'])
            inputs = aggregate['inputs']
            self.assertFalse(inputs['currency_conversion_applied'])
            self.assertIn('territory_membership', inputs)
            self.assertIn('territorial_composition_residual', inputs)
            for member in inputs['territory_membership']:
                event_id = member['basket_calculation_event_id']
                self.assertIsNotNone(event_id)
                self.assertIn(event_id, aggregate.get('cause_event_ids', []))
        national_prices = [row for row in all_rows
                           if row['kind'] == 'national_reference_price_aggregate']
        self.assertTrue(national_prices)
        for aggregate in national_prices:
            self.assertTrue(replay_event(aggregate)['matches'])
            inputs = aggregate['inputs']
            self.assertFalse(inputs['currency_conversion_applied'])
            self.assertEqual(inputs['coverage_count'],
                             len(inputs['member_price_records']))
            self.assertTrue(inputs['territory_membership'])
            for member in inputs['member_price_records']:
                event_id = member['source_price_event_id']
                if event_id is not None:
                    self.assertIn(event_id, aggregate.get('cause_event_ids', []))
                    self.assertEqual(all_rows_by_id[event_id]['metric_id'],
                                     'goods.price')
        food_history_aggregates = [row for row in all_rows
                                   if row['kind'] ==
                                   'national_food_price_history_aggregate']
        self.assertTrue(food_history_aggregates)
        self.assertTrue(all(replay_event(row)['matches']
                            for row in food_history_aggregates))
        latest_food_history = {
            row['subject']['id']: row['value_after']
            for row in food_history_aggregates if row['turn'] == server.turn}
        for nation in server.nations:
            self.assertAlmostEqual(
                round(latest_food_history[nation.name], 2),
                server._nation_history[nation.name]['food_price'][-1])
        latest_food_means = {
            row['subject']['id']: row['value_after']
            for row in national_prices if row['subject']['good'] == 'food'
            and row['turn'] == server.turn}
        for nation in server.nations:
            self.assertAlmostEqual(
                round(latest_food_means[nation.name], 2),
                server._nation_history[nation.name]['food_price'][-1])
        departures = [row for row in all_rows
                      if row['kind'] == 'route_shipment_departure']
        arrivals = [row for row in all_rows
                    if row['kind'] == 'route_shipment_arrival']
        self.assertTrue(departures)
        self.assertTrue(arrivals)
        pipeline_rows = [row for row in all_rows
                         if row['kind'] == 'trade_pipeline_depth_calculation']
        self.assertTrue(pipeline_rows)
        for pipeline in pipeline_rows:
            self.assertTrue(pipeline['formula_replay']['matches'])
            self.assertEqual(pipeline['value_after'], sum(
                shipment['quantity'] for shipment in
                pipeline['inputs']['shipments']))
            for shipment in pipeline['inputs']['shipments']:
                departure_id = shipment.get('departure_event_id')
                if departure_id is not None:
                    self.assertIn(departure_id,
                                  pipeline.get('cause_event_ids', []))
                    self.assertEqual(
                        all_rows_by_id[departure_id]['subject']['id'],
                        shipment['shipment_id'])
        for shipment_event in departures + arrivals:
            self.assertEqual(shipment_event['metric_id'],
                             'trade.shipment_quantity')
            self.assertEqual(shipment_event['value_after'],
                             shipment_event['inputs']['quantity'])
        self.assertTrue(any(row.get('inputs', {}).get('source_acquisition_event_ids')
                            and row['inputs']['source_acquisition_event_ids']
                            for row in departures))
        for departure in departures:
            for event_id in departure.get('inputs', {}).get(
                    'source_acquisition_event_ids', ()):
                self.assertIn(event_id, departure.get('cause_event_ids', []))
                self.assertIn(event_id, all_rows_by_id)
        for arrival in arrivals:
            departure_id = arrival['inputs']['departure_event_id']
            self.assertEqual(arrival['inputs']['departure_link_status'], 'linked')
            self.assertIn(departure_id, arrival.get('cause_event_ids', []))
            self.assertEqual(all_rows_by_id[departure_id]['kind'],
                             'route_shipment_departure')
        freight_rows = [row for row in all_rows
                        if row['kind'] == 'route_freight_settlement']
        self.assertTrue(freight_rows)
        for freight in freight_rows:
            self.assertEqual(freight['metric_id'],
                             'trade.route_freight_settlement')
            self.assertEqual(freight['value_after'],
                             freight['inputs']['amount'])
            self.assertIn(freight['inputs']['operation_id'].removeprefix('freight:'),
                          {row['subject']['id'] for row in departures})
        imported_supply = [row for row in all_rows
                           if row['kind'] == 'market_supply_total'
                           and any(lot.get('arrival_event_id') for lot in
                                   row.get('inputs', {}).get('import_lots', []))]
        self.assertTrue(imported_supply)
        for supply in imported_supply:
            for lot in supply['inputs']['import_lots']:
                arrival_id = lot.get('arrival_event_id')
                if arrival_id is not None:
                    self.assertIn(arrival_id, supply.get('cause_event_ids', []))
                    self.assertEqual(all_rows_by_id[arrival_id]['kind'],
                                     'route_shipment_arrival')
        imported_quotes = [row for row in all_rows
                           if row['kind'] == 'import_delivered_quote'
                           and row.get('inputs', {}).get('arrival_event_id')]
        self.assertTrue(imported_quotes)
        for quote in imported_quotes:
            self.assertIn(quote['inputs']['arrival_event_id'],
                          quote.get('cause_event_ids', []))
        imported_sales = [row for row in all_rows
                          if row['kind'] == 'paid_market_sale'
                          and row.get('inputs', {}).get('imported')]
        self.assertTrue(imported_sales)
        quote_ids = {row['event_id'] for row in imported_quotes}
        self.assertTrue(any(quote_ids.intersection(row.get('cause_event_ids', []))
                            for row in imported_sales))
        price_rows = server.run_trace.query(metric_id='goods.price', limit=10000)['events']
        replayed = [replay_event(row) for row in price_rows]
        self.assertTrue(all(result['matches'] for result in replayed if result))
        self.assertTrue(any(row['kind'] == 'price_bridge' for row in price_rows))
        for metric in ('goods.seller_ask', 'goods.delivered_quote'):
            quotes = server.run_trace.query(metric_id=metric, limit=10000)['events']
            self.assertTrue(all(replay_event(row)['matches'] for row in quotes
                                if replay_event(row)))

    def test_pipeline_history_links_in_transit_cargo_and_excludes_other_pools(self):
        from region import Region
        from transporter import Route

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'pipeline.ctr', 'pipeline')
            source = Region('Upland', t=0, number_of_agents=0)
            destination = SimpleNamespace(name='Lowland')
            source._run_trace = trace
            source._collective_trace_clock = {
                'turn': 1, 'phase': 'trade', 'next': 1}
            trader = Agent(0)
            initialize_agent(trader, Goods.food, 0, 0, 12.5)
            trader.is_trader = True
            source.agents = source.trader_agents = [trader]
            route = Route('Upland->Lowland', source, destination, base_delay=2)
            source.routes = {destination.name: route}
            for good, quantity in ((Goods.food, 4), (Goods.furniture, 2),
                                   (Goods.cotton, 3)):
                trader.inventory_export[good.value] = quantity
                route.post(trader, good, quantity)
            route.deliver_pending()
            trader.inventory_export[Goods.wood.value] = 5
            route.post(trader, Goods.wood, 5)

            source._log_metrics(1)

            row = next(row for row in trace.recent
                       if row.get('metric_id') == 'trade.pipeline_depth')
            self.assertEqual(source.pipeline_depth_log[-1], 6)
            self.assertEqual(row['value_after'], 6)
            self.assertTrue(row['formula_replay']['matches'])
            self.assertEqual({shipment['good'] for shipment in
                              row['inputs']['shipments']}, {'food', 'furniture'})
            self.assertEqual(len(row['cause_event_ids']), 2)
            self.assertTrue(all(shipment['departure_event_id'] in
                                row['cause_event_ids'] for shipment in
                                row['inputs']['shipments']))
            self.assertEqual(len(route.pending), 1)
            cash_row = next(row for row in trace.recent
                            if row.get('metric_id') == 'trade.trader_cash')
            self.assertEqual(cash_row['value_after'], 12.5)
            self.assertTrue(cash_row['formula_replay']['matches'])

    def test_population_rate_replays_full_and_incomplete_windows(self):
        from micro.region.stepper import log_population_rate

        cases = (([100] * 9 + [125], 25.0, 'full_window'),
                 ([100] * 9 + [80], -20.0, 'full_window'),
                 ([0] * 9 + [4], 0.0, 'zero_baseline'),
                 ([100, 125], 0.0, 'insufficient_history'))
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'growth.ctr', 'growth')
            clock = {'turn': 1, 'phase': 'local', 'next': 1}
            for index, (samples, expected, status) in enumerate(cases, 1):
                clock['turn'] = index
                region = SimpleNamespace(
                    name='Delta', total_population=samples,
                    population_change_rate_log=[], _run_trace=trace,
                    _collective_trace_clock=clock)
                log_population_rate(region, turn=index)
                row = trace.recent[-1]
                self.assertEqual(region.population_change_rate_log, [expected])
                self.assertEqual(row['value_after'], expected)
                self.assertEqual(row['inputs']['window_status'], status)
                self.assertTrue(row['formula_replay']['matches'])

    def test_wilderness_telemetry_records_zero_trader_and_pipeline_stocks(self):
        from region import Region

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'wilderness.ctr', 'wilderness')
            region = Region('Frontier', t=0, wilderness=True,
                            wilderness_pop=30)
            region._run_trace = trace
            region._collective_trace_clock = {
                'turn': 1, 'phase': 'local', 'next': 1}

            region.step(1)

            rows = [row for row in trace.recent
                    if row.get('metric_id') in (
                        'trade.trader_cash', 'trade.pipeline_depth',
                        'people.population_change_rate')
                    and row.get('formula_id') is not None]
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row['formula_replay']['matches'] for row in rows))
            self.assertTrue(all(row['value_after'] == 0 for row in rows))
            growth = next(row for row in rows
                          if row['metric_id'] == 'people.population_change_rate')
            self.assertEqual(growth['formula_id'],
                             'population.rate_wilderness_zero.v1')

    def test_career_switch_emits_typed_trace_event(self):
        import agent as agent_mod
        from labor_choice import apply_career_switch
        saved_id = agent_mod._agentid_counter[0]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                trace = RunTrace(Path(tmp) / 'career.ctr', 'career-fixture')
                clock = {'next': 1, 'turn': 12, 'phase': 'local'}
                region = SimpleNamespace(name='Delta', _collective_trace_clock=clock,
                                         _run_trace=trace)
                worker = Agent(42)
                initialize_agent(worker, Goods.food, 0, 0, 0)
                worker.birth_round = -10
                worker.last_career_switch = 4
                switched = apply_career_switch(
                    region, worker, Goods.wood, 12,
                    reason='INDEPENDENT_SWITCH',
                    formula_id='labor.career_switch.v2',
                    inputs={'current_income': 1.2, 'target_income': 2.5},
                    constraints={'min_cooldown_turns': 4},
                )
                self.assertTrue(switched)
                self.assertEqual(worker.output, Goods.wood)
                self.assertEqual(worker.last_career_switch, 12)
                self.assertEqual(worker.mem_last('mem_career_history'), 'food')
                rows = trace.query(turn=12, metric_id='labor.occupation_change')['events']
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row['value_before'], 'food')
                self.assertEqual(row['value_after'], 'wood')
                self.assertEqual(row['inputs']['prior_tenure'], 8)
                self.assertEqual(row['inputs']['age'], 22)
                self.assertAlmostEqual(row['inputs']['age_mobility_factor'], 1.35)
                self.assertEqual(row['inputs']['reason'], 'INDEPENDENT_SWITCH')
                self.assertEqual(row['constraints']['min_cooldown_turns'], 4)
        finally:
            agent_mod._agentid_counter[0] = saved_id

    def test_lifecycle_age_curve_and_childhood_lock(self):
        import agent as agent_mod
        from labor_choice import (
            career_lifecycle_age,
            career_mobility_age_factor,
            career_switch_hurdle_and_cooldown,
        )
        saved_id = agent_mod._agentid_counter[0]
        try:
            child = Agent(5)
            initialize_agent(child, Goods.food, 0, 0, 0)
            child.is_native_child = True
            child.last_career_switch = 5
            self.assertEqual(career_lifecycle_age(child, 12), 7)
            self.assertEqual(career_mobility_age_factor(child, 12), 0.0)
            hurdle_child, cooldown_child, _ = career_switch_hurdle_and_cooldown(child, 12)
            self.assertEqual(hurdle_child, float('inf'))
            self.assertEqual(cooldown_child, 7)

            # At age 15 (turn 20), child enters youth exploration window with zero initial cooldown
            hurdle_youth, cooldown_youth, factor_youth = career_switch_hurdle_and_cooldown(child, 20)
            self.assertAlmostEqual(factor_youth, 1.35)
            self.assertEqual(cooldown_youth, 0)

            # Senior founder (founding_age_offset=56) has much higher hurdle and cooldown than youth
            senior = Agent(0)
            initialize_agent(senior, Goods.wood, 0, 0, 0)
            senior.founding_age_offset = 56
            hurdle_senior, cooldown_senior, factor_senior = career_switch_hurdle_and_cooldown(senior, 4)
            self.assertAlmostEqual(factor_senior, 0.12)
            self.assertGreater(hurdle_senior, hurdle_youth * 1.8)
            self.assertEqual(cooldown_senior, 10)
        finally:
            agent_mod._agentid_counter[0] = saved_id

    def test_occupational_tenure_and_skill_tier_gating(self):
        import agent as agent_mod
        from labor_choice import (
            occupational_tenure_multiplier,
            can_enter_independent_trade,
        )
        saved_id = agent_mod._agentid_counter[0]
        try:
            worker = Agent(0)
            initialize_agent(worker, Goods.food, 0, 0, 2)
            worker.last_career_switch = 0
            worker.productivity = 0.45
            # 10 turns of continuous tenure in food gives +20% (1.20x), while unfamiliar wood is 1.00x
            self.assertAlmostEqual(occupational_tenure_multiplier(worker, Goods.food, 10), 1.20)
            self.assertAlmostEqual(occupational_tenure_multiplier(worker, Goods.wood, 10), 1.00)

            # Without capital/tools or prior joinery experience, Tier 2 furniture entry is gated
            allowed, reason = can_enter_independent_trade(worker, Goods.furniture, input_cost=2.0, turn=10)
            self.assertFalse(allowed)
            self.assertEqual(reason, 'artisan tool/skill barrier')

            # Prior experience in mem_career_history unlocks Tier 2 craft re-entry and retains partial tenure
            worker.mem_push('mem_career_history', 'furniture')
            allowed2, reason2 = can_enter_independent_trade(worker, Goods.furniture, input_cost=2.0, turn=10)
            self.assertTrue(allowed2)
            self.assertEqual(reason2, 'prior_craft_experience')
            self.assertAlmostEqual(occupational_tenure_multiplier(worker, Goods.furniture, 10), 1.04)
        finally:
            agent_mod._agentid_counter[0] = saved_id

    def test_emergency_fast_path_directionality_and_congestion_cap(self):
        import agent as agent_mod
        from economy.labor_mobility import LaborMobilityScheduler
        saved_id = agent_mod._agentid_counter[0]
        try:
            scheduler = LaborMobilityScheduler(base_batch_size=10)
            hungry_farmer = Agent(0)
            initialize_agent(hungry_farmer, Goods.food, 0, 0, 20)
            hungry_farmer.hungry_steps = 2
            hungry_farmer.assigned_plot_id = 'plot-1'
            hungry_farmer.social_class = 'serf'

            hungry_woodcutter = Agent(0)
            initialize_agent(hungry_woodcutter, Goods.wood, 0, 0, 20)
            hungry_woodcutter.hungry_steps = 2
            hungry_woodcutter.assigned_plot_id = 'plot-1'
            hungry_woodcutter.social_class = 'serf'

            region = SimpleNamespace(
                name='Parish',
                agents=[hungry_farmer, hungry_woodcutter],
                buildings=[],
                terrain={Goods.food: 1.0, Goods.wood: 1.0},
                recipes={
                    Goods.food: {'production': 6, 'price': 2.0, 'numInput': 0, 'maxinv': 10},
                    Goods.wood: {'production': 6, 'price': 15.0, 'numInput': 0, 'maxinv': 10},
                },
                sold_log={Goods.food: [10, 10, 10], Goods.wood: [20, 20, 20]},
                labor_scheduler_last_turn=-1,
            )
            scheduler.step_labor_cohort(region, t=5)
            # Hungry farmer must not switch out of food into wood despite high wood price
            self.assertEqual(hungry_farmer.output, Goods.food)
        finally:
            agent_mod._agentid_counter[0] = saved_id

    def test_market_stabilization_input_priority_and_scarcity_gating(self):
        import agent as agent_mod
        from region_market import clear_discriminatory, excess_non_producer_saleable
        saved_id = agent_mod._agentid_counter[0]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                trace = RunTrace(Path(tmp) / 'market_stab.ctr', 'market-stab')
                clock = {'next': 1, 'turn': 3, 'phase': 'local'}
                # 1. Even when producer inventory is 0, oversupply (demand_ratio = 0.5) must deflate price
                empty_producer = SimpleNamespace(output=Goods.wood, is_trader=False,
                                                 inv_get=lambda _good, _fallback: 0.0)
                region = SimpleNamespace(
                    name='Delta',
                    recipes={
                        Goods.wood: {'price': 5.0, 'maxinv': 10, 'numInput': 0, 'production': 4},
                        Goods.furniture: {'price': 12.0, 'maxinv': 10, 'input': Goods.wood,
                                          'numInput': 2, 'production': 4},
                    },
                    _price_ref={Goods.wood: 5.0, Goods.furniture: 12.0},
                    _trade_prices={},
                    _auction_import_sales={},
                    ASK_URGENCY_MIN=0.6,
                    ASK_URGENCY_MAX=1.3,
                    agents=[empty_producer],
                    _collective_trace_clock=clock,
                    _run_trace=trace,
                    home_currency='D',
                )
                update_price_ref(region, Goods.wood, 0.5, local_asks=10, imported_asks=0, bids=5)
                row = trace.query(turn=3, metric_id='goods.price')['events'][0]
                self.assertLess(row['value_after'], row['value_before'])
                self.assertEqual(row['inputs']['scarcity'], 0.0)
                self.assertTrue(replay_event(row)['matches'])

                # 2. Productive input buyers (furniture maker) get wood before hungry farmers
                #    and former woodcutters (now farmers) can sell excess wood above reserve (3)
                former_woodcutter = Agent(0)
                initialize_agent(former_woodcutter, Goods.food, 0, 0, 10)
                former_woodcutter.inv_set(Goods.wood, 5)  # 2 excess above 3 reserve
                self.assertEqual(excess_non_producer_saleable(region, former_woodcutter, Goods.wood), 2)

                hungry_farmer = Agent(0)
                initialize_agent(hungry_farmer, Goods.food, 0, 0, 50)
                hungry_farmer.hungry_steps = 4
                hungry_farmer.bid_wood = 2

                joiner = Agent(0)
                initialize_agent(joiner, Goods.furniture, 0, 0, 50)
                joiner.hungry_steps = 0
                joiner.bid_wood = 2

                region.agents = [former_woodcutter, hungry_farmer, joiner]
                units, _, _ = clear_discriminatory(
                    region, Goods.wood, 2.0, total_asks=2, total_bids=4,
                    imp_pool=[], agents=region.agents, t=3
                )
                self.assertEqual(units, 2)
                self.assertEqual(joiner.inv_get(Goods.wood, 0), 2)
                self.assertEqual(hungry_farmer.inv_get(Goods.wood, 0), 0)
                self.assertEqual(former_woodcutter.inv_get(Goods.wood, 0), 3)
        finally:
            agent_mod._agentid_counter[0] = saved_id


if __name__ == '__main__':
    unittest.main()
