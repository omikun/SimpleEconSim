from pathlib import Path
import tempfile
import unittest
from run_trace import RunTrace
from trace_report import report


class TraceIndexTests(unittest.TestCase):
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


if __name__=='__main__':unittest.main()
