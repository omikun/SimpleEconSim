import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from goods import Goods
from agent import Agent, initialize_agent
from region import Region
from nation import Nation
from externalities import step_tile_externalities
from production_emissions import output_emissions
from pollution_response import assess_pollution_health, pollution_investment
from demographics_consumption import consume_goods
from region_production import produce_independent
from tests.test_economic_policy_response import MemoryTrace


class PollutionOutputResponseTests(unittest.TestCase):
    def region(self):
        tile = Region('Pollution Test', 0, 0)
        tile.agents = []
        tile._run_trace = MemoryTrace()
        tile._collective_trace_clock = {'turn': 1, 'phase': 'ecology', 'next': 1}
        return tile

    def person(self, ident, good=Goods.food):
        a = Agent(ident)
        initialize_agent(a, good, 0, 0, 30)
        return a

    def test_idle_firms_and_carpentry_do_not_emit_industrial_pollution(self):
        tile = self.region()
        for g in (Goods.wood, Goods.furniture, Goods.iron):
            firm = self.person(int(g), g)
            firm.is_corporation = True
            tile.agents.append(firm)
        tile.emission_production_turn = 1
        tile.emission_production = {Goods.wood: 100, Goods.furniture: 100}
        step_tile_externalities(tile, 1)
        self.assertEqual(tile.pollution_air, 0)
        self.assertEqual(tile.pollution_water, 0)  # corporations are not sewage-producing residents

    def test_emissions_scale_with_output_and_ignore_stale_production(self):
        tile = self.region()
        tile.emission_production_turn = 1
        tile.emission_production = {Goods.nitrates: 10, Goods.iron: 5}
        step_tile_externalities(tile, 1)
        self.assertAlmostEqual(tile.pollution_air, 7.5)
        self.assertAlmostEqual(tile.pollution_water, 5.5)
        step_tile_externalities(tile, 2)
        self.assertAlmostEqual(tile.pollution_air, 7.5 * .85)
        self.assertAlmostEqual(tile.pollution_water, 5.5 * .88)
        air = [e for e in tile._run_trace.rows if e['kind']=='pollution_air_update'][0]
        self.assertEqual(air['inputs']['production_sources']['nitrates']['quantity'], 10)

    def test_controls_and_fertilizer_runoff_depend_on_production(self):
        tile = self.region()
        tile.use_fertilizer = True
        self.assertEqual(output_emissions(tile, Goods.food, 0)['fertilizer_runoff'], 0)
        self.assertEqual(output_emissions(tile, Goods.food, 100)['fertilizer_runoff'], 2)
        tile.emission_production_turn = 1
        tile.emission_production = {Goods.iron: 10, Goods.food: 100}
        tile.buildings = [NS(name='smoke_scrubber'), NS(name='water_filtration_plant')]
        step_tile_externalities(tile, 1)
        self.assertAlmostEqual(tile.pollution_air, 2.4)
        self.assertAlmostEqual(tile.pollution_water, 2.1)
        self.assertAlmostEqual(tile.pollution_soil, 2.8)

    def test_petition_revolt_unique_people_and_recovery(self):
        tile = self.region()
        tile.agents = [self.person(i) for i in range(20)]
        for a in tile.agents: a.birth_round = -30
        tile.agents[0].diseases = ['respiratory', 'waterborne']
        s = assess_pollution_health(tile, 1)
        self.assertEqual(s['stage'], 'petition')
        self.assertEqual(s['rate'], .05)
        for a in tile.agents[:4]: a.diseases = ['respiratory']
        s = assess_pollution_health(tile, 2)
        self.assertEqual(s['stage'], 'revolt')
        self.assertEqual(len(tile.pollution_revolt_ids), 4)
        from unrest import step_unrest
        with patch('unrest.rand.random', return_value=1):
            event = step_unrest(tile, 2)
        self.assertEqual(event['stage'], 'mob')
        self.assertTrue(event['pollution_revolt'])
        for a in tile.agents: a.diseases = []
        self.assertEqual(assess_pollution_health(tile, 3)['stage'], 'quiet')
        self.assertFalse(tile.pollution_revolt_ids)
        kinds = [e['kind'] for e in tile._run_trace.rows]
        self.assertIn('pollution_control_petition', kinds)
        self.assertIn('pollution_petition_resolved', kinds)

    def test_unrelated_illness_and_nonresidents_do_not_trigger_petition(self):
        tile = self.region()
        a = self.person(1); a.diseases = ['malnutrition', 'pestilence']
        firm = self.person(2); firm.is_corporation = True; firm.diseases = ['respiratory']
        dead = self.person(3); dead.alive = False; dead.diseases = ['waterborne']
        tile.agents = [a, firm, dead]
        s = assess_pollution_health(tile, 1)
        self.assertEqual((s['rate'], s['resident_count']), (0, 1))

    def test_pollution_revolt_withholds_production(self):
        tile = self.region(); a = self.person(1, Goods.wood)
        tile.pollution_revolt_ids = {a.id}; tile.pollution_health_state = {'stage':'revolt'}
        made = {}
        produce_independent(tile, a, tile.recipes[Goods.wood], Goods.wood, {Goods.wood:1}, made)
        self.assertFalse(made)
        self.assertEqual(tile._run_trace.rows[-1]['inputs']['reason'], 'pollution_illness_revolt')

    def test_workforce_trace_matches_pollution_withholding(self):
        from labor_resistance import record_workforce_availability
        tile = self.region()
        firm = self.person(1, Goods.iron); firm.is_corporation = True
        worker = self.person(2); worker.employer = firm
        firm.employees.append(worker); tile.agents = [firm, worker]
        tile.pollution_revolt_ids = {worker.id}
        record_workforce_availability(tile, 1)
        event = tile._run_trace.rows[-1]
        self.assertEqual(event['inputs']['working_employee_count'], 0)
        self.assertEqual(event['inputs']['available_worker_hours'], 0)
        self.assertEqual(event['inputs']['revolting_employee_ids'], [worker.id])

    def test_petition_selects_affordable_control_and_avoids_duplicate_project(self):
        tile = self.region(); nation = Nation('Test'); nation.add_tile(tile)
        tile.pollution_health_state = {'stage':'petition','rate':.1,'disease_counts':{'respiratory':10}}
        intent, rows = pollution_investment(nation, 2, 300)
        self.assertEqual(intent.building_type, 'smoke_scrubber')
        self.assertTrue(rows[0]['feasible'])
        self.assertIsNone(pollution_investment(nation, 2, 299)[0])
        nation.intents = [intent]
        intent.status = 'pending_approval'
        self.assertIsNone(pollution_investment(nation, 2, 1000)[0])
        nation.intents = []
        tile.construction_projects = [NS(status='in_progress')]
        self.assertIsNone(pollution_investment(nation, 2, 1000)[0])

    def test_furniture_maker_keeps_two_batches_but_consumes_excess(self):
        tile = self.region(); a = self.person(1, Goods.furniture)
        a.consumption_multiplier = 4
        ctx = NS(goods=[Goods.wood], recipes=tile.recipes,
                 profession={Goods.wood:'wood'}, source_region=tile)
        for stock, expected in [(1,1),(4,4),(5,4),(8,6)]:
            a.inv_set(Goods.wood, stock)
            consume_goods(ctx,a,0,0,0)
            self.assertEqual(a.inv_get(Goods.wood,0),expected)
        # The protected stock is usable for production, not a frozen reserve.
        with patch('region_production.rand.random', return_value=0):
            produce_independent(tile,a,tile.recipes[Goods.furniture],Goods.furniture,
                                {Goods.furniture:1},{})
        self.assertEqual(a.inv_get(Goods.wood,0),4)

if __name__=='__main__': unittest.main()
