"""Compact trace storage and decoding."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from run_trace import RunTrace, verify
from trace_codec import MAGIC, iter_payloads,CompactTraceWriter,TornTraceTail
from trace_report import report


class TraceCodecTests(unittest.TestCase):
    def test_writer_buffers_partial_block_until_reader_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'buffered.ctr';writer=CompactTraceWriter(path)
            writer.append('{"index":0}')
            writer.append('{"index":1}')
            self.assertEqual(len(MAGIC),path.stat().st_size)
            self.assertEqual(['{"index":0}','{"index":1}'],
                             list(iter_payloads(path)))
            self.assertEqual(writer.end_offset,path.stat().st_size)
            writer.close()

    def test_delayed_publish_io_failure_is_recorded_on_run_trace(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            trace=RunTrace(Path(directory)/'publish-error.ctr','publish-error')
            with patch.object(trace._compact_writer,'publish',side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError,'disk full'):
                    trace.publish()
            self.assertEqual('disk full',trace.write_error)

    def test_persistent_writer_publishes_without_path_reopens_and_rejects_short_write(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'persistent.ctr';writer=CompactTraceWriter(path)
            with patch.object(Path,'open',side_effect=AssertionError('append reopened file')),patch.object(Path,'stat',side_effect=AssertionError('append stat-ed file')):
                for index in range(300):writer.append(json.dumps({'index':index}))
            writer.publish()
            self.assertEqual(writer.end_offset,path.stat().st_size)
            self.assertEqual(300,len(list(iter_payloads(path))))
            boundary=writer.end_offset;stream=writer._stream
            class ShortWrite:
                closed=False
                def write(self,data):return stream.write(data[:-1])
            with patch.object(writer,'_stream',ShortWrite()):
                with self.assertRaisesRegex(OSError,'incomplete'):writer.append('{"index":300}')
            self.assertEqual(boundary,writer.end_offset)
            self.assertEqual(300,len(list(iter_payloads(path,end_offset=boundary))))
            with self.assertRaises(TornTraceTail):list(iter_payloads(path))
            writer.close()
            with self.assertRaisesRegex(OSError,'closed'):writer.append('{}')

    def test_compact_roundtrip_query_verify_and_cli_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compact = RunTrace(root / 'run.ctr', 'compact', seed=5)
            clock = {'next': 1, 'turn': 1, 'phase': 'test'}
            for number in range(200):
                compact.emit(clock, kind='price_observation',
                             subject={'type': 'tile', 'id': 'Delta', 'good': 'food'},
                             metric_id='goods.price', after=2.0 + number / 1000,
                             inputs={'source': 'the repeated market ledger',
                                     'index': number})
            compact.emit(clock, kind='route_shipment_departure',
                         subject={'type': 'shipment', 'id': 'route-1:1'},
                         inputs={'good': 'cotton', 'quantity': 3})
            self.assertEqual(compact.query(turn=1, metric_id='goods.price')['total'], 200)
            self.assertEqual(compact.query(kind='route_shipment_departure')['total'], 1)
            self.assertEqual(len(report(compact.path, turn=1, good='food')), 200)
            self.assertEqual(len(report(compact.path, kind='route_shipment_departure')), 1)
            compact.checkpoint(clock)
            self.assertEqual(verify(compact.path)['checkpoints'], 1)
            self.assertEqual(compact.path.read_bytes()[:len(MAGIC)], MAGIC)
            decoded = [json.loads(payload) for payload in iter_payloads(compact.path)]
            self.assertEqual(decoded[0]['record_class'], 'metadata')
            self.assertEqual(decoded[-1]['kind'], 'turn_checkpoint')
            decoded_bytes = sum(len(payload.encode()) + 1
                                for payload in iter_payloads(compact.path))
            self.assertLess(compact.path.stat().st_size, decoded_bytes * 0.6)
            exported = root / 'decoded.jsonl'
            command = [sys.executable, str(Path(__file__).with_name('trace_report.py')),
                       '--run', str(compact.path), '--decode-jsonl', str(exported)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual([json.loads(line) for line in exported.read_text().splitlines()],
                             decoded)
            kind_command = [sys.executable,
                            str(Path(__file__).with_name('trace_report.py')),
                            '--run', str(compact.path), '--kind',
                            'route_shipment_departure']
            kind_result = subprocess.run(kind_command, check=True,
                                         capture_output=True, text=True)
            self.assertIn('route_shipment_departure', kind_result.stdout)
            self.assertNotIn('price_observation', kind_result.stdout)

    def test_jsonl_input_rejected_and_torn_compact_tail_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / 'old.jsonl'
            legacy.write_text('{"kind":"legacy"}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unsupported causal trace format'):
                list(iter_payloads(legacy))
            with self.assertRaisesRegex(ValueError, 'must end in .ctr'):
                RunTrace(legacy, 'old')
            clock = {'next': 1, 'turn': 1, 'phase': 'test'}
            compact = RunTrace(root / 'new.ctr', 'new')
            compact.emit(clock, kind='new', metric_id='goods.price', after=2)
            compact._compact_writer.publish()
            path = compact.path
            data = path.read_bytes()
            path.write_bytes(data[:-2])
            with self.assertRaisesRegex(ValueError, 'truncated compact trace'):
                list(iter_payloads(path))


if __name__ == '__main__':
    unittest.main()
