import unittest

from client.web import manager_server, tech_sim_server
from macro.innovation import TECH_CATALOG


class TestTechSimServer(unittest.TestCase):
    def test_catalog_synced_with_macro_innovation(self):
        """Every technology in macro/innovation.py TECH_CATALOG must be present in the simulator catalog."""
        catalog = tech_sim_server.build_dynamic_catalog()
        for tech_id, tech in TECH_CATALOG.items():
            self.assertIn(tech_id, catalog, f"Missing {tech_id} from tech_sim_server catalog")
            entry = catalog[tech_id]
            self.assertEqual(entry["live_base_xp_required"], tech.base_xp_required)
            self.assertEqual(entry["live_domain"], tech.domain.value)
            self.assertGreaterEqual(len(entry["avenues"]), 3)
            self.assertEqual(len(entry["downstream"]), 4)

    def test_complexity_espionage_ceilings(self):
        """Verify complexity ceilings tighten from Era I (Gunpowder: 85 XP) to Era IV (Microchips: 30 XP)."""
        catalog = tech_sim_server.build_dynamic_catalog()
        self.assertEqual(catalog["gunpowder_blasting"]["max_steal_xp"], 85)
        self.assertEqual(catalog["steam_engines"]["max_steal_xp"], 65)
        self.assertEqual(catalog["petroleum_refining"]["max_steal_xp"], 50)
        self.assertEqual(catalog["microelectronics"]["max_steal_xp"], 30)

    def test_subsidy_modes_and_prereq_gate(self):
        """Crash 4x subsidy must outpace 1x standard subsidy in low-wage regimes, and missing prereq caps XP at 59."""
        std_res = tech_sim_server.simulate_trajectory({
            "tech_id": "steam_engines",
            "turns": 15,
            "prox_mult": 1.0,
            "wage_ratio": 0.4,
            "subsidy_mode": "standard",
            "discovery_progress": 100.0,
            "refinement_xp": 1.0,
            "has_prereq": True,
        })
        crash_res = tech_sim_server.simulate_trajectory({
            "tech_id": "steam_engines",
            "turns": 15,
            "prox_mult": 1.0,
            "wage_ratio": 0.4,
            "subsidy_mode": "crash",
            "discovery_progress": 100.0,
            "refinement_xp": 1.0,
            "has_prereq": True,
        })
        self.assertGreater(crash_res["refinement_rate_per_turn"], std_res["refinement_rate_per_turn"] * 2.0)
        self.assertGreater(crash_res["final_refinement_xp"], std_res["final_refinement_xp"])

        # Missing prerequisite sibling tech must hard-cap Refinement XP at 59 (Tier 2)
        gated_res = tech_sim_server.simulate_trajectory({
            "tech_id": "steam_engines",
            "turns": 40,
            "prox_mult": 4.0,
            "wage_ratio": 3.5,
            "subsidy_mode": "crash",
            "discovery_progress": 100.0,
            "refinement_xp": 50.0,
            "has_prereq": False,
        })
        self.assertEqual(gated_res["final_refinement_xp"], 59.0)
        self.assertEqual(gated_res["final_tier"], 2)

    def test_incumbent_guild_blockade_throttles_refinement(self):
        """Active incumbent guild legislation throttles refinement speed compared to an unblocked challenger."""
        blocked = tech_sim_server.simulate_trajectory({
            "tech_id": "petroleum_refining",
            "turns": 15,
            "discovery_progress": 100.0,
            "refinement_xp": 10.0,
            "guild_law_active": True,
        })
        unblocked = tech_sim_server.simulate_trajectory({
            "tech_id": "petroleum_refining",
            "turns": 15,
            "discovery_progress": 100.0,
            "refinement_xp": 10.0,
            "guild_law_active": False,
        })
        self.assertAlmostEqual(blocked["refinement_rate_per_turn"] * 4.0, unblocked["refinement_rate_per_turn"], places=1)
        self.assertGreater(unblocked["final_refinement_xp"], blocked["final_refinement_xp"])

    def test_manager_server_registers_techsim(self):
        """Server Control Center (manager_server.py) must register 'techsim' on port 8082."""
        self.assertIn("techsim", manager_server.SERVICES)
        spec = manager_server.SERVICES["techsim"]
        self.assertEqual(spec["default_port"], 8082)
        status = manager_server.get_service_status("techsim")
        self.assertEqual(status["key"], "techsim")
        self.assertEqual(status["port"], 8082)


if __name__ == "__main__":
    unittest.main()
