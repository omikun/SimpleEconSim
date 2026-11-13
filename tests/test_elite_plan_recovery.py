import io
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from goods import Goods
from world_config import ElitePlanningConfig
from economy.elite_plan_execution import review_plan, maintain_plans
from economy.elite_plan_receipts import observe_receipt
from economy.actor_accounts import record
from tests.test_elite_plan_execution import start_plan, auction


def continue_after_input(region, firm):
    from collections import defaultdict
    from region_production import produce_corporation
    from region_finance import pay_wages
    from region_market import trade
    produce_corporation(region, firm, region.recipes[firm.output], firm.output,
                       {firm.output:1}, defaultdict(float), turn=1)
    pay_wages(region, 1)
    region._last_turn = 2
    review_plan(region.elite_planner, firm, region, 2)
    trade(region, 2)
    return region.elite_planner._active_plans[firm.id]


def checkpoint_server(region):
    from sim_server.sim_server import SimServer
    from run_trace import RunTrace
    server = SimServer.__new__(SimServer)
    server.tiles, server.nations, server.turn = [region], [], 1
    server.gameplay_flags, server.gameplay_profile = region._gameplay_flags, 'custom'
    server.elite_planning_config = region._elite_planning_config
    server._lock = threading.RLock()
    directory = Path(tempfile.mkdtemp(prefix='elite-trace-'))
    server.run_trace = RunTrace(directory / 'fixture.ctr', '00000000000000000000000000000001-1')
    region._run_trace = server.run_trace
    region._collective_trace_clock = {'turn': 1, 'phase': 'local', 'next': 1}
    server.run_trace.bank_book.register_tiles([region], region._collective_trace_clock)
    return server


class PlanRecoveryTests(unittest.TestCase):
    def test_partial_fill_retry_and_expiry_keep_settled_cash_and_stock(self):
        r, firm, worker, supplier, buyer = start_plan()
        auction(r, Goods.wood, supplier, firm, 1, 1)
        plan = r.elite_planner._active_plans[firm.id]
        self.assertEqual(plan['input_filled'], 1)
        self.assertEqual(firm.inv_get(Goods.wood), 1)
        cash = firm.cash
        for turn in range(2, 5):
            r._last_turn = turn
            review_plan(r.elite_planner, firm, r, turn)
        self.assertEqual(plan['status'], 'cancelled')
        self.assertEqual((firm.cash, firm.inv_get(Goods.wood)), (cash, 1))

    def test_gate_exit_owner_and_worker_changes_cancel_instructions(self):
        for change in ('gate', 'mode', 'exit', 'worker', 'owner', 'deadline'):
            with self.subTest(change=change):
                r, firm, worker, supplier, buyer = start_plan()
                if change == 'gate': r._gameplay_flags = replace(r._gameplay_flags, elite_planning=False)
                if change == 'mode': r._elite_planning_config = ElitePlanningConfig(mode='shadow')
                if change == 'exit': r.agents.remove(firm)
                if change == 'worker': worker.is_striking = True
                if change == 'owner': buyer.company_owned = firm
                maintain_plans(r.elite_planner, r, 99 if change == 'deadline' else 2)
                self.assertEqual(r.elite_planner._active_plans[firm.id]['status'], 'cancelled')

    def test_receipts_survive_history_eviction_and_replay(self):
        r, firm, worker, supplier, buyer = start_plan()
        auction(r, Goods.wood, supplier, firm, 2, 1)
        plan = r.elite_planner._active_plans[firm.id]
        fill = next(e for e in r.economic_events if e.get('detail', {}).get('plan_id'))
        for _ in range(2100): record(r, 'test_observation', payer_id=buyer.id)
        self.assertNotIn(fill, r.economic_events)
        before = dict(plan)
        observe_receipt(r, fill)
        self.assertEqual(plan, before)
        self.assertEqual(plan['input_filled'], 2)

    def test_full_checkpoint_continues_active_plan_in_fresh_process(self):
        from simulation_checkpoint import save, restore
        from simulation_semantics import canonical_state, graph_differences
        from region_market import trade
        r, firm, worker, supplier, buyer = start_plan()
        buyer.consumption_multiplier = 2
        trade(r, 1)
        server = checkpoint_server(r)
        with tempfile.TemporaryDirectory() as directory:
            manifest = save(server, directory)
            plan = continue_after_input(r, firm)
            self.assertEqual(plan['status'], 'completed')
            expected = canonical_state([r], [])
            restored = restore(manifest, Path(directory) / 'branch')
            rr = restored.tiles[0]
            ff = next(a for a in rr.agents if a.id == firm.id)
            continue_after_input(rr, ff)
            observed = canonical_state([rr], [])
            self.assertFalse(graph_differences(expected['graph'], observed['graph']))
            script = '''import json,sys
from pathlib import Path
from simulation_checkpoint import restore
from simulation_semantics import canonical_state
from tests.test_elite_plan_recovery import continue_after_input
server=restore(sys.argv[1],sys.argv[2])
r=server.tiles[0]
f=next(a for a in r.agents if a.id==int(sys.argv[3]))
continue_after_input(r,f)
Path(sys.argv[4]).write_text(json.dumps(canonical_state([r],[])))
'''
            output = Path(directory) / 'continued.json'
            subprocess.run([sys.executable, '-c', script, str(manifest), str(Path(directory) / 'fresh'),
                            str(firm.id), str(output)], check=True, capture_output=True,
                           env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1])))
            self.assertFalse(graph_differences(expected['graph'], json.loads(output.read_text())['graph']))
            metadata = json.loads(Path(manifest).read_text())
            metadata['elite_planning']['horizon'] += 1
            Path(manifest).write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'elite planning configuration mismatch'):
                restore(manifest, Path(directory) / 'invalid')
