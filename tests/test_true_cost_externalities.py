"""
test_true_cost_externalities.py — Unit & Integration Tests for True Cost & Externalities Ledger.

Covers:
1. Industrial Steam Mill / Smelter: nominal profit vs smog & shift wear.
2. Four-Field Crop Rotation vs Intensive Monoculture: agroecological vs chemical depletion.
3. Landlord Enclosure & Eviction: ground rent vs peasant displacement liabilities.
4. Merchant Epidemic Vectoring: trade arbitrage vs disease transmission damage.
5. Clean Technology Internalization: scrubbers, sewers, rotation, and 8h shift cap restore positive Net Social Profit.
6. Conserved Currency & Performance Invariance: 0 leak, strict cash conservation.
7. Data-Driven Shadow Pricing & Scenario/Age Switch: JSON profile resolution and dynamic overrides.
"""

import unittest
import os
import json
import time
from goods import Goods
from region import Region
from nation import Nation
from land_tenure import LandPlot, TenureStatus
from agent import Agent, initialize_agent
from economy.true_cost_ledger import (
    get_true_cost_ledger,
    get_shadow_price_manager,
    ShadowPriceManager,
    EnterpriseExternalities,
    EnterpriseFinancials,
    TrueCostAuditRecord,
)
from region_production import produce_corporation, produce_independent
from labor_contract import CUSTOMARY_SHIFT_HOURS


def make_agent(aid: int, good=Goods.food, cash=50.0) -> Agent:
    a = Agent(aid)
    initialize_agent(a, good, 0, 5, cash)
    return a


class DummyBuilding:
    def __init__(self, name: str):
        self.name = name


class TestTrueCostExternalities(unittest.TestCase):

    def setUp(self):
        self.ledger = get_true_cost_ledger()
        self.ledger.reset()
        self.nation = Nation("Kingdom", initial_cash=1000.0)
        self.tile = Region("Wessex", 0, 110)
        self.nation.add_tile(self.tile)

    def test_01_industrial_mill_smog_and_health_wear(self):
        """Verify that an industrial steam mill running 14h shifts reports positive nominal profit
        but negative True Net Social Profit due to smog and worker health attrition."""
        # Create industrial furniture firm
        firm = make_agent(901, Goods.furniture, 200.0)
        firm.is_corporation = True
        firm.output = Goods.furniture
        firm.shift_hours = 14.0  # Excessive shift
        firm.safety_investment = 0.0  # Zero safety
        self.tile.agents.append(firm)

        # Hire 6 employees
        for i in range(6):
            w = make_agent(1000 + i, Goods.food, 10.0)
            w.employer = firm
            firm.employees.append(w)
            self.tile.agents.append(w)

        # Produce furniture
        self.tile.recipes[Goods.furniture] = {
            'commodity': Goods.furniture, 'production': 2, 'input': Goods.wood,
            'numInput': 1, 'price': 15.0, 'maxinv': 20, 'maxtotalprod': 100
        }
        self.tile.recipes[Goods.wood] = {
            'commodity': Goods.wood, 'production': 1, 'numInput': 0, 'price': 3.0, 'maxinv': 20, 'maxtotalprod': 100
        }
        firm.inv_add(Goods.wood, 10)

        # Run corporation production
        produce_corporation(self.tile, firm, self.tile.recipes[Goods.furniture], Goods.furniture,
                            {Goods.furniture: 1}, {})

        # Seal turn 1
        self.ledger.seal_turn(1, scenario_id="empire_of_cotton")
        rec = self.ledger.get_record(firm.id, turn=1)
        self.assertIsNotNone(rec)

        # Nominal profit should be positive (furniture value > wood input + wages)
        self.assertGreater(rec.financials.nominal_profit, 0)

        # Externalized costs: smog emitted + labor health wear from 14h shift
        self.assertGreater(rec.externalities.air_pollution_cost, 0)
        self.assertGreater(rec.externalities.labor_health_wear_cost, 0)
        self.assertGreater(rec.externalities.total_externalized_cost, 0)

        # Status should reflect heavy extraction
        self.assertIn(rec.parasitic_status, ("EXTRACTIVE_PARASITE", "SUBSIDIZED_BY_NATURE"))
        self.assertGreater(rec.pigouvian_tax_gap, 0)

    def test_02_crop_rotation_vs_intensive_monoculture(self):
        """Verify Norfolk four-field rotation achieves lower externalized soil degradation
        than intensive synthetic fertilizer monoculture."""
        # Firm A: Agroecological Four-Field Rotation Farm
        tile_a = Region("Norfolk", 0, 110)
        tile_a.farming_regime = 'rotation'
        tile_a.use_fertilizer = False
        tile_a.use_pesticides = False
        farm_a = make_agent(801, Goods.food, 100.0)
        farm_a.is_corporation = True
        farm_a.output = Goods.food
        farm_a.shift_hours = 8.0
        farm_a.safety_investment = 1.0
        tile_a.agents.append(farm_a)
        w_a = make_agent(802, Goods.food, 10.0)
        farm_a.employees.append(w_a)
        tile_a.agents.append(w_a)

        produce_corporation(tile_a, farm_a, tile_a.recipes[Goods.food], Goods.food, {Goods.food: 1}, {})

        # Firm B: Intensive Monoculture Farm with Synthetic Fertilizers & Pesticides
        tile_b = Region("Lancashire_Farms", 0, 110)
        tile_b.farming_regime = 'intensive'
        tile_b.use_fertilizer = True
        tile_b.use_pesticides = True
        farm_b = make_agent(803, Goods.food, 100.0)
        farm_b.is_corporation = True
        farm_b.output = Goods.food
        farm_b.shift_hours = 8.0
        tile_b.agents.append(farm_b)
        w_b = make_agent(804, Goods.food, 10.0)
        farm_b.employees.append(w_b)
        tile_b.agents.append(w_b)

        produce_corporation(tile_b, farm_b, tile_b.recipes[Goods.food], Goods.food, {Goods.food: 1}, {})

        self.ledger.seal_turn(1)
        rec_a = self.ledger.get_record(farm_a.id, turn=1)
        rec_b = self.ledger.get_record(farm_b.id, turn=1)

        self.assertIsNotNone(rec_a)
        self.assertIsNotNone(rec_b)

        # Intensive farm should have much higher soil depletion and chemical toxicity costs
        self.assertGreater(rec_b.externalities.soil_depletion_cost, rec_a.externalities.soil_depletion_cost)
        self.assertGreater(rec_b.externalities.water_effluent_cost, 0.0)
        self.assertGreater(rec_b.externalities.soil_toxicity_cost, 0.0)
        self.assertGreater(rec_b.externalities.total_externalized_cost, rec_a.externalities.total_externalized_cost)

    def test_03_landlord_enclosure_and_eviction(self):
        """Verify landlord ground rent profit is penalized by peasant eviction liabilities."""
        lord = make_agent(701, Goods.food, 50.0)

        # Create 3 evicted commoners
        evicted_count = 3.0
        self.ledger.record_landlord(
            lord=lord,
            region=self.tile,
            turn=1,
            gross_rent=60.0,
            collection_cost=5.0,
            evicted_count=evicted_count,
            commons_degrade=0.02
        )

        self.ledger.seal_turn(1)
        rec = self.ledger.get_record(lord.id, turn=1)

        self.assertIsNotNone(rec)
        self.assertEqual(rec.financials.nominal_profit, 55.0)  # 60 - 5
        self.assertGreater(rec.externalities.peasant_displacement_cost, 0)
        # Displacement cost = 3 * 25.0 = 75.0, so True Net Profit should be negative: 55 - (75 + soil_cost) < 0
        self.assertLess(rec.true_net_profit, 0)
        self.assertEqual(rec.parasitic_status, "EXTRACTIVE_PARASITE")

    def test_04_merchant_epidemic_vectoring(self):
        """Verify merchant trade arbitrage is offset when inter-tile route seeds epidemic infections."""
        trader = make_agent(601, Goods.transport, 50.0)
        trader.is_trader = True

        # Trader makes $40 gross arbitrage margin, paying $5 tolls
        # but seeds 1 plague infection into pristine destination
        self.ledger.record_merchant(
            trader=trader,
            region=self.tile,
            turn=1,
            gross_arbitrage=40.0,
            tolls_and_transport=5.0,
            infected_seeds=1.0,
            famine_risk=0.0
        )

        self.ledger.seal_turn(1)
        rec = self.ledger.get_record(trader.id, turn=1)

        self.assertIsNotNone(rec)
        self.assertEqual(rec.financials.nominal_profit, 35.0)  # 40 - 5
        # Epidemic vector cost = 1.0 * 40.0 = $40.0
        self.assertEqual(rec.externalities.epidemic_vector_cost, 40.0)
        self.assertLess(rec.true_net_profit, 0)  # 35 - 40 = -5

    def test_05_clean_technology_internalization(self):
        """Verify installing scrubbers, sewers, and 8h workday restores True Net Social Profit to positive."""
        # Create clean factory tile
        clean_tile = Region("Greenfield", 0, 110)
        clean_tile.buildings.append(DummyBuilding('smoke_scrubber'))
        clean_tile.buildings.append(DummyBuilding('trunk_sewer'))

        clean_firm = make_agent(501, Goods.furniture, 200.0)
        clean_firm.is_corporation = True
        clean_firm.output = Goods.furniture
        clean_firm.shift_hours = 8.0  # Compliant 8-hour shift
        clean_firm.safety_investment = 1.0  # Full safety standards
        clean_tile.agents.append(clean_firm)

        for i in range(4):
            w = make_agent(2000 + i, Goods.food, 10.0)
            w.employer = clean_firm
            clean_firm.employees.append(w)
            clean_tile.agents.append(w)

        clean_tile.recipes[Goods.furniture] = {
            'commodity': Goods.furniture, 'production': 3, 'input': Goods.wood,
            'numInput': 1, 'price': 20.0, 'maxinv': 30, 'maxtotalprod': 100
        }
        clean_tile.recipes[Goods.wood] = {
            'commodity': Goods.wood, 'production': 1, 'numInput': 0, 'price': 2.0, 'maxinv': 30, 'maxtotalprod': 100
        }
        clean_firm.inv_add(Goods.wood, 15)

        produce_corporation(clean_tile, clean_firm, clean_tile.recipes[Goods.furniture], Goods.furniture,
                            {Goods.furniture: 1}, {})

        self.ledger.seal_turn(1)
        rec = self.ledger.get_record(clean_firm.id, turn=1)

        self.assertIsNotNone(rec)
        # Smog should be reduced by 70%, effluent reduced by 70%, 0 excess shift wear
        self.assertGreater(rec.true_net_profit, 0)
        self.assertIn(rec.parasitic_status, ("ECO_RESTORATIVE", "SUBSIDIZED_BY_NATURE"))

    def test_06_conserved_currency_and_performance(self):
        """Ensure True Cost evaluation does not mutate or leak cash balances and runs sub-second."""
        initial_cash = sum(a.cash for a in self.tile.agents)

        firm = make_agent(401, Goods.wood, 100.0)
        firm.is_corporation = True
        firm.output = Goods.wood
        self.tile.agents.append(firm)

        start_t = time.perf_counter()

        for t in range(1, 21):
            produce_independent(self.tile, firm, self.tile.recipes[Goods.wood], Goods.wood, {Goods.wood: 1}, {})
            self.ledger.seal_turn(t)

        elapsed = time.perf_counter() - start_t
        self.assertLess(elapsed, 0.5)  # 20 turns executed in under 500ms

        final_cash = sum(a.cash for a in self.tile.agents)
        self.assertEqual(initial_cash + firm.cash, final_cash)

    def test_07_data_driven_shadow_pricing_json_and_age_switch(self):
        """Verify shadow pricing evaluates data-driven JSON coefficients, supports age switching,
        and applies scenario overrides."""
        mgr = get_shadow_price_manager()
        config = mgr.load_config()

        self.assertIn("profiles", config)
        self.assertIn("feudal_manorial", config["profiles"])
        self.assertIn("victorian_industrial", config["profiles"])
        self.assertIn("petrochemical_modern", config["profiles"])

        # Compare feudal vs modern coefficients for air pollution
        coeffs_feudal = mgr.get_coefficients(age="feudal_manorial")
        coeffs_modern = mgr.get_coefficients(age="petrochemical_modern")

        # In feudal era, air pollution shadow cost is low ($2.0), while in modern era it is $25.0
        self.assertEqual(coeffs_feudal["air_pollution_cost"], 2.0)
        self.assertEqual(coeffs_modern["air_pollution_cost"], 25.0)

        # Test scenario override
        coeffs_egypt = mgr.get_coefficients(scenario_id="egypt_1877")
        self.assertEqual(coeffs_egypt["soil_depletion_cost"], 30.0)

        # Test inline custom override
        custom_coeffs = mgr.get_coefficients(inline_overrides={"air_pollution_cost": 99.0})
        self.assertEqual(custom_coeffs["air_pollution_cost"], 99.0)

        # Verify monetized output shifts according to active age profile
        phys_damages = {"air_smog_emitted": 5.0}
        ext_feudal = mgr.monetize_damages(phys_damages, age="feudal_manorial")
        ext_modern = mgr.monetize_damages(phys_damages, age="petrochemical_modern")

        self.assertEqual(ext_feudal.air_pollution_cost, 10.0)   # 5.0 * 2.0
        self.assertEqual(ext_modern.air_pollution_cost, 125.0)  # 5.0 * 25.0

    def test_08_national_corporate_externalities_rollup(self):
        """Verify national corporate externalities rollup aggregates all country corps'
        profits, damages, and maps them to societal victim groups."""
        firm_a = make_agent(301, Goods.furniture, 200.0)
        firm_a.is_corporation = True
        firm_a.shift_hours = 12.0
        self.tile.agents.append(firm_a)
        w_a = make_agent(302, Goods.food, 10.0)
        firm_a.employees.append(w_a)
        self.tile.agents.append(w_a)

        self.tile.recipes[Goods.furniture] = {
            'commodity': Goods.furniture, 'production': 2, 'input': Goods.wood,
            'numInput': 1, 'price': 15.0, 'maxinv': 20, 'maxtotalprod': 100
        }
        self.tile.recipes[Goods.wood] = {
            'commodity': Goods.wood, 'production': 1, 'numInput': 0, 'price': 3.0, 'maxinv': 20, 'maxtotalprod': 100
        }
        firm_a.inv_add(Goods.wood, 5)

        produce_corporation(self.tile, firm_a, self.tile.recipes[Goods.furniture], Goods.furniture,
                            {Goods.furniture: 1}, {})
        self.ledger.seal_turn(1)

        world = {'tiles': [self.tile]}
        corps_summary = self.ledger.get_national_corporate_externalities("Kingdom", world)

        self.assertGreater(corps_summary['total_corporate_nominal_profit'], 0.0)
        self.assertGreater(corps_summary['total_corporate_externalized_cost'], 0.0)
        self.assertIn('damage_breakdown', corps_summary)
        self.assertGreater(corps_summary['damage_breakdown']['air_smog_cost'], 0.0)
        self.assertIn('victims_breakdown', corps_summary)

        vics = corps_summary['victims_breakdown']
        self.assertIn('Factory Proletariat & Wage Laborers', vics)
        self.assertIn('Urban Pop & Riparian Communities', vics)
        self.assertGreater(vics['Urban Pop & Riparian Communities']['cost'], 0.0)

    def test_09_decision_externalities_tracking_and_victims(self):
        """Verify decision tracking records externalized costs and identifies specific victim groups."""
        from economy.true_cost_ledger import get_decision_tracker
        tracker = get_decision_tracker()
        tracker.reset()

        # Record 4 historical decisions
        e1 = tracker.record_decision('incorporate_steam_mill', turn=1)
        e2 = tracker.record_decision('charter_enclosure_decree', turn=2)
        e3 = tracker.record_decision('procure_plantation_gangs', turn=3)
        e4 = tracker.record_decision('reduce_fellahin_tax', turn=4)

        entries = tracker.get_all_entries()
        self.assertEqual(len(entries), 4)

        # e1: Steam mill -> Factory Proletariat & Urban Pop
        self.assertEqual(e1.externalized_cost, 85.0)
        vic_groups_e1 = [v.victim_group for v in e1.victims]
        self.assertIn('Factory Proletariat', vic_groups_e1)
        self.assertIn('Urban Population', vic_groups_e1)

        # e2: Enclosure -> Customary Peasantry
        self.assertEqual(e2.externalized_cost, 95.0)
        vic_groups_e2 = [v.victim_group for v in e2.victims]
        self.assertIn('Customary Peasantry & Smallholders', vic_groups_e2)

        # e3: Captive labor -> Captive Enslaved Hands
        self.assertEqual(e3.externalized_cost, 150.0)
        self.assertEqual(e3.victims[0].victim_group, 'Captive Enslaved Hands')

        # e4: Tax reduction -> $0 externalized cost (restorative)
        self.assertEqual(e4.externalized_cost, 0.0)

        # Verify victims summary aggregates costs
        v_summary = tracker.get_victims_summary()
        self.assertIn('Factory Proletariat', v_summary)
        self.assertEqual(v_summary['Factory Proletariat']['total_cost'], 37.0)
        self.assertIn('Customary Peasantry & Smallholders', v_summary)
        self.assertEqual(v_summary['Customary Peasantry & Smallholders']['total_cost'], 75.0)
        self.assertIn('Captive Enslaved Hands', v_summary)
        self.assertEqual(v_summary['Captive Enslaved Hands']['total_cost'], 150.0)

    def test_10_end_of_scenario_debrief_integration(self):
        """Verify that concluding a scenario populates state['debrief'] with both
        corporate externalities and decisions externalities."""
        from scenario_empire_of_cotton import get_empire_of_cotton_interpreter
        interpreter = get_empire_of_cotton_interpreter()
        world = {
            'turn': 1,
            'tiles': [self.tile],
            'nations': [self.nation],
            'player_nation_name': 'Kingdom',
            'scenario_state': {
                'metrics': {},
            },
        }

        from economy.true_cost_ledger import get_decision_tracker
        get_decision_tracker().reset()

        # Apply decisions via interpreter
        interpreter.apply_action(world, 'incorporate_steam_mill')
        world['turn'] = 2
        interpreter.apply_action(world, 'charter_enclosure_decree')

        # Conclude scenario
        eval_ctx = {'turn': 2, 'state': world['scenario_state'], 'player_nation_name': 'Kingdom'}
        interpreter._conclude_scenario(world, 'test_conclude', 'Victory', 'Test summary', eval_ctx)

        debrief = world['scenario_state']['debrief']
        self.assertIn('corporate_externalities', debrief)
        self.assertIn('decisions_externalities', debrief)

        dec_entries = debrief['decisions_externalities']
        self.assertGreaterEqual(len(dec_entries), 2)
        act_ids = [d['action_id'] for d in dec_entries]
        self.assertIn('incorporate_steam_mill', act_ids)
        self.assertIn('charter_enclosure_decree', act_ids)

        # Verify victims are present in debrief decisions
        mill_entry = next(d for d in dec_entries if d['action_id'] == 'incorporate_steam_mill')
        self.assertGreater(mill_entry['externalized_cost'], 0)
        self.assertTrue(len(mill_entry['victims']) > 0)
        self.assertEqual(mill_entry['victims'][0]['victim_group'], 'Factory Proletariat')


if __name__ == "__main__":
    unittest.main()

