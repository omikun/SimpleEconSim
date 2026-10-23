"""Membership effects use balances at entry/exit, not world closing values."""
from pathlib import Path
import tempfile
import unittest
from nation import Nation
from region import Region
from run_trace import RunTrace
from treasury_trace import begin_public_change,finish_public_change


class TreasuryCompositionTraceTests(unittest.TestCase):
    def world(self,shared=False):
        nations=[Nation(name,'C',initial_cash=1000,register=False) for name in ('A','B')]
        tiles=[Region('A1',0,0),Region('B1',0,0)]
        for n,r in zip(nations,tiles):n.add_tile(r)
        if shared:
            r=Region('A2',0,0,institutions=tiles[0]._institutions);nations[0].add_tile(r);tiles.append(r)
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup)
        trace=RunTrace(Path(d.name)/'ownership.ctr','ownership',recent_limit=10000)
        clock={'turn':0,'phase':'setup','next':1}
        for source in [*nations,*tiles]:source._run_trace,source._collective_trace_clock=trace,clock
        trace.treasury_book.register_nations(nations,clock)
        before={('finance.treasury',n.name):(None,'C',n.treasury()['total']) for n in nations}
        clock.update(turn=1,phase='ownership')
        return nations,tiles,trace,clock,before

    def credit(self,source,agent,amount):
        ctx=begin_public_change(source,agent);agent.cash+=amount;finish_public_change(ctx,'test_payment')

    def close(self,nations,trace,clock,before):
        trace.treasury_book.close(nations,clock,before)
        rows=[r for r in trace.recent if r['kind']=='treasury_account_closure']
        self.assertEqual(2,len(rows))
        self.assertTrue(all(r['record_class']=='calculation' for r in rows),[r['inputs'] for r in rows])
        self.assertTrue(all(r['formula_replay']['matches'] for r in rows))
        return {r['subject']['id']:r for r in rows}

    def test_departed_account_changes_after_departure(self):
        nations,tiles,trace,clock,before=self.world();a,b=nations;r=tiles[0]
        self.credit(a,r.gov.agent,10)
        a.transfer_tile(r,b)
        self.credit(b,r.gov.agent,7)
        rows=self.close(nations,trace,clock,before)
        self.assertEqual(1000,rows['A']['value_after'])
        self.assertEqual(1417,rows['B']['value_after'])
        transitions=[step for step in rows['A']['inputs']['steps'] if step['type']=='transition']
        exited=[v['balance'] for v in transitions[0]['before']['accounts'].values() if v['balance']==210]
        self.assertEqual([210],exited)

    def test_out_and_back_with_intermediate_cash_change(self):
        nations,tiles,trace,clock,before=self.world();a,b=nations;r=tiles[0]
        a.transfer_tile(r,b);self.credit(b,r.gov.agent,7);b.transfer_tile(r,a)
        rows=self.close(nations,trace,clock,before)
        self.assertEqual(1207,rows['A']['value_after'])
        self.assertEqual(1200,rows['B']['value_after'])
        self.assertEqual(2,len([s for s in rows['A']['inputs']['steps'] if s['type']=='transition']))

    def test_shared_account_is_not_removed_when_one_alias_remains(self):
        nations,tiles,trace,clock,before=self.world(shared=True);a,b=nations;r=tiles[0]
        a.transfer_tile(r,b)
        rows=self.close(nations,trace,clock,before)
        # Existing game rules count the same shared government in both nations.
        self.assertEqual(1200,rows['A']['value_after'])
        self.assertEqual(1400,rows['B']['value_after'])

    def test_new_native_bank_association_is_a_verified_composition(self):
        from econsim_trade_money import Bank
        nations,tiles,trace,clock,before=self.world()
        tiles[0].bank=Bank(tiles[0].gov)
        self.close(nations,trace,clock,before)

    def test_missing_native_transition_cannot_be_filled_from_final_membership(self):
        nations,tiles,trace,clock,before=self.world();a,b=nations;r=tiles[0]
        a.tiles.remove(r);b.tiles.append(r);r.owner_nation=b
        trace.treasury_book.close(nations,clock,before)
        rows=[r for r in trace.recent if r['kind']=='treasury_account_closure']
        self.assertTrue(all(r['record_class']=='audit' for r in rows))


if __name__=='__main__':unittest.main()
