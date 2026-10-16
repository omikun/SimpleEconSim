"""Compact trace storage, decode, and legacy compatibility."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from run_trace import RunTrace, verify
from trace_codec import MAGIC, iter_payloads
from trace_report import report


class TraceCodecTests(unittest.TestCase):
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
            self.assertEqual(compact.query(turn=1, metric_id='goods.price')['total'], 200)
            self.assertEqual(len(report(compact.path, turn=1, good='food')), 200)
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

    def test_old_jsonl_still_reads_and_torn_compact_tail_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = RunTrace(root / 'old.jsonl', 'old')
            clock = {'next': 1, 'turn': 1, 'phase': 'test'}
            legacy.emit(clock, kind='legacy', metric_id='goods.price', after=2)
            legacy.checkpoint(clock)
            self.assertEqual(verify(legacy.path)['checkpoints'], 1)
            self.assertEqual(len(list(iter_payloads(legacy.path))), 3)

            compact = RunTrace(root / 'new.ctr', 'new')
            compact.emit(clock, kind='new', metric_id='goods.price', after=2)
            path = compact.path
            data = path.read_bytes()
            path.write_bytes(data[:-2])
            with self.assertRaisesRegex(ValueError, 'truncated compact trace'):
                list(iter_payloads(path))


if __name__ == '__main__':
    unittest.main()
