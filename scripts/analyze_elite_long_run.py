"""Summarize observed elite campaigns without changing or rerunning the economy."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def load_rows(folder, name):
    with gzip.open(folder / (name + '.jsonl.gz'), 'rt') as stream:
        return [json.loads(line) for line in stream]


def commercial(actor):
    return actor['is_corporation'] and not actor['is_lord']


def finances(actors):
    result = {}
    for currency in sorted({a['currency'] for a in actors}):
        group = [a for a in actors if a['currency'] == currency]
        result[currency] = dict(count=len(group), cash=sum(a['cash'] for a in group),
            deposits=sum(a['deposits_by_currency'].get(currency, 0) for a in group),
            bank_principal=sum(a['bank_debt_by_currency'].get(currency, 0) for a in group),
            cash_deposits_less_bank_principal=sum(a['financial_home'] for a in group))
    return result


def describe(folder):
    summary = json.loads((folder/'summary.json').read_text())
    if summary['turns_completed'] != 100 or not summary['source_unchanged']:
        raise ValueError('Analysis requires a completed, source-stable 100-turn run')
    actors, decisions, events, statements, searches = [load_rows(folder, n) for n in
        ('actors', 'decisions', 'economic_events', 'statements', 'searches')]
    initial = {a['id']:a for a in actors if a['turn'] == 0}
    end = {a['id']:a for a in actors if a['turn'] == 100}
    history = {(a['turn'], a['id']):a for a in actors}
    lord_ids = {i for i, a in initial.items() if a['is_lord']}
    corps = [a for a in end.values() if commercial(a) and a['alive'] and a['present']]
    production = defaultdict(float)
    for e in events:
        if e['kind'] == 'production':
            production[e['turn'], e['recipient_id']] += e['quantity']
    producing = {i for (t, i), q in production.items() if t >= 91 and q > 0}
    expansions = []
    for d in decisions:
        if d['result']['action_taken'] != 'CAPITAL_EXPANSION':
            continue
        target, turn = d['result']['details']['company_id'], d['turn']
        before, after = history.get((turn-1, target)), history.get((turn+5, target))
        if before and before['first_seen'] <= turn-5 and before['employees'] == 0 and not any(production[t, target] for t in range(max(1,turn-5), turn)):
            expansions.append(dict(turn=turn, target=target, payer=d['actor_id'],
                currency=d['before']['currency'], injection=d['result']['details']['injection'],
                employees_five_turns_later=None if after is None else after['employees'],
                produced_next_five=None if after is None else sum(production[t,target] for t in range(turn,turn+6))))
    corp_decisions = [d for d in decisions if commercial(d['before'])]
    lord_decisions = [d for d in decisions if d['before']['is_lord']]
    input_sales = [d for d in corp_decisions if (d['result']['action_taken'] or '').startswith('LIQUIDATE')
                   and d['before']['employees'] > 0
                   and d['result']['details'].get('good') == d['before']['input_good']
                   and d['after']['nominal_input_gap'] > d['before']['nominal_input_gap']]
    residuals = [s for s in statements if abs(s['unposted_cash_change']) > .011]
    wages = {}
    corp_ids = {a['id'] for a in corps}
    for currency in sorted({a['currency'] for a in corps}):
        wages[currency] = {kind:sum(e['amount'] for e in events if e['kind'] == kind
                                  and e['payer_id'] in corp_ids and e['currency'] == currency)
                           for kind in ('wage', 'scrip_wage')}
    rents = {c:sum(e['amount'] for e in events if e['kind'] == 'rent' and e['recipient_id'] in lord_ids
                  and e['currency'] == c) for c in sorted({a['currency'] for a in initial.values()})}
    matched_firm = {}
    for turn in (44,45,50,55,60,100):
        actor = history.get((turn,1768))
        if actor:
            matched_firm[str(turn)] = actor
    window = [e for e in events if 45 <= e['turn'] <= 50]
    result = dict(metadata=summary['metadata'], turns_completed=100, elapsed=summary['elapsed'],
        source_unchanged=True, final_population=summary['progress'][-1]['population'],
        corporations=dict(legal_entities=sum(a['is_corporation'] for a in end.values()),
            commercial_entities=len(corps), staffed=sum(a['employees']>0 for a in corps),
            produced_last_ten_turns=sum(a['id'] in producing for a in corps),
            finances=finances(corps), actions=dict(Counter(d['result']['action_taken'] or 'do_nothing' for d in corp_decisions)),
            input_liquidations_worsening_shortage=len(input_sales), input_liquidation_examples=input_sales[:3], payroll=wages),
        initial_lords=dict(count=len(lord_ids), alive_present=sum(end[i]['alive'] and end[i]['present'] for i in lord_ids),
            dual_corporate_survivors=sum(end[i]['is_corporation'] and end[i]['alive'] for i in lord_ids),
            initial_finances=finances(list(initial.values())),
            final_survivor_finances=finances([end[i] for i in lord_ids if end[i]['alive'] and end[i]['present']]),
            gross_rent_receipts=rents,
            actions=dict(Counter(d['result']['action_taken'] or 'do_nothing' for d in lord_decisions))),
        expansions=dict(unstaffed_nonproducing_targets=len(expansions),
            followup_available=sum(x['employees_five_turns_later'] is not None for x in expansions),
            still_unstaffed_five_turns_later=sum(x['employees_five_turns_later']==0 for x in expansions),
            no_staff_or_output_five_turns_later=sum(x['employees_five_turns_later']==0 and x['produced_next_five']==0 for x in expansions),
            examples=expansions[:8]),
        search=dict(requests=len(searches), reasons=dict(Counter(s['reason'] for s in searches)),
                    expanded_states=sum(s['expanded'] for s in searches), searches_that_expanded=[s for s in searches if s['expanded']]),
        experimental_decisions=[d for d in decisions if d['result']['action_taken'] in ('PRODUCTION_PLAN','WAIT_INPUT','DECLINE_INPUT')],
        firm_1768=dict(history=matched_firm,
            wages_45_to_50=sum(e['amount'] for e in window if e['kind']=='wage' and e['payer_id']==1768),
            production_45_to_50=sum(e['quantity'] for e in window if e['kind']=='production' and e['recipient_id']==1768)),
        accounting=dict(statements=len(statements), nonzero_cash_residuals=len(residuals),
            largest_cash_residual=max((abs(s['unposted_cash_change']) for s in residuals),default=0),
            world_violation_rows=sum(bool(p['violations']) for p in summary['progress'])),
        raw_files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                   for p in folder.glob('*.jsonl.gz')})
    return result, history


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--active', type=Path, required=True)
    parser.add_argument('--off', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    active, aa = describe(args.active)
    off, bb = describe(args.off)
    if active['metadata']['initial_actors'] != off['metadata']['initial_actors']:
        raise ValueError('Starting tracked actors differ')
    first = min((t for (t,i) in aa.keys()|bb.keys() if aa.get((t,i)) != bb.get((t,i))),default=None)
    result = dict(active=active, off=off, first_tracked_elite_difference=first,
                  raw_directories={'active':str(args.active),'off':str(args.off)},
                  limits=['One seed; later random/event paths diverge',
                          'Cash/deposit/principal figures are not net worth; inventory, land, equity and scrip are not valued',
                          'Legal company presence is not proof of business survival; closure flags were not captured',
                          'Nonzero actor cash-statement residuals preclude a fully reconciled profit claim'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('first_tracked_elite_difference','limits')},indent=2))


if __name__ == '__main__':
    main()
