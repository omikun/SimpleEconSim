"""Native campaign save/resume and creation-boundary checks for observations."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from governing_network import KEY, mode, project


class GoverningNetworkNativeTests(unittest.TestCase):
    def test_verification_relabels_run_identity_without_hiding_event_or_money_changes(self):
        from scripts.verify_governing_network import normalize_trace_identity
        left = {'receipt': 'desktop-left:42', 'cash': 17.5, 'other_uuid': 'project-abc'}
        right = {'receipt': 'desktop-right:42', 'cash': 17.5, 'other_uuid': 'project-abc'}
        normalize_trace_identity(left, 'desktop-left')
        normalize_trace_identity(right, 'desktop-right')
        self.assertEqual(left, right)
        later = {'receipt': 'desktop-right:43', 'cash': 18., 'other_uuid': 'project-def'}
        normalize_trace_identity(later, 'desktop-right')
        self.assertNotEqual(left['receipt'], later['receipt'])
        self.assertNotEqual(left['cash'], later['cash'])
        self.assertNotEqual(left['other_uuid'], later['other_uuid'])

    def test_wrong_scenario_and_unreleased_governing_mode_fail_before_generation(self):
        import client.desktop.engine as primary
        import worldview_engine as legacy
        for engine in (primary, legacy):
            with patch.object(engine, 'build_world') as generation:
                with self.assertRaises(ValueError):
                    engine.build_world_view(governing_network_mode='observe')
                with self.assertRaises(ValueError):
                    engine.build_world_view(scenario_id='egypt_1877', governing_network_mode='governing')
                generation.assert_not_called()

    def test_native_checkpoint_preserves_observation_and_continues_the_same_network(self):
        from client.desktop.engine import build_world_view, step_world
        from native_simulation_checkpoint import save_world, restore_world
        from world_config import get_map_topology, set_map_topology
        previous = get_map_topology()
        self.addCleanup(set_map_topology, previous)
        set_map_topology('voronoi')
        world = build_world_view(scenario_id='egypt_1877', governing_network_mode='observe')
        step_world(world)
        saved = deepcopy(world['scenario_state'][KEY])
        with tempfile.TemporaryDirectory() as directory:
            manifest = save_world(world, directory, engine_module='client.desktop.engine')
            step_world(world)
            expected = deepcopy(world['scenario_state'][KEY])
            restored = restore_world(manifest, Path(directory) / 'continued')
            self.assertEqual(mode(restored), 'observe')
            self.assertEqual(saved, restored['scenario_state'][KEY])
            self.assertEqual(project(restored)['turn'], restored['turn'])
            step_world(restored)
            self.assertEqual(expected, restored['scenario_state'][KEY])


if __name__ == '__main__':
    unittest.main()
