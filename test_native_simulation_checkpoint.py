"""Full native Egypt state and trace continuation across a process boundary."""
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from native_simulation_checkpoint import save_world, restore_world
from simulation_semantics import canonical_state, state_digest, graph_differences
from world_config import get_map_topology, set_map_topology
from worldview_engine import build_world_view, step_world


def economic_state(world):
    return canonical_state(world['tiles'], world['nations'], extra={
        'turn': world['turn'], 'pair_orders': world['pair_orders'],
        'currencies': world['currencies'], 'scenario_state': world['scenario_state'],
        'currency_totals': world['currency_totals'], 'violations': world['violations'],
        'player_nation_name': world['player_nation_name']})


class NativeSimulationCheckpointTests(unittest.TestCase):
    def test_egypt_native_continues_full_economy_in_fresh_process(self):
        previous_topology = get_map_topology()
        self.addCleanup(set_map_topology, previous_topology)
        set_map_topology('voronoi')
        with tempfile.TemporaryDirectory() as directory:
            world = build_world_view(scenario_id='egypt_1877')
            step_world(world)
            # A named renderer is recreated. Arbitrary locks are not ignored.
            world['_micropoly_gpu_renderer'] = threading.Lock()
            recursion_limit = sys.getrecursionlimit()
            manifest = save_world(world, directory)
            self.assertEqual(recursion_limit, sys.getrecursionlimit())
            original_path = world['run_trace'].path
            original_prefix = original_path.read_bytes()
            self.assertIn('_micropoly_gpu_renderer', world)
            world.pop('_micropoly_gpu_renderer')
            step_world(world)
            expected = economic_state(world)
            expected_digest = state_digest(expected)
            runner = Path(directory)/'continue_native.py'
            runner.write_text('''import gzip,json,sys
from native_simulation_checkpoint import restore_world
from worldview_engine import step_world
from simulation_semantics import canonical_state,state_digest
world=restore_world(sys.argv[1],sys.argv[2])
step_world(world)
state=canonical_state(world['tiles'],world['nations'],extra={
 'turn':world['turn'],'pair_orders':world['pair_orders'],'currencies':world['currencies'],
 'scenario_state':world['scenario_state'],'currency_totals':world['currency_totals'],
 'violations':world['violations'],'player_nation_name':world['player_nation_name']})
digest=state_digest(state)
print('NATIVE_STATE_DIGEST='+digest)
if digest!=sys.argv[3]:
 with gzip.open(sys.argv[4],'wt') as file:json.dump(state['graph'],file)
''')
            difference_path = Path(directory)/'difference.json.gz'
            result = subprocess.run(
                [sys.executable, str(runner), str(manifest), str(Path(directory)/'fresh'),
                 expected_digest, str(difference_path)], check=True, capture_output=True,
                text=True, env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parent)))
            if difference_path.exists():
                with gzip.open(difference_path, 'rt') as file:
                    self.fail(str(graph_differences(expected['graph'], json.load(file))))
            self.assertIn('NATIVE_STATE_DIGEST='+expected_digest, result.stdout)
            restored = restore_world(manifest, Path(directory)/'same-process')
            self.assertNotIn('_micropoly_gpu_renderer', restored)
            self.assertIs(restored['tiles'], restored['_trace_session'].tiles)
            self.assertIs(restored['run_trace'], restored['_trace_session'].run_trace)
            self.assertNotEqual(restored['run_trace'].path, original_path)
            egypt = next(nation for nation in restored['nations'] if nation.name == 'Egypt')
            self.assertIs(restored, egypt.government.scenario_debt_world)
            step_world(restored)
            actual = economic_state(restored)
            self.assertEqual(expected_digest, state_digest(actual),
                             str(graph_differences(expected['graph'], actual['graph'])))
            self.assertEqual(original_prefix, original_path.read_bytes()[:len(original_prefix)])
            self.assertEqual(recursion_limit, sys.getrecursionlimit())
            restored['unrecognized_runtime_resource'] = threading.Lock()
            committed = set(Path(directory).glob('*.checkpoint.json'))
            with self.assertRaises(TypeError):
                save_world(restored, directory)
            self.assertEqual(committed, set(Path(directory).glob('*.checkpoint.json')))
            self.assertEqual(recursion_limit, sys.getrecursionlimit())


if __name__ == '__main__':
    unittest.main()
