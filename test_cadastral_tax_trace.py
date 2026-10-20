import unittest
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from land_tenure import LandPlot, TenureStatus, TileTenure
from scenario_political_economy import _assess_arrears, _foreclose


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Government:
    def __init__(self, name, cash=0.0, tax_rate=0.0):
        self.name = name
        self.agent = Agent(9000 + len(name))
        self.agent.is_government = True
        self.agent.cash = cash
        self.tax_rate = tax_rate
        self.income = []

    def record_income(self, turn, source, amount):
        self.income.append((turn, source, amount))


def _person(agent_id, cash, *, lord=False):
    person = Agent(agent_id)
    initialize_agent(person, Goods.food, 0, 0, cash)
    person.id = agent_id
    person.alive = True
    person.is_lord = lord
    person.is_government = False
    person.is_corporation = False
    person.is_trader = False
    return person


def _tax_fixture(with_trace=True):
    taxpayer = _person(21, 2.0)
    taxpayer.assigned_plot_id = 'plot-a'
    local = Government('District', cash=0.0, tax_rate=5.0)
    national = Government('North', cash=0.0)
    nation = SimpleNamespace(name='North', currency='USD', government=national,
                            legitimacy=0.5, tiles=[])
    trace = MemoryTrace()
    tile = SimpleNamespace(
        name='District', home_currency='USD', agents=[taxpayer], gov=local,
        owner_nation=nation, tax_distribution_log=[{
            'total': 0.0, 'national': 0.0, 'municipal': 0.0}],
        _run_trace=trace,
        _collective_trace_clock={'turn': 4, 'phase': 'scenario_economy', 'next': 1})
    nation.tiles.append(tile)
    if not with_trace:
        del tile._run_trace
        del tile._collective_trace_clock
    world = {'turn': 4, 'scenario_state': {'political_economy': {
        'arrears': {}, 'tax_assessments': []}}}
    return world, tile, nation, local, national, taxpayer, trace


def _foreclosure_fixture(with_trace=True):
    lord = _person(1, 0.0, lord=True)
    cultivator = _person(2, 0.0)
    cultivator.assigned_plot_id = 'plot-a'
    buyer = _person(3, 100.0)
    plot = LandPlot('plot-a', 'District', lord.id,
                    tenure=TenureStatus.FEUDAL, fraction=1.0,
                    tenant_ids=[cultivator.id])
    local = Government('District', cash=0.0)
    national = Government('North', cash=0.0)
    nation = SimpleNamespace(name='North', currency='USD', government=national,
                            legitimacy=0.5, tiles=[])
    trace = MemoryTrace()
    tile = SimpleNamespace(
        name='District', home_currency='USD', agents=[lord, cultivator, buyer],
        gov=local, owner_nation=nation, tenure=TileTenure([plot]),
        bank=SimpleNamespace(is_frozen=False, deposits={}), unrest_level=0.1,
        tax_distribution_log=[{'total': 0.0, 'municipal': 0.0}],
        _run_trace=trace,
        _collective_trace_clock={'turn': 7, 'phase': 'scenario_economy', 'next': 1})
    nation.tiles.append(tile)
    if not with_trace:
        del tile._run_trace
        del tile._collective_trace_clock
    economy = {'arrears': {}, 'tenure_transfers': [],
               'scenario_strikers_by_tile': {tile.name: []}, 'migrations': []}
    world = {'turn': 7, 'scenario_state': {'political_economy': economy}}
    return world, tile, nation, local, lord, cultivator, buyer, plot, trace


class CadastralTaxTraceTests(unittest.TestCase):
    def test_distribution_history_replays_and_links_later_scenario_receipts(self):
        from finance_trace import emit_tax_distribution
        from run_trace import RunTrace

        with tempfile.TemporaryDirectory() as tmp:
            for mode, expected_total in (('assessment', 2.0), ('foreclosure', 6.0)):
                fixture = (_tax_fixture() if mode == 'assessment'
                           else _foreclosure_fixture())
                world, tile = fixture[:2]
                trace = RunTrace(Path(tmp) / f'{mode}.ctr', mode)
                tile._run_trace = trace
                emit_tax_distribution(
                    tile, turn=world['turn'], closing=tile.tax_distribution_log[-1],
                    reason='opening_income_tax_total')
                initial = {row['subject']['tax_tier']: row['event_id']
                           for row in trace.recent
                           if row.get('metric_id') == 'finance.tax_distribution'}
                if mode == 'assessment':
                    _assess_arrears(world, tile, set())
                else:
                    cultivator = fixture[5]
                    _foreclose(world, tile, cultivator,
                               {'balance': 6.0, 'missed': 3, 'plot_id': 'plot-a'})
                latest = {row['subject']['tax_tier']: row for row in trace.recent
                          if row.get('metric_id') == 'finance.tax_distribution'}
                self.assertEqual(latest['total']['value_after'], expected_total)
                for tier, row in latest.items():
                    self.assertTrue(row['formula_replay']['matches'])
                    self.assertEqual(row['value_after'],
                                     tile.tax_distribution_log[-1].get(tier, 0.0))
                    self.assertIn(initial[tier], row['cause_event_ids'])
                    self.assertGreater(len(row['cause_event_ids']), 1)

    def test_assessment_traces_household_payment_treasury_split_and_arrears(self):
        world, tile, nation, local, national, taxpayer, trace = _tax_fixture()

        _assess_arrears(world, tile, set())

        arrears = world['scenario_state']['political_economy']['arrears'][taxpayer.id]
        self.assertEqual(arrears['balance'], 3.0)
        self.assertEqual(arrears['missed'], 1)
        self.assertEqual(taxpayer.cash, 0.0)
        self.assertAlmostEqual(national.agent.cash, 0.5)
        self.assertAlmostEqual(local.agent.cash, 1.5)
        payment = next(row for row in trace.rows
                       if row.get('kind') == 'cadastral_tax_payment')
        payer_contract = payment['inputs']['transfer_contract']
        self.assertEqual(payer_contract['amount'], 2.0)
        self.assertEqual(payer_contract['payer_account']['balance_before'], 2.0)
        self.assertEqual(payer_contract['payer_account']['balance_after'], 0.0)
        self.assertEqual(payer_contract['payee_account']['balance_before'], 0.0)
        self.assertEqual(payer_contract['payee_account']['balance_after'], 2.0)
        balances = [row for row in trace.rows
                    if row.get('metric_id') == 'finance.tax_arrears_balance']
        self.assertEqual([(row['before'], row['after']) for row in balances], [(0.0, 3.0)])
        receipts = [row for row in trace.rows
                    if row.get('kind') == 'cadastral_tax_treasury_receipt']
        self.assertEqual([row['after'] for row in receipts], [0.5, 1.5])
        self.assertAlmostEqual(sum(row['after'] for row in receipts), 2.0)
        self.assertEqual([row['subject'] for row in receipts], [
            {'type': 'nation', 'id': 'North'},
            {'type': 'tile', 'id': 'District'}])
        for receipt in receipts:
            contract = receipt['inputs']['transfer_contract']
            self.assertEqual(contract['payer_account']['balance_scope'],
                             'collected_assessment_revenue')
            self.assertEqual(receipt['cause_event_ids'], [payment['event_id']])
        risk = next(row for row in trace.rows
                    if row.get('metric_id') == 'finance.tax_foreclosure_risk')
        self.assertEqual(risk['after'], 0.0)
        self.assertFalse(risk['inputs']['foreclosure_triggered'])

    def test_foreclosure_auction_reconciles_buyer_recovery_refund_and_causes(self):
        world, tile, nation, local, lord, cultivator, buyer, plot, trace = (
            _foreclosure_fixture())
        arrears = {'balance': 6.0, 'missed': 3, 'plot_id': plot.plot_id}

        _foreclose(world, tile, cultivator, arrears)

        self.assertEqual(buyer.cash, 90.0)
        self.assertEqual(local.agent.cash, 6.0)
        self.assertEqual(cultivator.cash, 4.0)
        self.assertEqual((buyer.cash + local.agent.cash + cultivator.cash), 100.0)
        self.assertEqual(arrears['balance'], 0.0)
        self.assertEqual(arrears['missed'], 0)
        self.assertEqual(plot.tenant_ids, [buyer.id])
        self.assertIsNone(cultivator.assigned_plot_id)
        self.assertEqual(buyer.assigned_plot_id, plot.plot_id)
        self.assertAlmostEqual(tile.unrest_level, 0.13)
        self.assertAlmostEqual(nation.legitimacy, 0.495)

        payment = next(row for row in trace.rows
                       if row.get('kind') == 'tax_foreclosure_auction_payment')
        recovery = next(row for row in trace.rows
                        if row.get('kind') == 'tax_foreclosure_treasury_recovery')
        refund = next(row for row in trace.rows
                      if row.get('kind') == 'tax_foreclosure_cultivator_refund')
        self.assertEqual(payment['inputs']['transfer_contract']['amount'], 10.0)
        self.assertEqual(recovery['after'], 6.0)
        self.assertEqual(refund['inputs']['transfer_contract']['amount'], 4.0)
        self.assertEqual(
            recovery['inputs']['transfer_contract']['payer_account']['balance_before'],
            10.0)
        self.assertEqual(
            recovery['inputs']['transfer_contract']['payer_account']['balance_after'],
            4.0)
        self.assertEqual(
            refund['inputs']['transfer_contract']['payer_account']['balance_before'], 4.0)
        self.assertEqual(
            refund['inputs']['transfer_contract']['payer_account']['balance_after'], 0.0)
        foreclosure = next(row for row in trace.rows
                           if row.get('metric_id') == 'land.tax_foreclosure')
        self.assertIn(payment['event_id'], foreclosure['cause_event_ids'])
        self.assertIn(recovery['event_id'], foreclosure['cause_event_ids'])
        self.assertIn(refund['event_id'], foreclosure['cause_event_ids'])
        unrest = next(row for row in trace.rows
                      if row.get('kind') == 'cadastral_foreclosure_unrest')
        legitimacy = next(row for row in trace.rows
                          if row.get('kind') == 'cadastral_foreclosure_legitimacy_loss')
        self.assertEqual(unrest['cause_event_ids'], [foreclosure['event_id']])
        self.assertEqual(legitimacy['cause_event_ids'], [foreclosure['event_id']])

    def test_tax_assessment_and_foreclosure_do_not_change_state_when_tracing(self):
        traced = _tax_fixture(with_trace=True)
        untraced = _tax_fixture(with_trace=False)
        for fixture in (traced, untraced):
            world, tile = fixture[:2]
            _assess_arrears(world, tile, set())

        def assessment_state(fixture):
            world, tile, nation, local, national, taxpayer, _ = fixture
            return (taxpayer.cash, local.agent.cash, national.agent.cash,
                    deepcopy(world['scenario_state']['political_economy']),
                    deepcopy(tile.tax_distribution_log))

        self.assertEqual(assessment_state(traced), assessment_state(untraced))

        traced = _foreclosure_fixture(with_trace=True)
        untraced = _foreclosure_fixture(with_trace=False)
        for fixture in (traced, untraced):
            world, tile, nation, local, lord, cultivator, buyer, plot, _ = fixture
            _foreclose(world, tile, cultivator,
                       {'balance': 6.0, 'missed': 3, 'plot_id': plot.plot_id})

        def foreclosure_state(fixture):
            world, tile, nation, local, lord, cultivator, buyer, plot, _ = fixture
            return (cultivator.cash, buyer.cash, local.agent.cash,
                    cultivator.assigned_plot_id, buyer.assigned_plot_id,
                    list(plot.tenant_ids), tile.unrest_level, nation.legitimacy,
                    deepcopy(world['scenario_state']['political_economy']))

        self.assertEqual(foreclosure_state(traced), foreclosure_state(untraced))


if __name__ == '__main__':
    unittest.main()
