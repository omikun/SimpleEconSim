"""Append-only, typed causal records in compact .ctr files."""

from __future__ import annotations

from collections import deque
import hashlib
import json
from pathlib import Path
from trace_codec import CompactTraceWriter, iter_payloads


SCHEMA_VERSION = 1


class RunTrace:
    def __init__(self, path, run_id, *, seed=None, scenario=None, recent_limit=256):
        self.path = Path(path)
        if self.path.suffix != '.ctr':
            raise ValueError('causal trace path must end in .ctr')
        self.run_id = str(run_id)
        self.branch_id = 'main'
        self.recent = deque(maxlen=recent_limit)
        self.write_error = None
        self.count = 0
        self.digest = '0' * 64
        self._active_turn = None
        self._calculated = set()
        self._calculated_values = {}
        self._latest_calculation_event_ids = {}
        self._latest_metric_event_ids = {}
        self._treasury_flows = {}
        self._price_mutations = {}
        self._person_flow_events = {}
        self._person_event_classes = {}
        self._previous_person_flow_events = {}
        self._turn_production_events = {}
        self._turn_tile_production_events = {}
        self._turn_temporary_activity_events = {}
        self._turn_living_cost_events = {}
        self._latest_food_intake_events = {}
        self._latest_reference_price_events = {}
        self._technology_events = {}
        self._shipment_departure_events = {}
        self._shipment_arrival_events = {}
        self._shipment_events_by_kind = {}
        self._latest_shipment_events = {}
        self._recent_private_grain_purchase_events = deque(maxlen=2048)
        self._known_event_ids = set()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(self.path)
        self._compact_writer = CompactTraceWriter(self.path)
        self._append({'schema_version': SCHEMA_VERSION, 'record_class': 'metadata',
                      'run_id': self.run_id, 'branch_id': self.branch_id,
                      'seed': seed, 'scenario': scenario,
                      'storage_format': 'deflate-sync-v1'})

    def _append(self, row):
        # No default=str: unsupported values are instrumentation errors.
        if self.write_error is not None:
            raise OSError(self.write_error)
        payload = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)
        self._compact_writer.append(payload)
        self.count += 1
        self.digest = hashlib.sha256((self.digest + payload).encode('utf-8')).hexdigest()

    def emit(self, clock, *, kind, record_class='observation', phase=None,
             subject=None, metric_id=None, before=None, after=None,
             unit=None, inputs=None, formula_id=None, constraints=None,
             cause_event_ids=None, **extra):
        sequence = clock['next']
        clock['next'] += 1
        if self._active_turn != clock.get('turn', 0):
            self._active_turn = clock.get('turn', 0)
            self._calculated.clear()
            self._calculated_values.clear()
            self._latest_calculation_event_ids.clear()
            self._latest_metric_event_ids.clear()
            self._treasury_flows.clear()
            self._price_mutations.clear()
            self._previous_person_flow_events = self._person_flow_events
            self._person_flow_events = {}
            self._person_event_classes = {}
            self._turn_production_events = {}
            self._turn_tile_production_events = {}
            self._turn_temporary_activity_events = {}
            self._turn_living_cost_events = {}
            self._latest_food_intake_events = {}
        row = {'schema_version': SCHEMA_VERSION, 'run_id': self.run_id,
               'branch_id': self.branch_id, 'event_id': f'{self.run_id}:{sequence}',
               'sequence': sequence, 'turn': clock.get('turn', 0),
               'phase': phase or clock.get('phase', 'unknown'),
               'kind': kind, 'record_class': record_class,
               'confidence': 'exact' if record_class in ('calculation', 'transfer', 'outcome')
               else 'unknown'}
        if subject is not None:
            row['subject'] = subject
        if metric_id is not None:
            row['metric_id'] = metric_id
        if before is not None:
            row['value_before'] = before
        if after is not None:
            row['value_after'] = after
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            row['delta'] = after - before
        for key, value in (('unit', unit), ('inputs', inputs),
                           ('formula_id', formula_id), ('constraints', constraints),
                           ('cause_event_ids', cause_event_ids)):
            if value is not None:
                row[key] = value
        row.update(extra)
        shipment_id = ((row.get('subject') or {}).get('id')
                       if (row.get('subject') or {}).get('type') == 'shipment'
                       else None)
        shipment_event_kind = (kind.removeprefix('route_shipment_')
                               if kind.startswith('route_shipment_') else None)
        if shipment_id is not None and shipment_event_kind is not None:
            previous_event_id = self._latest_shipment_events.get(str(shipment_id))
            if previous_event_id is not None:
                event_inputs = dict(row.get('inputs') or {})
                event_inputs['previous_route_event_id'] = previous_event_id
                row['inputs'] = event_inputs
                causes = list(row.get('cause_event_ids') or ())
                if previous_event_id not in causes:
                    causes.append(previous_event_id)
                row['cause_event_ids'] = causes
        if kind == 'route_shipment_departure':
            event_inputs = dict(row.get('inputs') or {})
            source_acquisition_event_ids = []
            source_acquisition_ids_missing = []
            source_shipment_event_ids = []
            for acquisition in event_inputs.get('source_acquisitions') or ():
                acquisition_event_id = (acquisition or {}).get(
                    'purchase_trace_event_id')
                if acquisition_event_id is None:
                    continue
                if acquisition_event_id in self._known_event_ids:
                    source_acquisition_event_ids.append(acquisition_event_id)
                else:
                    source_acquisition_ids_missing.append(acquisition_event_id)
            source_shipment_id = event_inputs.get('source_shipment_id')
            if source_shipment_id is not None and str(source_shipment_id) != str(shipment_id):
                source_arrival_id = self.shipment_event_id(source_shipment_id, 'arrival')
                if source_arrival_id is not None:
                    source_shipment_event_ids.append(source_arrival_id)
            event_inputs['source_acquisition_event_ids'] = source_acquisition_event_ids
            event_inputs['source_shipment_event_ids'] = source_shipment_event_ids
            event_inputs['source_acquisition_trace_status'] = (
                'linked' if source_acquisition_event_ids
                else 'referenced_trace_event_missing'
                if source_acquisition_ids_missing else 'no_trace_link_recorded')
            row['inputs'] = event_inputs
            causes = list(row.get('cause_event_ids') or ())
            for source_event_id in (source_acquisition_event_ids
                                    + source_shipment_event_ids):
                if source_event_id not in causes:
                    causes.append(source_event_id)
            if causes:
                row['cause_event_ids'] = causes
        if kind == 'route_shipment_arrival' and shipment_id is not None:
            departure_event_id = self._shipment_departure_events.get(str(shipment_id))
            if departure_event_id is not None:
                causes = list(row.get('cause_event_ids') or ())
                if departure_event_id not in causes:
                    causes.append(departure_event_id)
                row['cause_event_ids'] = causes
            event_inputs = dict(row.get('inputs') or {})
            event_inputs['departure_event_id'] = departure_event_id
            event_inputs['departure_link_status'] = (
                'linked' if departure_event_id is not None else 'departure_trace_missing')
            row['inputs'] = event_inputs
        if (formula_id == 'living.basket_prices_climate.v1'
                and (row.get('subject') or {}).get('type') == 'tile'):
            tile_id = str(row['subject'].get('id'))
            event_inputs = dict(row.get('inputs') or {})
            component_event_ids = {}
            for good_name in event_inputs.get('basket_component_goods', ()):
                source_event_id = self._latest_reference_price_events.get(
                    (tile_id, str(good_name)))
                component_event_ids[str(good_name)] = source_event_id
            event_inputs['component_price_event_ids'] = component_event_ids
            event_inputs['component_price_link_status'] = {
                good_name: ('linked' if source_event_id is not None
                            else 'no_prior_price_record')
                for good_name, source_event_id in component_event_ids.items()}
            row['inputs'] = event_inputs
            causes = list(row.get('cause_event_ids') or ())
            for source_event_id in component_event_ids.values():
                if source_event_id is not None and source_event_id not in causes:
                    causes.append(source_event_id)
            if causes:
                row['cause_event_ids'] = causes
        if formula_id is not None and (formula_id in (
                'aggregate.mean.v1', 'aggregate.sum.v1') or metric_id in (
                'goods.price', 'goods.seller_ask', 'goods.delivered_quote',
                'goods.transaction_vwap', 'goods.scenario_transaction_vwap',
                'goods.scenario_market_coverage',
                'goods.demand', 'goods.supply',
                'goods.demand_ratio', 'living.cost_of_living',
                'goods.national_reference_price', 'goods.national_food_price',
                'labor.firm_surplus_value', 'labor.surplus_value',
                'labor.exploitation_rate', 'finance.bank_equity',
                'finance.total_cash', 'labor.workhouse_inmates',
                'labor.forced_labor_hours', 'land.pasture_fraction',
                'people.population_change_rate', 'trade.trader_cash',
                'trade.pipeline_depth', 'finance.fiscal_deficit',
                'finance.fiscal_gap', 'finance.tax_rate',
                'finance.tax_assessment', 'finance.tax_distribution',
                'innovation.domain_experience', 'innovation.bottleneck_pressure',
                'innovation.breakthrough', 'innovation.diffusion_progress',
                'innovation.bounty_escrow', 'politics.faction_support',
                'politics.faction_grievance', 'labor.primary_livelihood',
                'labor.employment_status', 'labor.hungry_adults',
                'labor.temporary_work_share')):
            from price_trace import replay_event
            replay = replay_event(row)
            if replay is not None:
                row['formula_replay'] = replay
                if not replay['matches']:
                    row['confidence'] = 'unknown'
        provenance_key = (metric_id, json.dumps(subject, sort_keys=True)
                          if subject is not None else None)
        if record_class in ('calculation', 'transfer', 'outcome') and row.get(
                'formula_replay', {}).get('matches', True):
            self._calculated.add(provenance_key)
            if after is not None:
                self._calculated_values[provenance_key] = after
        if metric_id == 'goods.price' and record_class == 'calculation' and subject:
            price_key = (subject.get('id'), subject.get('good'))
            self._price_mutations.setdefault(price_key, []).append(row)
        if metric_id == 'finance.treasury_flow' and subject is not None:
            nation_id = subject.get('id') if subject.get('type') == 'nation' else None
            if nation_id is not None:
                flows = self._treasury_flows.setdefault(nation_id, [])
                flows.append({'event_id': row['event_id'], 'amount': after,
                              'kind': kind})
        try:
            self._append(row)
        except OSError as exc:
            self.write_error = str(exc)
        else:
            if metric_id is not None and subject is not None:
                self._latest_metric_event_ids[(
                    metric_id, json.dumps(subject, sort_keys=True))] = row['event_id']
            if (record_class == 'calculation' and metric_id is not None
                    and subject is not None):
                self._latest_calculation_event_ids[(
                    metric_id, json.dumps(subject, sort_keys=True))] = row['event_id']
        if self.write_error is None and shipment_id is not None:
            if kind == 'route_shipment_departure':
                self._shipment_departure_events[str(shipment_id)] = row['event_id']
            elif kind == 'route_shipment_arrival':
                self._shipment_arrival_events[str(shipment_id)] = row['event_id']
            if shipment_event_kind is not None:
                self._shipment_events_by_kind.setdefault(str(shipment_id), {})[
                    shipment_event_kind] = row['event_id']
                self._latest_shipment_events[str(shipment_id)] = row['event_id']
        if self.write_error is None:
            self._known_event_ids.add(row['event_id'])
            if (metric_id == 'innovation.technology_known' and after == 1
                    and record_class == 'outcome'
                    and subject is not None):
                self._technology_events[(str(subject.get('id')),
                                         str(subject.get('tech_id')))] = row['event_id']
        person_flow_kinds = {
            'birth', 'person_died', 'person_role_conversion',
            'migration_departure', 'migration_arrival',
            'enlisted_person_departure', 'enlisted_person_arrival',
            'scenario_person_departure', 'scenario_person_arrival',
        }
        if (self.write_error is None
                and (kind in person_flow_kinds
                     or metric_id in ('labor.occupation_change', 'labor.status_change', 'people.role'))):
            event_inputs = row.get('inputs') or {}
            event_subject = row.get('subject') or {}
            person_id = (event_inputs.get('agent_id')
                         if event_inputs.get('agent_id') is not None else
                         event_inputs.get('new_agent_id'))
            if person_id is None and event_subject.get('type') in ('agent', 'tile/agent'):
                person_id = event_subject.get('id')
            if person_id is not None:
                self._person_flow_events.setdefault(str(person_id), []).append(
                    row['event_id'])
                self._person_event_classes[row['event_id']] = (
                    'occupation' if metric_id == 'labor.occupation_change' else
                    'status' if metric_id == 'labor.status_change' else 'resident')
        if (self.write_error is None and metric_id == 'goods.production'
                and row.get('subject', {}).get('type') == 'agent'
                and row.get('subject', {}).get('good') is not None):
            key = (str(row['subject'].get('id')), str(row['subject']['good']))
            self._turn_production_events[key] = row['event_id']
        if (self.write_error is None and metric_id == 'goods.production'
                and kind == 'tile_production_total'
                and row.get('subject', {}).get('type') == 'tile'
                and row.get('subject', {}).get('good') is not None):
            key = (str(row['subject'].get('id')), str(row['subject']['good']))
            self._turn_tile_production_events[key] = row['event_id']
        if self.write_error is None and metric_id == 'goods.grain_transfer':
            transfer = ((row.get('inputs') or {}).get('transfer_contract') or {})
            payee = transfer.get('payee_account') or {}
            if (transfer.get('operation_type') == 'private_household_grain_sale'
                    and payee.get('id') is not None):
                self._recent_private_grain_purchase_events.append({
                    'agent_id': str(payee['id']), 'event_id': row['event_id'],
                    'turn': int(row.get('turn', 0)),
                    'food_units': int(transfer.get('amount', 0))})
        if (self.write_error is None and metric_id == 'labor.temporary_activity'
                and row.get('subject', {}).get('type') == 'agent'):
            self._turn_temporary_activity_events[
                str(row['subject'].get('id'))] = row['event_id']
        if (self.write_error is None and metric_id == 'goods.price'
                and row.get('subject', {}).get('type') == 'tile'
                and row.get('subject', {}).get('good') is not None):
            self._latest_reference_price_events[
                (str(row['subject'].get('id')), str(row['subject']['good']))] = row['event_id']
        if (self.write_error is None and metric_id == 'living.cost_of_living'
                and row.get('subject', {}).get('type') == 'tile'):
            self._turn_living_cost_events[str(row['subject'].get('id'))] = row['event_id']
        if (self.write_error is None and kind == 'household_food_intake'
                and row.get('subject', {}).get('type') == 'tile/agent'):
            agent_id = (row.get('inputs') or {}).get('agent_id')
            if agent_id is None:
                agent_id = row['subject'].get('id')
            if agent_id is not None:
                self._latest_food_intake_events[str(agent_id)] = row['event_id']
        self.recent.append(row)
        return row['event_id']

    def shipment_event_id(self, shipment_id, event_kind='arrival'):
        """Find the latest recorded route event for a shipment, if available."""
        if shipment_id is None:
            return None
        events = self._shipment_events_by_kind.get(str(shipment_id), {})
        if event_kind == 'latest':
            return self._latest_shipment_events.get(str(shipment_id))
        return events.get(event_kind)

    def latest_reference_price_event_id(self, tile_id, good_name):
        """Return the latest recorded local reference price for one good."""
        return self._latest_reference_price_events.get((str(tile_id), str(good_name)))

    def technology_event_id(self, nation_name, tech_id):
        """Find the latest knowledge addition, retaining links across turns."""
        return self._technology_events.get((str(nation_name), str(tech_id)))

    def turn_living_cost_event_id(self, tile_id):
        """Return the current-turn local basket calculation for one tile."""
        return self._turn_living_cost_events.get(str(tile_id))

    def food_intake_event_id(self, agent_id):
        """Return the current-turn food-intake calculation for one person."""
        return self._latest_food_intake_events.get(str(agent_id))

    def person_event_ids(self, agent_id, *, categories=None):
        """Current-turn recorded movements, roles, occupations and labor status."""
        events = self._person_flow_events.get(str(agent_id), ())
        return [event_id for event_id in events if categories is None
                or self._person_event_classes.get(event_id) in categories]

    def temporary_activity_event_id(self, agent_id):
        return self._turn_temporary_activity_events.get(str(agent_id))

    def latest_metric_calculation_event_id(self, metric_id, subject):
        """Return the latest current-turn calculation for an exact subject."""
        key = (metric_id, json.dumps(subject, sort_keys=True))
        return self._latest_calculation_event_ids.get(key)

    def latest_metric_event_id(self, metric_id, subject):
        """Return the latest current-turn record for an exact metric subject."""
        key = (metric_id, json.dumps(subject, sort_keys=True))
        return self._latest_metric_event_ids.get(key)

    def turn_tile_production_event_id(self, tile_id, good_name):
        """Return the current-turn aggregate production event for a tile good."""
        return self._turn_tile_production_events.get((str(tile_id), str(good_name)))

    def recent_private_grain_purchase_events(self, agent_id, *, before_turn=None,
                                             limit=8):
        """Return recent candidate inventory sources; this does not allocate consumed units."""
        matches = [dict(row) for row in self._recent_private_grain_purchase_events
                   if row['agent_id'] == str(agent_id)
                   and (before_turn is None or row['turn'] <= int(before_turn))]
        limit = max(0, int(limit))
        return matches[-limit:] if limit else []

    def snapshot(self, clock, *, subject, metric_id, unit, before, after):
        key = (metric_id, json.dumps(subject, sort_keys=True))
        explained = (self.write_error is None and key in self._calculated_values
                     and self._calculated_values[key] == after)
        event_id = self.emit(clock, kind='metric_snapshot', record_class='observation',
                             subject=subject, metric_id=metric_id, unit=unit,
                             before=before, after=after,
                             confidence='exact' if explained else 'unknown',
                             explanation_status='calculation_recorded' if explained else
                             'source_missing')
        if before is not None and before != after and not explained:
            self.emit(clock, kind='unexplained_change', record_class='audit',
                      subject=subject, metric_id=metric_id, unit=unit,
                      before=before, after=after, source='metric_catalog')
        return event_id

    def price_bridge(self, clock, *, subject, before, after, unit):
        """Reconcile ordered displayed-price writes within the current turn."""
        mutations = self._price_mutations.get((subject['id'], subject['good']), ())
        steps = []
        current = before
        gaps = []
        for row in mutations:
            opening = row.get('value_before')
            closing = row.get('value_after')
            if row.get('formula_replay', {}).get('matches') is False:
                gaps.append({'event_id': row['event_id'],
                             'reason': 'formula_replay_mismatch'})
            if current is not None and opening != current:
                gaps.append({'event_id': row['event_id'], 'expected_opening': current,
                             'recorded_opening': opening})
            if opening is not None and closing is not None:
                steps.append({'event_id': row['event_id'], 'kind': row['kind'],
                              'before': opening, 'after': closing,
                              'difference': closing - opening})
            current = closing
        if current != after:
            gaps.append({'expected_closing': after, 'recorded_closing': current})
        reconciled = not gaps and self.write_error is None
        change = after - before if before is not None else None
        return self.emit(clock, kind='price_bridge', record_class='audit',
                         subject=subject, metric_id='goods.price', unit=unit,
                         before=before, after=after,
                         confidence='exact' if reconciled else 'unknown',
                         explanation_status='ordered_writes_reconciled' if reconciled
                         else 'mutation_chain_incomplete',
                         inputs={'steps': steps, 'gaps': gaps,
                                 'absolute_change': change,
                                 'percent_change': 100 * change / before
                                 if change is not None and before != 0 else None},
                         cause_event_ids=[row['event_id'] for row in mutations])

    def checkpoint(self, clock):
        """End a turn with a count and hash of every preceding decoded row."""
        return self.emit(clock, kind='turn_checkpoint', record_class='audit',
                         phase='checkpoint', count_before=self.count,
                         sha256_before=self.digest)


    def query(self, *, turn=None, subject=None, metric_id=None, kind=None,
              event_id=None, offset=0, limit=100):
        found = []
        matched = 0
        for payload in iter_payloads(self.path):
            row = json.loads(payload)
            if row.get('record_class') == 'metadata':
                continue
            if event_id is not None and row.get('event_id') != event_id:
                continue
            if turn is not None and row.get('turn') != turn:
                continue
            if subject is not None and not all(
                    row.get('subject', {}).get(key) == value
                    for key, value in subject.items()):
                continue
            if metric_id is not None and row.get('metric_id') != metric_id:
                continue
            if kind is not None and row.get('kind') != kind:
                continue
            if matched >= offset and len(found) < limit:
                found.append(row)
            matched += 1
        return {'events': found, 'total': matched, 'offset': offset,
                'limit': limit, 'write_error': self.write_error}


def verify(path):
    """Validate typed JSON and every complete turn checkpoint."""
    digest = '0' * 64
    count = 0
    checkpoints = 0
    for number, payload in enumerate(iter_payloads(path), 1):
        row = json.loads(payload)
        if row.get('kind') == 'turn_checkpoint':
            if row.get('count_before') != count or row.get('sha256_before') != digest:
                raise ValueError(f'broken checkpoint at line {number}')
            checkpoints += 1
        digest = hashlib.sha256((digest + payload).encode('utf-8')).hexdigest()
        count += 1
    return {'rows': count, 'checkpoints': checkpoints, 'sha256': digest}


def emit(region, **kwargs):
    """Write at the authoritative mutation point, if tracing is enabled."""
    clock = getattr(region, '_collective_trace_clock', None)
    recorder = getattr(region, '_run_trace', None)
    if clock is not None and recorder is not None:
        return recorder.emit(clock, **kwargs)
    return None
