"""Sparse frontier capture preserves real activity, sources and historical boundaries."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from goods import Goods
from region import Region
from run_trace import RunTrace,verify
from trace_codec import iter_records,iter_storage_records,CorruptTrace
from trace_index import TraceIndex
from trace_snapshots import record,sample
from wilderness_trace import FIELDS,MAX_TILES
from explanations.context import capture
from explanations.packet import build_packet
from explanations.service import ExplanationService
from test_ai_explainer_service import FakeProvider,done


class MinimalWildernessTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);self.root=Path(folder.name)
        self.trace=RunTrace(self.root/'run.ctr','frontier',wilderness_policy='minimal')
        self.addCleanup(self.trace._compact_writer.close)
        self.clock={'turn':0,'epoch':0,'next':1,'phase':'setup'}
        self.tile=Region('Quiet',t=0,wilderness=True,wilderness_pop=30)
        self.tile._run_trace=self.trace;self.tile._collective_trace_clock=self.clock
        self.trace.wilderness.register([self.tile],[])
        self.trace.wilderness.record([self.tile],self.clock)
        self.session=SimpleNamespace(tiles=[self.tile],nations=[],run_trace=self.trace,
                                     _trace_previous=sample([self.tile],[]))

    def turn(self,number):
        self.clock.update(turn=number,epoch=0,phase='local')
        self.tile.step(number);record(self.session);self.trace.checkpoint(self.clock)

    def captured(self,metric,turn=1,**extra):
        return capture({'tiles':[self.tile],'nations':[],'turn':max(turn,self.clock['turn']),
                        'run_trace':self.trace},{'entity':'tile:Quiet','turn':turn,'metric_id':metric,**extra})

    def test_no_padded_economic_emissions_or_generic_snapshot_calls(self):
        with patch.object(self.trace,'snapshot',side_effect=AssertionError('per-stat capture')):
            self.turn(1)
        rows=[record.row for record in iter_storage_records(self.trace.path) if record.row.get('turn')==1]
        self.assertEqual(['wilderness_domain_coverage','turn_checkpoint'],[row['kind'] for row in rows])
        self.assertEqual(1,len(sample([self.tile],[])))
        self.assertGreater(len(sample([self.tile],[],full=True)),150)
        self.assertEqual(30,self.tile.wilderness_pop)
        self.assertEqual(0,self.tile.sold_log[Goods.food][-1])
        self.assertEqual(self.trace.event_count,verify(self.trace.path)['event_records'])

    def test_sparse_catalog_and_historical_state_preserve_native_population(self):
        self.turn(1);index=TraceIndex(self.trace.path)
        options=index.available_metrics(turn=1,subject={'type':'tile','id':'Quiet'})
        self.assertEqual(8,len(options))
        self.assertNotIn('goods.price',{row['metric_id'] for row in options})
        state=index.wilderness_status(turn=1,subject={'type':'tile','id':'Quiet'})
        self.assertEqual(30,state['state'][0])
        packet=build_packet(self.captured('frontier.native_population'))
        self.assertEqual((30,30,0),(packet['values']['before'],packet['values']['after'],packet['values']['delta']))
        self.assertEqual(0,build_packet(self.captured('people.residents'))['values']['after'])
        with closing(sqlite3.connect(index.index_path)) as db:
            self.assertEqual(2,db.execute('SELECT count(*) FROM wilderness').fetchone()[0])
            self.assertEqual(self.trace.event_count,db.execute('SELECT count(*) FROM events').fetchone()[0])
        index.index_path.unlink()
        self.assertEqual(30,index.wilderness_status(turn=1,subject={'type':'tile','id':'Quiet'})['state'][0])

    def test_quote_observation_on_use_reuses_value_and_changes_source_when_needed(self):
        self.turn(1);before=self.trace.count
        first=self.trace.latest_reference_price_event_id('Quiet','food')
        self.assertEqual(before+1,self.trace.count)
        self.assertEqual(first,self.trace.latest_reference_price_event_id('Quiet','food'))
        self.assertEqual(before+1,self.trace.count)
        self.tile.recipes[Goods.food]['price']+=1
        second=self.trace.latest_reference_price_event_id('Quiet','food')
        self.assertNotEqual(first,second)
        row=self.trace.query(event_id=second)['events'][0]
        self.assertFalse(row['inputs']['market_active']);self.assertEqual(2.,row['value_after'])
        decision=self.trace.emit(self.clock,kind='trader_route_decision',record_class='decision',
                                cause_event_ids=[second],inputs={'destination_price':2.})
        self.assertEqual([second],self.trace.query(event_id=decision)['events'][0]['cause_event_ids'])

    def test_migration_gate_links_consumed_neighbor_quote_but_preview_is_read_only(self):
        from agent import Agent
        from migration import run_migrations
        from region_logistics import migration_intent_score
        source=Region('Home',t=0);source.agents=[Agent(0)];source.gov=SimpleNamespace()
        source.neighbors={'Quiet':self.tile}
        source._run_trace=self.trace;source._collective_trace_clock=self.clock
        self.trace.wilderness.register([source,self.tile],[])
        count=self.trace.count;migration_intent_score(source)
        self.assertEqual(count,self.trace.count)
        run_migrations(1,[source])
        quotes=self.trace.query(kind='wilderness_reference_price_observation')['events']
        self.assertEqual(1,len(quotes));self.assertEqual('food',quotes[0]['subject']['good'])
        decision=self.trace.query(kind='migration_push_decision')['events'][0]
        self.assertIn(quotes[0]['event_id'],decision['cause_event_ids'])
        self.assertEqual(1.,decision['inputs']['neighbor_food_price_average'])

    def test_f11_empty_price_tab_explains_policy(self):
        from desktop_evidence_panel import load
        self.turn(1)
        world={'run_trace':self.trace,'selected_region':self.tile,'nations':[],
               '_causal_panel':{'tab':1,'turn':1,'boundary':self.trace.publish(),'offset':0}}
        load(world)
        self.assertIsNone(world['_causal_panel']['row'])
        self.assertIn('display defaults',world['_causal_panel']['policy_message'])

    def test_mode_transition_does_not_erase_new_market_source_and_reentry_invalidates_quote(self):
        first=self.trace.latest_reference_price_event_id('Quiet','food')
        self.tile.wilderness=False
        self.assertFalse(self.trace.wilderness.quiet(self.tile))
        market=self.trace.emit(self.clock,kind='market_price_update',subject={'type':'tile','id':'Quiet','good':'food'},
                               metric_id='goods.price',after=1.,unit='local_currency_per_unit')
        self.trace.wilderness.record([self.tile],self.clock)
        self.assertEqual(market,self.trace.latest_reference_price_event_id('Quiet','food'))
        self.tile.wilderness=True
        self.trace.wilderness.record([self.tile],self.clock)
        new=self.trace.latest_reference_price_event_id('Quiet','food')
        self.assertNotIn(new,(first,market))
        self.assertEqual(2,self.trace.query(kind='wilderness_capture_transition')['total'])

    def test_pollution_writer_and_closing_delta_are_preserved(self):
        self.turn(1);self.clock.update(turn=2,phase='local')
        old=self.tile.pollution_water;self.tile.pollution_water=old+3
        source=self.trace.emit(self.clock,kind='pollution_downstream_advection',record_class='calculation',
            subject={'type':'tile','id':'Quiet'},metric_id='ecology.pollution_water',before=old,after=old+3,
            unit='index',formula_id='aggregate.sum.v1',inputs={'member_values':[old,3]})
        record(self.session)
        snapshots=self.trace.query(turn=2,kind='metric_snapshot')['events']
        self.assertEqual(1,len(snapshots));self.assertEqual(3,snapshots[0]['delta'])
        self.assertEqual([source],snapshots[0]['cause_event_ids'])
        packet=build_packet(self.captured('ecology.pollution_water',turn=2))
        self.assertEqual(3,packet['values']['delta']);self.assertIn(source,[row['event_id'] for row in packet['evidence']])
        self.clock['turn']=3;record(self.session)
        self.assertEqual(old+3,build_packet(self.captured('ecology.pollution_water',turn=3))['values']['after'])

    def test_unknown_native_population_change_retains_gap(self):
        self.turn(1);self.clock['turn']=2;self.tile.wilderness_pop+=5;record(self.session)
        rows=self.trace.query(turn=2,metric_id='frontier.native_population',kind='metric_snapshot')['events']
        self.assertEqual(5,rows[0]['delta']);self.assertEqual('source_missing',rows[0]['explanation_status'])

    def test_coverage_is_exact_epoch_and_boundary_not_inferred_from_absence(self):
        self.turn(1);index=TraceIndex(self.trace.path);boundary=self.trace.publish()
        self.clock.update(turn=1,epoch=1);record(self.session)
        self.assertIsNone(index.wilderness_status(turn=1,epoch=1,subject={'type':'tile','id':'Quiet'},boundary=boundary))
        self.assertEqual(1,index.wilderness_status(turn=1,epoch=1,subject={'type':'tile','id':'Quiet'})['coverage']['epoch'])
        self.assertIsNone(index.wilderness_status(turn=2,subject={'type':'tile','id':'Quiet'}))

    def test_inapplicable_stat_works_without_api_key_and_never_calls_provider(self):
        self.turn(1);provider=FakeProvider();provider.unavailable='No API key'
        service=ExplanationService(provider,self.root/'cache',self.root/'planning');self.addCleanup(service.close)
        count=self.trace.count;digest=self.trace.digest
        result=done(service,service.request(self.captured('goods.price',good='food')))
        self.assertEqual('ready',result['state']);self.assertEqual(0,provider.calls)
        self.assertIsNone(result['result']['packet']['values']['delta'])
        self.assertIn('display defaults',result['result']['narrative']['claims'][0]['text'])
        self.assertEqual((count,digest),(self.trace.count,self.trace.digest))

    def test_scaffolding_is_quiet_but_active_cargo_factions_and_membership_are_not(self):
        route=SimpleNamespace(pending=[],in_transit=[],delivered_this_turn=[],parked_this_turn=[])
        self.tile.routes={'other':route}
        self.assertTrue(self.trace.wilderness.quiet(self.tile))
        route.pending=[object()];self.assertFalse(self.trace.wilderness.quiet(self.tile));route.pending=[]
        self.tile.factions.factions={'test':SimpleNamespace(membership={1})}
        self.assertFalse(self.trace.wilderness.quiet(self.tile));self.tile.factions.factions={}
        self.trace.wilderness.register([self.tile],[SimpleNamespace(tiles=[self.tile])])
        self.assertFalse(self.trace.wilderness.quiet(self.tile))

    def test_empty_ending_census_does_not_suppress_birth_death_activity(self):
        self.tile.deaths_this_turn=1
        self.assertFalse(self.trace.wilderness.quiet(self.tile))

    def test_resident_homesteader_retains_full_capture_and_unknown_opening(self):
        from agent import Agent
        resident=Agent(0);resident.is_homesteader=True
        self.tile.agents.append(resident)
        self.assertFalse(self.trace.wilderness.quiet(self.tile))
        self.assertTrue(any(key[0]=='goods.price' for key in sample([self.tile],[])))
        self.clock['turn']=1;record(self.session)
        self.assertEqual(0,self.trace.query(turn=1,kind='wilderness_domain_coverage')['total'])
        rows=self.trace.query(turn=1,metric_id='goods.price',kind='metric_snapshot')['events']
        self.assertTrue(rows);self.assertTrue(all(row.get('value_before') is None for row in rows))
        self.tile.agents.clear();self.clock['turn']=2;record(self.session)
        self.assertEqual(1,self.trace.query(turn=2,kind='wilderness_initial_state')['total'])

    def test_gap_requires_fresh_frontier_baseline(self):
        self.turn(1);self.clock['turn']=3;self.tile.wilderness_pop=0;record(self.session)
        state=TraceIndex(self.trace.path).wilderness_status(turn=3,subject={'type':'tile','id':'Quiet'})
        self.assertEqual('wilderness_initial_state',state['source']['kind'])
        self.assertEqual(0,state['state'][0])
        self.assertIsNone(build_packet(self.captured('frontier.native_population',turn=3))['values']['before'])

    def test_homesteader_forage_preserves_receipt_and_production_chain(self):
        from agent import Agent
        from land_tenure import TileTenure
        resident=Agent(0);resident.is_homesteader=True;resident.last_forage_turn=0
        self.tile.agents.append(resident);self.tile.tenure=TileTenure()
        self.turn(3)
        receipts=self.trace.query(turn=3,kind='foraged_food_receipt')['events']
        self.assertEqual(1,len(receipts));self.assertEqual(1,receipts[0]['value_after'])
        production=self.trace.query(turn=3,kind='wilderness_food_production')['events'][0]
        self.assertEqual(1,production['value_after'])
        self.assertIn(receipts[0]['event_id'],production['cause_event_ids'])
        self.assertEqual(0,self.trace.query(turn=3,kind='wilderness_domain_coverage')['total'])

    def test_legacy_formats_and_old_saved_policy_remain_full(self):
        for version in (3,4):
            with self.subTest(version=version):
                trace=RunTrace(self.root/f'legacy{version}.ctr','old',storage_version=version)
                self.addCleanup(trace._compact_writer.close)
                self.assertFalse(trace.wilderness.enabled)
        # Rebinding an old saved RunTrace without the policy field preserves
        # the original capture regime, regardless of the new-run default.
        trace=RunTrace(self.root/'before-policy.ctr','before',wilderness_policy='full')
        trace._compact_writer.close();del trace.wilderness
        trace.rebind(trace.path,'fork');self.addCleanup(trace._compact_writer.close)
        self.assertFalse(trace.wilderness.enabled)
        self.tile.deaths_this_turn=0;self.tile.births_this_turn=1
        self.assertFalse(self.trace.wilderness.quiet(self.tile))

    def test_bounded_cohorts_do_not_create_one_index_row_per_tile(self):
        tiles=[]
        for number in range(MAX_TILES+1):
            tile=SimpleNamespace(name='Q'+str(number),wilderness=True,agents=[])
            tiles.append(tile)
        self.trace.wilderness.register(tiles,[]);self.clock['turn']=1
        self.trace.wilderness.record(tiles,self.clock);self.trace.publish()
        rows=self.trace.query(turn=1,kind='wilderness_domain_coverage')['events']
        self.assertEqual([MAX_TILES,1],[len(row['inputs']['tiles']) for row in rows])
        index=TraceIndex(self.trace.path)
        self.assertIsNotNone(index.wilderness_status(turn=1,subject={'type':'tile','id':'Q512'}))
        with closing(sqlite3.connect(index.index_path)) as db:
            self.assertEqual(3,db.execute('SELECT count(*) FROM wilderness').fetchone()[0])

    def test_invalid_cohort_is_rejected_while_saved_prefix_remains_readable(self):
        boundary=self.trace.publish()
        row=json.loads(json.dumps(self.trace.query(kind='wilderness_domain_coverage')['events'][0]))
        row['event_id']='frontier:100';row['sequence']=100;row['inputs']['tiles'].append('Quiet')
        self.trace._compact_writer.append(row);self.trace._compact_writer.close()
        self.assertTrue(list(iter_storage_records(self.trace.path,end_offset=boundary)))
        with self.assertRaises(CorruptTrace):list(iter_storage_records(self.trace.path))


if __name__=='__main__':unittest.main()
