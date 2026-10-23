"""Revolutionary legitimacy must explain the native national chart reset."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from agents.resistance.manager import PopularResistanceManager
from nation import Nation
from region import Region
from run_trace import RunTrace
from price_trace import replay_event


class CommuneLegitimacyTraceTests(unittest.TestCase):
    def test_actual_commune_thresholds_and_reset_are_replayable(self):
        with tempfile.TemporaryDirectory() as directory:
            nation = Nation('Commune', 'C', legitimacy=.05, register=False)
            tile = Region('District', 0, number_of_agents=0)
            nation.add_tile(tile)
            trace = RunTrace(Path(directory)/'commune.ctr', 'commune')
            tile._run_trace = trace
            tile._collective_trace_clock = {'turn': 27, 'phase': 'resistance', 'next': 1}
            manager = PopularResistanceManager()
            manager.get_state(tile.name).has_barricades = True
            with patch('imperialism.get_imperialism_manager') as imperialism:
                imperialism.return_value.repudiate_all_imperial_obligations.return_value = {}
                events = manager.evaluate_revolutionary_commune(
                    nation, 27, {'tiles': [tile], 'nations': [nation]})
            self.assertEqual('REVOLUTIONARY_COMMUNE_DECLARED', events[0]['kind'])
            row = trace.query(kind='commune_legitimacy_reset')['events'][0]
            self.assertEqual(.85, nation.legitimacy)
            self.assertTrue(row['formula_replay']['matches'])
            tampered = copy.deepcopy(row)
            tampered['inputs']['barricaded_tile_ids'] = []
            self.assertFalse(replay_event(tampered)['matches'])
            self.assertEqual([], manager.evaluate_revolutionary_commune(nation, 28, {}))


if __name__ == '__main__':
    unittest.main()
