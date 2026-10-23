"""Manual and political paths resolve explicitly registered public accounts."""
from pathlib import Path
import tempfile
import unittest
from agent import Agent
from nation import Nation
from region import Region
from run_trace import RunTrace
from intents import execute_equalization_grant
from coup import seize_treasury


class ManualPoliticalAccountTests(unittest.TestCase):
    def world(self):
        n=Nation('Manual','C',initial_cash=1000,register=False)
        r=Region('City',0,0);n.add_tile(r)
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup)
        trace=RunTrace(Path(d.name)/'manual.ctr','manual',recent_limit=2000)
        clock={'turn':0,'phase':'setup','next':1}
        for source in (n,r):source._run_trace,source._collective_trace_clock=trace,clock
        trace.treasury_book.register_nations([n],clock)
        before={('finance.treasury',n.name):(None,'C',n.treasury()['total'])}
        clock.update(turn=1,phase='policy')
        return n,r,trace,clock,before

    def close(self,n,r,trace,clock,before):
        trace.treasury_book.close([n],clock,before)
        row=next(row for row in reversed(trace.recent) if row['kind']=='treasury_account_closure')
        self.assertEqual('calculation',row['record_class'],row['inputs'])
        self.assertTrue(row['formula_replay']['matches'])

    def test_equalization_records_both_legs_despite_zero_national_delta(self):
        n,r,trace,clock,before=self.world()
        result=execute_equalization_grant({'nations':[n],'tiles':[r]},n.name,r.name,grant_amount=20,t=1)
        self.assertTrue(result[0])
        self.close(n,r,trace,clock,before)
        writes=[row for row in trace.recent if row['kind']=='public_account_write']
        self.assertEqual([-20,20],[row['delta'] for row in writes])
        self.assertEqual(before[('finance.treasury',n.name)][2],n.treasury()['total'])

    def test_seizure_has_actual_treasury_chain(self):
        n,r,trace,clock,before=self.world()
        general=Agent(0);general.cash=7
        seized=seize_treasury(n,general,1)
        self.assertEqual(200,seized)
        self.assertEqual(207,general.cash)
        self.close(n,r,trace,clock,before)
        writes=[row for row in trace.recent if row['kind']=='public_account_write']
        self.assertEqual([-200],[row['delta'] for row in writes])


if __name__=='__main__':unittest.main()
