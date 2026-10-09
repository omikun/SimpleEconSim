"""Cash advances and current-harvest lien settlement."""
from labor_institutions import TenancyAgreement
from livelihood_access import assess_obligation


def offer_advance(lender, cultivator, region, amount, due_turn, collateral_plot_id,
                  interest_rate=0.0, lien_share=0.5):
    amount = max(0.0, float(amount))
    plot = getattr(region, 'tenure', None)
    plot = plot.find_plot(collateral_plot_id) if plot is not None else None
    if (amount <= 0 or lender is cultivator or not getattr(lender, 'alive', True)
            or not getattr(cultivator, 'alive', True) or plot is None
            or cultivator.id not in getattr(plot, 'tenant_ids', []) or lender.cash < amount):
        return None
    lender.cash -= amount
    cultivator.cash += amount
    claim = assess_obligation(region, cultivator.id, lender.id, 'advance', amount,
                              due_turn, interest_rate, collateral_plot_id)
    if claim is None:
        cultivator.cash -= amount
        lender.cash += amount
        return None
    claim.lien_share = max(0.0, min(1.0, float(lien_share)))
    claim.lien_good = getattr(cultivator, 'output', None)
    claim.lien_settled_turn = -1
    region.obligation_events = (getattr(region, 'obligation_events', []) + [
        {'turn': getattr(region, '_last_turn', 0), 'event': 'advance', 'claim_id': claim.id,
         'lender_id': lender.id, 'cultivator_id': cultivator.id, 'amount': amount}
    ])[-500:]
    return claim


def create_tenancy_agreement(region, tenant, landlord, plot_id, kind='cash_rent',
                             cash_rent=0.0, crop_share=0.0):
    plot = getattr(region, 'tenure', None)
    plot = plot.find_plot(plot_id) if plot is not None else None
    if plot is None or tenant.id == landlord.id or plot.lord_id != landlord.id:
        return None
    if kind not in ('cash_rent', 'crop_share'):
        return None
    for agreement in getattr(region, 'tenancy_agreements', []):
        if agreement.active and agreement.tenant_id == tenant.id and agreement.plot_id == plot_id:
            return None
    agreement = TenancyAgreement(tenant.id, landlord.id, plot_id, kind,
                                 max(0.0, float(cash_rent)),
                                 max(0.0, min(1.0, float(crop_share))))
    if not hasattr(region, 'tenancy_agreements'):
        region.tenancy_agreements = []
    region.tenancy_agreements.append(agreement)
    if tenant.id not in plot.tenant_ids:
        plot.tenant_ids.append(tenant.id)
    tenant.assigned_plot_id = plot_id
    from livelihood_access import grant_access
    grant_access(region, tenant.id, plot_id, 'field', source='tenancy')
    grant_access(region, tenant.id, plot_id, 'commons_food', source='tenancy')
    return agreement


def settle_crop_liens(region, turn):
    receipts = getattr(region, 'production_receipts', [])
    events = []
    agents = {a.id: a for a in getattr(region, 'agents', [])}
    for claim in sorted(getattr(region, 'cash_obligations', []), key=lambda c: c.id):
        if (claim.origin != 'advance' or claim.status != 'active'
                or claim.due_turn > turn or getattr(claim, 'lien_settled_turn', -1) == turn):
            continue
        tenant = agents.get(claim.debtor_id)
        creditor = agents.get(claim.creditor_id)
        if tenant is None or creditor is None or not tenant.alive or not creditor.alive:
            continue
        available = sum(r['quantity'] for r in receipts
                        if r['person_id'] == tenant.id and r['good'] == getattr(claim, 'lien_good', None))
        take = min(max(0, available), int(available * getattr(claim, 'lien_share', 0.0)))
        good = getattr(claim, 'lien_good', None)
        if take <= 0 or good is None:
            continue
        tenant.inv_add(good, -take)
        creditor.inv_add(good, take)
        unit_price = float(region.recipes.get(good, {}).get('price', 1.0))
        claim.balance = max(0.0, claim.balance - take * unit_price)
        claim.lien_settled_turn = turn
        if claim.balance <= 1e-9:
            claim.balance = 0.0
            claim.status = 'paid'
        events.append({'turn': turn, 'claim_id': claim.id, 'debtor_id': tenant.id,
                       'creditor_id': creditor.id, 'good': getattr(good, 'value', str(good)),
                       'quantity': take, 'balance': round(claim.balance, 2)})
    region.lien_events = (getattr(region, 'lien_events', []) + events)[-500:]
    return events


def settle_crop_shares(region, turn):
    receipts = getattr(region, 'production_receipts', [])
    agents = {a.id: a for a in getattr(region, 'agents', [])}
    events = []
    for agreement in sorted(getattr(region, 'tenancy_agreements', []),
                            key=lambda a: (a.plot_id, a.tenant_id)):
        if not agreement.active or agreement.type != 'crop_share' or agreement.crop_share <= 0:
            continue
        tenant, landlord = agents.get(agreement.tenant_id), agents.get(agreement.landlord_id)
        if tenant is None or landlord is None or not tenant.alive or not landlord.alive:
            continue
        good = getattr(tenant, 'output', None)
        quantity = sum(r['quantity'] for r in receipts
                       if r['person_id'] == tenant.id and r['good'] == good)
        take = min(quantity, int(quantity * agreement.crop_share))
        if take <= 0 or good is None:
            continue
        tenant.inv_add(good, -take)
        landlord.inv_add(good, take)
        events.append({'turn': turn, 'tenant_id': tenant.id, 'landlord_id': landlord.id,
                       'plot_id': agreement.plot_id, 'good': getattr(good, 'value', str(good)),
                       'quantity': take})
    region.crop_share_events = (getattr(region, 'crop_share_events', []) + events)[-500:]
    return events
