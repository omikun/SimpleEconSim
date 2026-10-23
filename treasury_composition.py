"""Timed changes to public accounting boundaries at native ownership setters."""
from functools import wraps
import math


def _book(sources):
    for source in sources:
        for candidate in (source, getattr(source, 'nation', None), getattr(source, 'owner_nation', None)):
            trace = getattr(candidate, '_run_trace', None)
            book = getattr(trace, 'treasury_book', None)
            clock = getattr(candidate, '_collective_trace_clock', None)
            if book is not None and clock is not None:
                return book, clock
    return None, None


def traced_membership_mutation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        book, clock = _book([*args, *kwargs.values()])
        if book is None or getattr(book, '_composition_depth', 0):
            return function(*args, **kwargs)
        book.start_turn(clock.get('turn', 0))
        before = capture(book, clock)
        book._composition_depth = 1
        completed = False
        try:
            result = function(*args, **kwargs)
            completed = True
            return result
        finally:
            book._composition_depth = 0
            after = capture(book, clock)
            if before != after:
                event_id = book.trace.emit(
                    clock, kind='public_account_membership_transition', record_class='outcome',
                    phase=clock.get('phase', 'ownership'),
                    metric_id='finance.treasury_membership',
                    inputs={'source_method': function.__module__ + '.' + function.__qualname__,
                            'before': before, 'after': after, 'mutation_completed': completed,
                            'currency_conversion_applied': False})
                book.transitions.append({'event_id': event_id, 'sequence': clock['next']-1,
                                         'before': before, 'after': after})
    return wrapped


def capture(book, clock):
    result = {}
    for nation in list(book.nations.values()):
        membership = book.membership(nation, clock, basis='membership_boundary')
        accounts = {}
        for ident, metadata in membership.items():
            info = book.accounts[metadata['key']]
            accounts[ident] = {key: value for key, value in metadata.items() if key != 'key'}
            accounts[ident]['balance'] = book.value(info)
        result[nation.name] = {'accounts': accounts,
                              'territory': sorted(tile.name for tile in nation.tiles),
                              'currencies': {tile.name: getattr(tile, 'home_currency', None) for tile in nation.tiles}}
    return result


def replay(inputs, actual):
    """Replay owned intervals and entry/exit balances; never use final exits."""
    close = lambda a,b: math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8)
    initial = inputs['initial_accounts']
    active = set(initial)
    territory = inputs['initial_territory']
    expected = inputs['opening_total']
    valid = (expected is not None and close(expected, sum(initial.values()))
             and all(row['complete'] for row in inputs['required_accounts']))
    expected = expected if expected is not None else 0.0
    for step in inputs['steps']:
        if step['type'] == 'write':
            if step['account_id'] in active:
                expected += step['after'] - step['before']
        else:
            before, after = step['before'], step['after']
            valid = valid and active == set(before['accounts']) and territory == before['territory']
            entered = set(after['accounts']) - active
            departed = active - set(after['accounts'])
            expected += sum(after['accounts'][ident]['balance'] for ident in entered)
            expected -= sum(before['accounts'][ident]['balance'] for ident in departed)
            active, territory = set(after['accounts']), after['territory']
    valid = valid and active == set(inputs['final_account_ids']) and territory == inputs['final_territory']
    return {'expected': expected, 'actual': actual, 'matches': valid and close(expected, actual)}


def closing_inputs(book, nation, results, current, before):
    prior = book.opening_memberships.get(nation.name, {})
    initial = {ident: book.accounts[metadata['key']]['opening'] for ident, metadata in prior.items()}
    required = set(prior) | set(current)
    transitions = []
    for transition in book.transitions:
        if nation.name not in transition['before'] or nation.name not in transition['after']:
            continue
        old, new = transition['before'][nation.name], transition['after'][nation.name]
        if old == new:
            continue
        required.update(old['accounts']);required.update(new['accounts'])
        transitions.append({'type':'transition', 'event_id':transition['event_id'],
                            'sequence':transition['sequence'], 'before':old, 'after':new})
    if not transitions:
        return None
    steps = transitions + [dict(step, type='write', account_id=ident)
                           for ident, operations in book.operations.items() if ident in required
                           for step in operations]
    steps.sort(key=lambda step: step['sequence'])
    return {'opening_total':before, 'initial_accounts':initial,
            'initial_territory':book.opening_territories.get(nation.name, []),
            'required_accounts':[results[ident] for ident in sorted(required)],
            'steps':steps, 'final_account_ids':sorted(current),
            'final_territory':sorted(tile.name for tile in nation.tiles),
            'currency_conversion_applied':False,
            'currency_semantics':'unconverted_public_cash_plus_deposits'}
