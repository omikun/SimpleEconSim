import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl_cache_coc")

from client.web import manager_server, tech_sim_server
from tile_resources import TileResource
from innovation import InnovationSystem, TECH_CATALOG
from run_trace import RunTrace


def _make_mock_nation(name: str, cash: float = 5000.0, resources=None):
    res_list = list(resources if resources is not None else list(TileResource))
    tile = SimpleNamespace(
        name=f"{name}_Capital",
        natural_resources=res_list,
        resources={r: 1.0 for r in res_list},
        firms=[],
        people=[],
        terrain="hills",
    )
    gov_agent = SimpleNamespace(cash=float(cash))
    gov = SimpleNamespace(agent=gov_agent)
    return SimpleNamespace(
        name=name,
        currency="USD",
        government=gov,
        tiles=[tile],
        last_All_M=1000.0,
    )


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

    def test_live_innovation_espionage_stepping_and_domestic_refinement(self):
        """
        Verify live InnovationSystem.attempt_tech_espionage:
        - Requires prerequisite techs first
        - Steps +1 Tier per steal up to the Era Complexity Ceiling (e.g. 30 XP / Tier 2 for Class IV microelectronics)
        - Allows the nation to domestically refine the stolen tech from Tier 2 up to Tier 4 (90+ XP)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            trace = RunTrace(Path(tmpdir) / "trace.ctr", "test_espionage")
            inno = InnovationSystem()
            inno.run_trace = trace
            source = _make_mock_nation("LeaderNation")
            challenger = _make_mock_nation("ChallengerNation")

            # Give source nation all prerequisites + Tier 4 microelectronics (100 XP)
            for tid in ("waterwheel_milling", "bloomery_iron", "three_field_rotation", "double_entry_accounting",
                        "BLAST_FURNACE", "coal_coking", "ocean_navigation", "steam_engines", "bessemer_steel",
                        "railway_locomotion", "dynamo_electrification", "microelectronics"):
                if tid in TECH_CATALOG:
                    inno.discovered_techs.setdefault(source.name, set()).add(tid)
                    inno.tech_refinement_xp.setdefault(source.name, {})[tid] = 100.0

            # 1. Challenger missing prerequisites ('dynamo_electrification') cannot steal 'microelectronics'
            ok_blocked, msg_blocked = inno.attempt_tech_espionage(challenger, "microelectronics", t=1, nations=[source, challenger])
            self.assertFalse(ok_blocked)
            self.assertIn("Dependency Lock", msg_blocked)

            # 2. Grant Challenger prerequisites with Tier 3 mastery on dynamo_electrification and bessemer_steel
            inno.discovered_techs.setdefault(challenger.name, set()).update({"dynamo_electrification", "bessemer_steel"})
            inno.tech_refinement_xp.setdefault(challenger.name, {})["dynamo_electrification"] = 70.0
            inno.tech_refinement_xp.setdefault(challenger.name, {})["bessemer_steel"] = 70.0

            # First steal: Tier 0 -> Tier 1 (15 XP)
            ok_t1, _ = inno.attempt_tech_espionage(challenger, "microelectronics", t=2, nations=[source, challenger])
            self.assertTrue(ok_t1)
            self.assertEqual(inno.get_tech_tier(challenger.name, "microelectronics"), 1)
            self.assertEqual(inno.get_refinement_xp(challenger.name, "microelectronics"), 15.0)

            # Second steal: Tier 1 -> Tier 2 (capped at Class IV ceiling = 30 XP)
            ok_t2, _ = inno.attempt_tech_espionage(challenger, "microelectronics", t=3, nations=[source, challenger])
            self.assertTrue(ok_t2)
            self.assertEqual(inno.get_tech_tier(challenger.name, "microelectronics"), 2)
            self.assertEqual(inno.get_refinement_xp(challenger.name, "microelectronics"), 30.0)

            # Third steal: Blocked by Class IV complexity ceiling (30 XP)
            ok_cap, msg_cap = inno.attempt_tech_espionage(challenger, "microelectronics", t=4, nations=[source, challenger])
            self.assertFalse(ok_cap)
            self.assertIn("Espionage Ceiling", msg_cap)

            # 3. Domestic refinement after reaching steal ceiling: switch to 4x crash subsidy and refine locally to Tier 4!
            inno.set_subsidy_mode(challenger, "microelectronics", "crash", t=5)
            for step_t in range(6, 28):
                inno.step_refinement([source, challenger], t=step_t)

            self.assertGreaterEqual(inno.get_refinement_xp(challenger.name, "microelectronics"), 90.0)
            self.assertEqual(inno.get_tech_tier(challenger.name, "microelectronics"), 4)

    def test_live_innovation_guild_blockade_and_resolution(self):
        """Verify incumbent guild legislative blockades throttle refinement to 0.25x until repealed/bought out/bypassed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trace = RunTrace(Path(tmpdir) / "trace.ctr", "test_guild")
            inno = InnovationSystem()
            inno.run_trace = trace
            incumbent = _make_mock_nation("IncumbentEmpire", cash=5000.0)
            inno.discovered_techs.setdefault(incumbent.name, set()).update({"coal_coking", "steam_engines"})
            inno.tech_refinement_xp.setdefault(incumbent.name, {})["coal_coking"] = 60.0
            inno.tech_refinement_xp.setdefault(incumbent.name, {})["steam_engines"] = 10.0

            # Activate guild blockade on steam_engines
            block = inno.get_guild_blockade(incumbent, "steam_engines")
            block["active"] = True
            block["clout"] = 75.0

            inno.step_refinement([incumbent], t=1)
            xp_after_blocked_step = inno.get_refinement_xp(incumbent.name, "steam_engines")
            blocked_delta = xp_after_blocked_step - 10.0
            self.assertGreater(blocked_delta, 0.0)

            # Repeal the guild charter and step again — refinement delta must quadruple
            ok_res, _ = inno.resolve_guild_blockade(incumbent, "steam_engines", "repeal", t=2)
            self.assertTrue(ok_res)
            self.assertFalse(inno.get_guild_blockade(incumbent, "steam_engines")["active"])

            inno.step_refinement([incumbent], t=3)
            unblocked_delta = inno.get_refinement_xp(incumbent.name, "steam_engines") - xp_after_blocked_step
            self.assertAlmostEqual(unblocked_delta, blocked_delta * 4.0, places=2)


if __name__ == "__main__":
    unittest.main()
