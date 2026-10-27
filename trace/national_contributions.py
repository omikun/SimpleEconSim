"""Exact regional arithmetic and gross fiscal totals, never guessed causation."""
import math
import os


def fiscal_totals(flows):
    if os.environ.get('COC_TRACE_NATIONAL_SUMMARIES', '1') == '0': return {}
    by_kind = {}
    for flow in flows:
        amount = flow['amount']
        bucket = by_kind.setdefault(flow['kind'], {'inflows': 0.0, 'outflows': 0.0, 'count': 0})
        bucket['inflows'] += max(0.0, amount)
        bucket['outflows'] += max(0.0, -amount)
        bucket['count'] += 1
    inflows = sum(row['inflows'] for row in by_kind.values())
    outflows = sum(row['outflows'] for row in by_kind.values())
    return {'gross_inflows': inflows, 'gross_outflows': outflows,
            'net_recorded_flow': inflows-outflows, 'flow_count': len(flows), 'gross_flows_by_kind': by_kind,
            'flow_basis': 'recorded signed national treasury flows; gaps remain in unattributed_residual'}


def summarize(prior, current):
    """Decompose sums/means including membership, missing coverage and weights.

    This attributes the arithmetic delta to regions. The linked region events
    establish mechanisms; a reconciled sum alone does not establish causation.
    """
    result = {'version': 1, 'basis': 'regional_arithmetic; upstream mechanisms require linked evidence',
              'baseline_available': prior is not None, 'opening': prior['value'] if prior else None,
              'closing': current['value'], 'reducer': current['reducer'],
              'unit': current['unit'], 'regions': []}
    result['observed_coverage_count'] = current.get('coverage_count')
    result['opening_observed_coverage_count'] = prior.get('coverage_count') if prior else None
    result['missing_value_policy'] = current.get('missing_value_policy')
    if prior is None:
        result.update(delta=None, gross_positive_contributions=None, gross_negative_contributions=None,
                      residual=None, reconciled=False, limitation='opening aggregate unavailable')
        return result
    before_rows = {row['tile_id']: row for row in prior['rows']}
    after_rows = {row['tile_id']: row for row in current['rows']}
    old_members, new_members = set(prior['members']), set(current['members'])
    old_denom = sum(row['value'] is not None for row in before_rows.values()) if prior['reducer'] == 'mean' else 1
    new_denom = sum(row['value'] is not None for row in after_rows.values()) if current['reducer'] == 'mean' else 1
    positive = negative = 0.0; unchanged = 0
    for tile in sorted(set(before_rows) | set(after_rows)):
        old, new = before_rows.get(tile, {}), after_rows.get(tile, {})
        before, after = old.get('value'), new.get('value')
        opening = before / max(1, old_denom) if before is not None else 0.0
        closing = after / max(1, new_denom) if after is not None else 0.0
        delta = closing-opening
        positive += max(0.0, delta); negative += min(0.0, delta)
        changed_membership = (tile in old_members) != (tile in new_members)
        changed_coverage = (before is None) != (after is None)
        if delta == 0 and not changed_membership and not changed_coverage:
            unchanged += 1
            continue
        reason = ('territory_entered' if tile not in old_members else 'territory_departed'
                  if tile not in new_members else 'coverage_entered' if before is None else
                  'coverage_departed' if after is None else 'regional_value_or_weight_change')
        row = {'tile_id': tile, 'before': before, 'after': after, 'contribution_delta': delta,
               'reason': reason, 'source_event_id': new.get('source_event_id'),
               'opening_source_event_id': old.get('source_event_id')}
        if before is not None and after is not None:
            row['regional_value_effect'] = (after-before) / max(1, new_denom)
            row['weight_effect'] = before * (1/max(1, new_denom) - 1/max(1, old_denom))
        result['regions'].append(row)
    delta = current['value']-prior['value']
    residual = delta-(positive+negative)
    comparable = (current['unit'] == prior['unit'] and current['reducer'] == prior['reducer']
                  and current.get('currencies') == prior.get('currencies'))
    result.update(delta=delta, gross_positive_contributions=positive, gross_negative_contributions=negative,
                  residual=residual, reconciled=math.isclose(residual, 0.0, rel_tol=1e-10, abs_tol=1e-8),
                  comparable_basis=comparable, opening_denominator=old_denom, closing_denominator=new_denom,
                  unchanged_region_count=unchanged, entered_tiles=sorted(new_members-old_members),
                  departed_tiles=sorted(old_members-new_members))
    if not comparable:
        result['limitation'] = 'unit/reducer/currency composition changed; arithmetic is not a like-for-like economic effect'
    return result


def attach(trace, clock, subject, metric_id, unit, value, inputs, *, series='stock', contribution_rows=None):
    """Attach evidence to existing aggregate records without allocating event IDs."""
    if os.environ.get('COC_TRACE_NATIONAL_SUMMARIES', '1') == '0': return
    from run_trace import _subject_key
    from trace_clock import boundary
    cache = getattr(trace, '_national_contribution_baselines', None)
    if cache is None:
        cache = trace._national_contribution_baselines = {}
    rows = contribution_rows if contribution_rows is not None else inputs.get('member_contributions')
    if rows is None:
        dimensions = {key:value for key,value in subject.items() if key not in ('type','id')}
        rows = [{'tile_id': tile, 'value': value,
                 'source_event_id': (trace.latest_metric_calculation_event_id(metric_id, {'type':'tile','id':tile, **dimensions})
                                     or trace.latest_metric_event_id(metric_id, {'type':'tile','id':tile, **dimensions}))}
                for tile, value in zip(inputs['member_tiles'], inputs['member_values'])]
    current = {'value': value, 'rows': [dict(row) for row in rows], 'members': list(inputs['member_tiles']),
               'reducer': inputs.get('reducer', 'mean' if inputs.get('denominator') is not None else 'sum'),
               'unit': unit, 'currencies': inputs.get('member_currencies'), 'boundary': boundary(clock),
               'coverage_count': inputs.get('coverage_count')}
    current['missing_value_policy'] = inputs.get('missing_recipe_contribution_policy', inputs.get('missing_history_policy'))
    key = (metric_id, _subject_key(subject), series)
    prior = cache.get(key)
    uncovered = False
    if prior:
        old_turn, old_epoch = prior['boundary']
        turn, epoch = current['boundary']
        consecutive = (turn == old_turn and old_epoch <= epoch <= old_epoch+1) or turn == old_turn+1
        if not consecutive:
            prior = None
            uncovered = True
    summary = summarize(prior, current)
    if uncovered:
        summary['limitation'] = 'opening contribution baseline unavailable after an uncovered turn/epoch interval'
    if prior:
        summary['opening_boundary'] = list(prior['boundary'])
    summary['closing_boundary'] = list(current['boundary'])
    inputs['national_contributions'] = summary
    cache[key] = current


def for_packet(summary, limit=12):
    """Full totals survive bounds; show strongest changes from both directions."""
    rows = summary.get('regions', [])
    positive = sorted((row for row in rows if row['contribution_delta'] > 0),
                      key=lambda row: -row['contribution_delta'])
    negative = sorted((row for row in rows if row['contribution_delta'] < 0),
                      key=lambda row: row['contribution_delta'])
    selected = positive[:limit//2] + negative[:limit//2]
    selected_ids = {row['tile_id'] for row in selected}
    remaining = sorted((row for row in rows if row['tile_id'] not in selected_ids),
                       key=lambda row: -abs(row['contribution_delta']))
    selected += remaining[:limit-len(selected)]
    return {**{key: value for key, value in summary.items() if key != 'regions'},
            'regions': selected, 'region_count': len(rows), 'omitted_region_count': len(rows)-len(selected),
            'detail_location': 'full regional ledger in the aggregate trace event'}
