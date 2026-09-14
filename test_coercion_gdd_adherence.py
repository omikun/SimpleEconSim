"""
test_coercion_gdd_adherence.py — Comprehensive test suite for non-scripted mechanics
and the Monopoly of Violence across all core simulation systems.
"""

import unittest
from unittest.mock import MagicMock
from goods import Goods
from agent import Agent, initialize_agent, seed_traits
from region import Region
from nation import Nation
from land_tenure import TileTenure, TenureStatus, LandPlot
from army import MilitaryUnit
from claims import check_and_apply_claims
from enclosure import execute_enclosure, step_enclosure_survey_debts
from land_rent import collect_rents
from coup import find_generals, coup_chance, execute_coup
from regime import step_regime
from unrest import apply_repression, _takeover, step_unrest
from labor_politics import evaluate_uprising_pressure, enact_ten_hour_act
from feudal_tribute import collect_tribute
from diplomacy import DiplomacySystem, TreatyType


class TestCoercionGDDAdherence(unittest.TestCase):

    def setUp(self):
        self.t = 10

    # ------------------------------------------------------------------
    # 1. Frontier Claims & Indigenous Resistance / Conserved Displacement
    # ------------------------------------------------------------------

    def test_frontier_claims_resistance_and_conserved_displacement(self):
        """Wilderness claims require force: unarmed claims are repelled; armed claims conserve population."""
        nation = Nation("Empire", "IMP")
        tile = Region("Frontier_West", 0)
        tile.wilderness = True
        tile.wilderness_pop = 20
        tile.elevation = 1.0
        tile.is_ocean = False
        tile.agents = []
        tile.neighbors = {}
        tile.forex_desks = {}

        # Add 25 homesteaders from Empire
        for _ in range(25):
            a = Agent(0)
            seed_traits(a)
            initialize_agent(a, Goods.none, 0, 0, 10.0)
            a.is_homesteader = True
            a.origin_nation = "Empire"
            a.military_xp = 0.0  # unarmed settlers
            tile.agents.append(a)

        # 1. Settlers have population majority (25 > 20), but zero military force
        # Native defense = 20 * 0.75 = 15.0. Settler force = 0.
        events = check_and_apply_claims(self.t, [tile], [nation])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event'], 'FRONTIER_CLAIM_REPELLED')
        self.assertTrue(tile.wilderness)
        self.assertEqual(tile.wilderness_pop, 20)

        # 2. Deploy military detachment to enforce frontier claim
        unit = MilitaryUnit(
            unit_id="garrison_frontier",
            nation_name="Empire",
            region_name=tile.name,
            soldiers=30,
            morale=1.0,
            equipment_quality=1.0
        )
        tile.military_units = [unit]

        # Claim attempt with military backing succeeds
        events_armed = check_and_apply_claims(self.t, [tile], [nation])
        self.assertFalse(tile.wilderness)
        self.assertEqual(tile.wilderness_pop, 0)
        # Verify native population was conserved into dispossessed agents
        dispossessed = [a for a in tile.agents if getattr(a, 'social_class', '') == 'dispossessed']
        self.assertGreaterEqual(len(dispossessed), 10)

    # ------------------------------------------------------------------
    # 2. Coercive Enclosure & Bailiff Enforcement
    # ------------------------------------------------------------------

    def test_enclosure_requires_bailiff_or_garrison_under_protest(self):
        """Enclosure without force under high protest energy is defied by commoners."""
        tile = Region("Customary_Valley", 0)
        tenure = TileTenure()
        tile.tenure = tenure

        lord = Agent(0)
        seed_traits(lord)
        initialize_agent(lord, Goods.none, 0, 0, 10.0)  # Lord has $10 (pays charter fee, cannot afford bailiffs)
        tile.agents.append(lord)

        plot = LandPlot(plot_id="plot_feudal", tile_name=tile.name, lord_id=lord.id, tenure=TenureStatus.FEUDAL, fraction=0.20)
        tenure.plots.append(plot)

        gov_agent = Agent(0)
        initialize_agent(gov_agent, Goods.none, 0, 0, 0.0)
        gov_agent.is_government = True
        gov_mock = MagicMock()
        gov_mock.agent = gov_agent
        tile.gov = gov_mock

        # Set protest energy high (commoners are militant)
        tile.protest_energy_log = [4.0]

        # 1. Enclosure without garrison or bailiffs fails
        ok, msg, evs = execute_enclosure(tile, plot.plot_id, self.t)
        self.assertFalse(ok)
        self.assertIn("DEFIED", msg)
        self.assertEqual(plot.tenure, TenureStatus.FEUDAL)

        # 2. Lord acquires funds to hire armed bailiffs ($25 cash: $10 fee + $10 bailiff + $5 spare)
        lord.cash = 25.0
        ok2, msg2, evs2 = execute_enclosure(tile, plot.plot_id, self.t)
        self.assertTrue(ok2)
        self.assertEqual(plot.tenure, TenureStatus.ENCLOSED)

    def test_eviction_resisted_without_bailiffs(self):
        """Statutory survey foreclosure eviction is resisted if authority lacks force."""
        tile = Region("Eviction_Tile", 0)
        tile.protest_energy_log = [5.0]
        tile.military_units = []
        tile.police_employed = 0

        tenant = Agent(0)
        initialize_agent(tenant, Goods.none, 0, 0, 0.0)  # insolvent
        tile.agents.append(tenant)

        tile.enclosure_survey_debts = [{
            'tenant_id': tenant.id,
            'fee': 15.0,
            'deadline': self.t,
            'plot_id': 'plot_01'
        }]

        events = step_enclosure_survey_debts(tile, self.t)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event'], 'EVICTION_RESISTED')
        self.assertGreater(tenant.mem_last('mem_promises'), 0.0)

    # ------------------------------------------------------------------
    # 3. Coups Governed by Force Ratio
    # ------------------------------------------------------------------

    def test_coup_force_ratio_deterministic(self):
        """Coup outcome is determined by armed force ratio, not random dice rolls."""
        nation = Nation("Kingdom", "KNG")
        nation.regime_type = "autocracy"
        nation.legitimacy = 0.20  # below threshold

        tile = Region("Capital", 0)
        tile.owner_nation = nation
        nation.tiles.append(tile)

        general = Agent(0)
        seed_traits(general)
        general.ambition = 0.9
        general.charisma = 0.9
        general.loyalty = 0.1
        general.birth_round = -30  # adult
        general.cash = 100.0       # personal war chest
        general.region = tile.name
        tile.agents.append(general)

        # 1. Conspirators face zero loyalist defense -> coup succeeds
        gen_cand, fires = coup_chance(nation, self.t)
        self.assertTrue(fires)
        self.assertEqual(gen_cand.id, general.id)

        # 2. Government deploys a loyal, well-paid garrison (strength 120.0)
        loyal_garrison = MilitaryUnit(
            unit_id="palace_guard",
            nation_name=nation.name,
            region_name="Barracks",
            soldiers=150,
            morale=1.0,
            equipment_quality=1.2
        )
        nation.military_units.append(loyal_garrison)

        # Coup attempt is deterred/crushed by superior loyalist armed force
        gen_cand2, fires2 = coup_chance(nation, self.t)
        self.assertFalse(fires2)

    def test_autocracy_does_not_hold_snap_election(self):
        """Autocratic regimes never hold snap elections when legitimacy collapses."""
        nation = Nation("Autocracy_State", "AUT")
        nation.regime_type = "autocracy"
        nation.legitimacy = 0.10  # severe collapse
        nation._last_election = 0

        events = step_regime(nation, self.t)
        election_events = [e for e in events if e.get('kind') == 'election']
        self.assertEqual(len(election_events), 0)

    # ------------------------------------------------------------------
    # 4. Physical Repression & Labor Concession Calculus
    # ------------------------------------------------------------------

    def test_repression_requires_military_or_police(self):
        """Repression cannot occur without armed garrisons or police."""
        tile = Region("Industrial_City", 0)
        tile.protest_energy_log = [7.0]
        tile.military_units = []
        tile.police_employed = 0

        # Unarmed authority cannot repress
        seeded = apply_repression(tile, self.t)
        self.assertEqual(seeded, 0)
        self.assertEqual(tile.protest_energy_log[-1], 7.0)

        # Deploy police
        tile.police_employed = 4
        seeded_armed = apply_repression(tile, self.t)
        self.assertLess(tile.protest_energy_log[-1], 7.0)

    def test_capitalist_armed_strikebreaking_vs_concession(self):
        """Bourgeoisie regime with strong military crushes strikes rather than conceding."""
        nation = Nation("Factory_Republic", "REP")
        nation.ruling_faction = "Bourgeoisie"
        tile = Region("Mill_Town", 0)
        nation.tiles.append(tile)

        # Create workers and strikers
        workers = []
        for _ in range(20):
            w = Agent(0)
            initialize_agent(w, Goods.none, 0, 0, 1.0)
            w.social_class = 'proletarian'
            w.is_striking = True
            workers.append(w)
            tile.agents.append(w)

        # 1. State possesses powerful military garrison -> armed strikebreaking
        unit = MilitaryUnit("dragoons", nation.name, tile.name, soldiers=50, morale=0.9)
        nation.military_units.append(unit)

        events = evaluate_uprising_pressure(nation, self.t)
        self.assertTrue(any(e.get('kind') == 'armed_strikebreaking' for e in events))
        self.assertFalse(getattr(nation, 'ten_hour_act', False))

        # 2. Without armed units, mass strikes force Ten-Hour Act concession
        nation.military_units.clear()
        for w in workers:
            w.is_striking = True

        events2 = evaluate_uprising_pressure(nation, self.t)
        self.assertTrue(any(e.get('kind') == 'ten_hour_act_concession' for e in events2))
        self.assertTrue(getattr(nation, 'ten_hour_act', False))

    # ------------------------------------------------------------------
    # 5. Coercive Feudal Tribute
    # ------------------------------------------------------------------

    def test_militant_serfs_withhold_feudal_tribute(self):
        """Serfs in high unrest withhold tribute unless landlord has armed force."""
        tile = Region("Serf_Village", 0)
        tenure = TileTenure()
        tile.tenure = tenure

        lord = Agent(0)
        initialize_agent(lord, Goods.none, 0, 0, 0.0)
        lord.is_lord = True
        tile.agents.append(lord)

        plot = LandPlot(plot_id="f1", tile_name=tile.name, lord_id=lord.id, tenure=TenureStatus.FEUDAL, fraction=1.0, tribute_rate=0.5)
        tenure.plots.append(plot)

        serf = Agent(0)
        initialize_agent(serf, Goods.food, 0, 0, 0.0)
        serf.inv_set(Goods.food, 10)  # Has 10 food
        tile.agents.append(serf)

        # High protest energy and no force -> tribute withheld
        tile.protest_energy_log = [6.0]
        tile.military_units = []
        tile.police_employed = 0

        res = collect_tribute(tile, self.t)
        self.assertEqual(res, {})
        self.assertEqual(serf.inv_get(Goods.food), 10)

        # Add armed garrison -> tribute extracted
        garrison = MilitaryUnit("garrison", "Kingdom", tile.name, soldiers=15, morale=1.0)
        tile.military_units.append(garrison)

        res2 = collect_tribute(tile, self.t)
        self.assertIn(lord.id, res2)
        self.assertGreater(lord.inv_get(Goods.food), 0)


if __name__ == '__main__':
    unittest.main()
