"""Read-only, bounded metric-level evidence assembled from a published trace."""
from collections import deque
import hashlib
import json
import math

from metric_catalog import METRICS
from trace_index import TraceIndex
from trace_explanation import describe

VERSION = '1'
MAX_EVENTS = 64
MAX_ROOTS = 48
MAX_DEPTH = 4


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def compact(value, depth=0):
    """Bound individual payloads as well as the number of traversed events."""
    if depth > 5:
        return '[nested data omitted]'
    if isinstance(value, dict):
        out = {str(k)[:100]: compact(v, depth + 1) for k, v in list(value.items())[:24]}
        if len(value) > 24:
            out['_omitted_fields'] = len(value) - 24
        return out
    if isinstance(value, (tuple, list)):
        out = [compact(v, depth + 1) for v in value[:16]]
        if len(value) > 16:
            out.append({'omitted_items': len(value) - 16})
        return out
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def input_summary(inputs):
    summarized = compact(inputs)
    if len(json.dumps(summarized)) <= 1800:
        return summarized
    # Large account books and operation lists retain scalar facts and field
    # shapes; linked events carry the bounded source detail. Never ship a whole
    # treasury book merely because it was nested in one recorded calculation.
    return {str(key)[:100]: compact(value) if not isinstance(value, (dict, list, tuple))
            else {'omitted_container': type(value).__name__, 'count': len(value)}
            for key, value in list(inputs.items())[:24]}


def build_packet(capture, stage=lambda value: None):
    selection = capture['selection']
    index = TraceIndex(capture['trace_path'])
    boundary = capture['boundary']
    filters = dict(turn=selection['turn'], subject=selection['subject'],
                   metric_id=selection['metric_id'], boundary=boundary)
    stage('collecting_evidence')
    result = index.query(**filters, limit=MAX_ROOTS)
    roots = result['events']
    if not roots:
        raise ValueError('No recorded evidence for this stat and selection. Use the recorded-evidence view.')
    gaps = []
    if result['total'] > len(roots):
        gaps.append('Metric records exceed the request limit; explanation is partial.')
    # Snapshots define a turn boundary. A random calculation is not a substitute.
    snapshot_page = index.query(**filters, kind='metric_snapshot', limit=1)
    snapshot_count = snapshot_page['total']
    snapshots = (index.query(**filters, kind='metric_snapshot', limit=64)['events'] if snapshot_count else [])
    epoch = selection.get('epoch')
    if epoch is not None:
        snapshots = [row for row in snapshots if row.get('epoch', 0) == epoch]
    # The first turn snapshot is the completed tick sample; later snapshots can
    # describe commands that occurred between ticks. Inspectors may name an epoch.
    selected = snapshots[0] if snapshots else None
    if selected and selected['event_id'] not in {r['event_id'] for r in roots}:
        roots = roots[:-1] + [selected] if len(roots) >= MAX_ROOTS else roots + [selected]
    if snapshot_count > 64:
        gaps.append('Snapshot boundary list was truncated; inspect exact epochs for additional command samples.')
    if epoch is not None and snapshot_count and not snapshots:
        raise ValueError('No metric snapshot was recorded at the requested epoch.')
    if not selected:
        # Closures have explicitly recorded opening/closing semantics.
        closures = [row for row in roots if row.get('kind') in
                    ('price_bridge', 'treasury_account_closure')]
        selected = closures[-1] if closures else None
    if not selected:
        # National chart aggregations are observations of the plotted raw
        # series, not necessarily stock snapshots with an opening field.
        for kind in ('nation_chart_history_aggregate', 'national_aggregate'):
            aggregate_page = index.query(**filters, kind=kind, limit=1)
            if aggregate_page['total']:
                selected = index.query(**filters, kind=kind,
                    offset=aggregate_page['total'] - 1, limit=1)['events'][0]
                break
        if selected and selected['event_id'] not in {r['event_id'] for r in roots}:
            roots = roots[:-1] + [selected] if len(roots) >= MAX_ROOTS else roots + [selected]
    before = selected.get('value_before') if selected else None
    after = selected.get('value_after') if selected else None
    if selected and before is None and selected.get('kind') in ('nation_chart_history_aggregate', 'national_aggregate'):
        previous_filters = {**filters, 'turn': selection['turn'] - 1, 'kind': selected['kind']}
        page = index.query(**previous_filters, limit=1)
        if page['total']:
            previous = index.query(**previous_filters, offset=page['total'] - 1, limit=1)['events'][0]
            if previous.get('unit') == selected.get('unit'):
                before = previous.get('value_after')
                roots = roots + [previous]
                gaps.append('Opening value is the preceding turn aggregate; changing membership or coverage may contribute to the delta.')
    if selected is None:
        gaps.append('No authoritative turn opening/closing record; individual events do not establish the turn delta.')
    elif snapshot_count > 1:
        gaps.append('Multiple turn/command samples exist. The first tick sample is used unless an inspector explicitly selects an epoch.')
    if not number(before):
        gaps.append('Opening sample unavailable; no numeric delta can be established.')
    delta = after - before if number(before) and number(after) else None
    def beyond_selection(row):
        return bool(selected and row.get('turn') == selected.get('turn')
                    and int(row['event_id'].rsplit(':', 1)[-1]) > int(selected['event_id'].rsplit(':', 1)[-1]))
    roots = [row for row in roots if not beyond_selection(row)]
    # Collect full arithmetic totals before compacting individual inputs. Rank
    # linked regions by their contribution rather than territorial list order.
    national_summaries = []
    prioritized = {}
    from national_contributions import for_packet
    for row in roots:
        summary = (row.get('inputs') or {}).get('national_contributions')
        if summary and row.get('subject', {}).get('type') == 'nation':
            if row.get('turn') != selection['turn']:
                continue
            if selected and row.get('epoch', 0) != selected.get('epoch', 0):
                continue
            if len(national_summaries) >= 4:
                gaps.append('Additional national series summaries omitted from this bounded packet; inspect the aggregate records.')
                continue
            bounded = for_packet(summary)
            national_summaries.append({'event_id': row['event_id'], **bounded})
            prioritized[row['event_id']] = list(dict.fromkeys(
                source for region in bounded['regions'] for source in
                (region.get('source_event_id'), region.get('opening_source_event_id')) if source))
    found = {row['event_id']: row for row in roots}
    queue = deque((row, 0) for row in roots)
    missing = set()
    while queue:
        row, depth = queue.popleft()
        all_causes = list(dict.fromkeys(prioritized.get(row['event_id'], []) + list(row.get('cause_event_ids') or ())))
        if len(all_causes) > 24:
            gaps.append('A source list exceeds the request limit; upstream provenance is partial.')
        for ident in all_causes[:24]:
            if ident in found or ident in missing:
                continue
            if depth >= MAX_DEPTH or len(found) >= MAX_EVENTS:
                gaps.append('Upstream traversal limit reached; provenance is incomplete.')
                continue
            rows = index.query(event_id=ident, boundary=boundary, limit=1)['events']
            source = rows[0] if rows else None
            if source is None or source.get('turn', 0) > selection['turn'] or beyond_selection(source):
                missing.add(ident)
                gaps.append('Missing or later source: ' + ident)
                continue
            found[ident] = source
            queue.append((source, depth + 1))
    evidence = []
    for row in found.values():
        explanation = describe(row, found.get)
        evidence.append({'event_id': row['event_id'], 'turn': row.get('turn'),
                         'kind': row.get('kind'), 'metric_id': row.get('metric_id'),
                         'subject': row.get('subject'), 'before': row.get('value_before'),
                         'after': row.get('value_after'), 'unit': row.get('unit'),
                         'status': explanation['status'], 'issues': compact(explanation['issues']),
                         'issue_count': len(explanation['issues']),
                         'notes': explanation['notes'], 'formula_id': row.get('formula_id'),
                         'inputs': input_summary(row.get('inputs') or {}),
                         'cause_event_ids': (row.get('cause_event_ids') or [])[:24],
                         'omitted_cause_count': max(0, len(row.get('cause_event_ids') or []) - 24)})
    if any(e['status'] == 'evidence_gap' for e in evidence):
        gaps.append('Some recorded causes have missing or inconsistent evidence; do not infer their missing causes.')
    gaps.append('Bounded inputs may omit detail; full evidence remains available in the trace inspector.')
    if selection.get('display'):
        gaps.append('The selected chart may transform/window raw values. The header below describes raw recorded turn values; do not equate these with the plotted delta.')
    if selection['subject']['type'] != 'nation':
        gaps.append('Geographic context uses the current owner at request time; historical territorial ownership is not established by that context alone.')
    definition = METRICS.get(selection['metric_id'], ('unknown', '', 'Definition not catalogued; do not guess.'))
    packet = {'version': VERSION, 'selection': selection, 'scenario': capture.get('scenario'),
              'nation': capture.get('nation'), 'era': capture.get('era'),
              'definition': definition, 'values': {'before': before, 'after': after,
              'delta': delta, 'percent': 100 * delta / abs(before)
              if delta is not None and before != 0 else None,
              'unit': selected.get('unit', definition[1]) if selected else definition[1],
              'epoch': selected.get('epoch') if selected else None},
              'root_event_ids': [row['event_id'] for row in roots],
              'evidence': evidence, 'limitations': list(dict.fromkeys(gaps)),
              'actions': capture['actions'], 'catalog_coverage': capture['catalog_coverage'],
              'national_contributions': national_summaries}
    packet['action_context_turn'] = capture.get('action_context_turn')
    if len(json.dumps(packet)) > 100000:
        packet['limitations'].append('Large evidence packet: nested inputs and issue details were further summarized. Inspect original sources for the full records.')
        for item in evidence:
            item['issues'] = item['issues'][:3]
            item['inputs'] = {key: value for key, value in item['inputs'].items()
                              if not isinstance(value, (dict, list))}
    if len(json.dumps(packet)) > 120000:
        raise ValueError('Evidence packet exceeds the bounded request size. Inspect individual trace records.')
    packet['selection_id'] = digest(packet)
    return packet
