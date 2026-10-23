"""Inspect or decode compact causal records from a run.

Example: venv/bin/python trace_report.py --run tmp/traces/RUN.ctr \
    --turn 12 --entity tile:Delta --metric goods.price
"""

import argparse
import json
from pathlib import Path
import sys
import sqlite3
import tempfile
from contextlib import closing

from trace_codec import decoded_size, iter_payloads


def iter_report(path, *, turn=None, entity=None, metric=None, kind=None,
           good=None, person_id=None, event_id=None):
    subject_type, _, subject_id = entity.partition(':') if entity else (None, None, None)
    if entity and (not subject_type or not subject_id):
        raise ValueError('entity must be type:id')
    for line_number, payload in enumerate(iter_payloads(path), start=1):
        try:
            row = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f'invalid JSON at record {line_number}') from exc
        if row.get('record_class') == 'metadata':
            continue
        if event_id is not None and row.get('event_id') != event_id:
            continue
        if turn is not None and row.get('turn') != turn:
            continue
        if metric is not None and row.get('metric_id') != metric:
            continue
        if kind is not None and row.get('kind') != kind:
            continue
        subject = row.get('subject', {})
        if person_id is not None:
            inputs = row.get('inputs', {}) or {}
            identifiers = [subject.get('id'), subject.get('agent_id')]
            identifiers.extend(inputs.get(key) for key in (
                'agent_id', 'person_id', 'worker_id', 'founder_id', 'new_agent_id'))
            if str(person_id) not in {str(value) for value in identifiers if value is not None}:
                continue
        if entity and (subject.get('type'), subject.get('id')) != (subject_type, subject_id):
            continue
        if good is not None and subject.get('good') != good:
            continue
        yield row


def report(path, **filters):
    """Materialized helper for callers needing comparison or random access."""
    return list(iter_report(path, **filters))


def render(row):
    subject = row.get('subject', {})
    entity = f"{subject.get('type', '?')}:{subject.get('id', '?')}"
    good = f"/{subject['good']}" if subject.get('good') else ''
    old = row.get('value_before', '—')
    new = row.get('value_after', '—')
    heading = (f"T{row.get('turn', '?')} #{row.get('sequence', '?')} "
               f"{entity}{good} {row.get('kind', '?')} "
               f"{row.get('metric_id', '')} {old} → {new} {row.get('unit', '')}")
    lines = [heading]
    if row.get('formula_id'):
        lines.append(f"  formula: {row['formula_id']}")
    if row.get('inputs'):
        lines.append('  inputs: ' + json.dumps(row['inputs'], sort_keys=True, allow_nan=False))
    if row.get('constraints'):
        lines.append('  constraints: ' + json.dumps(row['constraints'], sort_keys=True,
                                                      allow_nan=False))
    if row.get('explanation_status') == 'source_missing':
        lines.append('  Explanation unavailable: calculation source not recorded.')
    return '\n'.join(lines)


def diff_snapshots(left_rows, right_rows):
    """Compare observed values in two runs; this does not establish causation."""
    def keyed(rows):
        return {(row.get('turn'), json.dumps(row.get('subject'), sort_keys=True),
                 row.get('metric_id')): row
                for row in rows if row.get('kind') == 'metric_snapshot'}
    left = keyed(left_rows)
    right = keyed(right_rows)
    changes = []
    for key in sorted(left.keys() & right.keys()):
        a = left[key].get('value_after')
        b = right[key].get('value_after')
        if a != b:
            changes.append({'turn': key[0], 'subject': json.loads(key[1]),
                            'metric_id': key[2], 'left': a, 'right': b,
                            'difference': b - a if isinstance(a, (int, float))
                            and isinstance(b, (int, float)) else None})
    return changes


def iter_snapshot_differences(left_rows, right_rows):
    """Bounded-memory equivalent of diff_snapshots for CLI run comparisons."""
    with tempfile.TemporaryDirectory() as directory:
        with closing(sqlite3.connect(str(Path(directory)/'comparison.sqlite'))) as database:
            database.execute('PRAGMA cache_size=-2048')
            database.execute('CREATE TABLE snapshots(side TEXT,turn INTEGER,subject TEXT,metric TEXT,value TEXT,PRIMARY KEY(side,turn,subject,metric))')
            for side,rows in (('left',left_rows),('right',right_rows)):
                for row in rows:
                    if row.get('kind')!='metric_snapshot':continue
                    database.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?)',
                                     (side,row.get('turn'),json.dumps(row.get('subject'),sort_keys=True),
                                      row.get('metric_id'),json.dumps(row.get('value_after'),allow_nan=False)))
            query = """SELECT a.turn,a.subject,a.metric,a.value,b.value
                       FROM snapshots a JOIN snapshots b ON a.turn=b.turn AND a.subject=b.subject AND a.metric=b.metric
                       WHERE a.side='left' AND b.side='right' ORDER BY a.turn,a.subject,a.metric"""
            for turn,subject,metric,left,right in database.execute(query):
                a,b=json.loads(left),json.loads(right)
                if a!=b:
                    yield {'turn':turn,'subject':json.loads(subject),'metric_id':metric,
                           'left':a,'right':b,'difference':b-a if isinstance(a,(int,float)) and isinstance(b,(int,float)) else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--turn', type=int)
    parser.add_argument('--entity')
    parser.add_argument('--metric')
    parser.add_argument('--kind', help='filter an event kind, including metricless records')
    parser.add_argument('--event-id', help='show one exact event and its inputs')
    parser.add_argument('--good', help='filter a named good, such as food or cloth')
    parser.add_argument('--person-id', type=int,
                        help='show records naming this person as subject or actor')
    parser.add_argument('--decode-jsonl', metavar='OUTPUT',
                        help='losslessly decode the whole run to OUTPUT, or - for stdout')
    parser.add_argument('--storage-stats', action='store_true',
                        help='print stored size, decoded JSONL size and compression ratio')
    parser.add_argument('--verify', action='store_true', help='verify turn checkpoints')
    parser.add_argument('--compare-run', type=Path,
                        help='compare matched snapshots in another run (in-game counterfactual)')
    args = parser.parse_args()
    if args.storage_stats:
        stored = args.run.stat().st_size
        decoded = decoded_size(args.run)
        print(f'Stored: {stored} bytes; decoded JSONL: {decoded} bytes; '
              f'ratio: {stored / decoded:.3f}' if decoded else
              f'Stored: {stored} bytes; decoded JSONL: 0 bytes')
        return
    if args.decode_jsonl:
        if args.decode_jsonl != '-' and Path(args.decode_jsonl).resolve() == args.run.resolve():
            parser.error('decode output must differ from the input trace')
        output = (sys.stdout if args.decode_jsonl == '-'
                  else Path(args.decode_jsonl).open('w', encoding='utf-8'))
        try:
            for payload in iter_payloads(args.run):
                output.write(payload + '\n')
        finally:
            if output is not sys.stdout:
                output.close()
        return
    if args.verify:
        from run_trace import verify
        check = verify(args.run)
        print(f"Verified {check['rows']} rows and {check['checkpoints']} checkpoints")
    rows = iter_report(args.run, turn=args.turn, entity=args.entity, metric=args.metric,
                  kind=args.kind,
                  good=args.good, person_id=args.person_id,
                  event_id=args.event_id)
    if args.compare_run:
        other = iter_report(args.compare_run, turn=args.turn,
                       entity=args.entity, metric=args.metric, kind=args.kind,
                       good=args.good,
                       person_id=args.person_id, event_id=args.event_id)
        print('In-game run comparison; differing values alone do not prove a cause.')
        for change in iter_snapshot_differences(rows, other):
            print(json.dumps(change, sort_keys=True, allow_nan=False))
    else:
        for row in rows:
            print(render(row))


if __name__ == '__main__':
    main()
