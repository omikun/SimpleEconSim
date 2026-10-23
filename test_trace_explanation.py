"""All clients receive identical values and honest evidence status."""
from pathlib import Path
import tempfile
import unittest
from trace_explanation import describe, ExplanationReader
from run_trace import RunTrace


class TraceExplanationTests(unittest.TestCase):
    def test_unknown_formula_and_missing_source_do_not_become_verified(self):
        row={'kind':'calculation','record_class':'calculation','metric_id':'x','value_after':7,
             'formula_id':'unknown.v1','inputs':{'result':7}}
        self.assertEqual('unverified_formula',describe(row)['status'])
        row.update(formula_id='aggregate.sum.v1',inputs={'member_values':[3,4]},cause_event_ids=['missing'])
        result=describe(row,lambda ident:None)
        self.assertEqual('evidence_gap',result['status'])
        self.assertEqual('source_event_missing',result['issues'][0]['problem'])

    def test_treasury_receipts_spending_membership_and_residual_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            trace=RunTrace(Path(directory)/'treasury.ctr','treasury');clock={'turn':2,'next':1}
            subject={'type':'nation','id':'A'}
            receipt=trace.emit(clock,kind='tax',metric_id='finance.treasury_flow',after=30)
            expense=trace.emit(clock,kind='payroll',metric_id='finance.treasury_flow',after=-10)
            trace.emit(clock,kind='treasury_reconciliation',subject=subject,cause_event_ids=[receipt,expense])
            row_id=trace.emit(clock,kind='treasury_account_closure',subject=subject,
                             metric_id='finance.treasury',before=1000,after=1225,unit='C',
                             inputs={'steps':[{'type':'transition','before':{'accounts':{}},
                                       'after':{'accounts':{'new':{'balance':200}}}}],
                                     'required_accounts':[]})
            reader=ExplanationReader(trace.path)
            result=reader.explain(reader.lookup(row_id))
            money=result['treasury']
            self.assertEqual(30,money['recorded_receipts'])
            self.assertEqual(10,money['recorded_spending'])
            self.assertEqual(200,money['membership_effect'])
            self.assertEqual(5,money['unclassified_flow_residual'])
            self.assertFalse(money['flow_classification_complete'])
            self.assertEqual(1225,result['after'])


if __name__=='__main__':unittest.main()
