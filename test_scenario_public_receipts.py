"""Previously missing public receipts must close native scenario accounts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ScenarioPublicReceiptTests(unittest.TestCase):
    def test_frontier_and_supply_native_account_chains(self):
        script='''import json,random,sys,numpy as np
from sim_server.sim_server import SimServer
from trace_coverage import coverage
from trace_audit import audit
random.seed(int(sys.argv[2]));np.random.seed(int(sys.argv[2]))
s=SimServer(seed=int(sys.argv[2]),scenario_id=sys.argv[1])
for _ in range(3):s.step()
report={'coverage':coverage(s.run_trace.path),'audit':audit(s.run_trace.path),
 'public_operations':sorted(set(row['inputs']['operation_kind'] for row in s.run_trace.query(kind='public_account_write',limit=10000)['events']))}
open(sys.argv[3],'w').write(json.dumps(report))
'''
        for scenario,seed,required in (
            ('labor_frontier_rivalry',612,{'cash_obligation_payment','public_taxpayer_cash_debit','labor_law_petition_fee'}),
            ('supply_rivalry',812,{'route_freight_settlement'})):
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as directory:
                out=Path(directory)/'result.json'
                runner=Path(directory)/'scenario_receipts.py';runner.write_text(script)
                completed=subprocess.run([sys.executable,str(runner),scenario,str(seed),str(out)],
                    env=dict(os.environ,PYTHONHASHSEED='0',PYTHONPATH=str(Path(__file__).resolve().parent)),text=True,capture_output=True)
                self.assertEqual(0,completed.returncode,completed.stderr)
                result=json.loads(out.read_text())
                self.assertEqual(0,result['coverage']['_treasury_account_closure']['gaps'])
                self.assertTrue(required.issubset(result['public_operations']),result['public_operations'])
                self.assertTrue(result['audit']['structural_and_supported_formula_checks_pass'],result['audit']['issues'])
                self.assertFalse([(key,row) for key,row in result['coverage'].items() if row.get('unexplained')])


if __name__=='__main__':unittest.main()
