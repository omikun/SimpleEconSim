"""Shared, read-only player explanations for web, desktop and CLI records."""
from functools import lru_cache
import math

from causal_contracts import validate
from price_trace import replay_event
from trace_index import TraceIndex


LABELS={'observation':'Observation','forecast':'Forecast','recorded_decision':'Recorded decision',
        'verified_formula':'Verified formula','verified_chain':'Verified local chain',
        'unverified_formula':'Unverified calculation','evidence_gap':'Missing or inconsistent evidence'}


def _same(a,b):
    return isinstance(a,(int,float)) and isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8)


def describe(row,lookup=None,related=()):
    """Explain one record; verify local links without inventing missing causes."""
    problems=[];formula=None;contract=None;i=row.get('inputs') or {};sources=[]
    try:formula=replay_event(row) if row.get('formula_id') else None
    except (KeyError,TypeError,ValueError,ZeroDivisionError) as error:problems.append({'problem':'formula_input_error','detail':str(error)})
    if lookup is not None:
        try:contract=validate(row,lookup)
        except (KeyError,TypeError,ValueError) as error:problems.append({'problem':'source_contract_error','detail':str(error)})
        for ident in row.get('cause_event_ids') or ():
            source=lookup(ident)
            if source is None:problems.append({'problem':'source_event_missing','event_id':ident})
            else:
                account=next((account for account in i.get('accounts',i.get('required_accounts',())) if account.get('source_event_id')==ident),None)
                if account:
                    label=f"{account.get('tier','public').capitalize()} {account.get('account_kind','account')}: {account['opening']:,.3f} → {account['closing']:,.3f}"
                else:
                    label=str((source.get('inputs') or {}).get('operation_kind') or source.get('kind','record')).replace('_',' ').capitalize()
                    if isinstance(source.get('delta'),(int,float)):label+=f" · {source['delta']:+,.3f} {source.get('unit','')}"
                sources.append({'event_id':ident,'label':label,'turn':source.get('turn')})
    if row.get('record_class')=='calculation' and not row.get('formula_id'):
        problems.append({'problem':'calculation_formula_missing'})
    if formula is not None and not formula['matches']:problems.append({'problem':'formula_mismatch'})
    if contract is not None:problems.extend(contract['issues'])
    status=row.get('explanation_status','')
    if status in {'source_missing','account_chain_gap','balance_chain_gap','composition_chain_gap','mutation_chain_incomplete'}:
        problems.append({'problem':status})
    if row.get('kind')=='price_bridge':
        running=row.get('value_before')
        for step in i['steps']:
            if running is not None and not _same(running,step['before']):problems.append({'problem':'price_chain_discontinuity','event_id':step.get('event_id')})
            running=step['after']
        if not _same(running,row.get('value_after')):problems.append({'problem':'price_chain_closing_mismatch'})
    observed=(row.get('record_class')=='observation' or str(row.get('formula_id','')).endswith('sample.v1'))
    if problems:state='evidence_gap'
    elif row.get('record_class')=='forecast' or i.get('evidence_scope')=='diagnostic_preflight_snapshot':state='forecast'
    elif row.get('kind')=='price_bridge' and contract is not None:state='verified_chain'
    elif formula is not None and formula['matches']:
        state='verified_chain' if contract is not None else 'verified_formula'
    elif observed:state='observation'
    elif row.get('record_class')=='decision':state='recorded_decision'
    elif row.get('formula_id'):state='unverified_formula'
    else:state='observation'
    contributors=[]
    for name,value in i.get('raw_sources',{}).items():contributors.append({'label':name.replace('_',' '),'value':value})
    for step in i.get('steps',[]):
        if 'before' in step and 'after' in step and isinstance(step['before'],(int,float)) and isinstance(step['after'],(int,float)):
            contributors.append({'label':step.get('kind',step.get('operation_kind','account write')),
                                 'value':step['after']-step['before'],'event_id':step.get('event_id')})
    contributors.sort(key=lambda item:abs(item['value']),reverse=True)
    notes=[]
    if state=='verified_formula':notes.append('Arithmetic verified from recorded inputs; upstream provenance is not fully covered.')
    if state=='verified_chain':notes.append('Recorded changes reconcile with the closing value. Open a source below to inspect its evidence.')
    if state=='unverified_formula':notes.append('The formula is recorded but has no supported independent replay.')
    result={'event_id':row.get('event_id'),'status':state,'label':LABELS[state],
            'turn':row.get('turn'),'epoch':row.get('epoch',0),'subject':row.get('subject'),
            'metric_id':row.get('metric_id'),'unit':row.get('unit'),
            'before':row.get('value_before'),'after':row.get('value_after'),
            'formula':formula,'required_sources':contract,
            'contributors':contributors,'issues':problems,'notes':notes,
            'cause_event_ids':list(row.get('cause_event_ids') or ()), 'sources':sources}
    if row.get('kind')=='treasury_account_closure':
        receipts=spending=None;membership=0.0
        for step in i.get('steps',()):
            if step.get('type')!='transition':continue
            old,new=step['before']['accounts'],step['after']['accounts']
            membership+=sum(new[k]['balance'] for k in new.keys()-old.keys())-sum(old[k]['balance'] for k in old.keys()-new.keys())
        reconciliation=next((r for r in related if r.get('kind')=='treasury_reconciliation'
                             and r.get('epoch',0)==row.get('epoch',0)),None)
        flows=[]
        if reconciliation is not None and lookup is not None:
            flows=[lookup(ident) for ident in reconciliation.get('cause_event_ids',())]
            if all(flow is not None for flow in flows):
                amounts=[flow.get('value_after') for flow in flows]
                if all(isinstance(value,(int,float)) for value in amounts):
                    receipts=sum(max(0,value) for value in amounts)
                    spending=sum(max(0,-value) for value in amounts)
        accounts=i.get('accounts',i.get('required_accounts',[]))
        account_rows=[lookup(account['source_event_id']) for account in accounts] if lookup else []
        writes=[]
        if lookup:
            for account in account_rows:
                if account:
                    writes.extend(lookup(operation['event_id']) for operation in account.get('inputs',{}).get('operations',()))
        groups={}
        for write in writes:
            if write is None:continue
            inputs=write.get('inputs') or {}
            if inputs.get('operation_kind') not in {'cash_to_deposit','deposit_to_cash'}:continue
            groups.setdefault(inputs.get('operation_id'),[]).append(write)
        internal=0.0
        for ident,group in groups.items():
            if ident is not None and len(group)==2 and _same(sum(r['delta'] for r in group),0):
                internal+=sum(max(0,r['delta']) for r in group)
        residual=(row['value_after']-row['value_before']-membership-receipts+spending
                  if receipts is not None and row.get('value_before') is not None else None)
        result['treasury']={'opening':row.get('value_before'),'recorded_receipts':receipts,
                            'recorded_spending':spending,'confirmed_internal_cash_deposit_transfers':internal,
                            'membership_effect':membership,'closing':row.get('value_after'),
                            'unclassified_flow_residual':residual,
                            'flow_totals_reconciled':residual is not None and _same(residual,0),
                            'flow_classification_complete':False,
                            'accounts':accounts,'currency_conversion_applied':False,
                            'currency_semantics':i.get('currency_semantics')}
        result['notes'].append('Receipt and spending classifications are not fully verified, even when their totals reconcile.')
        result['notes'].append('Amounts follow the game treasury total; currencies were not converted.')
        if residual is None or not _same(residual,0):result['notes'].append('Recorded receipts and spending leave a residual; open the account writes to inspect it.')
    return result


class ExplanationReader:
    def __init__(self,path,boundary=None):
        self.index=TraceIndex(path);self.boundary=boundary
        self.lookup=lru_cache(maxsize=1024)(self._lookup)

    def _lookup(self,ident):
        rows=self.index.query(event_id=ident,limit=1,boundary=self.boundary)['events']
        return rows[0] if rows else None

    def explain(self,row):
        related=()
        if row.get('kind')=='treasury_account_closure':
            related=self.index.query(turn=row['turn'],subject=row['subject'],kind='treasury_reconciliation',
                                     boundary=self.boundary,limit=10000)['events']
        return describe(row,self.lookup,related)
