"""Delayed, named default cases for rent and advance claims."""
from labor_institutions import EnforcementCase
from livelihood_access import remove_access


def process_default_cases(region, turn):
    cases = getattr(region, 'enforcement_cases', [])
    claims = getattr(region, 'cash_obligations', [])
    by_id = {a.id: a for a in getattr(region, 'agents', [])}
    for claim in claims:
        if claim.status != 'active' or claim.due_turn > turn or claim.balance <= 0:
            continue
        if any(c.claim_id == claim.id and c.state == 'pending' for c in cases):
            continue
        cid = int(getattr(region, '_next_case_id', 1))
        region._next_case_id = cid + 1
        cases.append(EnforcementCase(cid, 'foreclosure', claim.debtor_id,
                                     claim.collateral_plot_id, claim.id, turn, turn + 1))
    police = max(0, int(getattr(region, 'police_employed', 0)))
    garrison = any(getattr(u, 'strength', 0) > 5 for u in getattr(region, 'military_units', []))
    resolved = []
    for case in sorted(cases, key=lambda c: c.id):
        if case.state != 'pending' or case.earliest_turn > turn:
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
