from pathlib import Path
from contextlib import closing
import tempfile
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import unittest
from run_trace import RunTrace
from trace_report import report


class TraceIndexTests(unittest.TestCase):
    def test_streamed_comparison_matches_materialized_latest_snapshots(self):
        from trace_report import diff_snapshots,iter_snapshot_differences
        base={'kind':'metric_snapshot','turn':1,'subject':{'type':'tile','id':'A'},'metric_id':'x'}
        left=[dict(base,value_after=1),dict(base,value_after=2),dict(base,turn=2,value_after=3)]
        right=[dict(base,value_after=4),dict(base,turn=2,value_after=3)]
        self.assertEqual(diff_snapshots(left,right),list(iter_snapshot_differences(iter(left),iter(right))))

    def test_queries_rebuild_and_fixed_boundary_paging_match_source(self):
        with tempfile.TemporaryDirectory() as d:
            trace=RunTrace(Path(d)/'index.ctr','index');clock={'turn':1,'next':1}
            for i in range(700):
                trace.emit(clock,kind='price',subject={'type':'tile','id':str(i%3),'good':'food'},metric_id='goods.price',after=i)
            result=trace.query(subject={'id':'1'},offset=5,limit=7)
            source=[r for r in report(trace.path) if r.get('subject',{}).get('id')=='1']
            self.assertEqual(source[5:12],result['events']);self.assertEqual(len(source),result['total'])
            boundary=result['boundary']
            trace.emit(clock,kind='price',subject={'type':'tile','id':'1','good':'food'},metric_id='goods.price',after=999)
            self.assertEqual(len(source),trace.query(subject={'id':'1'},boundary=boundary)['total'])
            self.assertEqual(len(source)+1,trace.query(subject={'id':'1'})['total'])
            ident=result['events'][0]['event_id']
            self.assertEqual([result['events'][0]],trace.query(event_id=ident)['events'])
            trace.path.with_suffix('.ctr.index.sqlite').unlink()
            self.assertEqual(result['events'],trace.query(subject={'id':'1'},offset=5,limit=7,boundary=boundary)['events'])
            trace.path.with_suffix('.ctr.index.sqlite').write_bytes(b'broken index')
            self.assertEqual(result['events'],trace.query(subject={'id':'1'},offset=5,limit=7,boundary=boundary)['events'])
            index_path=trace.path.with_suffix('.ctr.index.sqlite')
            with closing(sqlite3.connect(index_path)) as database, database:
                database.execute("UPDATE meta SET value='broken' WHERE key='end'")
            self.assertEqual(result['events'],trace.query(subject={'id':'1'},offset=5,limit=7,boundary=boundary)['events'])
            with ThreadPoolExecutor(max_workers=4) as workers:
                queries=[workers.submit(trace.query,subject={'id':'1'},offset=5,limit=7,boundary=boundary) for _ in range(12)]
                for i in range(10):trace.emit(clock,kind='later',after=i)
                self.assertTrue(all(task.result()['events']==result['events'] for task in queries))


if __name__=='__main__':unittest.main()
