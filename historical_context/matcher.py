"""Data-driven matching of game events to sourced historical moments."""

from __future__ import annotations

import json
from pathlib import Path


CATALOG_DIR = Path(__file__).with_name('catalog')

EVENT_TYPES = {
    'strike_started': ('labor.strike', 'walkout'),
    'owner_decision': ('labor.employer_response', 'employer_decision'),
    'offer_rejected': ('labor.negotiation', 'offer_rejected'),
    'agreement_signed': ('labor.negotiation', 'agreement_signed'),
    'payroll_breach': ('labor.employer_response', 'wage_breach'),
    'strike_ended': ('labor.resolution', 'strike_ended'),
    'settlement_review': ('labor.resolution', 'settlement_review'),
    'support_transfer': ('labor.mutual_aid', 'relief_transfer'),
    'public_support_transfer': ('labor.mutual_aid', 'public_relief'),
}


def load_catalog(directory=None):
    """Load every compact JSON catalog file and validate its top-level shape."""
    root = Path(directory) if directory is not None else CATALOG_DIR
    entries = []
    for path in sorted(root.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or not data.get('id'):
            raise ValueError(f'Invalid historical context catalog: {path}')
        if not isinstance(data.get('moments'), list):
            raise ValueError(f'Catalog has no moments list: {path}')
        for moment in data['moments']:
            if not moment.get('id') or not moment.get('category'):
                raise ValueError(f'Historical moment needs id and category: {path}')
            moment['_case'] = {key: value for key, value in data.items()
                               if key != 'moments'}
            moment['_source_path'] = path.name
            entries.append(moment)
    return entries


def _event_facts(row):
    facts = row.get('facts') or {}
    kind = row.get('kind', '')
    category, action = EVENT_TYPES.get(kind, ('', kind))
    category = facts.get('historical_category', category)
    action = facts.get('historical_action', action)
    tags = set(facts.get('historical_tags', ()))
    # Preserve real recorded outcomes as separate dimensions. Missing values
    # stay unknown; editorial tuning never fabricates casualty counts.
    bloodshed = float(facts.get('bloodshed', 0.0))
    reconciliation = float(facts.get('reconciliation', 0.0))
    return {'category': category, 'action': action, 'tags': tags,
            'bloodshed': bloodshed, 'reconciliation': reconciliation,
            'kind': kind, 'facts': facts}


def select_moment(row, *, settings=None, catalog=None):
    """Return the best eligible sourced moment, or None when no close match exists.

    Settings can require minimum event bloodshed/reconciliation and tune their
    ranking weights independently. These are game selection controls, not
    claims about the historical case's measured severity.
    """
    settings = settings or {}
    event = _event_facts(row)
    if not event['category']:
        return None
    # Levels are editorial 0–4 match descriptors, not casualty counts or
    # historical measurements. Omitted levels remain unranked unless filtered.
    tuning = settings or {}
    candidates = []
    for moment in catalog if catalog is not None else load_catalog():
        match = moment.get('match', {})
        if moment['category'] != event['category']:
            continue
        actions = match.get('actions', ())
        if actions and event['action'] not in actions:
            continue
        required = set(match.get('require_tags', ()))
        if not required.issubset(event['tags']):
            continue
        excluded = set(match.get('exclude_tags', ()))
        if excluded.intersection(event['tags']):
            continue
        signals = moment.get('signals', {})
        eligible = True
        for name in ('bloodshed', 'reconciliation'):
            level = signals.get(name)
            minimum = tuning.get(f'min_{name}')
            maximum = tuning.get(f'max_{name}')
            if minimum is not None and (level is None or level < float(minimum)):
                eligible = False
            if maximum is not None and (level is None or level > float(maximum)):
                eligible = False
        if not eligible:
            continue
        preferred = set(match.get('prefer_tags', ()))
        score = 10 + len(required) * 3 + len(preferred.intersection(event['tags']))
        score += int(moment.get('match', {}).get('specificity', 0))
        for name in ('bloodshed', 'reconciliation'):
            target = tuning.get(f'target_{name}')
            if target is not None and signals.get(name) is not None:
                weight = float(tuning.get(f'{name}_weight', 1.0))
                score -= abs(float(signals[name]) - float(target)) * weight
        candidates.append((score, moment))
    if not candidates:
        return None
    score, selected = max(candidates, key=lambda item: (item[0], item[1]['id']))
    case = selected['_case']
    return {'id': f"{case['id']}:{selected['id']}",
            'case_id': case['id'], 'case_title': case['title'],
            'period': case.get('period', ''), 'place': case.get('place', ''),
            'moment_title': selected.get('title', case['title']),
            'category': selected['category'], 'score': round(score, 3),
            'signals': dict(selected.get('signals', {})),
            'facts': selected.get('facts', ''),
            'interpretation': selected.get('interpretation', ''),
            'difference': selected.get('difference', ''),
            'sources': list(case.get('sources', ())),
            'catalog_file': selected['_source_path']}


def annotate_event(row, *, settings=None, catalog=None):
    """Attach a serializable context card to a collective event, when matched."""
    card = select_moment(row, settings=settings, catalog=catalog)
    game_event = {'kind': row.get('kind'), 'turn': row.get('turn'),
                  'region': row.get('region'), 'firm_name': row.get('firm_name'),
                  'message': row.get('message', '')}
    if card is not None:
        card['game_event'] = game_event
        row['historical_context'] = card
    elif row.get('kind') in EVENT_TYPES:
        category, _action = EVENT_TYPES[row['kind']]
        row['historical_context'] = {
            'id': f"unmatched:{row.get('id', row.get('kind'))}",
            'case_id': None, 'case_title': 'No close historical match',
            'period': '', 'place': '', 'moment_title': category,
            'category': category, 'facts': row.get('message', ''),
            'interpretation': 'The event is recorded, but the catalog has no close sourced example for these circumstances yet.',
            'difference': '', 'sources': [], 'catalog_file': None,
            'game_event': game_event}
    return row
