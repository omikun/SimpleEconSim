"""Recorded bank balance transitions and strict closing-stock reconciliation."""
from trace_clock import boundary

import math
import json


FIELDS = {'capital': 'finance.bank_capital', 'deposits': 'finance.bank_deposits',
          'liabilities': 'finance.bank_liabilities'}


def balances(bank):
    return {'capital': float(bank.capital), 'deposits': float(bank.total_deposits),
            'liabilities': float(bank.total_liabilities)}


def begin_change(bank, region=None):
    candidates = [region] if region is not None else []
    candidates.extend(getattr(bank, '_attached_regions', ()))
    for candidate in candidates:
        trace = getattr(candidate, '_run_trace', None)
        if (getattr(trace, 'bank_book', None) is not None
                and getattr(candidate, '_collective_trace_clock', None) is not None):
            return trace, candidate, balances(bank)
    return None


def finish_change(bank, context, kind, *, inputs=None, cause_event_ids=None):
    if context is None:
        return None
    trace, region, before = context
    after = balances(bank)
    if before == after:
        return None
    return trace.bank_book.operation(bank, region, before, after, kind,
                                     inputs or {}, cause_event_ids)


def _same(first, second):
    return math.isclose(first, second, rel_tol=1e-10, abs_tol=1e-8)


class BankTraceBook:
    def __init__(self, trace):
        self.trace = trace
        self.banks = {}
        self.operations = {}
        self.turn = None
        self.previous_aliases = {}

    def start_turn(self, turn):
        if self.turn == turn:
            return
        self.turn = turn
        self.operations = {}
        for info in self.banks.values():
            info['opening'] = dict(info['observed_close'])
            info['turn_opening_events'] = dict(info['opening_events'])

    def register(self, bank, region, clock, *, opening=None, basis='registration_observation'):
        key = id(bank)
        if key not in self.banks:
            value = dict(opening) if opening is not None else balances(bank)
            info = {'id': f'{self.trace.run_id}:bank:{len(self.banks) + 1}',
                    'bank': bank, 'opening': value, 'observed_close': dict(value),
                    'currency': getattr(region, 'home_currency', None) or 'local_currency',
                    'opening_events': {}, 'registration_basis': basis}
            self.banks[key] = info
            event_id = self.trace.emit(
                clock, kind='bank_registered', record_class='observation', phase='finance',
                subject={'type': 'bank', 'id': info['id']},
                metric_id='finance.bank_registration', unit='balance_sheet',
                inputs={'starting_balances': value, 'basis': basis,
                        'first_observed_tile': region.name,
                        'currency': info['currency']})
            info['opening_events'] = {field: event_id for field in FIELDS}
            info['turn_opening_events'] = dict(info['opening_events'])
        return self.banks[key]

    def register_tiles(self, tiles, clock, *, basis='world_setup'):
        for region in tiles:
            bank = getattr(region, 'bank', None)
            if bank is not None:
                self.register(bank, region, clock, basis=basis)

    def operation(self, bank, region, before, after, kind, inputs, causes):
        clock = region._collective_trace_clock
        info = self.register(bank, region, clock, opening=before,
                             basis='before_first_recorded_operation')
        event_id = self.trace.emit(
            clock, kind='bank_balance_operation', record_class='outcome', phase='finance',
            subject={'type': 'bank', 'id': info['id']},
            metric_id='finance.bank_balance_operation', unit='balance_sheet',
            before=before, after=after,
            inputs={'operation_kind': kind, 'source_tile': region.name, **inputs},
            cause_event_ids=causes)
        self.operations.setdefault(info['id'], []).append(
            {'event_id': event_id, 'kind': kind, 'before': before, 'after': after})
        return event_id

    def close(self, tiles, clock, previous_values):
        self.start_turn(boundary(clock))
        # Closing stocks require closure evidence even if an earlier operation
        # happened to have the same numeric value as the final stock.
        for region in tiles:
            subject_key = json.dumps({'type': 'tile', 'id': region.name}, sort_keys=True)
            for metric_id in (*FIELDS.values(), 'finance.bank_equity'):
                self.trace._calculated_values.pop((metric_id, subject_key), None)
        aliases = {}
        for region in tiles:
            bank = getattr(region, 'bank', None)
            if bank is not None:
                info = self.register(bank, region, clock, basis='turn_end_first_observation')
                aliases.setdefault(info['id'], []).append(region)
        for info in self.banks.values():
            bank_id = info['id']
            operations = list(self.operations.get(bank_id, ()))
            if bank_id not in aliases and not operations:
                continue
            final = balances(info['bank'])
            results = {}
            for field, metric_id in FIELDS.items():
                opening = info['opening'][field]
                steps, gaps = [], []
                running = opening
                for operation in operations:
                    before, after = operation['before'][field], operation['after'][field]
                    if not _same(running, before):
                        gaps.append({'before_event_id': operation['event_id'],
                                     'expected_before': running, 'observed_before': before})
                    steps.append({'event_id': operation['event_id'],
                                  'operation_kind': operation['kind'], 'before': before, 'after': after})
                    running = after
                if not _same(running, final[field]):
                    gaps.append({'before_event_id': None, 'expected_before': running,
                                 'observed_before': final[field], 'location': 'closing_boundary'})
                expected = opening + sum(step['after'] - step['before'] for step in steps)
                complete = not gaps and _same(expected, final[field])
                event_id = self.trace.emit(
                    clock, kind='bank_closing_balance',
                    record_class='calculation' if complete else 'audit', phase='snapshot',
                    subject={'type': 'bank', 'id': bank_id}, metric_id=metric_id,
                    unit=info['currency'], before=opening, after=final[field],
                    formula_id='bank.opening_plus_transitions.v1',
                    confidence='exact' if complete else 'unknown',
                    explanation_status='operations_reconciled' if complete else 'balance_chain_gap',
                    inputs={'field': field, 'opening_balance': opening, 'operations': steps,
                            'opening_source_event_id': info['turn_opening_events'].get(field),
                            'chain_gaps': gaps, 'unattributed_residual': final[field] - expected,
                            'tile_aliases': [region.name for region in aliases.get(bank_id, ())]},
                    cause_event_ids=([info['turn_opening_events'][field]] if info['turn_opening_events'].get(field) else [])
                    + [step['event_id'] for step in steps if step['event_id']])
                results[field] = (complete, event_id, final[field], metric_id)
                info['opening_events'][field] = event_id
            equity = final['capital'] + final['deposits'] - final['liabilities']
            equity_complete = all(result[0] for result in results.values())
            equity_id = self.trace.emit(
                clock, kind='bank_closing_equity',
                record_class='calculation' if equity_complete else 'observation', phase='snapshot',
                subject={'type': 'bank', 'id': bank_id}, metric_id='finance.bank_equity',
                unit=info['currency'], after=equity, formula_id='finance.bank_equity_balance_sheet.v1',
                inputs={**final, 'component_closure_complete': equity_complete},
                cause_event_ids=[result[1] for result in results.values() if result[1]])
            results['equity'] = (equity_complete, equity_id, equity, 'finance.bank_equity')
            for region in aliases.get(bank_id, ()):
                for _field, (complete, source_id, value, metric_id) in results.items():
                    if not complete:
                        continue
                    key = (metric_id, region.name)
                    self.trace.emit(
                        clock, kind='bank_tile_closing_alias', record_class='calculation',
                        phase='snapshot', subject={'type': 'tile', 'id': region.name},
                        metric_id=metric_id, unit='local_currency',
                        before=previous_values[key][2] if key in previous_values else None,
                        after=value, formula_id='bank.tile_closing_alias.v1',
                        inputs={'bank_id': bank_id, 'bank_closing_balance': value,
                                'previous_bank_id': self.previous_aliases.get(region.name),
                                'native_bank_currency': info['currency'],
                                'tile_currency': getattr(region, 'home_currency', None),
                                'currency_conversion_applied': False},
                        cause_event_ids=([source_id] if source_id else None))
                self.previous_aliases[region.name] = bank_id
            info['observed_close'] = final
