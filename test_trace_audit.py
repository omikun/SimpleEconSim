from pathlib import Path
import tempfile
import unittest
from run_trace import RunTrace
from trace_audit import audit
import json
import subprocess
import sys
from trace_codec import CompactTraceWriter, iter_payloads


class TraceAuditTests(unittest.TestCase):
    def test_decoded_byte_count_matches_streamed_export(self):
        with tempfile.TemporaryDirectory() as directory:
            trace=RunTrace(Path(directory)/'cache.ctr','cache');clock={'turn':1,'next':1}
            subject={'type':'tile','id':'A','good':'food'}
            opening=trace.emit(clock,kind='native_sample',record_class='calculation',
                               metric_id='economy.gini',subject=subject,after=.5,
                               formula_id='aggregate.sum.v1',inputs={'member_values':[.2,.3]})
            for number in range(40):
                noise=trace.emit(clock,kind='other_sample',metric_id='economy.gini',subject=subject,after=.5)
                if number%5==0:
                    trace.emit(clock,kind='other_retained',record_class='calculation',
                               metric_id='economy.gini',subject=subject,after=.5,
                               formula_id='gini.recorded_sample.v1',
                               inputs={'sampled_gini':.5,'source_event_id':noise},cause_event_ids=[noise])
            for _ in range(20):
                trace.emit(clock,kind='retained',record_class='calculation',
                           metric_id='economy.gini',subject=subject,after=.5,
                           formula_id='gini.recorded_sample.v1',
                           inputs={'sampled_gini':.5,'source_event_id':opening},cause_event_ids=[opening])
            trace.checkpoint(clock)
            result=audit(trace.path)
            self.assertTrue(result['structural_and_supported_formula_checks_pass'])
            export=Path(directory)/'decoded.jsonl'
            subprocess.run([sys.executable,str(Path(__file__).with_name('trace_report.py')),
                            '--run',str(trace.path),'--decode-jsonl',str(export)],check=True,capture_output=True)
            self.assertEqual(export.stat().st_size,result['decoded_trace_bytes'])

    def test_malformed_required_contract_is_a_failure_report(self):
        with tempfile.TemporaryDirectory() as directory:
            trace=RunTrace(Path(directory)/'original.ctr','malformed');clock={'turn':1,'next':1}
            trace.emit(clock,kind='bad_inputs',record_class='calculation',after=0)
            path=Path(directory)/'malformed.ctr'
            writer=CompactTraceWriter(path)
            for payload in iter_payloads(trace.path):
                row=json.loads(payload)
                if row.get('kind')=='bad_inputs':
                    row.update(formula_id='treasury.account_chain.v1',inputs={})
                writer.append(json.dumps(row,sort_keys=True,separators=(',',':')))
            writer.close()
            result=audit(path)
            self.assertFalse(result['structural_and_supported_formula_checks_pass'])
            self.assertEqual(1,result['counts']['malformed_source_contract_inputs'])
            self.assertEqual(1,result['counts']['malformed_formula_inputs'])

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

    def test_omitted_required_link_fails_even_with_matching_balance(self):
        with tempfile.TemporaryDirectory() as d:
            trace=RunTrace(Path(d)/'required.ctr','required');clock={'turn':1,'next':1}
            subject={'type':'public_account','id':'A'}
            opening=trace.emit(clock,kind='opening',after=10,subject=subject)
            operation=trace.emit(clock,kind='public_account_write',before=10,after=12,subject=subject)
            trace.emit(clock,kind='public_account_close',record_class='calculation',
                       metric_id='finance.public_account_balance',subject=subject,before=10,after=12,
                       formula_id='treasury.account_chain.v1',
                       inputs={'opening_balance':10,'opening_source_event_id':opening,
                               'operations':[{'event_id':operation,'before':10,'after':12}]},
                       cause_event_ids=[opening])
            result=audit(trace.path)
            self.assertFalse(result['structural_and_supported_formula_checks_pass'])
            self.assertEqual(1,result['counts']['source_contract_failures'])
            self.assertEqual(1,result['counts']['formula_verified'])
            self.assertEqual('required_cause_not_declared',result['issues'][0]['source_contract_issues'][0]['problem'])

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
