"""Count explained and unexplained metric changes in a run trace."""

import argparse
from collections import defaultdict
import json
from pathlib import Path


def coverage(path):
    counts = defaultdict(lambda: {'snapshots': 0, 'changed': 0,
                                  'explained': 0, 'unexplained': 0})
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
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
    return dict(sorted(counts.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(coverage(args.run), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
