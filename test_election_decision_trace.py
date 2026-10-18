import json
import unittest
from types import SimpleNamespace

from election import (Candidate, faction_weighted_vote, generate_candidates,
                      run_election)
from faction import Faction
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


def _voter(agent_id, charisma, promise=0.0):
    return SimpleNamespace(
        id=agent_id, charisma=float(charisma), alive=True,
        is_corporation=False, is_government=False, is_trader=False,
        cash=0.0, home_currency='USD', wallets={},
        age=lambda _turn: 30,
        mem_avg=lambda _memory, default: float(promise)
        if promise is not None else default)


def _world(voters, factions, *, traced=True, incumbent='Labor'):
    tile = SimpleNamespace(name='Capital', agents=list(voters),
                           factions=SimpleNamespace(factions=factions))
    nation = SimpleNamespace(name='Republic', tiles=[tile],
                             _incumbent_faction=incumbent,
                             currency='USD')
    tile.gov = SimpleNamespace(agent=SimpleNamespace(
        id='treasury', cash=100.0))
    tile._last_turn = 7
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 7, 'phase': 'election', 'next': 1}
    return nation, tile, trace


def _candidate_state(candidates):
    return [(candidate.agent.id, candidate.backing_faction,
             candidate.popularity, dict(candidate.platform))
            for candidate in candidates]


def _election_world(*, traced):
    gentry = Faction('Gentry', 'class')
    gentry.support = 0.8
    gentry.influence = 0.1
    labor = Faction('Labor', 'class')
    labor.support = 0.5
    labor.influence = 0.2
    gentry_voter = _voter('gentry-agent', 0.6)
    labor_voter = _voter('labor-agent', 0.9)
    gentry.membership.add(gentry_voter.id)
    labor.membership.add(labor_voter.id)
    return _world([gentry_voter, labor_voter],
                  {'Gentry': gentry, 'Labor': labor}, traced=traced,
                  incumbent='Gentry')


class ElectionDecisionTraceTests(unittest.TestCase):
    def test_candidate_pool_records_faction_leader_and_independent_fill(self):
        labor = Faction('Labor', 'class')
        labor.support = 0.6
        labor.add_demand('workday_reduction', weight=0.8)
        member = _voter(1, 0.7)
        leader = _voter(2, 0.9)
        independent = _voter(3, 0.8)
        labor.membership.update({member.id, leader.id})
        traced = _world([member, leader, independent], {'Labor': labor})

        candidates = generate_candidates(traced[0], 7)

        self.assertEqual([candidate.agent.id for candidate in candidates], [3, 2])
        self.assertEqual(candidates[0].backing_faction, None)
        self.assertEqual(candidates[1].backing_faction, 'Labor')
        row = self._row(traced, 'election_candidate_pool_decision')
        self.assertEqual(row['before'], 2)
        self.assertEqual(row['after'], 2)
        faction = row['inputs']['faction_candidate_evaluations'][0]
        self.assertEqual(faction['candidate_id'], '2')
        self.assertEqual(faction['eligible_faction_members'], 2)
        self.assertEqual(faction['top_charisma_members'][0]['agent_id'], '2')
        self.assertEqual(row['inputs']['independent_slots_needed'], 1)
        self.assertEqual(row['inputs']['independent_candidates_selected'][0]
                         ['candidate_id'], '3')
        self.assertEqual(row['inputs']['selected_candidate_ids'], ['3', '2'])
        self._assert_catalogued(traced[2].rows)

    def test_full_election_traces_campaign_and_winner_without_changing_result(self):
        traced = _election_world(traced=True)
        plain = _election_world(traced=False)

        traced_result = run_election(traced[0], 7, campaign_budget=10.0)
        plain_result = run_election(plain[0], 7, campaign_budget=10.0)

        self.assertEqual(traced_result['winner'].agent.id,
                         plain_result['winner'].agent.id)
        self.assertEqual(
            {c.agent.id: traced_result['votes'][c]
             for c in traced_result['candidates']},
            {c.agent.id: plain_result['votes'][c]
             for c in plain_result['candidates']})
        self.assertEqual(traced[1].gov.agent.cash, 90.0)
        self.assertEqual(plain[1].gov.agent.cash, 90.0)
        self.assertEqual(traced[1].economic_events,
                         plain[1].economic_events)

        rows = traced[2].rows
        campaign_decisions = [row for row in rows
                              if row.get('kind') ==
                              'election_campaign_candidate_budget']
        transfers = [row for row in rows
                     if row.get('kind') == 'election_campaign_transfer']
        outcomes = [row for row in rows
                    if row.get('kind') ==
                    'election_campaign_candidate_outcome']
        self.assertEqual(len(campaign_decisions), 2)
        self.assertEqual(len(transfers), 2)
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(
            {row['event_id'] for row in campaign_decisions},
            {row['cause_event_ids'][0] for row in transfers})
        decisions_by_candidate = {
            row['subject']['id']: row['event_id']
            for row in campaign_decisions}
        for outcome in outcomes:
            self.assertEqual(len(outcome['inputs']['transfer_event_ids']), 1)
            self.assertEqual(outcome['cause_event_ids'], [
                decisions_by_candidate[outcome['subject']['id']],
                outcome['inputs']['transfer_event_ids'][0]])
            self.assertAlmostEqual(outcome['after'], 5.0)
        result_row = self._row(traced, 'election_result')
        self.assertEqual(result_row['after'],
                         str(traced_result['winner'].agent.id))
        self.assertFalse(result_row['inputs']['candidate_popularity_used_in_vote'])
        self.assertTrue(
            result_row['inputs']['candidate_popularity_used_in_candidate_pool'])
        self.assertTrue(
            result_row['inputs']['base_popularity_order_used_as_vote_tiebreak'])
        self.assertEqual(result_row['inputs']['campaign_spending_total'], 10.0)
        self.assertEqual(len(result_row['cause_event_ids']), 3)
        popularity_rows = [row for row in rows if row.get('kind') ==
                           'election_campaign_popularity_change']
        self.assertEqual(len(popularity_rows), 2)
        by_candidate = {candidate.agent.id: candidate
                        for candidate in traced_result['candidates']}
        for row in popularity_rows:
            candidate = by_candidate[row['subject']['id']]
            expected_dilution = 0.5 + 0.5 * candidate.agent.charisma
            self.assertEqual(row['formula_id'],
                             'election.campaign_popularity.v1')
            self.assertAlmostEqual(
                row['after'] - row['before'],
                5.0 * expected_dilution / 2000.0)
        self._assert_catalogued(rows)

    def test_empty_candidate_pool_records_why_no_winner_was_returned(self):
        traced = _world([], {})

        result = run_election(traced[0], 7, campaign_budget=10.0)

        self.assertIsNone(result['winner'])
        self.assertEqual(result['candidates'], [])
        pool = self._row(traced, 'election_candidate_pool_decision')
        self.assertEqual(pool['inputs']['reason'],
                         'no_eligible_faction_leaders_or_voters')
        outcome = self._row(traced, 'election_result')
        self.assertEqual(outcome['after'], 'no_candidates')
        self.assertEqual(outcome['inputs']['reason'], 'candidate_pool_empty')

    def test_weighted_votes_trace_membership_fallback_and_betrayal(self):
        gentry = Faction('Gentry', 'class')
        gentry.support = 0.8
        gentry.influence = 0.1
        proletariat = Faction('Proletariat', 'class')
        proletariat.support = 0.5
        proletariat.influence = 0.2
        populist = Faction('Populist', 'political')
        populist.support = 0.3
        populist.influence = 0.1

        aligned = _voter('aligned', 0.6, promise=0.1)
        defector = _voter('defector', 0.6, promise=0.9)
        no_membership = _voter('independent-voter', 0.4)
        lower_membership = _voter('proletariat-voter', 0.3)
        missing_candidate = _voter('populist-voter', 0.2)
        gentry.membership.add(aligned.id)
        gentry.membership.add(defector.id)
        proletariat.membership.add(lower_membership.id)
        populist.membership.add(missing_candidate.id)
        traced = _world([aligned, defector, no_membership,
                         lower_membership, missing_candidate],
                        {'Gentry': gentry, 'Proletariat': proletariat,
                         'Populist': populist}, incumbent='Gentry')
        plain = _world([aligned, defector, no_membership,
                        lower_membership, missing_candidate],
                       {'Gentry': gentry, 'Proletariat': proletariat,
                        'Populist': populist}, traced=False,
                       incumbent='Gentry')
        gentry_candidate = Candidate(_voter('gentry-candidate', 0.5),
                                     backing_faction='Gentry')
        proletariat_candidate = Candidate(
            _voter('labor-candidate', 0.9), backing_faction='Proletariat')
        independent_candidate = Candidate(
            _voter('independent-candidate', 0.7), backing_faction=None)
        candidates = [gentry_candidate, proletariat_candidate,
                      independent_candidate]

        traced_votes = faction_weighted_vote(traced[0], candidates, 7)
        plain_votes = faction_weighted_vote(plain[0], candidates, 7)

        self.assertEqual(traced_votes, plain_votes)
        self.assertAlmostEqual(traced_votes[gentry_candidate], 0.88)
        self.assertAlmostEqual(traced_votes[proletariat_candidate], 2.81)
        self.assertEqual(traced_votes[independent_candidate], 0.0)
        decisions = [row for row in traced[2].rows
                     if row.get('kind') == 'election_voter_decision']
        by_voter = {row['inputs']['voter_id']: row for row in decisions}
        self.assertEqual(by_voter['aligned']['after'], 'gentry-candidate')
        self.assertEqual(by_voter['defector']['after'], 'labor-candidate')
        self.assertEqual(by_voter['defector']['inputs']['reason'],
                         'broken_promise_defection')
        self.assertEqual(by_voter['independent-voter']['inputs']['vote_weight'],
                         1.0)
        self.assertEqual(by_voter['populist-voter']['inputs']['reason'],
                         'faction_candidate_missing_charisma_fallback')
        tallies = {row['subject']['id']: row['after']
                   for row in traced[2].rows
                   if row.get('kind') == 'election_candidate_vote_tally'}
        self.assertAlmostEqual(tallies['gentry-candidate'], 0.88)
        self.assertAlmostEqual(tallies['labor-candidate'], 2.81)
        self._assert_catalogued(traced[2].rows)

    def _row(self, fixture, kind):
        return next(row for row in fixture[2].rows
                    if row.get('kind') == kind)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
