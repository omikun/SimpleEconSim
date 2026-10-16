"""Append-only, typed causal records for a simulation run.

The recorder keeps a bounded UI window. The JSONL file is the source of truth
for older turns; read failures never affect simulation state.
"""

from __future__ import annotations

from collections import deque
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = 1


class RunTrace:
    def __init__(self, path, run_id, *, seed=None, scenario=None, recent_limit=256):
        self.path = Path(path)
        self.run_id = str(run_id)
        self.branch_id = 'main'
        self.recent = deque(maxlen=recent_limit)
        self.write_error = None
        self.count = 0
        self.digest = '0' * 64
        self._active_turn = None
        self._calculated = set()
        self._calculated_values = {}
        self._treasury_flows = {}
        self._price_mutations = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(self.path)
        self._append({'schema_version': SCHEMA_VERSION, 'record_class': 'metadata',
                      'run_id': self.run_id, 'branch_id': self.branch_id,
                      'seed': seed, 'scenario': scenario})

    def _append(self, row):
        # No default=str: unsupported values are instrumentation errors.
        payload = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(payload + '\n')
        self.count += 1
        self.digest = hashlib.sha256((self.digest + payload).encode('utf-8')).hexdigest()

    def emit(self, clock, *, kind, record_class='observation', phase=None,
             subject=None, metric_id=None, before=None, after=None,
             unit=None, inputs=None, formula_id=None, constraints=None,
             cause_event_ids=None, **extra):
        sequence = clock['next']
        clock['next'] += 1
        if self._active_turn != clock.get('turn', 0):
            self._active_turn = clock.get('turn', 0)
            self._calculated.clear()
            self._calculated_values.clear()
            self._treasury_flows.clear()
            self._price_mutations.clear()
        row = {'schema_version': SCHEMA_VERSION, 'run_id': self.run_id,
               'branch_id': self.branch_id, 'event_id': f'{self.run_id}:{sequence}',
               'sequence': sequence, 'turn': clock.get('turn', 0),
               'phase': phase or clock.get('phase', 'unknown'),
               'kind': kind, 'record_class': record_class,
               'confidence': 'exact' if record_class in ('calculation', 'transfer', 'outcome')
               else 'unknown'}
        if subject is not None:
            row['subject'] = subject
        if metric_id is not None:
            row['metric_id'] = metric_id
        if before is not None:
            row['value_before'] = before
        if after is not None:
            row['value_after'] = after
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            row['delta'] = after - before
        for key, value in (('unit', unit), ('inputs', inputs),
                           ('formula_id', formula_id), ('constraints', constraints),
                           ('cause_event_ids', cause_event_ids)):
            if value is not None:
                row[key] = value
        row.update(extra)
        if formula_id is not None and metric_id in (
                'goods.price', 'goods.seller_ask', 'goods.delivered_quote',
                'goods.transaction_vwap'):
            from price_trace import replay_event
            replay = replay_event(row)
            if replay is not None:
                row['formula_replay'] = replay
                if not replay['matches']:
                    row['confidence'] = 'unknown'
        provenance_key = (metric_id, json.dumps(subject, sort_keys=True)
                          if subject is not None else None)
        if record_class in ('calculation', 'transfer', 'outcome') and row.get(
                'formula_replay', {}).get('matches', True):
            self._calculated.add(provenance_key)
            if after is not None:
                self._calculated_values[provenance_key] = after
        if metric_id == 'goods.price' and record_class == 'calculation' and subject:
            price_key = (subject.get('id'), subject.get('good'))
            self._price_mutations.setdefault(price_key, []).append(row)
        if metric_id == 'finance.treasury_flow' and subject is not None:
            nation_id = subject.get('id') if subject.get('type') == 'nation' else None
            if nation_id is not None:
                flows = self._treasury_flows.setdefault(nation_id, [])
                flows.append({'event_id': row['event_id'], 'amount': after,
                              'kind': kind})
        try:
            self._append(row)
        except OSError as exc:
            self.write_error = str(exc)
        self.recent.append(row)
        return row['event_id']

    def snapshot(self, clock, *, subject, metric_id, unit, before, after):
        key = (metric_id, json.dumps(subject, sort_keys=True))
        explained = (self.write_error is None and key in self._calculated_values
                     and self._calculated_values[key] == after)
        event_id = self.emit(clock, kind='metric_snapshot', record_class='observation',
                             subject=subject, metric_id=metric_id, unit=unit,
                             before=before, after=after,
                             confidence='exact' if explained else 'unknown',
                             explanation_status='calculation_recorded' if explained else
                             'source_missing')
        if before is not None and before != after and not explained:
            self.emit(clock, kind='unexplained_change', record_class='audit',
                      subject=subject, metric_id=metric_id, unit=unit,
                      before=before, after=after, source='metric_catalog')
        return event_id

    def price_bridge(self, clock, *, subject, before, after, unit):
        """Reconcile ordered displayed-price writes within the current turn."""
        mutations = self._price_mutations.get((subject['id'], subject['good']), ())
        steps = []
        current = before
        gaps = []
        for row in mutations:
            opening = row.get('value_before')
            closing = row.get('value_after')
            if row.get('formula_replay', {}).get('matches') is False:
                gaps.append({'event_id': row['event_id'],
                             'reason': 'formula_replay_mismatch'})
            if current is not None and opening != current:
                gaps.append({'event_id': row['event_id'], 'expected_opening': current,
                             'recorded_opening': opening})
            if opening is not None and closing is not None:
                steps.append({'event_id': row['event_id'], 'kind': row['kind'],
                              'before': opening, 'after': closing,
                              'difference': closing - opening})
            current = closing
        if current != after:
            gaps.append({'expected_closing': after, 'recorded_closing': current})
        reconciled = not gaps and self.write_error is None
        change = after - before if before is not None else None
        return self.emit(clock, kind='price_bridge', record_class='audit',
                         subject=subject, metric_id='goods.price', unit=unit,
                         before=before, after=after,
                         confidence='exact' if reconciled else 'unknown',
                         explanation_status='ordered_writes_reconciled' if reconciled
                         else 'mutation_chain_incomplete',
                         inputs={'steps': steps, 'gaps': gaps,
                                 'absolute_change': change,
                                 'percent_change': 100 * change / before
                                 if change is not None and before != 0 else None},
                         cause_event_ids=[row['event_id'] for row in mutations])

    def checkpoint(self, clock):
        """End a turn with a count and hash of every preceding JSONL row."""
        return self.emit(clock, kind='turn_checkpoint', record_class='audit',
                         phase='checkpoint', count_before=self.count,
                         sha256_before=self.digest)


    def query(self, *, turn=None, subject=None, metric_id=None, offset=0, limit=100):
        found = []
        matched = 0
        with self.path.open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row.get('record_class') == 'metadata':
                    continue
                if turn is not None and row.get('turn') != turn:
                    continue
                if subject is not None and not all(
                        row.get('subject', {}).get(key) == value
                        for key, value in subject.items()):
                    continue
                if metric_id is not None and row.get('metric_id') != metric_id:
                    continue
                if matched >= offset and len(found) < limit:
                    found.append(row)
                matched += 1
        return {'events': found, 'total': matched, 'offset': offset,
                'limit': limit, 'write_error': self.write_error}


def verify(path):
    """Validate typed JSON and every complete turn checkpoint."""
    digest = '0' * 64
    count = 0
    checkpoints = 0
    with Path(path).open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            row = json.loads(line)
            if row.get('kind') == 'turn_checkpoint':
                if row.get('count_before') != count or row.get('sha256_before') != digest:
                    raise ValueError(f'broken checkpoint at line {number}')
                checkpoints += 1
            payload = line.rstrip('\n')
            digest = hashlib.sha256((digest + payload).encode('utf-8')).hexdigest()
            count += 1
    return {'rows': count, 'checkpoints': checkpoints, 'sha256': digest}


def emit(region, **kwargs):
    """Write at the authoritative mutation point, if tracing is enabled."""
    clock = getattr(region, '_collective_trace_clock', None)
    recorder = getattr(region, '_run_trace', None)
    if clock is not None and recorder is not None:
        return recorder.emit(clock, **kwargs)
    return None
