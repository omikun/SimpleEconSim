from pathlib import Path
import tempfile
import unittest
from run_trace import RunTrace
from trace_audit import audit


class TraceAuditTests(unittest.TestCase):
    def test_missing_cause_is_not_hidden_by_numeric_agreement(self):
        with tempfile.TemporaryDirectory() as d:
            trace=RunTrace(Path(d)/'audit.ctr','audit');clock={'turn':1,'next':1}
            trace.emit(clock,kind='result',record_class='calculation',metric_id='x',after=3,
                       formula_id='aggregate.sum.v1',inputs={'member_values':[1,2]},cause_event_ids=['missing:1'])
            trace.checkpoint(clock)
            result=audit(trace.path)
            self.assertFalse(result['structural_and_supported_formula_checks_pass'])
            self.assertEqual(1,result['counts']['unresolved_causes'])
            self.assertEqual(1,result['counts']['formula_verified'])

    def test_price_snapshot_requires_ordered_bridge(self):
        with tempfile.TemporaryDirectory() as d:
            trace=RunTrace(Path(d)/'price.ctr','price');clock={'turn':1,'next':1}
            subject={'type':'tile','id':'A','good':'food'}
            trace.emit(clock,kind='unverified_price',record_class='calculation',subject=subject,
                       metric_id='goods.price',before=1,after=2)
            trace.snapshot(clock,subject=subject,metric_id='goods.price',unit='C',before=1,after=2)
            snapshot=next(r for r in trace.recent if r['kind']=='metric_snapshot')
            self.assertEqual('source_missing',snapshot['explanation_status'])
            # Even if a later outcome happens to equal final price, a broken
            # chain must not become complete snapshot coverage.
            trace.price_bridge(clock,subject=subject,before=0,after=2,unit='C')
            trace.snapshot(clock,subject=subject,metric_id='goods.price',unit='C',before=0,after=2)
            self.assertEqual('source_missing',list(trace.recent)[-2]['explanation_status'])


if __name__=='__main__':unittest.main()
