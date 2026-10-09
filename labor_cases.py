"""Delayed, named default cases for rent and advance claims."""
from labor_institutions import EnforcementCase
from livelihood_access import remove_access


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
        cases.append(EnforcementCase(cid, kind, claim.debtor_id,
                                     claim.collateral_plot_id, claim.id, turn, turn + 1))
    police = max(0, int(getattr(region, 'police_employed', 0)))
    garrison = any(getattr(u, 'strength', 0) > 5 for u in getattr(region, 'military_units', []))
    resolved = []
    for case in sorted(cases, key=lambda c: c.id):
        if case.kind not in ('foreclosure', 'quit_penalty') or case.state != 'pending' or case.earliest_turn > turn:
            continue
        claim = next((c for c in claims if c.id == case.claim_id), None)
        if claim is None or claim.status in ('paid', 'canceled'):
            case.state, case.outcome = 'closed', 'claim settled before hearing'
            continue
        if case.target_person_id not in by_id:
            case.state, case.outcome = 'closed', 'debtor absent'
            continue
        if police <= 0 and not garrison:
            case.outcome = 'pending: no enforcement capacity'
            continue
        debtor = by_id[case.target_person_id]
        plot = region.tenure.find_plot(case.target_plot_id) if case.target_plot_id and getattr(region, 'tenure', None) else None
        if case.kind == 'quit_penalty':
            case.state, case.outcome = 'resolved', 'unpaid penalty remains a cash claim'
            resolved.append(case.id)
            continue
        if plot is None or debtor.id not in getattr(plot, 'tenant_ids', []):
            case.state, case.outcome = 'closed', 'collateral occupancy ended'
            continue
        plot.tenant_ids.remove(debtor.id)
        debtor.assigned_plot_id = None
        debtor.social_class = 'dispossessed'
        debtor.mem_push('mem_debt_trap', 1.0)
        debtor.mem_push('mem_eviction', 1.0)
        remove_access(region, debtor.id, plot.plot_id)
        case.state, case.outcome = 'resolved', 'evicted after delayed foreclosure'
        region.access_events = (getattr(region, 'access_events', []) + [
            {'turn': turn, 'person_id': debtor.id, 'plot_id': plot.plot_id,
             'cause': 'foreclosure', 'claim_id': claim.id}
        ])[-500:]
        resolved.append(case.id)
        if police:
            police -= 1
    region.enforcement_cases = cases
    return resolved


def process_vagrancy_cases(region, turn):
    from workhouse import has_workhouse
    cases = getattr(region, 'enforcement_cases', [])
    if (not getattr(region, 'vagrancy_law_active', False) or not has_workhouse(region)):
        return []
    for person in sorted(region.agents, key=lambda a: a.id):
        if (person.alive and not person.is_trader and not person.is_government
                and not getattr(person, 'is_police', False) and person.social_class != 'constable'
                and not getattr(person, 'is_lord', False) and person.employer is None
                and not getattr(person, 'in_workhouse', False)
                and (person.social_class == 'dispossessed'
                     or (getattr(person, 'assigned_plot_id', None) is None and person.cash < 5.0))
                and not any(c.kind == 'vagrancy' and c.target_person_id == person.id
                            and c.state == 'pending' for c in cases)):
            cid = int(getattr(region, '_next_case_id', 1))
            region._next_case_id = cid + 1
            cases.append(EnforcementCase(cid, 'vagrancy', person.id, None, None,
                                         turn, turn))
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
        target = next((a for a in region.agents if a.id == case.target_person_id and a.alive), None)
        if target is None or not getattr(region, 'vagrancy_law_active', False):
            case.state, case.outcome = 'closed', 'target absent or law repealed'
            continue
        if capacity <= 0 and not has_garrison:
            case.outcome = 'pending: no enforcement capacity'
            continue
        if capacity > 0:
            if not constables or region.gov.agent.cash < 1.0:
                case.outcome = 'pending: no funded constable payee'
                continue
            constable = constables[(len(resolved)) % len(constables)]
            region.gov.agent.cash -= 1.0
            constable.cash += 1.0
            capacity -= 1
            case.officer_cost = 1.0
        target.in_workhouse = True
        target.social_class = 'dispossessed'
        target.mem_push('mem_workhouse', 1.0)
        case.state, case.outcome = 'resolved', 'confined after funded vagrancy hearing'
        resolved.append(case.id)
    region.enforcement_cases = cases
    return resolved
