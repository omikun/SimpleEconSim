"""Inspect causal records from a run JSONL file.

Example: venv/bin/python trace_report.py --run tmp/traces/RUN.jsonl \
    --turn 12 --entity tile:Delta --metric goods.price
"""

import argparse
import json
from pathlib import Path


def report(path, *, turn=None, entity=None, metric=None):
    subject_type, _, subject_id = entity.partition(':') if entity else (None, None, None)
    if entity and (not subject_type or not subject_id):
        raise ValueError('entity must be type:id')
    rows = []
    with Path(path).open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'truncated or invalid JSON at line {line_number}') from exc
            if row.get('record_class') == 'metadata':
                continue
            if turn is not None and row.get('turn') != turn:
                continue
            if metric is not None and row.get('metric_id') != metric:
                continue
            subject = row.get('subject', {})
            if entity and (subject.get('type'), subject.get('id')) != (subject_type, subject_id):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--turn', type=int)
    parser.add_argument('--entity')
    parser.add_argument('--metric')
    parser.add_argument('--verify', action='store_true', help='verify turn checkpoints')
    args = parser.parse_args()
    if args.verify:
        from run_trace import verify
        check = verify(args.run)
        print(f"Verified {check['rows']} rows and {check['checkpoints']} checkpoints")
    for row in report(args.run, turn=args.turn, entity=args.entity, metric=args.metric):
        print(render(row))


if __name__ == '__main__':
    main()
