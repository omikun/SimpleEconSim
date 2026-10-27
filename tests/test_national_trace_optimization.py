"""Causal reductions preserve checked evidence, gross flows and regional effects."""
from copy import deepcopy
import json
import os
from pathlib import Path
import pickle
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from run_trace import RunTrace, verify
from trace_codec import iter_records, iter_payloads, _frames
from trace_packing import SharedEvidence, SharedInputs, canonical, unpack
from national_contributions import summarize, fiscal_totals, attach, for_packet


class NationalTraceOptimizationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def trace(self, name):
        trace = RunTrace(self.root / (name+'.ctr'), 'same')
        self.addCleanup(trace._compact_writer.close)
        return trace

    def events(self, trace):
        return [json.loads(row) for row in iter_payloads(trace.path)]

    def test_templates_match_previous_logical_events_and_recent_view(self):
        views = []
        for enabled in ('0', '1'):
            with patch.dict(os.environ, COC_TRACE_TEMPLATES=enabled):
                trace = self.trace(enabled)
            clock = {'turn': 2, 'epoch': 3, 'phase': 'local', 'next': 1}
            subject = {'type': 'tile', 'id': 'A', 'good': 'food'}
            trace.emit(clock, kind='start')
            for rule, value, inputs in (
                ('gini.wilderness_zero.v1', 0, {'wilderness': True, 'sample_point': 'native_wilderness_history_write',
                    'history_rule': 'wilderness writer stores zero', 'output_good': 'food'}),
                ('gini.retain_previous_value.v1', .4, {'previous_gini': .4, 'sample_point': 'native_local_history_write',
                    'recomputed_this_turn': False, 'refresh_interval_turns': 10, 'initial_empty_series': False, 'output_good': 'food'})):
                trace.emit(clock, kind='gini_series_calculation', record_class='calculation', subject=subject,
                    metric_id='economy.gini', unit='ratio', before=value, after=value,
                    formula_id=rule, inputs=inputs, cause_event_ids=['same:1'])
            clock['phase'] = 'snapshot'
            trace.emit(clock, kind='closing_active_disease_census', record_class='calculation', phase='snapshot',
                subject={'type':'tile','id':'A','disease':'malnutrition'}, metric_id='health.active_disease_cases',
                unit='people', after=0, formula_id='disease.count_active_cases.v1',
                inputs={'sample_point':'closing_live_state','case_agent_ids':[],'disease':'malnutrition'})
            trace.emit(clock, kind='tax_revenue_distribution_calculation', record_class='calculation',
                subject={'type':'tile','id':'A','tax_tier':'total'}, metric_id='finance.tax_distribution',
                unit='C', before=0.0, after=0.0, formula_id='fiscal.tax_distribution.v1',
                inputs={'turn':2,'reason':'empty','tax_tier':'total',
                        'opening_components':dict.fromkeys(('total','municipal','provincial','national'),0.0),
                        'receipts':[],'aggregation_rule':'opening plus receipt allocations; total uses receipt amount'})
            trace.price_bridge(clock, subject=subject, before=2., after=2., unit='C')
            trace.snapshot(clock, subject=subject, metric_id='goods.price', unit='C', before=2., after=2.)
            trace.snapshot(clock, subject=subject, metric_id='goods.sold', unit='units', before=0, after=0)
            trace.checkpoint(clock)
            rows = self.events(trace)
            self.assertEqual(list(trace.recent), rows[1:])
            restored_recent = pickle.loads(pickle.dumps(trace.recent))
            self.assertEqual(list(trace.recent), list(restored_recent))
            self.assertEqual(rows[-2], trace.recent[-2])
            self.assertEqual(list(reversed(trace.recent)), list(reversed(rows[1:])))
            views.append([{k:v for k,v in row.items() if k != 'sha256_before'} for row in rows])
            self.assertEqual(trace.digest, verify(trace.path)['sha256'])
        self.assertEqual(views[0], views[1])

    def test_literal_marker_fields_in_regular_events_remain_literal(self):
        trace = self.trace('markers')
        event = trace.emit({'turn':1,'next':1}, kind='literal',
                           **{'@rule':'not_a_rule','@shared_input':123,'@source':'literal'})
        row = trace.query(event_id=event)['events'][0]
        self.assertEqual('not_a_rule',row['@rule'])
        self.assertEqual(123,row['@shared_input'])

    def test_direct_observation_freezes_subject_and_current_source(self):
        trace = self.trace('immutable'); clock = {'turn': 1, 'next': 1}
        trace.emit(clock, kind='start')
        subject = {'type': 'tile', 'id': 'A', 'good': 'food'}
        first = trace.snapshot(clock, subject=subject, metric_id='goods.sold', unit='u', before=0, after=0)
        subject['id'] = 'B'
        trace.recent[-1]['subject']['id'] = 'C'
        self.assertEqual('A', trace.query(event_id=first)['events'][0]['subject']['id'])

    def test_offsetting_price_writes_are_never_certified_as_inactive(self):
        trace = self.trace('writes'); clock = {'turn': 1, 'next': 1}
        subject = {'type':'tile', 'id':'A', 'good':'food'}
        ids = [trace.emit(clock, kind='price_write', record_class='calculation', subject=subject,
                         metric_id='goods.price', before=a, after=b) for a,b in ((2.,3.), (3.,2.))]
        event = trace.price_bridge(clock, subject=subject, before=2., after=2., unit='C')
        bridge = trace.query(event_id=event)['events'][0]
        self.assertEqual(ids, bridge['cause_event_ids'])
        self.assertEqual([1.,-1.], [row['difference'] for row in bridge['inputs']['steps']])

    def test_shared_census_inputs_expand_exactly_and_seek_without_prior_packets(self):
        trace = self.trace('shared'); clock = {'turn': 1, 'next': 1}
        original = {'adult_records': [{'id': str(i), 'cash': i} for i in range(8)], 'prior': None}
        evidence = SharedEvidence(original)
        for i in range(150):
            trace.emit(clock, kind='fixture', inputs=SharedInputs(evidence, {'category': str(i)}))
        original['adult_records'][0]['cash'] = 999
        trace.recent[-1]['inputs']['adult_records'][0]['cash'] = 888
        records = list(iter_records(trace.path))
        row = trace.query(kind='fixture', offset=130, limit=1)['events'][0]
        self.assertEqual(0, row['inputs']['adult_records'][0]['cash'])
        selected = records[131]
        sought = list(iter_records(trace.path, start_offset=selected.block_offset))
        self.assertEqual(row, sought[selected.record_in_block].row)
        packets = [json.loads(payload)['packet'] for _,kind,payload,*_ in _frames(trace.path) if kind == b'P']
        packet = next(packet for packet in packets if 'shared_inputs' in packet)
        self.assertEqual(2, packet['version']); self.assertEqual(1, len(packet['shared_inputs']))
        broken = deepcopy(packet)
        for schema in broken['schemas']:
            if '@shared_input' in schema['keys']:
                schema['keys'][schema['keys'].index('@shared_input')] = '@shared_input'
        for schema_id, values in broken['rows']:
            keys = broken['schemas'][schema_id]['keys']
            if '@shared_input' in keys:
                values[keys.index('@shared_input')] = 999
                break
        with self.assertRaisesRegex(ValueError, 'shared evidence'): list(unpack(broken))

    def state(self, values, reducer='sum', members=None, **kwargs):
        known = [v for v in values.values() if v is not None]
        return {'rows':[{'tile_id':k, 'value':v, 'source_event_id':k+':1'} for k,v in values.items()],
                'members': list(values) if members is None else members, 'reducer':reducer,
                'value':sum(known)/(max(1,len(known)) if reducer=='mean' else 1), 'unit':'u', **kwargs}

    def test_offsetting_regional_and_fiscal_changes_keep_both_directions(self):
        result = summarize(self.state({'A':100, 'B':100}), self.state({'A':80, 'B':120}))
        self.assertEqual(0, result['delta']); self.assertTrue(result['reconciled'])
        self.assertEqual(20, result['gross_positive_contributions'])
        self.assertEqual(-20, result['gross_negative_contributions'])
        flows = fiscal_totals([{'kind':'income_tax_collected', 'amount':100},
                               {'kind':'relief_spending', 'amount':-100}])
        self.assertEqual((100,100,0,2), tuple(flows[k] for k in
            ('gross_inflows','gross_outflows','net_recorded_flow','flow_count')))
        self.assertEqual(100, flows['gross_flows_by_kind']['income_tax_collected']['inflows'])
        self.assertEqual(100, flows['gross_flows_by_kind']['relief_spending']['outflows'])

    def test_mean_membership_and_coverage_changes_are_not_local_value_changes(self):
        result = summarize(self.state({'A':10}, 'mean'), self.state({'A':10, 'B':30}, 'mean'))
        self.assertEqual(10, result['delta']); self.assertTrue(result['reconciled'])
        a, b = result['regions']
        self.assertEqual((0,-5), (a['regional_value_effect'], a['weight_effect']))
        self.assertEqual('territory_entered', b['reason'])
        result = summarize(self.state({'A':None, 'B':4}), self.state({'A':0, 'B':None}))
        self.assertEqual(['coverage_entered','coverage_departed'], [r['reason'] for r in result['regions']])
        self.assertTrue(result['reconciled'])

    def test_missing_opening_and_inconsistent_aggregate_remain_explicit(self):
        current = self.state({'A':2})
        self.assertIsNone(summarize(None, current)['delta'])
        current['value'] = 10
        result = summarize(self.state({'A':1}), current)
        self.assertEqual(8, result['residual']); self.assertFalse(result['reconciled'])
        current['unit'] = 'different'
        self.assertFalse(summarize(self.state({'A':1}), current)['comparable_basis'])

    def test_partial_price_coverage_keeps_actual_tile_alignment(self):
        trace = self.trace('coverage'); subject = {'type':'nation','id':'A','good':'food'}
        for turn, price in ((1,10),(2,12)):
            inputs = {'member_tiles':['missing','priced'], 'member_values':[price], 'denominator':1,
                      'coverage_count':1}
            attach(trace, {'turn':turn}, subject, 'goods.national_reference_price','C',price,inputs,
                   contribution_rows=[{'tile_id':'missing','value':None}, {'tile_id':'priced','value':price}])
        summary = inputs['national_contributions']
        self.assertTrue(summary['reconciled'])
        self.assertEqual(['priced'],[row['tile_id'] for row in summary['regions']])
        self.assertEqual(2,summary['delta'])
        self.assertEqual(1,summary['observed_coverage_count'])

    def test_packet_summary_keeps_exact_totals_and_both_directions_under_bounds(self):
        prior = self.state({str(i):100 for i in range(40)})
        current = self.state({str(i):100+(i if i%2 else -i) for i in range(40)})
        complete = summarize(prior,current); bounded = for_packet(complete)
        self.assertEqual(12, len(bounded['regions']))
        self.assertTrue(any(r['contribution_delta']>0 for r in bounded['regions']))
        self.assertTrue(any(r['contribution_delta']<0 for r in bounded['regions']))
        self.assertEqual(27, bounded['omitted_region_count'])
        self.assertEqual(complete['gross_positive_contributions'], bounded['gross_positive_contributions'])

    def test_baseline_boundaries_survive_pickle_and_command_epochs(self):
        trace = self.trace('baseline'); subject = {'type':'nation','id':'A'}
        first = {'member_tiles':['x'], 'member_values':[10]}
        attach(trace, {'turn':1,'epoch':0}, subject, 'm', 'u', 10, first)
        self.assertFalse(first['national_contributions']['baseline_available'])
        cache = pickle.loads(pickle.dumps(trace._national_contribution_baselines))
        trace._national_contribution_baselines = cache
        second = {'member_tiles':['x'], 'member_values':[12]}
        attach(trace, {'turn':1,'epoch':1}, subject, 'm', 'u', 12, second)
        self.assertEqual([1,0], second['national_contributions']['opening_boundary'])
        self.assertEqual([1,1], second['national_contributions']['closing_boundary'])
        self.assertEqual(2, second['national_contributions']['delta'])

    def test_uncovered_turn_or_epoch_never_implies_carry_forward(self):
        for closing in ({'turn':3,'epoch':0}, {'turn':1,'epoch':2}):
            with self.subTest(closing=closing):
                trace = self.trace('gap-'+str(closing['turn']))
                subject = {'type':'nation','id':'A'}
                attach(trace, {'turn':1,'epoch':0},subject,'m','u',10,
                       {'member_tiles':['x'],'member_values':[10]})
                current = {'member_tiles':['x'],'member_values':[14]}
                attach(trace, closing,subject,'m','u',14,current)
                self.assertIsNone(current['national_contributions']['delta'])
                self.assertFalse(current['national_contributions']['baseline_available'])
                self.assertIn('uncovered',current['national_contributions']['limitation'])

    def test_national_packet_includes_material_sources_beyond_territorial_prefix(self):
        from explanations.packet import build_packet
        trace = self.trace('packet'); clock = {'turn':1, 'epoch':0, 'next':1}
        nation = {'type':'nation','id':'A'}
        for turn in (1,2):
            clock['turn'] = turn
            contributions = []
            for i in range(40):
                value = 100 + ((100 if i==38 else -100 if i==39 else 0) if turn==2 else 0)
                source = trace.emit(clock, kind='regional_calculation', record_class='calculation',
                    subject={'type':'tile','id':str(i)}, metric_id='goods.production', unit='u',
                    after=value, formula_id='aggregate.sum.v1', inputs={'member_values':[value]})
                contributions.append({'tile_id':str(i),'value':value,'source_event_id':source})
            inputs = {'member_tiles':[str(i) for i in range(40)], 'member_values':[row['value'] for row in contributions],
                      'member_contributions':contributions, 'reducer':'sum'}
            attach(trace, clock, nation, 'goods.production', 'u', 4000, inputs)
            trace.emit(clock, kind='national_aggregate', record_class='calculation', subject=nation,
                metric_id='goods.production', unit='u', after=4000, formula_id='aggregate.sum.v1',
                inputs=inputs, cause_event_ids=[row['source_event_id'] for row in contributions])
            trace.snapshot(clock, subject=nation, metric_id='goods.production', unit='u', before=4000, after=4000)
            trace.checkpoint(clock)
        packet = build_packet({'selection': {'turn':2, 'subject':nation, 'metric_id':'goods.production'},
            'trace_path':str(trace.path), 'boundary':trace.publish(), 'actions':[], 'catalog_coverage':{}})
        summary = packet['national_contributions'][0]
        self.assertEqual((100,-100,0), (summary['gross_positive_contributions'],
                         summary['gross_negative_contributions'], summary['delta']))
        included = {row['subject']['id'] for row in packet['evidence'] if row['kind']=='regional_calculation'}
        self.assertTrue({'38','39'} <= included)
        clock['epoch'] = 1
        command_inputs = {'member_tiles':['38','39'], 'member_values':[150,250], 'reducer':'sum'}
        attach(trace,clock,nation,'goods.production','u',400,command_inputs)
        trace.emit(clock,kind='national_aggregate',record_class='calculation',subject=nation,
                   metric_id='goods.production',unit='u',after=400,formula_id='aggregate.sum.v1',inputs=command_inputs)
        trace.snapshot(clock,subject=nation,metric_id='goods.production',unit='u',before=4000,after=400)
        command = build_packet({'selection':{'turn':2,'epoch':1,'subject':nation,'metric_id':'goods.production'},
            'trace_path':str(trace.path),'boundary':trace.publish(),'actions':[],'catalog_coverage':{}})
        self.assertEqual(400,command['values']['after'])
        self.assertEqual(1,len(command['national_contributions']))
        self.assertEqual([2,1],command['national_contributions'][0]['closing_boundary'])
        self.assertEqual(-3600,command['national_contributions'][0]['delta'])

    def test_actual_offsetting_public_writes_and_fiscal_flow_events_survive_recording(self):
        from nation import Nation
        from region import Region
        from trace_snapshots import sample, record
        from treasury_trace import begin_public_change, finish_public_change
        trace = self.trace('fiscal'); clock = {'turn':0,'next':1}
        nation = Nation('A','C',initial_cash=1000,register=False)
        tile = Region('District',0,0); nation.add_tile(tile)
        for obj in (nation,tile):
            obj._run_trace = trace; obj._collective_trace_clock = clock
        trace.treasury_book.register_nations([nation],clock)
        server = SimpleNamespace(tiles=[tile],nations=[nation],run_trace=trace,
                                 _trace_previous=sample([tile],[nation]))
        before = nation.treasury()['total']; clock['turn'] = 1
        for kind,amount in (('income_tax_collected',100), ('relief_spending',-100)):
            change = begin_public_change(tile,tile.gov.agent)
            tile.gov.agent.cash += amount
            finish_public_change(change,kind)
            trace.emit(clock,kind=kind,record_class='transfer',subject={'type':'nation','id':'A'},
                       metric_id='finance.treasury_flow',unit='C',after=amount)
        record(server)
        self.assertEqual(before,nation.treasury()['total'])
        flows = trace.query(metric_id='finance.treasury_flow')['events']
        self.assertEqual([100,-100],[row['value_after'] for row in flows])
        writes = trace.query(kind='public_account_write')['events']
        self.assertEqual([100,-100],[row['delta'] for row in writes])
        reconciliation = trace.query(kind='treasury_reconciliation')['events'][0]
        self.assertEqual((100,100,0), tuple(reconciliation['inputs'][key] for key in
                         ('gross_inflows','gross_outflows','unattributed_residual')))
        self.assertEqual([row['event_id'] for row in flows],reconciliation['cause_event_ids'])


if __name__ == '__main__': unittest.main()
