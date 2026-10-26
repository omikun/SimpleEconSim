"""Strict output contract plus application checks for references and evidence levels."""
import re

VERSION = '1'


def obj(fields):
    return {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}


S = {'type': 'string'}
STRINGS = {'type': 'array', 'items': S}
CLAIM = obj({'text': S, 'evidence_ids': STRINGS,
             'level': {'type': 'string', 'enum': ['observation', 'recorded_decision',
                        'verified_formula', 'verified_chain', 'evidence_gap', 'forecast']}})
FUTURE = obj({'capability': S, 'title': S, 'unmet_need': S, 'gap_reason': S,
              'proposal': S, 'tradeoffs': S, 'acceptance_criteria': STRINGS,
              'evidence_ids': STRINGS, 'source_ids': STRINGS})
SCHEMA = obj({'selection_id': S, 'claims': {'type': 'array', 'items': CLAIM},
              'historical_parallel': {'anyOf': [obj({'entry_id': S, 'comparison': S,
                                                    'difference': S}), {'type': 'null'}]},
              'suggested_actions': {'type': 'array', 'items': obj({'action_id': S, 'rationale': S})},
              'future_mechanics': {'type': 'array', 'items': FUTURE}})


def _shape(value, schema):
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try:
                _shape(value, option)
                return
            except ValueError:
                pass
        raise ValueError('Invalid nullable result.')
    kind = schema['type']
    if kind == 'null':
        if value is not None:
            raise ValueError('Expected null.')
    elif kind == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['properties']):
            raise ValueError('Unexpected output fields.')
        for key, prop in schema['properties'].items():
            _shape(value[key], prop)
    elif kind == 'array':
        if not isinstance(value, list) or len(value) > 12:
            raise ValueError('Too many output items.')
        for item in value:
            _shape(item, schema['items'])
    elif kind == 'string':
        if not isinstance(value, str) or len(value) > 1800 or not value.strip():
            raise ValueError('Invalid output text.')
        if 'enum' in schema and value not in schema['enum']:
            raise ValueError('Unknown evidence level.')


def validate(result, packet):
    _shape(result, SCHEMA)
    if result['selection_id'] != packet['selection_id']:
        raise ValueError('Response belongs to another selection.')
    if not 1 <= len(result['claims']) <= 4 or len(result['future_mechanics']) > 1 or len(result['suggested_actions']) > 2:
        raise ValueError('Explanation exceeds the response limits.')
    events = {e['event_id']: e for e in packet['evidence']}
    actions = {a['id']: a for a in packet['actions']}
    histories = {h['id']: h for h in packet['historical_candidates']}
    sources = {s['id'] for h in histories.values() for s in h['sources']}
    for claim in result['claims']:
        if not claim['evidence_ids'] or any(e not in events for e in claim['evidence_ids']):
            raise ValueError('Narrative claim has no valid recorded source.')
        for ident in claim['evidence_ids']:
            status = events[ident]['status']
            if claim['level'] not in ('observation', 'evidence_gap') and claim['level'] != status:
                raise ValueError('Narrative upgrades the recorded evidence level.')
    historical = result['historical_parallel']
    if historical and historical['entry_id'] not in histories:
        raise ValueError('Unknown historical source.')
    for action in result['suggested_actions']:
        if action['action_id'] not in actions:
            raise ValueError('Unknown playable action.')
    for proposal in result['future_mechanics']:
        if not re.fullmatch(r'[a-z][a-z0-9_]{2,70}', proposal['capability']):
            raise ValueError('Invalid proposed capability.')
        if any(proposal['capability'] in a['capabilities'] or proposal['capability'] == a['id']
               or proposal['title'].casefold() == a['label'].casefold() for a in actions.values()):
            raise ValueError('Proposed capability already exists; blocked actions are not new mechanics.')
        if not proposal['evidence_ids'] or any(e not in events for e in proposal['evidence_ids']):
            raise ValueError('Future proposal requires recorded provenance.')
        if any(s not in sources for s in proposal['source_ids']) or not proposal['acceptance_criteria']:
            raise ValueError('Invalid proposal sources or acceptance criteria.')
    # Model prose must not introduce unsupported figures. Authoritative numbers,
    # years and costs are rendered from the packet and reviewed library instead.
    texts = [c['text'] for c in result['claims']]
    texts += [a['rationale'] for a in result['suggested_actions']]
    if historical:
        texts += [historical['comparison'], historical['difference']]
    for text in texts:
        if re.search(r'\d|https?://', text):
            raise ValueError('Use qualitative prose; numeric values and URLs are attached from trusted records.')
    return result
