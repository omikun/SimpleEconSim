"""Native campaign save/resume and creation-boundary checks for observations."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from governing_network import KEY, mode, project


def without_recording_references(value):
    # Native restore forks the causal recorder and emits a branch event. The
    # new branch's future event IDs intentionally differ; keep every decision,
    # person, material value and financial operation reference in the comparison.
    if isinstance(value, dict):
        return {key: without_recording_references(item) for key, item in value.items()
                if key != 'trace_event_id'}
    if isinstance(value, list):
        return [without_recording_references(item) for item in value]
    return value


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

    def test_wrong_scenario_and_unknown_mode_fail_before_generation(self):
        import client.desktop.engine as primary
        import worldview_engine as legacy
        for engine in (primary, legacy):
            with patch.object(engine, 'build_world') as generation:
                with self.assertRaises(ValueError):
                    engine.build_world_view(governing_network_mode='observe')
                with self.assertRaises(ValueError):
                    engine.build_world_view(scenario_id='egypt_1877', governing_network_mode='future')
                generation.assert_not_called()

    def test_native_checkpoint_preserves_observation_and_continues_the_same_network(self):
        from client.desktop.engine import build_world_view, step_world
        from native_simulation_checkpoint import save_world, restore_world
        from world_config import get_map_topology, set_map_topology
        previous = get_map_topology()
        self.addCleanup(set_map_topology, previous)
        set_map_topology('voronoi')
        for selected_mode in ('observe', 'governing'):
            with self.subTest(mode=selected_mode):
                world = build_world_view(scenario_id='egypt_1877', governing_network_mode=selected_mode)
                step_world(world)
                saved = deepcopy(world['scenario_state'][KEY])
                saved_flags = {p.id: deepcopy(getattr(p, '_strike_sources', None))
                               for tile in world['tiles'] for p in tile.agents}
                with tempfile.TemporaryDirectory() as directory:
                    manifest = save_world(world, directory, engine_module='client.desktop.engine')
                    step_world(world)
                    expected = deepcopy(world['scenario_state'][KEY])
                    from scripts.verify_governing_network import sampled_digest
                    expected_material = sampled_digest(world)
                    restored = restore_world(manifest, Path(directory) / 'continued')
                    self.assertEqual(mode(restored), selected_mode)
                    self.assertEqual(saved, restored['scenario_state'][KEY])
                    self.assertEqual(saved_flags, {p.id: getattr(p, '_strike_sources', None)
                                                  for tile in restored['tiles'] for p in tile.agents})
                    self.assertEqual(project(restored)['turn'], restored['turn'])
                    step_world(restored)
                    self.assertEqual(without_recording_references(expected),
                                     without_recording_references(restored['scenario_state'][KEY]))
                    self.assertEqual(expected_material, sampled_digest(restored))


if __name__ == '__main__':
    unittest.main()
