"""Invariant checks for the plunder-of-labor state added in Phases 1–6."""


def audit_labor_institutions(region):
    issues = []
    agents = {a.id: a for a in getattr(region, 'agents', [])}
    for agent in agents.values():
        employer = getattr(agent, 'employer', None)
        if employer is not None and agent not in getattr(employer, 'employees', []):
            issues.append(f'worker {agent.id} missing from employer roster')
    for firm in agents.values():
        if not getattr(firm, 'is_corporation', False):
            continue
        for worker in getattr(firm, 'employees', []):
            if getattr(worker, 'employer', None) is not firm:
                issues.append(f'firm {firm.id} has stale worker {worker.id}')
    for person_id, rights in getattr(region, 'access_rights', {}).items():
        for right in rights:
            if not (0 <= right.legal_share <= 1 and 0 <= right.usable_share <= 1):
                issues.append(f'access share outside [0,1] for person {person_id}')
    for claim in getattr(region, 'cash_obligations', []):
        if claim.balance < -1e-9 or claim.original_principal < 0:
            issues.append(f'invalid obligation balance {claim.id}')
    seen_settlements = set()
    for event in getattr(region, 'obligation_events', []):
        key = (event.get('id'), event.get('turn'))
        if key in seen_settlements:
            issues.append(f'duplicate obligation settlement {key}')
        seen_settlements.add(key)
    seen_cases = set()
    for case in getattr(region, 'enforcement_cases', []):
        if case.claim_id is not None and case.state == 'pending':
            key = (case.kind, case.claim_id)
            if key in seen_cases:
                issues.append(f'duplicate pending case {key}')
            seen_cases.add(key)
    for agent in agents.values():
        if any(value < 0 for value in agent.inventory):
            issues.append(f'negative inventory on agent {agent.id}')
    active_tenancies = set()
    for agreement in getattr(region, 'tenancy_agreements', []):
        if agreement.active:
            key = (agreement.tenant_id, agreement.plot_id)
            if key in active_tenancies:
                issues.append(f'duplicate active tenancy {key}')
            active_tenancies.add(key)
    return issues
