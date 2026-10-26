"""Actual public stock chains for rescue, sovereign settlement and fees."""
from pathlib import Path
import random
import tempfile
import unittest
from nation import Nation
from region import Region
from run_trace import RunTrace
from banking_policy import recapitalize_domestic_banks
from sovereign_bonds import SovereignBondMarket


class FinancialAccountCompletionTests(unittest.TestCase):
    def world(self, cash=3000, bank_capital=None):
        nations=[];tiles=[]
        for name in ('Issuer','Holder'):
            nation=Nation(name,'C',initial_cash=cash,register=False)
            tile=Region(name+' City',0,0)
            nation.add_tile(tile)
            nations.append(nation);tiles.append(tile)
        if bank_capital is not None:tiles[0].bank.capital=bank_capital
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        trace=RunTrace(Path(directory.name)/'financial.ctr','financial',recent_limit=20000)
        clock={'turn':0,'phase':'setup','next':1}
        for source in [*nations,*tiles]:source._run_trace,source._collective_trace_clock=trace,clock
        trace.bank_book.register_tiles(tiles,clock)
        trace.treasury_book.register_nations(nations,clock)
        before={('finance.treasury',n.name):(None,'C',n.treasury()['total']) for n in nations}
        clock.update(turn=1,phase='finance')
        return nations,tiles,trace,clock,before

    def close(self,nations,tiles,trace,clock,before):
        trace.bank_book.close(tiles,clock,{})
        self.assertTrue(all(row['formula_replay']['matches'] for row in trace.recent
                            if row['kind']=='bank_closing_balance'))
        trace.treasury_book.close(nations,clock,before)
        closes=[row for row in trace.recent if row['kind']=='treasury_account_closure']
        self.assertEqual(len(nations),len(closes))
        for row in closes:
            self.assertEqual('calculation',row['record_class'],row['inputs'])
            flows=trace._treasury_flows.get(row['subject']['id'],())
            self.assertAlmostEqual(row['delta'],sum(flow['amount'] for flow in flows))

    def test_rescue_rejected_then_funded_has_one_actual_debit(self):
        nations,tiles,trace,clock,before=self.world(cash=20,bank_capital=0)
        bank=tiles[0].bank
        bank.is_frozen=True
        self.assertFalse(recapitalize_domestic_banks(nations[0],target_capital=50)[0])
        self.assertFalse(any(row['kind']=='public_account_write' for row in trace.recent))
        self.assertTrue(recapitalize_domestic_banks(nations[0],target_capital=10)[0])
        self.close(nations,tiles,trace,clock,before)
        funding=next(row for row in trace.recent if row['kind']=='bank_recapitalization_funding')
        writes={row['event_id'] for row in trace.recent if row['kind']=='public_account_write'}
        self.assertTrue(writes.intersection(funding['cause_event_ids']))
        self.assertEqual(10,nations[0].government.agent.cash)

    def test_foreign_issue_coupon_and_early_redemption(self):
        nations,tiles,trace,clock,before=self.world()
        issuer,holder=nations;world={'nations':nations,'tiles':tiles};market=SovereignBondMarket()
        ok,_,bond=market.issue_bond(issuer,holder,100,20,0,world=world)
        self.assertTrue(ok)
        market.step(world,1)
        self.assertTrue(market.redeem_bond_early(bond.bond_id,world,1)[0])
        self.close(nations,tiles,trace,clock,before)
        for row in trace.recent:
            if row.get('metric_id')=='finance.treasury_flow' and row['kind'].startswith('sovereign_bond'):
                self.assertTrue(row.get('cause_event_ids'))

    def test_domestic_creation_and_maturity_preserve_existing_rule(self):
        nations,tiles,trace,clock,before=self.world()
        market=SovereignBondMarket();world={'nations':nations,'tiles':tiles}
        initial=nations[0].government.agent.cash
        ok,_,bond=market.issue_bond(nations[0],None,100,20,0,world=world)
        self.assertTrue(ok);self.assertEqual(initial+100,nations[0].government.agent.cash)
        # Mature within this audit turn to exercise both physical writes.
        bond.maturity_turn=1
        market.step(world,1)
        self.close(nations,tiles,trace,clock,before)
        self.assertEqual(initial,nations[0].government.agent.cash)

    def test_rating_fees_have_account_and_signed_flow_evidence(self):
        nations,tiles,trace,clock,before=self.world()
        rating=SovereignBondMarket().isrb
        rng=random.getstate()
        try:
            random.seed(77)
            rating.lobby_upgrade(nations[0],1)
            rating.lobby_adversary_downgrade(nations[0],nations[1].name,1)
            rating.acquire_board_seat(nations[0])
        finally:random.setstate(rng)
        self.close(nations,tiles,trace,clock,before)
        self.assertEqual(1850,nations[0].government.agent.cash)


if __name__=='__main__':unittest.main()
