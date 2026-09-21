"""Unit tests for Endogenous Pestilence Genesis, Trade-Route Contagion, Cordon Sanitaire, and Granary Relief."""

import unittest
import random
from region import Region
from agent import Agent
from goods import Goods
from transporter import Route
from disease import (
    DIS_PESTILENCE,
    evaluate_pestilence_genesis,
    step_trade_epidemic_transmission,
    step_tile_diseases,
)
from labor_politics import (
    enact_trade_quarantine,
    repeal_trade_quarantine,
    emergency_granary_relief,
)
from demographics_estate import handle_death
from random_cache import rand


class MockLiveContext:
    def __init__(self, carrying_capacity=100):
        self.starve_limit = 10
        self.carrying_capacity = carrying_capacity
        self.bank = type('MockBank', (), {'deposits': {}})()
        self.disease_fatalities_this_turn = 0
        self.cost_of_living = 2.0
        self.default_gov = None
        self.charity = None


class TestTradeRouteEpidemicTransmission(unittest.TestCase):

    def setUp(self):
        random.seed(42)
        rand.reset()

    def test_endogenous_pestilence_genesis_under_famine(self):
        """Verify that The Great Pestilence ignites endogenously under chronic famine and crowding."""
        r = Region("PlagueHollow", 0, 0)
        r.granary_stock = 0.0
        r.nutrition_density = 0.50
        r.famine_outbreak_turns = 2
        r.capacity = 30

        # Spawn 25 agents (crowding = 25/30 = 0.833 >= 0.70)
        for i in range(25):
            a = Agent(0)
            a.id = i
            a.alive = True
            a.hungry_steps = 3  # Starving for 3 consecutive turns
            a.diseases = []
            r.agents.append(a)

        # Pre-condition: no plague
        self.assertEqual(getattr(r, 'active_pestilence_count', 0), 0)

        # Trigger genesis check
        ignited = evaluate_pestilence_genesis(r, t=5)
        self.assertTrue(ignited)
        self.assertGreater(r.active_pestilence_count, 0)
        pest_agents = [a for a in r.agents if DIS_PESTILENCE in getattr(a, 'diseases', [])]
        self.assertGreater(len(pest_agents), 0)

    def test_emergency_granary_relief_prevents_genesis(self):
        """Verify that emergency granary grain disbursement halts starvation and resets outbreak progression."""
        r = Region("ReliefCity", 0, 0)
        r.granary_stock = 50.0
        r.nutrition_density = 0.50
        r.famine_outbreak_turns = 3
        r.capacity = 30

        for i in range(25):
            a = Agent(0)
            a.id = i
            a.alive = True
            a.hungry_steps = 2
            a.diseases = []
            r.agents.append(a)

        # Sovereign enacts emergency granary relief
        ok, msg = emergency_granary_relief(r, food_amount=25.0)
        self.assertTrue(ok)
        self.assertEqual(r.famine_outbreak_turns, 0)

        # Starvation is mitigated: hungry_steps reset to 0
        starving_count = sum(1 for a in r.agents if a.hungry_steps > 0)
        self.assertEqual(starving_count, 0)

        # Subsequent genesis check fails to ignite
        ignited = evaluate_pestilence_genesis(r, t=6)
        self.assertFalse(ignited)
        self.assertEqual(getattr(r, 'active_pestilence_count', 0), 0)

    def test_trade_route_epidemic_transmission(self):
        """Verify that infected origin transmits The Great Pestilence along active routes to uninfected destination."""
        origin = Region("Genoa", 0, 0)
        destination = Region("Marseille", 1, 0)

        # Populate origin with plague
        origin.active_pestilence_count = 5
        for i in range(10):
            a = Agent(0)
            a.id = i
            a.alive = True
            a.diseases = [DIS_PESTILENCE] if i < 5 else []
            origin.agents.append(a)

        # Populate destination with healthy agents
        for i in range(10):
            b = Agent(0)
            b.id = 100 + i
            b.alive = True
            b.diseases = []
            destination.agents.append(b)

        self.assertEqual(getattr(destination, 'active_pestilence_count', 0), 0)

        # Connect trade route
        rt = Route("Genoa_Marseille", origin, destination, 1, 10)
        origin.routes["Marseille"] = rt

        # Route carries contagion from origin port and delivers cargo to Marseille
        rt.has_contagion = True
        rt.delivered_this_turn = {Goods.food: 10}

        # Step transmission across routes
        events = step_trade_epidemic_transmission([origin, destination], t=12)

        # Route delivered contagion and infected destination
        self.assertGreater(len(events), 0)
        self.assertGreater(getattr(destination, 'active_pestilence_count', 0), 0)
        dest_infected = [a for a in destination.agents if DIS_PESTILENCE in getattr(a, 'diseases', [])]
        self.assertGreater(len(dest_infected), 0)

    def test_cordon_sanitaire_blocks_contagion(self):
        """Verify that enacting Trade Quarantine freezes routes and blocks infected shipments."""
        origin = Region("InfectedPort", 0, 0)
        destination = Region("ProtectedHaven", 1, 0)

        origin.active_pestilence_count = 8
        for i in range(10):
            a = Agent(0)
            a.id = i
            a.alive = True
            a.diseases = [DIS_PESTILENCE]
            origin.agents.append(a)

        for i in range(10):
            b = Agent(0)
            b.id = 200 + i
            b.alive = True
            b.diseases = []
            destination.agents.append(b)

        rt = Route("TradeRoute", origin, destination, 1, 10)
        origin.routes["ProtectedHaven"] = rt
        destination.routes["InfectedPort"] = rt

        # Enact Trade Quarantine on destination
        ok, msg = enact_trade_quarantine(destination)
        self.assertTrue(ok)
        self.assertTrue(destination.quarantine_active)
        self.assertTrue(rt.is_quarantined)
        self.assertTrue(rt.is_frozen)

        # Mark route as carrying pestilence
        rt.has_contagion = True
        rt.delivered_this_turn = {Goods.food: 15}

        # Step epidemic transmission
        events = step_trade_epidemic_transmission([origin, destination], t=15)

        # Contagion is intercepted by Quarantine Block
        block_events = [e for e in events if e.get('type') == 'QUARANTINE_BLOCK']
        self.assertGreater(len(block_events), 0)
        self.assertEqual(getattr(destination, 'active_pestilence_count', 0), 0)
        dest_infected = [a for a in destination.agents if DIS_PESTILENCE in getattr(a, 'diseases', [])]
        self.assertEqual(len(dest_infected), 0)

        # Repeal Trade Quarantine
        ok, rep_msg = repeal_trade_quarantine(destination)
        self.assertTrue(ok)
        self.assertFalse(destination.quarantine_active)
        self.assertFalse(rt.is_quarantined)

    def test_acute_pestilence_mortality(self):
        """Verify that Black Death pestilence carries severe acute mortality in demographics."""
        ctx = MockLiveContext(carrying_capacity=100)

        # 50 healthy young agents vs 50 plague agents
        healthy_agents = []
        for i in range(50):
            a = Agent(0)
            a.id = i
            a.alive = True
            a.hungry_steps = 0
            a.diseases = []
            a.output = Goods.food
            healthy_agents.append(a)

        plague_agents = []
        for i in range(50):
            a = Agent(0)
            a.id = 100 + i
            a.alive = True
            a.hungry_steps = 0
            a.diseases = [DIS_PESTILENCE]
            a.output = Goods.wood
            plague_agents.append(a)

        all_agents = healthy_agents + plague_agents

        dead_healthy = sum(1 for a in healthy_agents if handle_death(ctx, 20, a, all_agents))
        dead_plague = sum(1 for a in plague_agents if handle_death(ctx, 20, a, all_agents))

        # Plague mortality must be dramatically higher (~35% base per turn)
        self.assertGreater(dead_plague, dead_healthy)
        self.assertGreaterEqual(dead_plague, 8)


if __name__ == '__main__':
    unittest.main()
