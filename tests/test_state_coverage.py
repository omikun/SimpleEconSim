"""V5 reduces generated records/index rows while preserving historical facts."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from run_trace import RunTrace, verify
from trace_codec import (iter_records,iter_payloads,iter_storage_records,storage_stats,
                         CompactTraceWriter,TornTraceTail,CorruptTrace,MAGIC,HEADER)
from trace_index import TraceIndex
from trace_state_coverage import MAX_CELLS


class StateCoverageTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)

    def trace(self,name,version=5):
        trace=RunTrace(self.root/(name+'.ctr'),'same',storage_version=version)
        self.addCleanup(trace._compact_writer.close)
        return trace

    def sample(self,trace,clock,turn,tiles=4,metrics=200):
        clock['turn']=turn
        trace.emit(clock,kind='start')
        for tile in range(tiles):
            for good in range(metrics):
                trace.snapshot(clock,subject={'type':'tile','id':str(tile),'good':str(good)},
                               metric_id='goods.sold',unit='u',before=0,after=0)
        trace.checkpoint(clock)

    def test_exact_views_and_actual_counts_with_sparse_index(self):
        views=[]
        for version in (4,5):
            trace=self.trace('v'+str(version),version);clock={'turn':0,'epoch':0,'next':1}
            for turn in (1,2,3):self.sample(trace,clock,turn)
            views.append([{key:value for key,value in row.items()
                           if key not in ('sha256_before','digest_scope','event_count_before')}
                          for row in map(json.loads,iter_payloads(trace.path)) if row.get('record_class')!='metadata'])
            self.assertEqual(trace.count,verify(trace.path)['rows'])
            self.assertEqual(trace.event_count,verify(trace.path)['event_records'])
        self.assertEqual(views[0],views[1])
        self.assertLess(trace.event_count,trace.count/20)
        stats=storage_stats(trace.path)
        self.assertEqual(2400,stats['virtual_samples']);self.assertEqual(12,stats['coverage_groups'])
        self.assertEqual(trace.count,stats['expanded_records'])
        index=TraceIndex(trace.path)
        result=index.query(turn=2,subject={'id':'2'},metric_id='goods.sold',limit=3,offset=50)
        expected=[row for row in views[1] if row.get('turn')==2 and row.get('subject',{}).get('id')=='2']
        self.assertEqual(expected[50:53],result['events'])
        self.assertEqual(200,result['total'])
        with closing(sqlite3.connect(index.index_path)) as db:
            self.assertEqual(trace.event_count,db.execute('SELECT count(*) FROM events').fetchone()[0])
            self.assertEqual(12,db.execute('SELECT count(*) FROM coverage').fetchone()[0])
            self.assertEqual(0,db.execute("SELECT count(*) FROM events WHERE kind='metric_snapshot'").fetchone()[0])

    def test_catalog_never_eagerly_materializes_virtual_event_rows(self):
        trace=self.trace('catalog');clock={'turn':0,'next':1}
        self.sample(trace,clock,1)
        with (patch('trace_state_coverage.expand_cell',side_effect=AssertionError('eager expansion')),
              patch('trace_index.expand_cell',side_effect=AssertionError('eager expansion'))):
            rows=TraceIndex(trace.path).available_metrics(turn=1,subject={'type':'tile','id':'2'})
        self.assertEqual(200,len(rows));self.assertTrue(all(row['count']==1 for row in rows))

    def test_historical_boundary_sources_epochs_and_index_rebuild(self):
        trace=self.trace('history');clock={'turn':1,'epoch':0,'next':1}
        trace.emit(clock,kind='start')
        subject={'type':'tile','id':'A','good':'food','eligible':None}
        first=trace.snapshot(clock,subject=subject,metric_id='goods.sold',unit='u',before=0,after=0)
        boundary=trace.publish();digest=trace.digest
        trace.recent[-1]['subject']['id']='mutated'
        clock['epoch']=1
        second=trace.snapshot(clock,subject=subject,metric_id='goods.sold',unit='u',before=0,after=0)
        trace.emit(clock,kind='linked',cause_event_ids=[first,second])
        index=TraceIndex(trace.path)
        self.assertEqual(first,index.query(boundary=boundary,metric_id='goods.sold')['events'][0]['event_id'])
        self.assertEqual(1,index.query(boundary=boundary,metric_id='goods.sold')['total'])
        self.assertEqual([0,1],[row['epoch'] for row in index.query(subject=subject,metric_id='goods.sold')['events']])
        self.assertEqual([],index.query(boundary=boundary,event_id=second)['events'])
        self.assertEqual('A',index.query(event_id=first)['events'][0]['subject']['id'])
        self.assertIn(first,trace._known_event_ids);self.assertIn(second,trace._known_event_ids)
        prefix,number=first.rsplit(':',1)
        self.assertNotIn(prefix+':0'+number,trace._known_event_ids)
        self.assertNotIn(prefix+':+'+number,trace._known_event_ids)
        self.assertEqual(digest,list(iter_storage_records(trace.path,end_offset=boundary))[-1].digest_after)
        index.index_path.unlink()
        self.assertEqual(second,index.query(event_id=second)['events'][0]['event_id'])

    def test_group_boundaries_and_zero_changes_are_explicit(self):
        trace=self.trace('bounds');clock={'turn':1,'next':1}
        trace.emit(clock,kind='start')
        for index in range(1200):
            trace.snapshot(clock,subject={'type':'tile','id':'A','good':str(index)},
                           metric_id='goods.sold',unit='u',before=0,after=0)
        changed=trace.snapshot(clock,subject={'type':'tile','id':'A'},metric_id='goods.sold',unit='u',before=3,after=0)
        missing=trace.snapshot(clock,subject={'type':'tile','id':'B'},metric_id='goods.sold',unit='u',before=None,after=0)
        trace.publish()
        groups=[record.row for record in iter_storage_records(trace.path) if record.row.get('kind')=='state_coverage']
        self.assertEqual([512,512,176,1],[len(row['inputs']['cells']) for row in groups])
        self.assertTrue(all(len(row['inputs']['cells'])<=MAX_CELLS for row in groups))
        ordinary={record.row.get('event_id'):record.row for record in iter_storage_records(trace.path)}
        self.assertEqual(-3,ordinary[changed]['delta'])
        self.assertNotIn(missing,ordinary)
        self.assertNotIn('value_before',trace.query(event_id=missing)['events'][0])
        self.assertEqual(1,storage_stats(trace.path)['initial_samples'])

    def test_v5_resume_and_v4_resume_keep_their_formats(self):
        for version in (4,5):
            trace=self.trace('resume'+str(version),version);clock={'turn':1,'next':1}
            self.sample(trace,clock,1,tiles=1,metrics=30)
            trace._compact_writer.close();prefix=trace.path.read_bytes()
            trace.rebind(trace.path,'fork')
            self.sample(trace,clock,2,tiles=1,metrics=30)
            self.assertEqual(version,trace._compact_writer.version)
            self.assertEqual(prefix,trace.path.read_bytes()[:len(prefix)])
            self.assertEqual(trace.count,verify(trace.path)['rows'])
            self.assertEqual(trace.event_count,verify(trace.path)['event_records'])

    def test_coverage_publish_failure_stops_recording_and_keeps_saved_prefix(self):
        trace=self.trace('failure');clock={'turn':1,'next':1}
        trace.emit(clock,kind='start');boundary=trace.publish()
        trace.snapshot(clock,subject={'type':'tile','id':'A'},metric_id='x',unit='u',before=0,after=0)
        stream=trace._compact_writer._stream
        class ShortWrite:
            closed=False
            def write(self,data):return stream.write(data[:-1])
        with patch.object(trace._compact_writer,'_stream',ShortWrite()):
            with self.assertRaises(OSError):trace.publish()
        self.assertIsNotNone(trace.write_error)
        self.assertEqual(2,len(list(iter_storage_records(trace.path,end_offset=boundary))))
        with self.assertRaises(TornTraceTail):list(iter_records(trace.path))
        with self.assertRaises(OSError):
            trace.snapshot(clock,subject={'type':'tile','id':'A'},metric_id='x',unit='u',before=0,after=0)

    def test_initial_samples_keep_missing_opening_and_current_source(self):
        trace=self.trace('initial');clock={'turn':1,'next':1}
        subject={'type':'tile','id':'A'}
        source=trace.emit(clock,kind='sum',record_class='calculation',subject=subject,
                          metric_id='m',after=4,formula_id='aggregate.sum.v1',inputs={'member_values':[4]})
        initial=trace.snapshot(clock,subject=subject,metric_id='m',unit='u',before=None,after=4)
        row=trace.query(event_id=initial)['events'][0]
        self.assertEqual([source],row['cause_event_ids']);self.assertEqual(4,row['value_after'])
        self.assertNotIn('value_before',row);self.assertNotIn('delta',row)
        self.assertEqual('calculation_recorded',row['explanation_status'])

    def test_invalid_group_rule_is_rejected_without_losing_a_complete_prefix(self):
        trace=self.trace('corrupt');clock={'turn':1,'next':1}
        trace.emit(clock,kind='start')
        trace.snapshot(clock,subject={'type':'tile','id':'A'},metric_id='x',unit='u',before=0,after=0)
        boundary=trace.publish()
        group=next(record.row for record in iter_storage_records(trace.path) if record.row.get('kind')=='state_coverage')
        group=json.loads(json.dumps(group))
        group['inputs']['cells'][0][1]='unsupported_rule'
        group['inputs']['cells'][0][0]=10
        group['inputs']['sequence_min']=group['inputs']['sequence_max']=group['sequence']=10
        group['event_id']='same:coverage:10'
        trace._compact_writer.append(group);trace._compact_writer.close()
        self.assertTrue(list(iter_storage_records(trace.path,end_offset=boundary)))
        with self.assertRaises(CorruptTrace):list(iter_storage_records(trace.path))


if __name__=='__main__':unittest.main()
