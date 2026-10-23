"""Delayed, named default cases for rent and advance claims."""
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
from labor_institutions import EnforcementCase
from livelihood_access import remove_access


def _plot_access_shares(region, person_id, plot_id):
    totals = {}
    for right in getattr(region, 'access_rights', {}).get(int(person_id), ()):
        if right.plot_id != plot_id:
            continue
        resource = str(right.resource)
        amounts = totals.setdefault(resource, {'legal': 0.0, 'usable': 0.0})
        amounts['legal'] += float(right.legal_share)
        amounts['usable'] += float(right.usable_share)
    return totals


def _trace_case(region, turn, case, reason, *, state_before, inputs=None,
                cause_event_ids=None):
    from run_trace import emit

    return emit(
        region, kind='labor_enforcement_case', record_class='outcome',
        phase='labor_enforcement',
        subject={'type': 'labor_case', 'id': case.id,
                 'tile': getattr(region, 'name', 'unknown')},
        metric_id='labor.enforcement_case', unit='case_state',
        before=state_before, after=case.state,
        formula_id='labor.enforcement_case_resolution.v1',
        inputs={'case_id': int(case.id), 'case_kind': case.kind,
                'turn': int(turn),
                'target_person_id': int(case.target_person_id),
                'target_plot_id': case.target_plot_id,
                'claim_id': case.claim_id, 'reason': reason,
                'outcome': case.outcome,
                'officer_cost': float(case.officer_cost),
                **(inputs or {})},
        cause_event_ids=cause_event_ids)


def _pay_constable(region, turn, case, payer, payee, *, amount=1.0):
    payer_before = float(payer.cash)
    payee_before = float(payee.cash)
    _trace_cash_write = _trace_public_begin(None, payer)
    payer.cash -= amount
    _trace_public_finish(_trace_cash_write, 'labor_cases:_pay_constable',
                         inputs={"source_writer": 'labor_cases.py:_pay_constable:c01ef6a5e2a129b8:1'})
    _trace_cash_write = _trace_public_begin(None, payee)
    payee.cash += amount
    _trace_public_finish(_trace_cash_write, 'labor_cases:_pay_constable',
                         inputs={"source_writer": 'labor_cases.py:_pay_constable:d91309f7c3aa7800:1'})
    currency = getattr(region, 'home_currency', None) or 'local_currency'
    operation_id = f'labor-enforcement:{region.name}:{turn}:{case.id}'
    from finance_trace import (account_ref, cash_transfer_contract,
                               emit_cash_transfer)
    contract = cash_transfer_contract(
        operation_id, 'labor_enforcement_service', amount=amount,
        currency=currency,
        payer_account=account_ref(
            'government', payer.id, currency,
            balance_before=payer_before, balance_after=float(payer.cash),
            balance_scope='cash'),
        payee_account=account_ref(
            'agent', payee.id, currency,
            balance_before=payee_before, balance_after=float(payee.cash),
            balance_scope='cash'),
        mutation_reference={'turn': int(turn), 'case_id': int(case.id),
                            'tile': region.name})
    event_id = emit_cash_transfer(
        region, kind='labor_enforcement_officer_payment', contract=contract,
        phase='labor_enforcement',
        subject={'type': 'labor_case', 'id': case.id,
                 'tile': getattr(region, 'name', 'unknown')},
        inputs={'turn': int(turn), 'case_id': int(case.id),
                'case_kind': case.kind,
                'officer_id': int(payee.id),
                'service': 'debt_collection' if case.kind in
                ('foreclosure', 'quit_penalty') else 'vagrancy_confinement'})
    return event_id


def _trace_vagrancy_gate(region, turn, *, law_active, workhouse_active):
    from run_trace import emit

    reason = ('vagrancy_law_inactive' if not law_active else
              'workhouse_unavailable' if not workhouse_active else 'eligible')
    return emit(
        region, kind='labor_vagrancy_enforcement_gate',
        record_class='observation', phase='labor_enforcement',
        subject={'type': 'tile', 'id': getattr(region, 'name', 'unknown')},
        metric_id='labor.enforcement_gate', unit='status',
        after=reason, formula_id='labor.vagrancy_enforcement_gate.v1',
        inputs={'turn': int(turn), 'law_active': bool(law_active),
                'workhouse_active': bool(workhouse_active),
                'pending_case_count': sum(
                    1 for case in getattr(region, 'enforcement_cases', [])
                    if case.kind == 'vagrancy' and case.state == 'pending')})


def process_default_cases(region, turn):
    cases = getattr(region, 'enforcement_cases', [])
    claims = getattr(region, 'cash_obligations', [])
    by_id = {a.id: a for a in getattr(region, 'agents', [])}
    for claim in claims:
        if (claim.status != 'active' or claim.due_turn > turn or claim.balance <= 0
                or claim.origin not in ('rent', 'survey', 'advance', 'quit_penalty')):
            continue
        if any(c.claim_id == claim.id and c.state == 'pending' for c in cases):
            continue
        cid = int(getattr(region, '_next_case_id', 1))
        region._next_case_id = cid + 1
        kind = 'quit_penalty' if claim.origin == 'quit_penalty' else 'foreclosure'
        case = EnforcementCase(cid, kind, claim.debtor_id,
                               claim.collateral_plot_id, claim.id, turn, turn + 1)
        cases.append(case)
        _trace_case(region, turn, case, 'overdue_claim_awaiting_hearing',
                    state_before='not_created',
                    inputs={'claim_origin': claim.origin,
                            'claim_balance': float(claim.balance),
                            'claim_due_turn': int(claim.due_turn),
                            'claim_status': claim.status,
                            'requested_turn': int(turn),
                            'earliest_hearing_turn': int(turn + 1),
                            'collateral_plot_id': claim.collateral_plot_id})
    police = max(0, int(getattr(region, 'police_employed', 0)))
    garrison = any(getattr(u, 'strength', 0) > 5 for u in getattr(region, 'military_units', []))
    constables = sorted((a for a in getattr(region, 'agents', []) if a.alive and
                         (getattr(a, 'is_police', False) or a.social_class == 'constable')),
                        key=lambda a: a.id)
    resolved = []
    for case in sorted(cases, key=lambda c: c.id):
        if case.kind not in ('foreclosure', 'quit_penalty') or case.state != 'pending' or case.earliest_turn > turn:
            continue
        state_before = case.state
        claim = next((c for c in claims if c.id == case.claim_id), None)
        if claim is None or claim.status in ('paid', 'canceled'):
            case.state, case.outcome = 'closed', 'claim settled before hearing'
            _trace_case(region, turn, case, 'claim_settled_before_hearing',
                        state_before=state_before,
                        inputs={'claim_status': getattr(claim, 'status', 'missing')})
            continue
        if case.target_person_id not in by_id:
            case.state, case.outcome = 'closed', 'debtor absent'
            _trace_case(region, turn, case, 'debtor_absent',
                        state_before=state_before)
            continue
        if police <= 0 and not garrison:
            case.outcome = 'pending: no enforcement capacity'
            _trace_case(region, turn, case, 'no_enforcement_capacity',
                        state_before=state_before,
                        inputs={'police_capacity_remaining': police,
                                'garrison_available': garrison})
            continue
        payment_event_id = None
        officer_id = None
        if police > 0:
            gov_agent = getattr(getattr(region, 'gov', None), 'agent', None)
            payee = next((a for a in constables if a.id not in (case.target_person_id, claim.creditor_id)), None)
            if payee is None or gov_agent is None or gov_agent.cash < 1.0:
                case.outcome = 'pending: no funded constable payee'
                reason = ('eligible_constable_missing' if payee is None else
                          'government_treasury_missing' if gov_agent is None else
                          'treasury_cannot_fund_constable')
                _trace_case(region, turn, case, reason,
                            state_before=state_before,
                            inputs={'police_capacity_remaining': police,
                                    'garrison_available': garrison,
                                    'treasury_cash': (float(gov_agent.cash)
                                                      if gov_agent else None),
                                    'eligible_constable_found': payee is not None})
                continue
            payment_event_id = _pay_constable(
                region, turn, case, gov_agent, payee)
            officer_id = payee.id
            case.officer_cost = 1.0
            police -= 1
        debtor = by_id[case.target_person_id]
        plot = region.tenure.find_plot(case.target_plot_id) if case.target_plot_id and getattr(region, 'tenure', None) else None
        if case.kind == 'quit_penalty':
            case.state, case.outcome = 'resolved', 'unpaid penalty remains a cash claim'
            resolved.append(case.id)
            _trace_case(region, turn, case, 'unpaid_quit_penalty_claim_remains',
                        state_before=state_before,
                        inputs={'police_capacity_remaining': police,
                                'garrison_available': garrison,
                                'officer_id': officer_id,
                                'claim_balance': float(claim.balance),
                                'collateral_action': 'none'},
                        cause_event_ids=([payment_event_id]
                                         if payment_event_id else None))
            continue
        if plot is None or debtor.id not in getattr(plot, 'tenant_ids', []):
            case.state, case.outcome = 'closed', 'collateral occupancy ended'
            _trace_case(region, turn, case, 'collateral_occupancy_ended',
                        state_before=state_before,
                        inputs={'police_capacity_remaining': police,
                                'garrison_available': garrison,
                                'officer_id': officer_id,
                                'claim_balance': float(claim.balance),
                                'collateral_plot_found': plot is not None,
                                'debtor_occupies_collateral': bool(
                                    plot is not None and debtor.id in
                                    getattr(plot, 'tenant_ids', []))},
                        cause_event_ids=([payment_event_id]
                                         if payment_event_id else None))
            continue
        plot.tenant_ids.remove(debtor.id)
        debtor.assigned_plot_id = None
        debtor.social_class = 'dispossessed'
        debtor.mem_push('mem_debt_trap', 1.0)
        debtor.mem_push('mem_eviction', 1.0)
        access_before = _plot_access_shares(region, debtor.id, plot.plot_id)
        remove_access(region, debtor.id, plot.plot_id)
        access_after = _plot_access_shares(region, debtor.id, plot.plot_id)
        case.state, case.outcome = 'resolved', 'evicted after delayed foreclosure'
        region.access_events = (getattr(region, 'access_events', []) + [
            {'turn': turn, 'person_id': debtor.id, 'plot_id': plot.plot_id,
             'cause': 'foreclosure', 'claim_id': claim.id}
        ])[-500:]
        resolved.append(case.id)
        if police:
            police -= 1
        _trace_case(region, turn, case, 'foreclosure_eviction',
                    state_before=state_before,
                    inputs={'police_capacity_remaining': police,
                            'garrison_available': garrison,
                            'officer_id': officer_id,
                            'claim_balance': float(claim.balance),
                            'plot_id': plot.plot_id,
                            'tenant_removed': debtor.id not in plot.tenant_ids,
                            'access_shares_before': access_before,
                            'access_shares_after': access_after,
                            'access_removed': access_before != access_after,
                            'debtor_social_class_after': debtor.social_class},
                    cause_event_ids=([payment_event_id]
                                     if payment_event_id else None))
    region.enforcement_cases = cases
    return resolved


def process_vagrancy_cases(region, turn):
    from workhouse import has_workhouse
    cases = getattr(region, 'enforcement_cases', [])
    law_active = bool(getattr(region, 'vagrancy_law_active', False))
    workhouse_active = bool(has_workhouse(region))
    gate_event_id = _trace_vagrancy_gate(
        region, turn, law_active=law_active,
        workhouse_active=workhouse_active)
    if not law_active or not workhouse_active:
        return []
    case_open_event_ids = {}
    for person in sorted(region.agents, key=lambda a: a.id):
        dispossessed = person.social_class == 'dispossessed'
        plotless_poor = (getattr(person, 'assigned_plot_id', None) is None
                         and person.cash < 5.0)
        if (person.alive and not person.is_trader and not person.is_government
                and not getattr(person, 'is_police', False) and person.social_class != 'constable'
                and not getattr(person, 'is_lord', False) and person.employer is None
                and not getattr(person, 'in_workhouse', False)
                and (dispossessed or plotless_poor)
                and not any(c.kind == 'vagrancy' and c.target_person_id == person.id
                            and c.state == 'pending' for c in cases)):
            cid = int(getattr(region, '_next_case_id', 1))
            region._next_case_id = cid + 1
            case = EnforcementCase(cid, 'vagrancy', person.id, None, None,
                                  turn, turn)
            cases.append(case)
            open_event_id = _trace_case(
                region, turn, case, 'vagrancy_eligibility_met',
                state_before='not_created',
                inputs={'candidate_reasons': [
                            code for code, eligible in (
                                ('dispossessed', dispossessed),
                                ('plotless_cash_below_5', plotless_poor))
                            if eligible],
                                'person_cash': float(person.cash),
                                'assigned_plot_id': getattr(
                                    person, 'assigned_plot_id', None),
                                'employer_id': getattr(
                                    getattr(person, 'employer', None), 'id', None),
                                'vagrancy_law_active': law_active,
                                'workhouse_active': workhouse_active})
            if open_event_id is not None:
                case_open_event_ids[case.id] = open_event_id
    capacity = max(0, int(getattr(region, 'police_employed', 0)))
    has_garrison = any(getattr(u, 'strength', 0) > 5
                       for u in getattr(region, 'military_units', []))
    constables = sorted((a for a in region.agents if a.alive and
                         (getattr(a, 'is_police', False) or a.social_class == 'constable')),
                        key=lambda a: a.id)
    resolved = []
    for case in sorted(cases, key=lambda c: c.id):
        if case.kind != 'vagrancy' or case.state != 'pending' or case.earliest_turn > turn:
            continue
        state_before = case.state
        target = next((a for a in region.agents if a.id == case.target_person_id and a.alive), None)
        if target is None or not getattr(region, 'vagrancy_law_active', False):
            case.state, case.outcome = 'closed', 'target absent or law repealed'
            _trace_case(region, turn, case,
                        'target_absent' if target is None else 'vagrancy_law_repealed',
                        state_before=state_before,
                        inputs={'police_capacity_remaining': capacity,
                                'garrison_available': has_garrison},
                        cause_event_ids=[event_id for event_id in (
                            gate_event_id, case_open_event_ids.get(case.id))
                            if event_id] or None)
            continue
        if capacity <= 0 and not has_garrison:
            case.outcome = 'pending: no enforcement capacity'
            _trace_case(region, turn, case, 'no_enforcement_capacity',
                        state_before=state_before,
                        inputs={'police_capacity_remaining': capacity,
                                'garrison_available': has_garrison},
                        cause_event_ids=[event_id for event_id in (
                            gate_event_id, case_open_event_ids.get(case.id))
                            if event_id] or None)
            continue
        payment_event_id = None
        officer_id = None
        if capacity > 0:
            gov_agent = getattr(getattr(region, 'gov', None), 'agent', None)
            if not constables or gov_agent is None or gov_agent.cash < 1.0:
                case.outcome = 'pending: no funded constable payee'
                reason = ('eligible_constable_missing' if not constables else
                          'government_treasury_missing' if gov_agent is None else
                          'treasury_cannot_fund_constable')
                _trace_case(region, turn, case, reason,
                            state_before=state_before,
                            inputs={'police_capacity_remaining': capacity,
                                    'garrison_available': has_garrison,
                                    'treasury_cash': (float(gov_agent.cash)
                                                      if gov_agent else None),
                                    'eligible_constable_found': bool(constables)},
                            cause_event_ids=[event_id for event_id in (
                                gate_event_id, case_open_event_ids.get(case.id))
                                if event_id] or None)
                continue
            constable = constables[(len(resolved)) % len(constables)]
            payment_event_id = _pay_constable(
                region, turn, case, gov_agent, constable)
            officer_id = constable.id
            capacity -= 1
            case.officer_cost = 1.0
        former_employer = target.employer
        if former_employer is not None:
            if target in getattr(former_employer, 'employees', []):
                former_employer.employees.remove(target)
            target.employer = None
        target.in_workhouse = True
        case_cause_event_ids = [event_id for event_id in (
            gate_event_id, case_open_event_ids.get(case.id), payment_event_id)
            if event_id]
        from labor_choice import record_labor_status
        record_labor_status(region, target, turn,
                            before='employed' if former_employer is not None else 'independent',
                            after='workhouse', reason='funded_vagrancy_hearing',
                            employer_before=former_employer,
                            cause_event_ids=case_cause_event_ids or None)
        target.social_class = 'dispossessed'
        target.mem_push('mem_workhouse', 1.0)
        case.state, case.outcome = 'resolved', 'confined after funded vagrancy hearing'
        resolved.append(case.id)
        _trace_case(region, turn, case, 'vagrancy_confinement',
                    state_before=state_before,
                    inputs={'police_capacity_remaining': capacity,
                            'garrison_available': has_garrison,
                            'officer_id': officer_id,
                            'officer_cost': float(case.officer_cost),
                            'enforcement_force': ('police' if officer_id is not None
                                                  else 'garrison'),
                            'former_employer_id': getattr(former_employer, 'id', None),
                            'in_workhouse_after': bool(target.in_workhouse),
                            'target_social_class_after': target.social_class},
                    cause_event_ids=case_cause_event_ids or None)
    region.enforcement_cases = cases
    return resolved
