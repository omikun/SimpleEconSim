"""Demand-only generation, immutable evidence, client lifecycle, and planning persistence."""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from run_trace import RunTrace
from explanations.context import capture, capture_server
from explanations.packet import build_packet
from explanations.service import ExplanationService, TERMINAL
from explanations.schema import validate
from explanations.proposals import ProposalLog


def response(packet, future=False):
    result = {'selection_id': packet['selection_id'],
              'claims': [{'text': 'The recorded calculation explains the closing value; upstream provenance remains limited.',
                          'evidence_ids': [packet['evidence'][0]['event_id']], 'level': 'observation'}],
              'historical_parallel': None, 'suggested_actions': [], 'future_mechanics': []}
    if future:
        result['future_mechanics'] = [{'capability': 'targeted_contamination_prevention',
            'title': 'Targeted water protection', 'unmet_need': 'Prevent repeated exposure.',
            'gap_reason': 'Medical funding does not remove the exposure; catalog coverage needs review.',
            'proposal': 'Let players protect a water source and track maintenance.',
            'tradeoffs': 'Requires construction resources and upkeep; effects need testing.',
            'acceptance_criteria': ['Record exposure before and after maintenance.'],
            'evidence_ids': [packet['evidence'][0]['event_id']], 'source_ids': []}]
    return result


class FakeProvider:
    model = 'fixture-model'
    unavailable = None

    def __init__(self, future=False, gate=None):
        self.calls = 0; self.future = future; self.gate = gate

    def generate(self, packet):
        self.calls += 1
        if self.gate is not None:
            self.gate.wait(3)
        return response(packet, self.future), {'model': self.model, 'usage': {}}


def done(service, job):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = service.status(job['job_id'], job['viewer'])
        if current['state'] in TERMINAL:
            return current
        time.sleep(.01)
    raise AssertionError('Explanation did not reach a terminal state')


class TraceFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = RunTrace(self.root / 'run.ctr', 'run-a')
        self.addCleanup(self.trace._compact_writer.close)
        self.clock = {'turn': 1, 'epoch': 0, 'next': 1}
        self.subject = {'type': 'tile', 'id': 'Delta'}
        self.source = self.trace.emit(self.clock, kind='production_total', record_class='calculation',
            subject=self.subject, metric_id='economy.gdp_nominal', unit='C', before=100, after=120,
            formula_id='aggregate.sum.v1', inputs={'member_values': [40, 80]})
        self.trace.snapshot(self.clock, subject=self.subject, metric_id='economy.gdp_nominal',
                            unit='C', before=100, after=120)
        self.trace.checkpoint(self.clock)
        self.nation = SimpleNamespace(name='Egypt', government=None, tiles=[])
        self.tile = SimpleNamespace(name='Delta', owner_nation=self.nation)
        self.nation.tiles = [self.tile]
        self.world = {'tiles': [self.tile], 'nations': [self.nation], 'turn': 1,
                      'run_trace': self.trace, 'scenario_id': 'egypt_1877'}
        self.selection = {'entity': 'tile:Delta', 'metric_id': 'economy.gdp_nominal', 'turn': 1}

    def service(self, provider=None):
        service = ExplanationService(provider or FakeProvider(), self.root / 'cache', self.root / 'planning')
        self.addCleanup(service.close)
        return service


class ExplainerTests(TraceFixture):
    def test_packet_preserves_boundary_values_evidence_and_read_only_state(self):
        import random
        rng = random.getstate(); count = self.trace.count; digest = self.trace.digest
        before = deepcopy(self.tile.__dict__)
        packet = build_packet(capture(self.world, self.selection))
        self.assertEqual({'before': 100, 'after': 120, 'delta': 20, 'percent': 20., 'unit': 'C', 'epoch': 0}, packet['values'])
        self.assertEqual('verified_formula', packet['evidence'][0]['status'])
        self.assertEqual(rng, random.getstate()); self.assertEqual(count, self.trace.count)
        self.assertEqual(digest, self.trace.digest); self.assertEqual(before.keys(), self.tile.__dict__.keys())

    def test_snapshot_after_many_events_is_not_lost_at_page_limit(self):
        clock = self.clock; clock['turn'] = 2
        for i in range(70):
            self.trace.emit(clock, kind='observation', subject=self.subject,
                            metric_id='economy.gdp_nominal', after=i)
        self.trace.snapshot(clock, subject=self.subject, metric_id='economy.gdp_nominal',
                            unit='C', before=120, after=130)
        self.trace.checkpoint(clock); self.world['turn'] = 2
        packet = build_packet(capture(self.world, {**self.selection, 'turn': 2}))
        self.assertEqual(130, packet['values']['after'])
        self.assertTrue(any('partial' in gap for gap in packet['limitations']))

    def test_unchanged_zero_baseline_missing_sample_and_no_invented_delta(self):
        for turn, before, after in ((2, 0, 10), (3, 10, 10), (4, None, 8)):
            clock = self.clock; clock['turn'] = turn
            self.trace.snapshot(clock, subject=self.subject, metric_id='economy.gdp_nominal', unit='C', before=before, after=after)
            self.trace.checkpoint(clock)
            self.world['turn'] = turn
            packet = build_packet(capture(self.world, {**self.selection, 'turn': turn}))
            self.assertEqual(None if before is None else after - before, packet['values']['delta'])
            if not before: self.assertIsNone(packet['values']['percent'])

    def test_missing_source_and_later_events_remain_gaps(self):
        clock = dict(self.clock, turn=2)
        later = self.trace.emit(clock, kind='later', after=10)
        self.clock['next'] = clock['next']
        self.trace.emit(self.clock, kind='calculation', subject=self.subject,
                        metric_id='economy.gdp_nominal', after=120, cause_event_ids=[later, 'missing'])
        self.clock['epoch'] = 1
        self.trace.snapshot(self.clock, subject=self.subject, metric_id='economy.gdp_nominal',
                            unit='C', before=120, after=120)
        self.trace.publish()
        packet = build_packet(capture(self.world, {**self.selection, 'epoch': 1}))
        self.assertNotIn(later, [e['event_id'] for e in packet['evidence']])
        self.assertTrue(any('Missing or later source' in gap for gap in packet['limitations']))

    def test_default_tick_sample_is_separate_from_between_turn_command_epoch(self):
        self.clock['epoch'] = 1
        self.trace.snapshot(self.clock, subject=self.subject, metric_id='economy.gdp_nominal', unit='C', before=120, after=110)
        self.trace.publish()
        tick = build_packet(capture(self.world, self.selection))
        command = build_packet(capture(self.world, {**self.selection, 'epoch': 1}))
        self.assertEqual(20, tick['values']['delta']); self.assertEqual(-10, command['values']['delta'])

    def test_unknown_metric_and_absent_trace_do_not_call_provider(self):
        provider = FakeProvider(); service = self.service(provider)
        job = service.request(capture(self.world, {**self.selection, 'metric_id': 'unknown.stat'}))
        self.assertEqual('failed', done(service, job)['state']); self.assertEqual(0, provider.calls)
        with self.assertRaises(ValueError): capture({**self.world, 'run_trace': None}, self.selection)

    def test_no_generation_without_request_even_after_state_reads(self):
        provider = FakeProvider(); service = self.service(provider)
        for _ in range(20):
            capture(self.world, self.selection)
            build_packet(capture(self.world, self.selection))
        self.assertIsNone(service.executor); self.assertEqual(0, provider.calls)

    def test_duplicate_requests_share_work_and_cache_survives_restart(self):
        gate = threading.Event(); provider = FakeProvider(gate=gate); service = self.service(provider)
        captured = capture(self.world, self.selection)
        a = service.request(captured); b = service.request(captured)
        self.assertEqual(a['job_id'], b['job_id']); self.assertNotEqual(a['viewer'], b['viewer'])
        service.cancel(a['job_id'], a['viewer']); gate.set()
        ready = done(service, b); self.assertEqual('ready', ready['state']); self.assertEqual(1, provider.calls)
        second = self.service(FakeProvider()); cached = done(second, second.request(captured))
        self.assertEqual('ready', cached['state']); self.assertEqual(0, second.provider.calls)

    def test_later_turns_and_affordability_do_not_regenerate_cached_tick(self):
        service = self.service()
        first = done(service, service.request(capture(self.world, self.selection)))
        self.clock['turn'] = 2
        self.trace.emit(self.clock, kind='later_turn', after=7)
        self.trace.checkpoint(self.clock); self.world['turn'] = 2
        changed = capture(self.world, self.selection)
        changed['actions'][0]['available'] = not changed['actions'][0]['available']
        repeat = done(service, service.request(changed))
        self.assertEqual(first['job_id'], repeat['job_id']); self.assertEqual(1, service.provider.calls)

    def test_cancelled_job_cannot_publish_or_log(self):
        gate = threading.Event(); provider = FakeProvider(True, gate); service = self.service(provider)
        a = service.request(capture(self.world, self.selection))
        deadline = time.monotonic() + 2
        while provider.calls == 0 and time.monotonic() < deadline: time.sleep(.01)
        service.cancel(a['job_id'], a['viewer']); gate.set()
        service.jobs[a['job_id']]['future'].result(timeout=3)
        self.assertEqual('cancelled', service.jobs[a['job_id']]['state'])
        self.assertFalse(list((self.root / 'planning').glob('*.json')))

    def test_queue_capacity_is_bounded_and_status_does_not_create_work(self):
        gate = threading.Event(); service = self.service(FakeProvider(gate=gate))
        captured = capture(self.world, self.selection)
        for i in range(4): service.request({**captured, 'nation': str(i)})
        with self.assertRaises(ValueError): service.request({**captured, 'nation': 'overflow'})
        with self.assertRaises(ValueError): service.status('absent', 'absent')
        gate.set()

    def test_disabled_provider_does_not_make_network_request(self):
        provider = FakeProvider(); provider.unavailable = 'Disabled for this test.'
        service = self.service(provider); job = service.request(capture(self.world, self.selection))
        self.assertEqual('unavailable', done(service, job)['state']); self.assertEqual(0, provider.calls)

    def test_checkpoints_exclude_explanation_workers_and_credentials(self):
        from simulation_checkpoint import capture_globals
        service = self.service()
        with patch('explanations.service._DEFAULT', service):
            values, _ = capture_globals()
        self.assertFalse(any(module.startswith('explanations') for module, _, _ in values))

    def test_validation_rejects_invented_actions_sources_numbers_and_evidence_upgrades(self):
        packet = build_packet(capture(self.world, self.selection)); packet['historical_candidates'] = []
        base = response(packet)
        validate(base, packet)
        for change in (
            lambda r: r['suggested_actions'].append({'action_id': 'invented', 'rationale': 'Act now.'}),
            lambda r: r['claims'][0].update(evidence_ids=['invented']),
            lambda r: r['claims'][0].update(level='verified_chain'),
            lambda r: r['claims'][0].update(text='Output rose by 999.'),
            lambda r: r.update(historical_parallel={'entry_id': 'invented', 'comparison': 'Similar.', 'difference': 'Different.'}),
        ):
            invalid = deepcopy(base); change(invalid)
            with self.assertRaises(ValueError): validate(invalid, packet)

    def test_future_proposal_not_playable_and_deduplicates_preserving_reviews(self):
        service = self.service(FakeProvider(True)); job = service.request(capture(self.world, self.selection))
        ready = done(service, job); self.assertEqual('ready', ready['state'], ready['message'])
        result = ready['result']; self.assertEqual([], result['narrative']['suggested_actions'])
        path = next((self.root / 'planning').glob('*.json')); record = json.loads(path.read_text())
        self.assertEqual('proposed', record['status'])
        record['status'] = 'rejected'; record['review_notes'] = 'Already covered elsewhere.'
        path.write_text(json.dumps(record))
        service.retry_logging(job['job_id'], job['viewer'])
        updated = json.loads(path.read_text()); self.assertEqual('rejected', updated['status'])
        self.assertEqual('Already covered elsewhere.', updated['review_notes'])
        self.assertEqual(1, len(updated['occurrences'])); self.assertEqual(1, service.provider.calls)
        # A distinct selection becomes another occurrence of the same capability.
        packet = deepcopy(result['packet']); packet['selection_id'] = 'another'
        service.proposals.record(result['narrative']['future_mechanics'][0], packet)
        self.assertEqual(2, len(json.loads(path.read_text())['occurrences']))

    def test_log_failure_keeps_explanation_and_retry_needs_no_model(self):
        service = self.service(FakeProvider(True))
        with patch.object(ProposalLog, 'record', side_effect=OSError('unwritable')):
            job = service.request(capture(self.world, self.selection)); ready = done(service, job)
        self.assertEqual('ready', ready['state']); self.assertEqual('not_logged', ready['result']['proposal_logs'][0]['status'])
        retry = service.retry_logging(job['job_id'], job['viewer'])
        self.assertEqual('logged', retry['result']['proposal_logs'][0]['status']); self.assertEqual(1, service.provider.calls)

    def test_concurrent_proposal_occurrences_are_preserved_atomically(self):
        from concurrent.futures import ThreadPoolExecutor
        packet = build_packet(capture(self.world, self.selection)); packet['historical_candidates'] = []
        proposal = response(packet, True)['future_mechanics'][0]
        log = ProposalLog(self.root / 'concurrent-planning')
        def write(index):
            local = deepcopy(packet); local['selection_id'] = 'selection-' + str(index)
            return log.record(proposal, local)
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(write, range(12)))
        files = list((self.root / 'concurrent-planning').glob('*.json'))
        self.assertEqual(1, len(files)); self.assertEqual(12, len(json.loads(files[0].read_text())['occurrences']))

    def test_current_availability_changes_without_regenerating_historical_advice(self):
        from explanations.mechanics import current
        packet = build_packet(capture(self.world, self.selection))
        self.tile.agents = [SimpleNamespace(alive=True, hungry_steps=2)]
        available = current(self.world, packet)
        self.assertTrue(next(a for a in available['actions'] if a['id'] == 'nat_emergency_granary')['available'])
        self.tile.agents[0].hungry_steps = 0
        blocked = current(self.world, packet)
        self.assertFalse(next(a for a in blocked['actions'] if a['id'] == 'nat_emergency_granary')['available'])
        self.assertEqual(20, packet['values']['delta'])

    def test_existing_blocked_capability_is_not_future_mechanic(self):
        packet = build_packet(capture(self.world, self.selection)); packet['historical_candidates'] = []
        proposal = response(packet, True); proposal['future_mechanics'][0]['capability'] = 'immediate_food_relief'
        packet['actions'][0]['available'] = False
        with self.assertRaises(ValueError): validate(proposal, packet)

    def test_history_matches_mechanism_and_does_not_force_same_nation(self):
        from explanations.history import candidates
        packet = build_packet(capture(self.world, self.selection))
        packet['selection']['metric_id'] = 'goods.food_aid'
        self.assertEqual('ireland_food_relief_1845', candidates(packet)[0]['id'])
        packet['selection']['metric_id'] = 'finance.treasury'
        self.assertEqual('egypt_revenue_pledges_1876', candidates(packet)[0]['id'])

    def test_capture_rejects_old_world_and_invalid_dimensions(self):
        sim = SimpleNamespace(_lock=threading.RLock(), run_trace=self.trace, tiles=[self.tile],
                              nations=[self.nation], turn=1, scenario_id=None)
        with self.assertRaises(ValueError): capture_server(sim, {**self.selection, 'run_id': 'old'})
        for updates in ({'turn': 2}, {'turn': True}, {'boundary': -1}, {'good': {}}, {'entity': 'tile:Missing'}):
            with self.assertRaises(ValueError): capture(self.world, {**self.selection, **updates})

    def test_http_generation_and_status_require_authentication(self):
        from client.web.server import CoCHTTPRequestHandler
        class Handler(CoCHTTPRequestHandler):
            def __init__(self, method, path, data=None, token='token'):
                self.server = SimpleNamespace(api_token='token', sim_server=SimpleNamespace(
                    _lock=threading.RLock(), run_trace=self_outer.trace, tiles=[self_outer.tile],
                    nations=[self_outer.nation], turn=1, scenario_id=None))
                raw = json.dumps(data or {}).encode(); self.path = path
                self.headers = {'Content-Length': str(len(raw)), 'X-COC-Token': token}
                self.rfile = BytesIO(raw); self.wfile = BytesIO()
                if method == 'POST': self.do_POST()
                else: self.do_GET()
            def send_response(self, status, message=None): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        self_outer = self
        self.nation.treasury = lambda: {'food': 0}
        service = self.service()
        with patch('explanations.service.default_service', return_value=service):
            denied = Handler('POST', '/api/ai-explanations', self.selection, token='wrong')
            self.assertEqual(403, denied.status); self.assertEqual(0, service.provider.calls)
            metrics = Handler('GET', '/api/ai-metrics'); self.assertEqual(200, metrics.status)
            self.assertEqual(0, service.provider.calls)
            submitted = Handler('POST', '/api/ai-explanations', self.selection)
            self.assertEqual(200, submitted.status)
            job = json.loads(submitted.wfile.getvalue()); ready = done(service, job)
            self.assertEqual('ready', ready['state'], ready['message'])
            denied = Handler('GET', '/api/ai-explanations/' + job['job_id'] + '?viewer=' + job['viewer'], token='wrong')
            self.assertEqual(403, denied.status)
            unknown = Handler('GET', '/api/ai-explanations/absent?viewer=absent')
            self.assertEqual(400, unknown.status)
            availability = Handler('GET', '/api/ai-explanations/' + job['job_id'] + '/availability?viewer=' + job['viewer'])
            self.assertEqual(200, availability.status)
            self.assertEqual(1, service.provider.calls)

    def test_provider_sends_strict_schema_without_tools_or_persisted_inputs(self):
        from explanations.provider import OpenAIProvider
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture-secret', 'COC_AI_MODEL': 'fixture-model', 'COC_AI_EXPLAINER': '1'}):
            provider = OpenAIProvider()
        packet = build_packet(capture(self.world, self.selection)); packet['historical_candidates'] = []
        raw = {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(response(packet))}]}]}
        with patch('urllib.request.urlopen') as fetch:
            fetch.return_value.__enter__.return_value.read.return_value = json.dumps(raw).encode()
            result, _ = provider.generate(packet)
            request = fetch.call_args.args[0]; body = json.loads(request.data)
            self.assertFalse(body['store']); self.assertTrue(body['text']['format']['strict']); self.assertNotIn('tools', body)
            self.assertEqual(packet['selection_id'], result['selection_id'])


if __name__ == '__main__':
    unittest.main()
