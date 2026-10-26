"""Seeded live simulation smoke: requesting narratives preserves semantic state/RNG."""
import json
import random
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from explanations.context import capture_server
from explanations.service import ExplanationService
from test_ai_explainer_service import FakeProvider, done


class LiveExplainerTests(unittest.TestCase):
    def test_seeded_turn_evidence_and_requests_do_not_mutate_the_world(self):
        from sim_server.sim_server import SimServer
        from trace_snapshots import sample
        from simulation_semantics import canonical_state, state_digest
        sim = SimServer(seed=4243, scenario_id='labor_frontier_rivalry')
        self.addCleanup(sim.run_trace._compact_writer.close)
        with tempfile.TemporaryDirectory() as directory:
            service = ExplanationService(FakeProvider(), Path(directory) / 'cache', Path(directory) / 'planning')
            try:
                for _ in range(3): sim.step()
                self.assertEqual(0, service.provider.calls)
                self.assertIsNone(service.executor)
                before = sample(sim.tiles, sim.nations)
                full_before = state_digest(canonical_state(sim.tiles, sim.nations, extra={'turn': sim.turn, 'history': sim._nation_history}))
                random_before = random.getstate(); numpy_before = np.random.get_state()
                count = sim.run_trace.count; digest = sim.run_trace.digest
                nation = sim.nations[0].name
                reports = []
                for metric, dimensions in (
                    ('finance.treasury', {}), ('people.population', {}),
                    ('goods.national_food_price', {'good': 'food'}),
                    ('politics.protest_energy', {})):
                    selection = {'entity': 'nation:' + nation, 'metric_id': metric, 'turn': sim.turn, **dimensions}
                    started = time.monotonic()
                    result = done(service, service.request(capture_server(sim, selection)))
                    self.assertEqual('ready', result['state'], metric + ': ' + result['message'])
                    reports.append({'metric': metric, 'values': result['result']['packet']['values'],
                                    'seconds_with_fixture_provider': time.monotonic() - started})
                self.assertEqual(before, sample(sim.tiles, sim.nations))
                self.assertEqual(full_before, state_digest(canonical_state(sim.tiles, sim.nations, extra={'turn': sim.turn, 'history': sim._nation_history})))
                self.assertEqual(random_before, random.getstate())
                after = np.random.get_state()
                self.assertEqual(numpy_before[0], after[0]); np.testing.assert_array_equal(numpy_before[1], after[1])
                self.assertEqual(numpy_before[2:], after[2:])
                self.assertEqual(count, sim.run_trace.count); self.assertEqual(digest, sim.run_trace.digest)
                target = Path(__file__).resolve().parents[1] / 'tmp' / 'ai-explainer-live-smoke.json'
                target.write_text(json.dumps({'seed': 4243, 'scenario': 'labor_frontier_rivalry',
                    'turn': sim.turn, 'model_calls_without_request': 0, 'requested_reports': reports,
                    'semantic_state_and_rng_unchanged': True}, indent=2))
            finally:
                service.close()


if __name__ == '__main__': unittest.main()
