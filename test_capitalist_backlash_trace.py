import json
import unittest
from types import SimpleNamespace

from labor_politics import capitalist_electoral_backlash
from metric_catalog import METRICS, TRACE_INSTRUMENTED


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _actor(agent_id, *, cash=0.0, home_currency='USD', wallets=None,
           social_class='proletarian', charisma=0.5, corporation=False):
    return SimpleNamespace(id=agent_id, cash=float(cash), alive=True,
                           home_currency=home_currency,
                           wallets=dict(wallets or {}),
                           social_class=social_class,
                           charisma=float(charisma),
                           is_corporation=corporation)


def _fixture(*, traced=True, labor_laws=True, no_candidates=False):
    domestic_donor = _actor('domestic', cash=100.0,
                            social_class='capitalist')
    wallet_donor = _actor('wallet-donor', cash=100.0,
                          home_currency='JPY', wallets={'USD': 80.0},
                          social_class='landlord')
    corporate_donor = _actor('corporation', cash=60.0,
                             social_class='', corporation=True)
    below_threshold = _actor('small-capitalist', cash=25.0,
                              social_class='capitalist')
    incumbent_agent = _actor('incumbent-agent', cash=10.0, charisma=0.99)
    target_agent = _actor('target-agent', cash=10.0, home_currency='JPY',
                          wallets={'USD': 5.0}, charisma=0.8)
    runner_up_agent = _actor('runner-up-agent', cash=10.0, charisma=0.7)
    tile = SimpleNamespace(
        name='Industrial District',
        agents=[domestic_donor, wallet_donor, corporate_donor,
                below_threshold, incumbent_agent, target_agent,
                runner_up_agent])
    incumbent = SimpleNamespace(agent=incumbent_agent,
                                backing_faction='Labor', popularity=0.1)
    target = SimpleNamespace(agent=target_agent,
                             backing_faction='Gentry', popularity=0.2)
    runner_up = SimpleNamespace(agent=runner_up_agent,
                                backing_faction='Bourgeoisie', popularity=0.3)
    candidates = [] if no_candidates else [incumbent, target, runner_up]
    nation = SimpleNamespace(
        name='Industrial Republic', currency='USD', tiles=[tile],
        ten_hour_act=bool(labor_laws), factory_safety_act=False,
        max_workday_hours=10.0 if labor_laws else 16.0,
        _incumbent_faction='Labor', regime_log=[])
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 4, 'phase': 'election', 'next': 1}
    return (nation, candidates, tile, domestic_donor, wallet_donor,
            corporate_donor, below_threshold, incumbent, target,
            runner_up, trace)


def _state(fixture):
    return (fixture[3].cash, fixture[4].cash, fixture[4].wallets['USD'],
            fixture[5].cash, fixture[6].cash,
            fixture[7].popularity, fixture[8].popularity,
            fixture[9].popularity, tuple(fixture[0].regime_log))


class CapitalistBacklashTraceTests(unittest.TestCase):
    def test_cash_and_wallet_donations_link_to_candidate_popularity(self):
        traced = _fixture()
        plain = _fixture(traced=False)

        amount = capitalist_electoral_backlash(traced[0], traced[1], 4)
        plain_amount = capitalist_electoral_backlash(plain[0], plain[1], 4)

        self.assertEqual(amount, plain_amount)
        self.assertEqual(_state(traced), _state(plain))
        self.assertEqual(amount, 27.0)
        self.assertEqual(traced[3].cash, 88.0)
        self.assertEqual(traced[4].wallets['USD'], 71.0)
        self.assertEqual(traced[5].cash, 54.0)
        self.assertEqual(traced[6].cash, 25.0)
        self.assertEqual(traced[8].agent.wallets['USD'], 32.0)
        self.assertEqual(traced[7].popularity, 0.1)
        self.assertAlmostEqual(traced[8].popularity, 0.2162)

        gate = self._row(traced, 'capitalist_backlash_gate')
        selection = self._row(traced, 'capitalist_backlash_candidate_selection')
        transfers = [row for row in traced[10].rows
                     if row.get('kind') == 'capitalist_backlash_donation']
        donor_rows = [row for row in traced[10].rows
                      if row.get('kind') == 'capitalist_backlash_donor_decision']
        popularity = [row for row in traced[10].rows
                      if row.get('kind') == 'capitalist_backlash_popularity_effect']
        outcome = self._row(traced, 'capitalist_backlash_outcome')
        self.assertTrue(gate['after'])
        self.assertEqual(selection['inputs']['selected_candidate_id'],
                         'target-agent')
        self.assertEqual(len(transfers), 3)
        self.assertEqual(len(donor_rows), 4)
        self.assertEqual(len(popularity), 3)
        wallet_transfer = next(row for row in transfers
                               if row['inputs']['donor_id'] == 'wallet-donor')
        contract = wallet_transfer['inputs']['transfer_contract']
        self.assertEqual(contract['payer_account']['balance_before'], 80.0)
        self.assertEqual(contract['payer_account']['balance_after'], 71.0)
        self.assertEqual(contract['payee_account']['balance_before'], 17.0)
        self.assertEqual(contract['payee_account']['balance_after'], 26.0)
        wallet_donor_decision = next(
            row for row in donor_rows
            if row['subject']['id'] == 'wallet-donor')
        self.assertIn(wallet_donor_decision['event_id'],
                      wallet_transfer['cause_event_ids'])
        domestic_transfer = next(row for row in transfers
                                 if row['inputs']['donor_id'] == 'domestic')
        self.assertIn(domestic_transfer['event_id'],
                      wallet_transfer['cause_event_ids'])
        self.assertEqual(wallet_transfer['cause_event_ids'], [
            wallet_donor_decision['event_id'], domestic_transfer['event_id']])
        self.assertEqual(outcome['inputs']['total_donations'], 27.0)
        self.assertAlmostEqual(outcome['inputs']['popularity_gain_total'], 0.0162)
        self._assert_catalogued(traced[10].rows)

    def test_gate_explains_missing_candidates_and_missing_labor_law(self):
        no_candidates = _fixture(no_candidates=True)
        no_law = _fixture(labor_laws=False)

        self.assertEqual(capitalist_electoral_backlash(
            no_candidates[0], no_candidates[1], 4), 0.0)
        self.assertEqual(capitalist_electoral_backlash(
            no_law[0], no_law[1], 4), 0.0)

        self.assertEqual(self._row(no_candidates, 'capitalist_backlash_gate')
                         ['inputs']['reason'], 'no_candidates')
        self.assertEqual(self._row(no_candidates, 'capitalist_backlash_outcome')
                         ['after'], 'no_candidates')
        self.assertEqual(self._row(no_law, 'capitalist_backlash_gate')
                         ['inputs']['reason'], 'no_pro_labor_laws')
        self.assertEqual(self._row(no_law, 'capitalist_backlash_outcome')
                         ['after'], 'blocked_no_pro_labor_laws')
        self._assert_catalogued(no_candidates[10].rows)
        self._assert_catalogued(no_law[10].rows)

    def _row(self, fixture, kind):
        return next(row for row in fixture[10].rows
                    if row.get('kind') == kind)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
