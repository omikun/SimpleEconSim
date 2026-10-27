"""Versioned, lossless event batches and explicit unchanged-observation coverage.

Coverage carries a checked baseline value AND this observation's current source.
It never infers a value from a missing event or reuses a previous turn's source.
Each batch is self-contained, so seeking needs no unbounded history replay.
"""
import json
import math

CONTEXT = ('schema_version', 'run_id', 'branch_id', 'turn', 'epoch', 'phase',
           'kind', 'record_class', 'confidence', 'explanation_status')
COVERAGE_RULE = 'checked_unchanged_snapshot.v1'
SNAPSHOT_KEYS = frozenset((*CONTEXT, 'event_id', 'sequence', 'subject', 'metric_id',
                          'unit', 'value_before', 'value_after', 'delta',
                          'inputs', 'cause_event_ids'))
SNAPSHOT_REDUNDANT = frozenset(('kind', 'record_class', 'value_before', 'delta', 'inputs',
                              'cause_event_ids', 'confidence', 'explanation_status'))


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
    for row in rows:
        coverage = _coverage(row) if sparse else None
        rule = COVERAGE_RULE if coverage is not None else None
        # A batch normally has only a few row shapes. Compute its column list
        # once, rather than filtering/sorting every observation's fields.
        shape = (rule, tuple(row))
        index = schema_ids.get(shape)
        if index is None:
            keys = tuple(key for key in row if key not in excluded
                         and (coverage is None or key not in SNAPSHOT_REDUNDANT))
            if coverage is not None: keys += ('@source',)
            index = len(schemas); schema_ids[shape] = index
            schemas.append({'rule': rule, 'keys': keys})
        else:
            keys = schemas[index]['keys']
        if coverage is None:
            values = [row[key] for key in keys]
        else:
            values = [row[key] for key in keys[:-1]] + [coverage[0]]
        encoded.append([index, values])
        covered += coverage is not None
    return {'version': 1, 'header': common, 'sequence_base': start if implicit else None,
            'schemas': schemas, 'rows': encoded, 'covered_observations': covered}


def unpack(packet):
    if packet.get('version') != 1: raise ValueError('unsupported packed event version')
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
            source = row.pop('@source')
            value = row['value_after']
            if ((source is not None and type(source) is not str) or type(value) not in (str, int, float, bool)
                    or (type(value) is float and not math.isfinite(value))):
                raise ValueError('invalid checked observation baseline/source')
            row.update(kind='metric_snapshot', record_class='observation', value_before=value,
                       inputs={'source_event_id': source}, cause_event_ids=[source] if source else [],
                       confidence='exact' if source else 'unknown',
                       explanation_status='calculation_recorded' if source else 'source_missing')
            if isinstance(value, (int, float)): row['delta'] = value - value
            covered += 1
        elif schema['rule'] is not None:
            raise ValueError('unsupported coverage rule')
        yield row
    if covered != packet['covered_observations']: raise ValueError('incorrect coverage count')
