"""Full live-world checkpoints, branch identity, retries and damaged-save gates."""
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from sim_server.sim_server import SimServer
from sim_server.protocol import CommandMessage, CommandType
from simulation_checkpoint import save, restore, recover
from trace_audit import audit
from trace_codec import CorruptTrace
from trace_snapshots import sample
import random_cache


class SimulationCheckpointTests(unittest.TestCase):
    def test_live_state_rng_shared_accounts_and_retry_continue_on_new_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            server=SimServer(seed=4242,terrain_seed=4242,nation_seed=4242)
            nation=server.nations[0]
            command=CommandMessage(CommandType.SOVEREIGN_BOND,
                {'action':'lobby_upgrade','nation':nation.name},command_id='saved-command')
            response=server.execute_command(command)
            server.step()
            manifest=save(server,directory)
            original_path=server.run_trace.path
            original_prefix=original_path.read_bytes()
            server.step()
            expected=sample(server.tiles,server.nations)
            rng=random.getstate();numpy_rng=np.random.get_state()
            expected_digest=hashlib.sha256(json.dumps(sorted(expected.items()),sort_keys=True).encode()).hexdigest()
            script = """import hashlib,json,sys
from simulation_checkpoint import restore
from trace_snapshots import sample
server=restore(sys.argv[1],sys.argv[2])
server.step()
print('SEMANTIC_DIGEST='+hashlib.sha256(json.dumps(sorted(sample(server.tiles,server.nations).items()),sort_keys=True).encode()).hexdigest())
"""
            completed=subprocess.run([sys.executable,'-c',script,str(manifest),str(Path(directory)/'fresh-process')],
                                     check=True,text=True,capture_output=True)
            self.assertIn('SEMANTIC_DIGEST='+expected_digest,completed.stdout)
            cache=(list(random_cache.rand._buf),random_cache.rand._idx)
            restored=restore(manifest,Path(directory)/'branches')
            self.assertEqual(1,restored.turn)
            self.assertNotEqual(original_path,restored.run_trace.path)
            count=restored.run_trace.count
            self.assertEqual(response,restored.execute_command(command))
            self.assertEqual(count,restored.run_trace.count)
            restored.step()
            observed=sample(restored.tiles,restored.nations)
            differences={key:(expected.get(key),observed.get(key)) for key in expected.keys()|observed.keys()
                         if expected.get(key)!=observed.get(key)}
            self.assertFalse(differences,str(list(differences.items())[:12]))
            self.assertEqual(rng,random.getstate())
            self.assertEqual(numpy_rng[0],np.random.get_state()[0])
            np.testing.assert_array_equal(numpy_rng[1],np.random.get_state()[1])
            self.assertEqual(numpy_rng[2:],np.random.get_state()[2:])
            self.assertEqual(cache,(random_cache.rand._buf,random_cache.rand._idx))
            self.assertEqual(original_prefix,original_path.read_bytes()[:len(original_prefix)])
            result=audit(restored.run_trace.path)
            self.assertTrue(result['structural_and_supported_formula_checks_pass'],result['issues'])
            # Physical account identities are preserved while address keys are
            # rebuilt for the restored objects; shared banks remain shared.
            for key,info in restored.run_trace.bank_book.banks.items():
                self.assertEqual(id(info['bank']),key)
            self.assertEqual(len(server.run_trace.treasury_book.accounts),len(restored.run_trace.treasury_book.accounts))

    def test_pending_cargo_loan_and_technology_causes_survive_restore(self):
        from agent import Agent, initialize_agent
        from goods import Goods
        from transporter import Route
        from innovation import get_innovation_system
        from innovation_trace import record_technology
        with tempfile.TemporaryDirectory() as directory:
            server=SimServer(seed=4242,terrain_seed=4242,nation_seed=4242)
            source=next(tile for tile in server.tiles if tile.bank is not None)
            destination=next(tile for tile in server.tiles if tile is not source)
            trader=Agent(0)
            initialize_agent(trader,Goods.food,0,0,20)
            trader.is_trader=True
            source.agents.append(trader)
            source.trader_agents.append(trader)
            route=Route('checkpoint-cargo',source,destination,base_delay=1)
            source.routes[destination.name]=route
            trader.inventory_export[Goods.food.value]=4
            route.post(trader,Goods.food,4)
            departure=server.run_trace.query(kind='route_shipment_departure')['events'][-1]
            source.bank.Borrow(0,trader,10,trace_region=source)
            loan=trader.loans[-1]
            nation=server.nations[0]
            get_innovation_system().get_discovered_techs(nation.name).add('checkpoint-tech')
            technology=record_technology(nation,'checkpoint-tech',0,'checkpoint_fixture')
            manifest=save(server,directory)
            route.deliver_pending();route.advance();loan.pay(2)
            expected=(trader.inventory_foreign[Goods.food.value],loan.principle_paid,source.bank.total_liabilities)
            restored=restore(manifest,Path(directory)/'branches')
            restored_source=next(tile for tile in restored.tiles if tile.name==source.name)
            restored_route=restored_source.routes[destination.name]
            restored_trader=restored_route.pending[0][0]
            restored_loan=restored_trader.loans[-1]
            self.assertIs(restored_loan,restored_source.bank.loans[-1])
            self.assertIs(restored_source.bank,restored_loan.bank)
            restored_route.deliver_pending();restored_route.advance();restored_loan.pay(2)
            self.assertEqual(expected,(restored_trader.inventory_foreign[Goods.food.value],
                                      restored_loan.principle_paid,restored_source.bank.total_liabilities))
            arrival=restored.run_trace.query(kind='route_shipment_arrival')['events'][-1]
            self.assertIn(departure['event_id'],arrival['cause_event_ids'])
            self.assertEqual(technology,restored.run_trace.technology_event_id(nation.name,'checkpoint-tech'))
            self.assertTrue(get_innovation_system().has_tech(nation.name,'checkpoint-tech'))
            self.assertTrue(audit(restored.run_trace.path)['structural_and_supported_formula_checks_pass'])

    def test_manifest_publication_failure_and_torn_tail_recovery_preserve_source(self):
        with tempfile.TemporaryDirectory() as directory:
            server=SimServer(seed=4242,terrain_seed=4242,nation_seed=4242)
            manifest=save(server,directory)
            source=server.run_trace.path
            saved=json.loads(manifest.read_text())
            server.run_trace.emit(server.tiles[0]._collective_trace_clock,kind='uncommitted_test')
            damaged=source.read_bytes()[:-1]
            source.write_bytes(damaged)
            recovered,report=recover(manifest,source,Path(directory)/'recovery')
            self.assertEqual(0,recovered.turn)
            self.assertTrue(report['torn_tail'])
            self.assertEqual(damaged,source.read_bytes())
            self.assertGreater(report['discarded_tail_bytes'],0)
            # An interior checksum error cannot be presented as tail recovery.
            corrupt=bytearray(damaged);corrupt[40]^=1;source.write_bytes(corrupt)
            with self.assertRaises(CorruptTrace):recover(manifest,source,Path(directory)/'corrupt')
            state=Path(directory)/saved['state_file']
            state.write_bytes(state.read_bytes()+b'x')
            with self.assertRaisesRegex(ValueError,'state digest'):restore(manifest,Path(directory)/'badstate')
            active=SimServer(seed=4242,terrain_seed=4242,nation_seed=4242)
            committed=set(Path(directory).glob('*.checkpoint.json'))
            import simulation_checkpoint
            publish=simulation_checkpoint._publish
            def fail_manifest(path,data):
                if path.name.endswith('.checkpoint.json'):raise OSError('injected publication failure')
                return publish(path,data)
            with patch('simulation_checkpoint._publish',side_effect=fail_manifest):
                with self.assertRaisesRegex(OSError,'publication failure'):save(active,directory)
            self.assertEqual(committed,set(Path(directory).glob('*.checkpoint.json')))
            with patch.object(active.run_trace._compact_writer,'append',side_effect=OSError('injected trace failure')):
                with self.assertRaisesRegex(OSError,'trace failure'):save(active,directory)
            self.assertEqual(committed,set(Path(directory).glob('*.checkpoint.json')))


if __name__=='__main__':unittest.main()
