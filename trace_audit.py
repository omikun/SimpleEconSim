"""Streaming causal link and formula audit, independent of snapshot matching.

Event identity is stored in a temporary SQLite table to bound Python memory.
Unknown formulas are reported separately; numeric agreement is not provenance.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from price_trace import replay_event
from causal_contracts import validate as validate_sources
from trace_codec import iter_payloads


def audit(path):
    counters=Counter();issues=[];digest='0'*64;rows=0
    with tempfile.TemporaryDirectory() as directory:
        database=sqlite3.connect(str(Path(directory)/'events.sqlite'))
        database.execute('CREATE TABLE events(id TEXT PRIMARY KEY, sequence INTEGER, turn INTEGER, row TEXT)')
        previous_sequence=None
        for payload in iter_payloads(path):
            row=json.loads(payload);counters['rows']+=1
            if row.get('kind')=='turn_checkpoint':
                valid=row.get('count_before')==rows and row.get('sha256_before')==digest
                counters['checkpoints_verified' if valid else 'checkpoint_failures']+=1
            digest=hashlib.sha256((digest+payload).encode()).hexdigest();rows+=1
            ident=row.get('event_id')
            if ident is None:
                if row.get('record_class')!='metadata':counters['missing_event_ids']+=1
                continue
            sequence=row.get('sequence')
            if previous_sequence is not None and sequence<=previous_sequence:
                counters['sequence_failures']+=1
            previous_sequence=sequence
            for cause in row.get('cause_event_ids') or ():
                if database.execute('SELECT 1 FROM events WHERE id=?',(cause,)).fetchone() is None:
                    counters['unresolved_causes']+=1
                    if len(issues)<100:issues.append({'event_id':ident,'missing_cause':cause})
            def lookup(source_id):
                found=database.execute('SELECT row FROM events WHERE id=?',(source_id,)).fetchone()
                return json.loads(found[0]) if found else None
            contract=validate_sources(row,lookup)
            if contract is None:
                if row.get('formula_id'):counters['source_contract_not_supported']+=1
            elif contract['matches']:counters['source_contract_verified']+=1
            else:
                counters['source_contract_failures']+=1
                if len(issues)<100:issues.append({'event_id':ident,'source_contract_issues':contract['issues']})
            try:database.execute('INSERT INTO events VALUES(?,?,?,?)',(ident,sequence,row.get('turn'),payload))
            except sqlite3.IntegrityError:counters['duplicate_ids']+=1
            if row.get('formula_id'):
                try:replayed=replay_event(row)
                except (KeyError,TypeError,ValueError,ZeroDivisionError) as error:
                    counters['malformed_formula_inputs']+=1
                    if len(issues)<100:issues.append({'event_id':ident,'formula_error':str(error)})
                    continue
                if replayed is None:counters['formula_not_supported_by_replay']+=1
                elif replayed['matches']:counters['formula_verified']+=1
                elif row.get('record_class')=='audit':counters['expected_gap_audits']+=1
                else:
                    counters['formula_mismatches']+=1
                    if len(issues)<100:issues.append({'event_id':ident,'formula_id':row['formula_id']})
            elif row.get('record_class')=='calculation':counters['calculation_without_formula']+=1
        database.close()
    failures=sum(counters[key] for key in ('checkpoint_failures','missing_event_ids','sequence_failures',
                  'unresolved_causes','duplicate_ids','malformed_formula_inputs','formula_mismatches','source_contract_failures'))
    return {'counts':dict(counters),'structural_and_supported_formula_checks_pass':failures==0,
            'complete_causal_coverage':False,
            'limits':['Unknown formulas and missing per-metric source contracts remain unverified.',
                      'Required-source contracts cover named stock/production formulas; other metrics remain outside provenance coverage.',
                      'Explicit gap audits are retained and are not repaired by this report.'],
            'issues':issues,'issue_examples_truncated':sum(counters[k] for k in ('unresolved_causes','formula_mismatches','malformed_formula_inputs'))>len(issues)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.run),indent=2,sort_keys=True))


if __name__=='__main__':main()
