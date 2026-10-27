"""Versioned, lossless event batches and explicit unchanged-observation coverage.

Coverage carries a checked baseline value AND this observation's current source.
It never infers a value from a missing event or reuses a previous turn's source.
Each batch is self-contained, so seeking needs no unbounded history replay.
"""
import json
import math
from collections import deque

CONTEXT = ('schema_version', 'run_id', 'branch_id', 'turn', 'epoch', 'phase',
           'kind', 'record_class', 'confidence', 'explanation_status')
COVERAGE_RULE = 'checked_unchanged_snapshot.v1'
BASELINE_RULE = 'checked_initial_snapshot.v1'
SNAPSHOT_KEYS = frozenset((*CONTEXT, 'event_id', 'sequence', 'subject', 'metric_id',
                          'unit', 'value_before', 'value_after', 'delta',
                          'inputs', 'cause_event_ids'))
SNAPSHOT_REDUNDANT = frozenset(('kind', 'record_class', 'value_before', 'delta', 'inputs',
                              'cause_event_ids', 'confidence', 'explanation_status'))
PRICE_IDLE_RULE = 'checked_no_price_writes.v1'
GINI_ZERO_RULE = 'checked_wilderness_gini_zero.v1'
GINI_RETAIN_RULE = 'checked_retained_gini.v1'
DISEASE_EMPTY_RULE = 'checked_empty_disease_census.v1'
TAX_EMPTY_RULE = 'checked_empty_tax_distribution.v1'


class SharedEvidence:
    """An internal census captured once, reused within self-contained packets."""
    def __init__(self, value):
        self.value = freeze(value, [0])
        self._captured = None

    def captured(self):
        # The append-side copy is private: even a caller mutating its recent
        # input view cannot change already queued census history.
        if self._captured is None:
            self._captured = SharedEvidence(self.value)
            self._captured._captured = self._captured
        return self._captured


class SharedInputs(dict):
    def __init__(self, evidence, specific):
        if evidence.value.keys() & specific.keys():
            raise ValueError('shared evidence fields cannot be overridden')
        self.evidence = evidence
        self.specific = specific
        super().__init__(evidence.value, **specific)

    def captured(self, budget):
        return SharedInputs(self.evidence.captured(), freeze(self.specific, budget))


class PreparedEvent:
    """A compact observation/certificate; full logical rows materialize on read."""
    def __init__(self, context, rule, fields):
        budget = [0]
        self.stored = {**context, **freeze(fields, budget), '@rule': rule}
        self.size = budget[0] + 512

    def expand(self):
        row = freeze(self.stored, [0])
        expand_rule(row, row.pop('@rule'))
        return row


class RecentEvents(deque):
    """Keep the small public recent-event view compatible without eager expansion."""
    def __iter__(self):
        return (row.expand() if isinstance(row, PreparedEvent) else row for row in super().__iter__())

    def __reversed__(self):
        return (row.expand() if isinstance(row, PreparedEvent) else row for row in super().__reversed__())

    def __getitem__(self, index):
        row = super().__getitem__(index)
        return row.expand() if isinstance(row, PreparedEvent) else row


def expand_rule(row, rule):
    if rule in (COVERAGE_RULE, BASELINE_RULE):
        source = row.pop('@source')
        value = row['value_after']
        if ((source is not None and type(source) is not str) or type(value) not in (str, int, float, bool)
                or (type(value) is float and not math.isfinite(value))):
            raise ValueError('invalid checked observation baseline/source')
        row.update(kind='metric_snapshot', record_class='observation',
                   inputs={'source_event_id': source}, cause_event_ids=[source] if source else [],
                   confidence='exact' if source else 'unknown',
                   explanation_status='calculation_recorded' if source else 'source_missing')
        if rule == COVERAGE_RULE:
            row['value_before'] = value
            if isinstance(value, (int, float)): row['delta'] = value - value
    elif rule == PRICE_IDLE_RULE:
        value = row['value_after']
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('invalid no-write price baseline')
        change = value - value
        row.update(kind='price_bridge', record_class='audit', confidence='exact',
                   value_before=value, delta=change, explanation_status='ordered_writes_reconciled',
                   inputs={'steps': [], 'gaps': [], 'absolute_change': change,
                           'percent_change': 100 * change / value if value != 0 else None}, cause_event_ids=[])
    elif rule in (GINI_ZERO_RULE, GINI_RETAIN_RULE):
        value = row['value_after']; good = row['subject']['good']
        if (type(value) not in (int, float) or not math.isfinite(value)
                or (rule == GINI_ZERO_RULE and value != 0)):
            raise ValueError('invalid checked Gini baseline')
        expected = 0 if rule == GINI_ZERO_RULE else value
        row.update(kind='gini_series_calculation', record_class='calculation', confidence='exact',
                   value_before=value, delta=value-value,
                   formula_id='gini.wilderness_zero.v1' if rule == GINI_ZERO_RULE else 'gini.retain_previous_value.v1',
                   formula_replay={'expected': expected, 'actual': value, 'matches': True},
                   inputs=({'wilderness': True, 'sample_point': 'native_wilderness_history_write',
                            'history_rule': 'wilderness writer stores zero', 'output_good': good}
                           if rule == GINI_ZERO_RULE else
                           {'previous_gini': value, 'sample_point': 'native_local_history_write',
                            'recomputed_this_turn': False, 'refresh_interval_turns': 10,
                            'initial_empty_series': False, 'output_good': good}))
    elif rule == DISEASE_EMPTY_RULE:
        if type(row['value_after']) is not int or row['value_after'] != 0:
            raise ValueError('invalid empty disease census')
        row.update(kind='closing_active_disease_census', record_class='calculation', confidence='exact',
                   formula_id='disease.count_active_cases.v1',
                   formula_replay={'expected':0,'actual':0,'matches':True},
                   inputs={'sample_point':'closing_live_state','case_agent_ids':[], 'disease':row['subject']['disease']})
    elif rule == TAX_EMPTY_RULE:
        value = row['value_after']
        if type(value) is not float or value != 0.0:
            raise ValueError('invalid empty tax distribution')
        row.update(kind='tax_revenue_distribution_calculation',record_class='calculation',confidence='exact',
                   value_before=value,delta=value-value,formula_id='fiscal.tax_distribution.v1',
                   formula_replay={'expected':0.0,'actual':value,'matches':True},
                   inputs={'turn':row.pop('@tax_turn'),'reason':row.pop('@tax_reason'),
                           'tax_tier':row['subject']['tax_tier'],
                           'opening_components':{key:0.0 for key in ('total','municipal','provincial','national')},
                           'receipts':[], 'aggregation_rule':'opening plus receipt allocations; total uses receipt amount'})
    elif rule is not None:
        raise ValueError('unsupported coverage rule')


def _same(left, right):
    return (type(left) is type(right) and left == right
            and (type(left) is not float or math.copysign(1, left) == math.copysign(1, right)))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def freeze(value, budget):
    """Capture mutable inputs now, while validating JSON without serializing it.

    The budget is a conservative buffer estimate, not an on-disk byte count.
    Non-string dictionary keys take the existing JSON normalization path.
    """
    kind = type(value)
    if isinstance(value, SharedInputs):
        return value.captured(budget)
    if kind is str:
        budget[0] += 12 * len(value) + 2
        return value
    if value is None or kind in (bool, int):
        budget[0] += 32
        return value
    if isinstance(value, float):
        if not math.isfinite(value): raise ValueError('Out of range float values are not JSON compliant')
        budget[0] += 32
        return value
    if isinstance(value, dict):
        result = {}
        estimated = 4 * len(value) + 2
        for key, item in value.items():
            if type(key) is not str:
                return freeze(json.loads(canonical(value)), budget)
            estimated += (6 if key.isascii() else 12) * len(key)
            item_type = type(item)
            if item_type is str:
                estimated += (6 if item.isascii() else 12) * len(item) + 2
                result[key] = item
            elif item is None or item_type in (bool, int):
                estimated += 32; result[key] = item
            elif isinstance(item, float):
                if not math.isfinite(item): raise ValueError('Out of range float values are not JSON compliant')
                estimated += 32; result[key] = item
            else:
                result[key] = freeze(item, budget)
        budget[0] += estimated
        return result
    if isinstance(value, (list, tuple)):
        budget[0] += 2 * len(value) + 2
        return [freeze(item, budget) for item in value]
    # Match JSON's supported scalar subclasses; unsupported native objects fail.
    if isinstance(value, (str, int)):
        return freeze(str(value) if isinstance(value, str) else int(value), budget)
    raise TypeError(f'Object of type {kind.__name__} is not JSON serializable')


def _coverage(row):
    if (row.get('kind') != 'metric_snapshot' or row.get('record_class') != 'observation'
            or not SNAPSHOT_KEYS.issuperset(row) or 'value_before' not in row or 'value_after' not in row):
        return None
    before, after = row['value_before'], row['value_after']
    if type(before) not in (str, int, float, bool) or type(before) is not type(after) or before != after:
        return None
    if type(before) is float and math.copysign(1, before) != math.copysign(1, after):
        return None
    inputs = row.get('inputs')
    if type(inputs) is not dict or set(inputs) != {'source_event_id'}: return None
    source = inputs['source_event_id']
    if source is not None and type(source) is not str: return None
    if row.get('cause_event_ids') != ([source] if source else []): return None
    if row.get('confidence') != ('exact' if source else 'unknown'): return None
    if row.get('explanation_status') != ('calculation_recorded' if source else 'source_missing'): return None
    numeric = isinstance(before, (int, float))
    if numeric:
        expected = after - before
        if ('delta' not in row or type(row['delta']) is not type(expected) or row['delta'] != expected
                or (type(expected) is float and math.copysign(1, row['delta']) != math.copysign(1, expected))):
            return None
    elif 'delta' in row:
        return None
    return (source,)


def pack(rows, *, sparse=True):
    prepared_rules = [row.stored['@rule'] if isinstance(row, PreparedEvent) else None for row in rows]
    rows = [row.stored if isinstance(row, PreparedEvent) else row for row in rows]
    common = {}
    for key in CONTEXT:
        if key not in rows[0]: continue
        first = rows[0][key]; value_type = type(first)
        if value_type is float:
            matched = all(key in row and _same(row[key], first) for row in rows)
        else:
            matched = all(key in row and type(row[key]) is value_type and row[key] == first for row in rows)
        if matched: common[key] = first
    start = rows[0].get('sequence')
    implicit = type(start) is int and all(type(row.get('sequence')) is int
        and type(row.get('run_id')) is str and type(row.get('branch_id')) is str
        and row.get('sequence') == start + i
        and row.get('event_id') == row.get('run_id', '') +
        (':' + row['branch_id'] if row.get('branch_id', 'main') != 'main' else '') + ':' + str(start + i)
        for i, row in enumerate(rows))
    excluded = set(common) | ({'sequence', 'event_id'} if implicit else set())
    schemas, schema_ids, encoded = [], {}, []
    covered = 0
    shared, shared_ids = [], {}
    for row, prepared_rule in zip(rows, prepared_rules):
        coverage = _coverage(row) if sparse and prepared_rule is None else None
        rule = prepared_rule or (COVERAGE_RULE if coverage is not None else None)
        shared_input = isinstance(row.get('inputs'), SharedInputs) and '@shared_input' not in row
        if shared_input:
            inputs = row['inputs']; identity = id(inputs.evidence)
            shared_id = shared_ids.get(identity)
            if shared_id is None:
                shared_id = len(shared); shared_ids[identity] = shared_id
                shared.append(inputs.evidence.value)
            row = {**row, 'inputs': inputs.specific, '@shared_input': shared_id}
        # A batch normally has only a few row shapes. Compute its column list
        # once, rather than filtering/sorting every observation's fields.
        shape = (rule, shared_input, tuple(row))
        index = schema_ids.get(shape)
        if index is None:
            keys = tuple(key for key in row if key not in excluded and (key != '@rule' or prepared_rule is None)
                         and (coverage is None or key not in SNAPSHOT_REDUNDANT))
            if coverage is not None: keys += ('@source',)
            index = len(schemas); schema_ids[shape] = index
            schemas.append({'rule': rule, 'keys': keys})
            if shared_input: schemas[-1]['shared_inputs'] = True
        else:
            keys = schemas[index]['keys']
        if coverage is None:
            values = [row[key] for key in keys]
        else:
            values = [row[key] for key in keys[:-1]] + [coverage[0]]
        encoded.append([index, values])
        covered += rule == COVERAGE_RULE
    version = 2 if shared or any(rule not in (None, COVERAGE_RULE) for rule in prepared_rules) else 1
    packet = {'version': version, 'header': common, 'sequence_base': start if implicit else None,
              'schemas': schemas, 'rows': encoded, 'covered_observations': covered}
    if shared: packet['shared_inputs'] = shared
    return packet


def unpack(packet):
    if packet.get('version') not in (1, 2): raise ValueError('unsupported packed event version')
    header, schemas, rows = packet['header'], packet['schemas'], packet['rows']
    if not isinstance(header, dict) or not isinstance(schemas, list) or not isinstance(rows, list) or not rows:
        raise ValueError('invalid packed event structure')
    if len(rows) > 128: raise ValueError('packed logical row limit exceeded')
    if type(packet.get('covered_observations')) is not int or not 0 <= packet['covered_observations'] <= len(rows):
        raise ValueError('invalid coverage count')
    covered = 0
    for i, (schema_id, values) in enumerate(rows):
        if type(schema_id) is not int or not 0 <= schema_id < len(schemas): raise ValueError('invalid packed schema index')
        schema = schemas[schema_id]; keys = schema['keys']
        if (not isinstance(keys, list) or not isinstance(values, list) or not all(type(key) is str for key in keys)
                or len(keys) != len(set(keys)) or len(keys) != len(values) or set(keys) & set(header)):
            raise ValueError('invalid packed schema fields')
        row = {**header, **dict(zip(keys, values))}
        if packet['sequence_base'] is not None:
            if type(packet['sequence_base']) is not int: raise ValueError('invalid sequence base')
            row['sequence'] = packet['sequence_base'] + i
            row['event_id'] = row['run_id'] + (':' + row['branch_id'] if row['branch_id'] != 'main' else '') + ':' + str(row['sequence'])
        if schema['rule'] == COVERAGE_RULE:
            covered += 1
        if schema['rule'] not in (None, COVERAGE_RULE) and packet['version'] != 2:
            raise ValueError('certificate requires packed version 2')
        expand_rule(row, schema['rule'])
        if schema.get('shared_inputs') is True:
            shared_id = row.pop('@shared_input')
            shared = packet.get('shared_inputs', [])
            if (packet['version'] != 2 or type(shared_id) is not int
                    or not 0 <= shared_id < len(shared) or not isinstance(shared[shared_id], dict)
                    or not isinstance(row.get('inputs'), dict) or shared[shared_id].keys() & row['inputs'].keys()):
                raise ValueError('invalid shared evidence reference')
            row['inputs'] = {**shared[shared_id], **row['inputs']}
        yield row
    if covered != packet['covered_observations']: raise ValueError('incorrect coverage count')
