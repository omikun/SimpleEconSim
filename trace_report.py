"""Inspect or decode compact causal records from a run.

Example: venv/bin/python trace_report.py --run tmp/traces/RUN.ctr \
    --turn 12 --entity tile:Delta --metric goods.price
"""

import argparse
import json
from pathlib import Path
import sys

from trace_codec import decoded_size, iter_payloads


def report(path, *, turn=None, entity=None, metric=None, good=None):
    subject_type, _, subject_id = entity.partition(':') if entity else (None, None, None)
    if entity and (not subject_type or not subject_id):
        raise ValueError('entity must be type:id')
    rows = []
    for line_number, payload in enumerate(iter_payloads(path), start=1):
        try:
            row = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f'invalid JSON at record {line_number}') from exc
        if row.get('record_class') == 'metadata':
            continue
        if turn is not None and row.get('turn') != turn:
            continue
        if metric is not None and row.get('metric_id') != metric:
            continue
        subject = row.get('subject', {})
        if entity and (subject.get('type'), subject.get('id')) != (subject_type, subject_id):
            continue
        if good is not None and subject.get('good') != good:
            continue
        rows.append(row)
    return rows


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--turn', type=int)
    parser.add_argument('--entity')
    parser.add_argument('--metric')
    parser.add_argument('--good', help='filter a named good, such as food or cloth')
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
    rows = report(args.run, turn=args.turn, entity=args.entity, metric=args.metric,
                  good=args.good)
    if args.compare_run:
        other = report(args.compare_run, turn=args.turn,
                       entity=args.entity, metric=args.metric, good=args.good)
        print('In-game run comparison; differing values alone do not prove a cause.')
        for change in diff_snapshots(rows, other):
            print(json.dumps(change, sort_keys=True, allow_nan=False))
    else:
        for row in rows:
            print(render(row))


if __name__ == '__main__':
    main()
