import unittest
from unittest.mock import MagicMock
from popular_resistance import (
    PopularResistanceManager,
    ResistanceState,
    RebellionConfig,
    AssassinationPlot,
    reset_popular_resistance_manager,
)
from agent import Agent

class DummyTenure:
    def __init__(self, plots):
        self._plots = plots
    def enclosed_plots(self):
        return self._plots
    def find_plot(self, pid):
        for p in self._plots:
            if p.plot_id == pid:
                return p
        return None

class DummyTile:
    def __init__(self, name="Testshire", x=2, y=3):
        self.name = name
        self.x = x
        self.y = y
        self.enclosure_protest_turns = 1
        self.enclosure_protested = False
        self.has_police_post = False
        self.has_military_garrison = False
        self.tenure = DummyTenure([])
        self.agents = []
        self.unrest_level = 0.0
        self.gov = MagicMock()
        self.gov.police_officers = 0
        self.gov.agent = MagicMock()
        self.gov.agent.cash = 500.0
        self.charity = MagicMock()
        self.charity.agent = MagicMock()
        self.charity.agent.cash = 0.0

class DummyPlot:
    def __init__(self, plot_id="plot_0", fraction=0.4):
        self.plot_id = plot_id
        self.fraction = fraction

class TestCharismaticRebellion(unittest.TestCase):
    def setUp(self):
        reset_popular_resistance_manager()
        self.mgr = PopularResistanceManager()
        self.mgr.config = RebellionConfig(
            fermentation_pace=1.0,
            alpha_broadcast=0.25,
            beta_contagion=0.30,
            deterrence_factor=0.05,
            f_crit_ratio=0.35,
            eruption_ratio=0.70
        )
        self.tile = DummyTile()
        self.tile.tenure = DummyTenure([DummyPlot("plot_enclosed", 0.5)])
        self.world = {
            'tiles': [self.tile],
            'ticker_messages': []
        }

    def _create_agent(self, agent_id, charisma=0.5, ambition=0.5, social_class="proletarian", cash=50.0):
        ag = Agent(0)
        ag.id = agent_id
        ag.charisma = charisma
        ag.ambition = ambition
        ag.social_class = social_class
        ag.cash = cash
        ag.alive = True
        ag.hungry_steps = 1
        self.tile.agents.append(ag)
        return ag

    def test_leader_emergence(self):
        ag1 = self._create_agent(101, charisma=0.2, ambition=0.1)
        ag2 = self._create_agent(102, charisma=0.9, ambition=0.8)
        
        # State before emergence
        state = self.mgr.get_state(self.tile.name)
        self.assertIsNone(state.leader_id)
        
        leader = self.mgr._find_or_emerge_leader(self.tile)
        self.assertIsNotNone(leader)
        self.assertEqual(leader.id, 102)
        self.assertEqual(state.leader_id, 102)
        self.assertGreater(state.leader_charisma, 0.7)
        self.assertIn(102, state.followers)

    def test_fermentation_growth_and_eruption(self):
        # Create a population of 10 sympathizers
        leader = self._create_agent(1, charisma=1.0, ambition=0.9)
        for i in range(2, 11):
            self._create_agent(i, charisma=0.3, ambition=0.3)
            
        state = self.mgr.get_state(self.tile.name)
        self.tile.unrest_level = 1.0 # High grievance to drive fast fermentation
        
        # Step fermentation over multiple turns until natural eruption
        erupted = False
        for turn in range(1, 20):
            evs = self.mgr.step_rebellion_fermentation(self.tile, t=turn, world=self.world)
            if any(ev.get('kind') == "ENCLOSURE_REVOLT_ORGANIZING" for ev in evs):
                erupted = True
                break
                
        self.assertTrue(erupted, "Rebellion should naturally erupt when followers cross eruption_ratio")
        self.assertEqual(state.enclosure_stage, "organizing")
        self.assertGreaterEqual(len(state.followers), int(len(self.tile.agents) * self.mgr.config.eruption_ratio))

    def test_fermentation_pace_tuning(self):
        # Setup population
        for i in range(1, 11):
            self._create_agent(i, charisma=0.8 if i == 1 else 0.2)
            
        # Slower pace
        self.mgr.config.fermentation_pace = 0.2
        self.mgr.step_rebellion_fermentation(self.tile, t=1, world=self.world)
        state_slow = self.mgr.get_state(self.tile.name)
        followers_slow = len(state_slow.followers)
        
        # Reset and fast pace
        self.mgr.tile_states.clear()
        self.tile.agents.clear()
        for i in range(1, 11):
            self._create_agent(i, charisma=0.8 if i == 1 else 0.2)
        self.mgr.config.fermentation_pace = 2.0
        self.mgr.step_rebellion_fermentation(self.tile, t=1, world=self.world)
        state_fast = self.mgr.get_state(self.tile.name)
        followers_fast = len(state_fast.followers)
        
        self.assertGreater(followers_fast, followers_slow)

    def test_assassination_plot_initiation_and_conservation(self):
        leader = self._create_agent(1, charisma=0.8, cash=100.0)
        state = self.mgr.get_state(self.tile.name)
        state.leader_id = 1
        state.leader_name = "Rebel Bob"
        
        gov_initial_cash = self.tile.gov.agent.cash
        cost = 100.0
        success, msg, data = self.mgr.initiate_assassination_plot(
            tile=self.tile,
            t=10,
            world=self.world,
            operative_funds=cost,
            turns_delay=3
        )
        self.assertTrue(success)
        self.assertIsNotNone(state.active_plot)
        self.assertEqual(state.active_plot.turns_remaining, 3)
        self.assertEqual(self.tile.gov.agent.cash, gov_initial_cash - cost)

    def test_early_assassination_decapitation(self):
        # Create 10 agents, 1 follower (below F_crit = 3)
        leader = self._create_agent(1, charisma=0.8, cash=50.0)
        for i in range(2, 11):
            self._create_agent(i, charisma=0.2)
            
        state = self.mgr.get_state(self.tile.name)
        state.leader_id = 1
        state.leader_name = "Young Rebel"
        state.followers = [1] # Only leader, len-1 = 0 < F_crit (3)
        
        plot = AssassinationPlot(
            target_leader_id=1,
            target_leader_name="Young Rebel",
            tile_name=self.tile.name,
            turns_remaining=1,
            total_turns=2,
            funding_allocated=75.0,
            detection_risk_per_turn=0.0
        )
        state.active_plot = plot
        
        # Step fermentation to turn where plot strikes
        evs = self.mgr.step_rebellion_fermentation(self.tile, t=2, world=self.world)
        
        self.assertFalse(leader.alive)
        self.assertIsNone(state.leader_id)
        self.assertEqual(len(state.followers), 0)
        self.assertGreater(state.terror_cooldown, 0)
        self.assertEqual(len(state.martyrs), 0)
        self.assertEqual(self.tile.charity.agent.cash, 50.0) # Leader cash conserved

    def test_late_assassination_martyrdom_cascade(self):
        # Create 10 agents, 6 followers (above F_crit = 3)
        leader = self._create_agent(1, charisma=0.9, cash=75.0)
        for i in range(2, 11):
            self._create_agent(i, charisma=0.3)
            
        state = self.mgr.get_state(self.tile.name)
        state.leader_id = 1
        state.leader_name = "Iconic Leader"
        state.followers = [1, 2, 3, 4, 5, 6]
        initial_followers_count = len(state.followers)
        
        plot = AssassinationPlot(
            target_leader_id=1,
            target_leader_name="Iconic Leader",
            tile_name=self.tile.name,
            turns_remaining=1,
            total_turns=3,
            funding_allocated=75.0,
            detection_risk_per_turn=0.0
        )
        state.active_plot = plot
        
        evs = self.mgr.step_rebellion_fermentation(self.tile, t=2, world=self.world)
        
        self.assertFalse(leader.alive)
        self.assertGreater(len(state.followers), initial_followers_count)
        self.assertGreater(state.martyrdom_multiplier, 1.0)
        self.assertIn("Iconic Leader", state.martyrs)
        self.assertEqual(state.enclosure_stage, "protest")
        self.assertEqual(self.tile.charity.agent.cash, 75.0)

    def test_debug_telemetry_and_fog_of_war(self):
        leader = self._create_agent(1, charisma=0.7)
        for i in range(2, 11):
            self._create_agent(i)
            
        state = self.mgr.get_state(self.tile.name)
        state.leader_id = 1
        state.leader_name = "Agitator Debug"
        state.followers = [1, 2]
        state.fermentation_turns = 4
        
        # Developer debug telemetry (exact values)
        debug_info = self.mgr.get_rebellion_debug_info(self.tile)
        self.assertEqual(debug_info['leader_id'], 1)
        self.assertEqual(debug_info['followers_count'], 2)
        self.assertEqual(debug_info['sympathizers_capacity_k'], 10)
        self.assertEqual(debug_info['f_crit_threshold'], 3)
        self.assertEqual(debug_info['t_rebel_threshold'], 7)
        self.assertEqual(debug_info['current_regime_zone'], 'DECAPITATION_ZONE')
        
        # Player fog-of-war intelligence report (qualitative)
        intel = self.mgr.get_player_intelligence_report(self.tile)
        self.assertIn('public_atmosphere', intel)
        self.assertIn('martyrdom_risk_assessment', intel)
        self.assertTrue(intel['leader_known'])
        self.assertNotIn('followers_count', intel) # Exact count hidden
        self.assertNotIn('f_crit_threshold', intel) # Exact threshold hidden
        self.assertEqual(intel['martyrdom_risk_assessment'], 'Moderate / Unstable')

if __name__ == '__main__':
    unittest.main()
