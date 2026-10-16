"""Count explained and unexplained metric changes in a run trace."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from trace_codec import iter_payloads


def coverage(path):
    counts = defaultdict(lambda: {'snapshots': 0, 'changed': 0,
                                  'explained': 0, 'unexplained': 0})
    treasury_reconciliations = {'turns': 0, 'fully_attributed': 0,
                                'unattributed_absolute_total': 0.0}
    for payload in iter_payloads(path):
        row = json.loads(payload)
        if row.get('kind') == 'treasury_reconciliation':
            treasury_reconciliations['turns'] += 1
            residual = row.get('inputs', {}).get('unattributed_residual', 0.0)
            treasury_reconciliations['unattributed_absolute_total'] += abs(residual)
            if abs(residual) < 1e-8:
                treasury_reconciliations['fully_attributed'] += 1
        if row.get('kind') != 'metric_snapshot':
            continue
        metric_id = row['metric_id']
        entry = counts[metric_id]
        entry['snapshots'] += 1
        if 'value_before' in row and row.get('value_before') != row.get('value_after'):
            entry['changed'] += 1
            if row.get('explanation_status') == 'calculation_recorded':
                entry['explained'] += 1
            else:
                entry['unexplained'] += 1
    result = dict(sorted(counts.items()))
    result['_treasury_reconciliation'] = treasury_reconciliations
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(coverage(args.run), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
