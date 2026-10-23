"""Public-account stock continuity, independent of signed flow summaries.

Only explicitly probed writes enter a chain. Unrecorded writes and changes in
account membership remain audits even if their net effect happens to cancel.
"""
from trace_clock import boundary
import json
import math


def same(a, b):
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8)


def begin_public_change(source, agent, *, bank=None, cash=True, deposit=False):
    if not getattr(agent, 'is_government', False):
        return None
    candidates = [source] if source is not None else []
    candidates.extend(getattr(source, 'regions', ()))
    candidates.extend(getattr(bank, '_attached_regions', ()))
    candidates.extend(getattr(getattr(agent, '_bank_ref', None), '_attached_regions', ()))
    if getattr(agent, 'region', None) is not None:
        candidates.append(agent.region)
    registered_source = getattr(agent, '_public_trace_source', None)
    if registered_source is not None:
        candidates.append(registered_source)
    for region in candidates:
        trace = getattr(region, '_run_trace', None)
        book = getattr(trace, 'treasury_book', None)
        clock = getattr(region, '_collective_trace_clock', None)
        if book is not None and clock is not None:
            keys = []
            if cash:
                keys.append(('cash', id(agent)))
            if deposit and bank is not None:
                keys.append(('deposit', id(agent), id(bank)))
            if not all(key in book.accounts for key in keys):
                nation = (region if callable(getattr(region, '_treasury_entities', None))
                          else getattr(region, 'owner_nation', None))
                if callable(getattr(nation, '_treasury_entities', None)):
                    book.register_nations([nation], clock, basis='before_recorded_write')
            keys = [key for key in keys if key in book.accounts]
            if keys:
                return book, clock, [(key, book.value(book.accounts[key])) for key in keys], region.name
    return None


def finish_public_change(context, kind, *, inputs=None, cause_event_ids=None):
    if context is None:
        return []
    book, clock, before, source_name = context
    operation_id = f'{book.trace.run_id}:public-write:{clock["next"]}'
    cause_event_ids = list(cause_event_ids or ())
    command = clock.get('command_event_id')
    if command is not None and command not in cause_event_ids:cause_event_ids.append(command)
    event_ids = []
    for key, opening in before:
        info = book.accounts[key]
        after = book.value(info)
        if opening != after:
            event_id = book.operation(key, clock, opening, after, kind,
                           {'operation_id': operation_id, 'source_entity': source_name,
                            'source_phase': clock.get('phase'), **(inputs or {})}, cause_event_ids)
            if event_id is not None:
                event_ids.append(event_id)
    return event_ids


class TreasuryTraceBook:
    def __init__(self, trace):
        self.trace = trace
        self.accounts = {}
        self.nations = {}
        self.transitions = []
        self.operations = {}
        self.turn = None
        self.observed_memberships = {}
        self.opening_memberships = {}
        self.observed_territories = {}
        self.opening_territories = {}

    @staticmethod
    def value(info):
        agent, bank = info['agent'], info['bank']
        return float(agent.cash if bank is None else bank.deposits.get(agent, 0.0))

    def start_turn(self, turn):
        if turn == self.turn:
            return
        self.turn = turn
        self.operations = {}
        self.transitions = []
        self.opening_memberships = {name: dict(rows) for name, rows in self.observed_memberships.items()}
        self.opening_territories = {name: list(tiles) for name, tiles in self.observed_territories.items()}
        for info in self.accounts.values():
            info['opening'] = info['observed_close']
            info['opening_source'] = info['last_source']

    def membership(self, nation, clock, *, basis):
        result = {}
        governments, banks = nation._treasury_entities()
        for government, tier in governments:
            agent = government.agent
            # Trace metadata only: explicit writers can resolve their registered
            # account even when a manual/scenario API has no region parameter.
            agent._public_trace_source = nation
            for bank in [None, *banks]:
                key = ('cash', id(agent)) if bank is None else ('deposit', id(agent), id(bank))
                if key not in self.accounts:
                    bank_id = None
                    if bank is not None:
                        # Reuse the physical bank ID, including banks reachable
                        # through public references outside current tile aliases.
                        source = next(iter(getattr(bank, '_attached_regions', ())), nation)
                        bank_id = self.trace.bank_book.register(
                            bank, source, clock, basis='public_account_inventory')['id']
                    info = {'id': f'{self.trace.run_id}:public-account:{len(self.accounts) + 1}',
                            'agent': agent, 'bank': bank, 'bank_id': bank_id,
                            'currency': getattr(agent, 'home_currency', None), 'last_source': None}
                    value = self.value(info)
                    info.update(opening=value, observed_close=value, opening_source=None)
                    self.accounts[key] = info
                    event_id = self.trace.emit(
                        clock, kind='public_account_registered', record_class='observation',
                        phase='finance', subject={'type': 'public_account', 'id': info['id']},
                        metric_id='finance.public_account_balance', unit='local_currency', after=value,
                        inputs={'government_id': agent.id, 'government_name': government.name,
                                'account_kind': key[0], 'bank_id': bank_id, 'basis': basis,
                                'native_currency': info['currency'], 'first_observed_nation': nation.name})
                    info['opening_source'] = info['last_source'] = event_id
                info = self.accounts[key]
                result[info['id']] = {'key': key, 'government_id': agent.id, 'tier': tier,
                                      'account_kind': key[0], 'bank_id': info['bank_id']}
        return result

    def register_nations(self, nations, clock, *, basis='world_setup'):
        for nation in nations:
            if not callable(getattr(nation, '_treasury_entities', None)):
                continue
            self.nations[nation.name] = nation
            rows = self.membership(nation, clock, basis=basis)
            if basis == 'world_setup':
                self.observed_memberships[nation.name] = rows
                self.opening_memberships[nation.name] = dict(rows)
                self.observed_territories[nation.name] = sorted(tile.name for tile in nation.tiles)
                self.opening_territories[nation.name] = list(self.observed_territories[nation.name])

    def operation(self, key, clock, before, after, kind, inputs, causes):
        info = self.accounts[key]
        event_id = self.trace.emit(
            clock, kind='public_account_write', record_class='outcome', phase='finance',
            subject={'type': 'public_account', 'id': info['id']},
            metric_id='finance.public_account_balance', unit='local_currency',
            before=before, after=after,
            inputs={'operation_kind': kind, 'government_id': info['agent'].id,
                    'account_kind': key[0], 'bank_id': info['bank_id'], **inputs},
            cause_event_ids=causes)
        self.operations.setdefault(info['id'], []).append(
            {'event_id': event_id, 'sequence': clock['next']-1, 'operation_kind': kind, 'before': before, 'after': after})
        return event_id

    def close(self, nations, clock, previous_values):
        self.start_turn(boundary(clock))
        supported = []
        for nation in nations:
            if callable(getattr(nation, '_treasury_entities', None)):
                supported.append(nation)
            else:
                subject = {'type': 'nation', 'id': nation.name}
                self.trace._calculated_values.pop(('finance.treasury', json.dumps(subject, sort_keys=True)), None)
                self.trace.emit(clock, kind='treasury_account_inventory_unavailable',
                                record_class='audit', subject=subject, metric_id='finance.treasury',
                                inputs={'reason': 'public_account_enumerator_unavailable'})
        nations = supported
        memberships = {nation.name: self.membership(nation, clock, basis='closing_first_observation')
                       for nation in nations}
        results = {}
        # Include departed accounts so the missing continuity remains inspectable.
        for key, info in self.accounts.items():
            operations = list(self.operations.get(info['id'], ()))
            running, gaps = info['opening'], []
            for step in operations:
                if not same(running, step['before']):
                    gaps.append({'before_event_id': step['event_id'],
                                 'expected_before': running, 'observed_before': step['before']})
                running = step['after']
            final = self.value(info)
            if not same(running, final):
                gaps.append({'before_event_id': None, 'location': 'closing_boundary',
                             'expected_before': running, 'observed_before': final})
            expected = info['opening'] + sum(row['after'] - row['before'] for row in operations)
            complete = not gaps and same(expected, final)
            source = info['opening_source']
            event_id = self.trace.emit(
                clock, kind='public_account_close', record_class='calculation' if complete else 'audit',
                phase='snapshot', subject={'type': 'public_account', 'id': info['id']},
                metric_id='finance.public_account_balance', unit='local_currency',
                before=info['opening'], after=final, formula_id='treasury.account_chain.v1',
                explanation_status='account_chain_verified' if complete else 'account_chain_gap',
                inputs={'opening_balance': info['opening'], 'opening_source_event_id': source,
                        'operations': operations, 'chain_gaps': gaps,
                        'unattributed_residual': final - expected, 'account_kind': key[0],
                        'government_id': info['agent'].id, 'bank_id': info['bank_id']},
                cause_event_ids=([source] if source else []) + [row['event_id'] for row in operations])
            results[info['id']] = {'account_id': info['id'], 'opening': info['opening'],
                                  'closing': final, 'complete': complete, 'source_event_id': event_id}
            info['observed_close'], info['last_source'] = final, event_id
        for nation in nations:
            prior = self.opening_memberships.get(nation.name, {})
            current = memberships[nation.name]
            rows = [dict(results[account_id], **{k: v for k, v in metadata.items() if k != 'key'})
                    for account_id, metadata in current.items()]
            before = previous_values.get(('finance.treasury', nation.name), (None, None, None))[2]
            actual = nation.treasury()['total']
            opening_sum = sum(row['opening'] for row in rows)
            closing_sum = sum(row['closing'] for row in rows)
            # Even a zero-valued new association is an unverified membership transition.
            territory_same = (sorted(tile.name for tile in nation.tiles)
                              == self.opening_territories.get(nation.name))
            membership_same = current == prior and territory_same
            complete = (membership_same and before is not None and same(before, opening_sum)
                        and all(row['complete'] for row in rows) and same(actual, closing_sum))
            from treasury_composition import closing_inputs, replay
            composition = closing_inputs(self, nation, results, current, before)
            if composition is not None:
                verified = replay(composition, actual)['matches']
                subject = {'type': 'nation', 'id': nation.name}
                self.trace._calculated_values.pop(('finance.treasury', json.dumps(subject, sort_keys=True)), None)
                self.trace.emit(
                    clock, kind='treasury_account_closure', record_class='calculation' if verified else 'audit',
                    phase='snapshot', subject=subject, metric_id='finance.treasury', unit=nation.currency,
                    before=before, after=actual, formula_id='treasury.timed_composition.v1',
                    inputs={**composition, 'membership_unchanged': False},
                    explanation_status='timed_composition_verified' if verified else 'composition_chain_gap',
                    cause_event_ids=[step['event_id'] for step in composition['steps']]
                    + [row['source_event_id'] for row in composition['required_accounts']])
                continue
            subject = {'type': 'nation', 'id': nation.name}
            self.trace._calculated_values.pop(('finance.treasury', json.dumps(subject, sort_keys=True)), None)
            self.trace.emit(
                clock, kind='treasury_account_closure', record_class='calculation' if complete else 'audit',
                phase='snapshot', subject=subject, metric_id='finance.treasury', unit=nation.currency,
                before=before, after=actual, formula_id='treasury.closed_accounts.v1',
                explanation_status='accounts_reconciled' if complete else 'account_chain_or_membership_gap',
                inputs={'accounts': rows, 'opening_total': before, 'opening_account_sum': opening_sum,
                        'membership_unchanged': membership_same,
                        'incomplete_accounts': [row['account_id'] for row in rows if not row['complete']],
                        'opening_residual': None if before is None else before - opening_sum,
                        'closing_residual': actual - closing_sum,
                        'entered_accounts': sorted(set(current) - set(prior)),
                        'departed_accounts': sorted(set(prior) - set(current)),
                        'previous_membership': {ident: {k: v for k, v in metadata.items() if k != 'key'}
                                                for ident, metadata in prior.items()},
                        'member_tiles': sorted(tile.name for tile in nation.tiles),
                        'previous_member_tiles': self.opening_territories.get(nation.name, []),
                        'territory_unchanged': territory_same,
                        'currency_conversion_applied': False,
                        'currency_semantics': 'unconverted_public_cash_plus_deposits'},
                cause_event_ids=[row['source_event_id'] for row in rows])
        self.observed_memberships = memberships
        self.observed_territories = {nation.name: sorted(tile.name for tile in nation.tiles) for nation in nations}


def replay_chain(inputs, actual):
    expected = inputs['opening_balance'] + sum(row['after'] - row['before'] for row in inputs['operations'])
    running, continuous = inputs['opening_balance'], True
    for row in inputs['operations']:
        continuous = continuous and same(running, row['before'])
        running = row['after']
    return {'expected': expected, 'actual': actual,
            'matches': continuous and same(running, actual) and same(expected, actual)}


def replay_aggregate(inputs, actual):
    expected = sum(row['closing'] for row in inputs['accounts'])
    valid = (inputs['membership_unchanged'] and inputs['opening_total'] is not None
             and same(inputs['opening_total'], sum(row['opening'] for row in inputs['accounts']))
             and all(row['complete'] for row in inputs['accounts']))
    return {'expected': expected, 'actual': actual, 'matches': valid and same(expected, actual)}
