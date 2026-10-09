"""Named livelihood rights and conserved cash claims for a region."""
from __future__ import annotations

from labor_institutions import AccessRight, CashObligation
from land_tenure import TenureStatus


def _ensure(region):
    if not hasattr(region, 'access_rights'):
        region.access_rights = {}
        region._access_rights_seeded = False
    if not hasattr(region, 'cash_obligations'):
        region.cash_obligations = []
        region._next_obligation_id = 1
    if not hasattr(region, 'access_events'):
        region.access_events = []


def seed_access_rights(region):
    _ensure(region)
    if region._access_rights_seeded:
        return
    for plot in sorted(getattr(getattr(region, 'tenure', None), 'plots', []), key=lambda p: p.plot_id):
        for person_id in sorted(set(getattr(plot, 'tenant_ids', []))):
            grant_access(region, person_id, plot.plot_id, 'field')
            grant_access(region, person_id, plot.plot_id, 'commons_food')
    region._access_rights_seeded = True


def grant_access(region, person_id, plot_id, resource, legal=1.0, usable=1.0, source='customary'):
    _ensure(region)
    rights = region.access_rights.setdefault(int(person_id), [])
    for right in rights:
        if right.plot_id == plot_id and right.resource == resource:
            right.legal_share = max(0.0, min(1.0, float(legal)))
            right.usable_share = max(0.0, min(1.0, float(usable)))
            right.source = source
            return right
    right = AccessRight(int(person_id), str(plot_id), str(resource),
                        max(0.0, min(1.0, float(legal))),
                        max(0.0, min(1.0, float(usable))), source)
    rights.append(right)
    return right


def effective_access(person, region, resource='commons_food', official=False):
    _ensure(region)
    seed_access_rights(region)
    rights = region.access_rights.get(int(person.id), [])
    tenure = getattr(region, 'tenure', None)
    if tenure is None:
        return 0.0
    total = 0.0
    for right in rights:
        if right.resource != resource:
            continue
        plot = tenure.find_plot(right.plot_id)
        if plot is None:
            continue
        weight = {TenureStatus.FEUDAL: 1.0, TenureStatus.COMMONS: 1.0,
                  TenureStatus.LEASEHOLD: 0.5, TenureStatus.ENCLOSED: 0.0}.get(plot.tenure, 0.0)
        share = right.legal_share if official else right.usable_share
        total += plot.fraction * weight * share
    return max(0.0, min(1.0, total))


def transfer_access(region, from_person_id, to_person_id, plot_id, source='transfer'):
    _ensure(region)
    prior = [r for r in region.access_rights.get(int(from_person_id), []) if r.plot_id == plot_id]
    for r in prior:
        grant_access(region, to_person_id, plot_id, r.resource, r.legal_share, r.usable_share, source)


def remove_access(region, person_id, plot_id=None):
    _ensure(region)
    rights = region.access_rights.get(int(person_id), [])
    for right in rights:
        if plot_id is None or right.plot_id == plot_id:
            right.legal_share = 0.0
            right.usable_share = 0.0


def assess_obligation(region, debtor_id, creditor_id, origin, amount, due_turn,
                      interest_rate=0.0, collateral_plot_id=None):
    _ensure(region)
    amount = max(0.0, float(amount))
    if amount <= 0 or debtor_id == creditor_id:
        return None
    for item in region.cash_obligations:
        if (item.status == 'active' and item.debtor_id == debtor_id and
                item.creditor_id == creditor_id and item.origin == origin and
                item.due_turn == due_turn and item.collateral_plot_id == collateral_plot_id):
            return item
    oid = int(getattr(region, '_next_obligation_id', 1))
    region._next_obligation_id = oid + 1
    item = CashObligation(oid, int(debtor_id), int(creditor_id), str(origin), amount,
                          amount, max(0.0, float(interest_rate)), int(due_turn), collateral_plot_id)
    region.cash_obligations.append(item)
    return item


def due_cash_for(person_id, region, turn):
    _ensure(region)
    total = 0.0
    for claim in region.cash_obligations:
        if claim.debtor_id != int(person_id) or claim.status != 'active' or claim.due_turn > turn:
            continue
        projected = claim.balance * (1.0 + claim.interest_rate if claim.last_accrued_turn < turn else 1.0)
        total += projected
    return total


def accrue_obligations(region, turn):
    _ensure(region)
    for claim in region.cash_obligations:
        if claim.status == 'active' and claim.due_turn <= turn and claim.last_accrued_turn < turn:
            claim.balance *= (1.0 + claim.interest_rate)
            claim.last_accrued_turn = turn


def settle_obligations(region, turn):
    _ensure(region)
    accrue_obligations(region, turn)
    by_id = {int(a.id): a for a in getattr(region, 'agents', [])}
    events = []
    for claim in sorted(region.cash_obligations, key=lambda c: c.id):
        if claim.status != 'active' or claim.due_turn > turn or claim.last_settled_turn == turn:
            continue
        debtor, creditor = by_id.get(claim.debtor_id), by_id.get(claim.creditor_id)
        if debtor is None or creditor is None or not debtor.alive or not creditor.alive:
            continue
        paid = min(max(0.0, float(debtor.cash)), max(0.0, claim.balance))
        if paid:
            debtor.cash -= paid
            creditor.cash += paid
            claim.balance = max(0.0, claim.balance - paid)
        claim.last_settled_turn = turn
        if claim.balance <= 1e-9:
            claim.balance = 0.0
            claim.status = 'paid'
        events.append({'id': claim.id, 'debtor_id': claim.debtor_id,
                       'creditor_id': claim.creditor_id, 'origin': claim.origin,
                       'turn': turn,
                       'paid': round(paid, 2), 'balance': round(claim.balance, 2)})
    region.obligation_events = (getattr(region, 'obligation_events', []) + events)[-500:]
    return events


def cancel_obligation(region, obligation_id):
    _ensure(region)
    for claim in region.cash_obligations:
        if claim.id == int(obligation_id) and claim.status == 'active':
            claim.status = 'canceled'
            claim.balance = 0.0
            return True
    return False
