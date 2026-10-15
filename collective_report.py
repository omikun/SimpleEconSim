"""Export a reproducible, ordered explanation of collective action in a run.

Usage:
  venv/bin/python collective_report.py --scenario labor-frontier-rivalry \
      --seed 612 --turns 20 --output tmp/collective_run.jsonl

The first JSON line records the run configuration. Following lines keep
observed transfers, votes, output, payroll, settlement reviews, and relevant
scenario market/policy events with their source and turn. Forecasts remain
marked as forecasts; the report never converts exposure into booked losses.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def trace_rows(world):
    """Return existing ledger rows in deterministic turn and phase order."""
    rows = []
    for tile_index, region in enumerate(world.get('tiles', ())):
        for ordinal, row in enumerate(getattr(region, 'collective_log', ())):
            kind = row.get('kind')
            phase = (1 if kind in ('organization_check', 'strike_vote', 'strike_started', 'participation',
                                   'participant_left', 'support_transfer')
                     or (kind == 'strike_ended' and
                         row.get('facts', {}).get('reason') != 'agreement') else
                     2 if kind == 'production_observed' else
                     3 if kind in ('payroll_observed', 'payroll_breach', 'settlement_review') else
                     4 if kind == 'needs_observed' else
                     5 if kind in ('owner_decision', 'offer_rejected',
                                   'agreement_signed', 'strike_ended') else
                     7 if kind == 'public_support_transfer' else 6)
            rows.append((int(row['turn']), phase, tile_index, ordinal,
                         {'source': 'collective', **row}))
        for ordinal, row in enumerate(getattr(region, 'labor_decision_log', ())):
            rows.append((int(row.get('turn', 0)), 0, tile_index, ordinal,
                         {'source': 'labor_offer', 'region': region.name, **row}))
    for nation_index, nation in enumerate(world.get('nations', ())):
        seen_sequences = set()
        for ordinal, row in enumerate(getattr(nation, 'regime_log', ())):
            if row.get('kind') not in ('armed_strikebreaking', 'ten_hour_act_concession',
                                       'factory_safety_concession'):
                continue
            sequence = row.get('sequence')
            if sequence is not None and sequence in seen_sequences:
                continue
            if sequence is not None:
                seen_sequences.add(sequence)
            rows.append((int(row.get('turn', 0)), 5, nation_index, ordinal,
                         {'source': 'national_labor_policy', **row}))
    state = world.get('scenario_state', {})
    for field, phase, source in (('timeline', 7, 'scenario_timeline'),
                                 ('market_sales', 6, 'paid_market_sale'),
                                 ('cotton_purchases', 6, 'paid_input_purchase')):
        for ordinal, row in enumerate(state.get(field, ())):
            rows.append((int(row.get('turn', 0)), phase, 0, ordinal,
                         {'source': source, **row}))
    # The shared sequence is the exact append order of newly stamped ledgers.
    # Older saved rows use the documented approximate phase order.
    rows.sort(key=lambda entry: (entry[0], 0, int(entry[4]['sequence']), entry[2])
              if entry[4].get('sequence') is not None
              else (entry[0], 1, entry[1], entry[2], entry[3]))
    return [row for _, _, _, _, row in rows]


def export_trace(world, path, *, seed=None, scenario=None):
    """Write existing run evidence as JSON Lines; return event count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = trace_rows(world)
    with path.open('w', encoding='utf-8') as stream:
        stream.write(_trace_text(world, rows, seed=seed, scenario=scenario))
    return len(rows)


def _trace_text(world, rows, *, seed=None, scenario=None):
    header = {'source': 'run', 'schema': 1, 'seed': seed,
              'scenario': scenario or world.get('scenario_id'),
              'final_turn': int(world.get('turn', 0)), 'event_count': len(rows),
              'ordered_rows': sum('sequence' in row for row in rows)}
    return ''.join(json.dumps(row, sort_keys=True, default=str) + '\n'
                   for row in (header, *rows))


def current_trace_text(world, *, seed=None, scenario=None):
    """Return the live world's full trace for an HTTP download."""
    return _trace_text(world, trace_rows(world), seed=seed, scenario=scenario)


def main():
    parser = argparse.ArgumentParser(description='Run and export collective-action evidence')
    parser.add_argument('--scenario', choices=('labor-frontier-rivalry', 'default'),
                        default='labor-frontier-rivalry')
    parser.add_argument('--seed', type=int, default=612)
    parser.add_argument('--turns', type=int, default=20)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.turns < 0:
        parser.error('--turns must be nonnegative')
    if args.scenario == 'labor-frontier-rivalry':
        from scenario_labor_frontier_rivalry import create_world, step_world
        world = create_world(seed=args.seed)
        for _ in range(args.turns):
            step_world(world)
    else:
        from sim_server.sim_server import SimServer
        server = SimServer(seed=args.seed)
        for _ in range(args.turns):
            server.step()
        world = server.get_world_dict()
    count = export_trace(world, args.output, seed=args.seed,
                         scenario=args.scenario)
    print(f'Wrote {count} evidence rows through turn {world.get("turn", 0)} to {args.output}')


if __name__ == '__main__':
    main()
