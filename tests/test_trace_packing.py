"""Packed storage/coverage is transparent to historical causal consumers."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

from run_trace import RunTrace, verify
from trace_codec import (CompactTraceWriter, CorruptTrace, TornTraceTail,
                         MAGIC, LEGACY_MAGIC, iter_records, iter_payloads, storage_stats)
from trace_codec import _frames, HEADER
from trace_packing import canonical, pack, unpack
from trace_index import TraceIndex


class PackedTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def trace(self, name, **kwargs):
        trace = RunTrace(self.root / (name + '.ctr'), 'same-run', **kwargs)
        self.addCleanup(trace._compact_writer.close)
        return trace

    def record(self, trace):
        clock = {'turn': 1, 'epoch': 0, 'next': 1, 'phase': 'snapshot'}
        subject = {'type': 'tile', 'id': 'Delta مصر', 'good': 'food'}
        for turn in range(1, 4):
            clock['turn'] = turn
            source = trace.emit(clock, kind='fixture_calculation', record_class='calculation',
                subject=subject, metric_id='goods.production', after=10, unit='units',
                formula_id='aggregate.sum.v1', inputs={'member_values': [5, 5]})
            for i in range(190):
                trace.snapshot(clock, subject={**subject, 'cohort': str(i)}, metric_id='goods.sold',
                               unit='units', before=0, after=0)
            trace.snapshot(clock, subject=subject, metric_id='goods.production', unit='units', before=10, after=10)
            trace.snapshot(clock, subject=subject, metric_id='goods.supply', unit='units', before=2, after=0)
            trace.snapshot(clock, subject=subject, metric_id='goods.demand', unit='units', before=None, after=0)
            trace.checkpoint(clock)
        return subject

    def test_legacy_dense_and_sparse_have_identical_logical_evidence(self):
        traces = [self.trace('legacy', storage_version=3), self.trace('packed', sparse=False), self.trace('sparse')]
        views = []
        for trace in traces:
            self.record(trace)
            rows = [json.loads(payload) for payload in iter_payloads(trace.path)]
            views.append([{k: v for k, v in row.items() if k not in ('sha256_before', 'digest_scope', 'event_count_before')}
                          for row in rows if row.get('record_class') != 'metadata'])
            self.assertEqual(3, verify(trace.path)['checkpoints'])
            self.assertEqual(trace.count, verify(trace.path)['rows'])
            self.assertEqual(trace.digest, verify(trace.path)['sha256'])
        self.assertEqual(views[0], views[1]); self.assertEqual(views[0], views[2])
        self.assertEqual(LEGACY_MAGIC, traces[0].path.read_bytes()[:len(MAGIC)])
        stats = storage_stats(traces[2].path)
        self.assertEqual(573, stats['covered_snapshots'])
        self.assertEqual(6, stats['explicit_snapshots']+stats['initial_samples'])
        self.assertLess(stats['physical_frames'], stats['logical_records'] // 10)
        self.assertEqual(0, storage_stats(traces[1].path)['covered_snapshots'])

    def test_coverage_retains_current_sources_epochs_and_zero_closings(self):
        trace = self.trace('sources'); subject = self.record(trace)
        index = TraceIndex(trace.path)
        for turn in range(1, 4):
            source = index.query(turn=turn, metric_id='goods.production', kind='fixture_calculation')['events'][0]
            row = index.query(turn=turn, metric_id='goods.production', kind='metric_snapshot')['events'][0]
            self.assertEqual([source['event_id']], row['cause_event_ids'])
            self.assertEqual(source['event_id'], row['inputs']['source_event_id'])
            self.assertEqual(turn, row['turn'])
            closing = index.query(turn=turn, metric_id='goods.supply', kind='metric_snapshot')['events'][0]
            self.assertEqual(-2, closing['delta'])
            missing = index.query(turn=turn, metric_id='goods.demand', kind='metric_snapshot')['events'][0]
            self.assertNotIn('value_before', missing)
        clock = {'turn': 3, 'epoch': 1, 'next': 10000}
        trace.snapshot(clock, subject=subject, metric_id='goods.production', unit='units', before=10, after=10)
        trace.publish()
        self.assertEqual([0, 1], [row['epoch'] for row in index.query(turn=3, subject=subject,
            metric_id='goods.production', kind='metric_snapshot')['events']])

    def test_historical_catalog_event_lookup_boundaries_and_seek(self):
        trace = self.trace('seek'); self.record(trace)
        records = list(iter_records(trace.path)); boundary = records[-1].end_offset
        # Every batch is independently seekable and its internal row ordinals stable.
        selected = records[270]
        seek = list(iter_records(trace.path, start_offset=selected.block_offset, end_offset=boundary))
        self.assertEqual(selected.payload, seek[selected.record_in_block].payload)
        index = TraceIndex(trace.path)
        expected = json.loads(selected.payload)
        self.assertEqual([expected], index.query(event_id=expected['event_id'])['events'])
        trace.emit({'turn': 4, 'next': 20000}, kind='later', metric_id='new.metric',
                   subject={'type': 'tile', 'id': 'Delta مصر'})
        trace.publish()
        self.assertEqual(0, index.query(boundary=boundary, turn=4)['total'])
        variants = index.available_metrics(turn=2, subject={'type': 'tile', 'id': 'Delta مصر'}, boundary=boundary)
        self.assertEqual(190, sum(row['metric_id'] == 'goods.sold' for row in variants))
        self.assertEqual([], index.available_metrics(turn=0, subject={'type': 'tile', 'id': 'Delta مصر'}))
        for sidecar in (index.index_path,): sidecar.unlink()
        self.assertEqual([expected], index.query(event_id=expected['event_id'])['events'])

    def test_input_mutation_cannot_rewrite_queued_history_and_invalid_data_fails(self):
        trace = self.trace('immutable'); clock = {'turn': 1, 'next': 1}
        inputs = {'members': [{'amount': 2}], 'list': [1]}; subject = {'type': 'tile', 'id': 'A'}
        trace.emit(clock, kind='original', inputs=inputs, subject=subject)
        inputs['members'][0]['amount'] = 999; inputs['list'].append(5); subject['id'] = 'B'
        row = trace.query(kind='original')['events'][0]
        self.assertEqual(2, row['inputs']['members'][0]['amount'])
        self.assertEqual([1], row['inputs']['list']); self.assertEqual('A', row['subject']['id'])
        with self.assertRaises(TypeError): trace.emit(clock, kind='bad', inputs={'bad': {1, 2}})
        with self.assertRaises(ValueError): trace.emit(clock, kind='bad', after=float('nan'))

    def test_sparse_codec_preserves_types_signed_zero_unicode_and_unknown_rules_fail(self):
        trace = self.trace('types'); clock = {'turn': 1, 'next': 1}
        for i, value in enumerate((0, 0., -0., True, False, 'calm', 'مصر "\\')):
            trace.snapshot(clock, subject={'type': 'tile', 'id': str(i)}, metric_id='value',
                           before=value, after=value, unit='unit')
        rows = [json.loads(payload) for payload in iter_payloads(trace.path)]
        packet = pack(rows)
        self.assertEqual(canonical(rows), canonical(list(unpack(json.loads(canonical(packet))))))
        changed = deepcopy(packet)
        changed['schemas'][0]['rule'] = 'unknown'
        with self.assertRaises(ValueError): list(unpack(json.loads(canonical(changed))))

    def test_resume_in_fresh_process_preserves_prefix_chain_and_branch_sources(self):
        trace = self.trace('resume'); self.record(trace); trace._compact_writer.close()
        prefix = trace.path.read_bytes()
        script = self.root / 'resume.py'
        script.write_text('''from trace_codec import CompactTraceWriter
from pathlib import Path
import sys
writer=CompactTraceWriter(Path(sys.argv[1]),resume=True)
writer.append({'run_id':'same-run','branch_id':'fork','sequence':9000,'event_id':'same-run:fork:9000',
 'record_class':'audit','kind':'fork_event','turn':4,'cause_event_ids':['same-run:1']})
writer.close()
''')
        subprocess.run([sys.executable, str(script), str(trace.path)], check=True,
                       env=__import__('os').environ | {'PYTHONPATH': str(Path(__file__).resolve().parents[1])})
        self.assertEqual(prefix, trace.path.read_bytes()[:len(prefix)])
        self.assertEqual(3, verify(trace.path)['checkpoints'])
        self.assertEqual('same-run:fork:9000', json.loads(list(iter_payloads(trace.path))[-1])['event_id'])

    def test_truncation_corruption_and_short_write_keep_fixed_prefix_readable(self):
        trace = self.trace('broken'); self.record(trace); trace._compact_writer.close()
        data = trace.path.read_bytes(); records = list(iter_records(trace.path))
        boundary = records[200].end_offset
        trace.path.write_bytes(data[:-1])
        self.assertTrue(list(iter_records(trace.path, end_offset=boundary)))
        with self.assertRaises(TornTraceTail): list(iter_records(trace.path))
        damaged = bytearray(data); damaged[-10] ^= 1; trace.path.write_bytes(damaged)
        with self.assertRaises(CorruptTrace): list(iter_records(trace.path))

    def test_repaired_crc_does_not_hide_a_broken_packet_digest_chain(self):
        trace = self.trace('chain'); self.record(trace); trace._compact_writer.close()
        data = trace.path.read_bytes(); version, kind, payload, block, _, end = list(_frames(trace.path))[-1]
        envelope = json.loads(payload); envelope['previous_digest'] = '0' * 64
        compressor = zlib.compressobj(6, zlib.DEFLATED, -15)
        chunk = compressor.compress((canonical(envelope) + '\n').encode()) + compressor.flush(zlib.Z_SYNC_FLUSH)
        rewritten = HEADER.pack(b'S', 0, 0) + HEADER.pack(b'P', len(chunk), zlib.crc32(chunk)) + chunk
        trace.path.write_bytes(data[:block] + rewritten)
        with self.assertRaisesRegex(CorruptTrace, 'digest chain'): list(iter_records(trace.path))

    def test_failed_packed_append_exposes_only_the_safe_fixed_prefix(self):
        trace = self.trace('short-packed'); writer = trace._compact_writer
        boundary = trace.publish(); stream = writer._stream
        class ShortWrite:
            closed = False
            def write(self, data): return stream.write(data[:-1])
        trace.emit({'turn': 1, 'next': 1}, kind='pending')
        with patch.object(writer, '_stream', ShortWrite()):
            with self.assertRaisesRegex(OSError, 'incomplete'): trace.publish()
        self.assertIsNotNone(trace.write_error)
        self.assertEqual(1, len(list(iter_records(trace.path, end_offset=boundary))))
        with self.assertRaises(TornTraceTail): list(iter_records(trace.path))

    def test_legacy_trace_can_fork_and_resume_with_legacy_checkpoint_integrity(self):
        trace = self.trace('old-fork', storage_version=3); self.record(trace); trace._compact_writer.close()
        original = trace.path.read_bytes(); fork = self.root / 'old-branch.ctr'; fork.write_bytes(original)
        trace.rebind(fork, 'fork')
        event = trace.emit({'turn': 4, 'next': 10000}, kind='continued', cause_event_ids=['same-run:1'])
        trace.checkpoint({'turn': 4, 'next': 10001})
        self.assertEqual('same-run:fork:10000', event)
        self.assertEqual(original, fork.read_bytes()[:len(original)])
        self.assertEqual(4, verify(fork)['checkpoints'])
        self.assertEqual(trace.digest, verify(fork)['sha256'])

    def test_seek_from_raw_block_into_packed_batch_restores_its_known_chain(self):
        path = self.root / 'mixed.ctr'
        writer = CompactTraceWriter(path, block_records=1)
        writer.append(canonical({'kind': 'first'}))
        writer.append(canonical({'kind': 'raw'}))
        writer.append({'kind': 'packed'})
        writer.close()
        records = list(iter_records(path))
        selected = list(iter_records(path, start_offset=records[1].block_offset))
        self.assertEqual(['raw', 'packed'], [json.loads(record.payload)['kind'] for record in selected])
        self.assertIsNone(selected[0].digest_before)
        self.assertIsNone(selected[0].digest_after)
        self.assertEqual(records[-1].digest_after, selected[-1].digest_after)

    def test_retained_zero_categories_do_not_invent_native_command_changes(self):
        from trace_snapshots import samples_match
        normal = ('economy.cash', 'A')
        profession = ('people.profession_population', 'A', 'wood')
        livelihood = ('labor.primary_livelihood', 'A', 'wood')
        status = ('labor.employment_status', 'A', 'independent')
        observed = ({'type': 'tile', 'id': 'A'}, 'people', 0)
        current = {normal: ({'type': 'tile', 'id': 'A'}, 'C', 10)}
        previous = {**current, profession: observed, livelihood: observed, status: observed}
        self.assertTrue(samples_match(previous, current))
        self.assertFalse(samples_match(previous, {**current, profession: (observed[0], 'people', 1)}))
        self.assertFalse(samples_match({**previous, profession: (observed[0], 'people', 1)}, current))
        self.assertFalse(samples_match(previous, {normal: (observed[0], 'C', 11)}))
        self.assertFalse(samples_match({**previous, ('some.other.metric', 'A'): observed}, current))

    def test_native_step_records_once_for_quiet_zero_categories_and_keeps_real_actions(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from desktop_trace_session import traced_world_step
        for pending_action in (False, True):
            clock = {'turn': 1, 'epoch': 0, 'next': 1}
            tile = SimpleNamespace(_collective_trace_clock=clock)
            trace = MagicMock(count=11 if pending_action else 10)
            session = SimpleNamespace(tiles=[tile], nations=[], run_trace=trace, pending_start=10,
                _trace_previous={('people.profession_population', 'A', 'wood'): ({}, 'people', 0)})
            world = {'turn': 1, '_trace_session': session, 'tiles': [tile], 'nations': []}
            @traced_world_step
            def step(state): state['turn'] += 1
            with patch('trace_snapshots.sample', return_value={}), patch('trace_snapshots.record') as record:
                step(world)
            self.assertEqual(2 if pending_action else 1, record.call_count)
            self.assertEqual(2 if pending_action else 1, trace.checkpoint.call_count)

if __name__ == '__main__': unittest.main()
