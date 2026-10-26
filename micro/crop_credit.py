"""Cash advances and current-harvest lien settlement."""
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
from labor_institutions import TenancyAgreement
from livelihood_access import assess_obligation


def offer_advance(lender, cultivator, region, amount, due_turn, collateral_plot_id,
                  interest_rate=0.0, lien_share=0.5, offtake_quantity=0,
                  offtake_price=None, accepted_proposal_id=None):
    from supply_proposals import authorized
    if not authorized(region, accepted_proposal_id, lender.id, cultivator.id,
                      ('advance_offtake', 'crop_advance')):
        return None
    amount = max(0.0, float(amount))
    plot = getattr(region, 'tenure', None)
    plot = plot.find_plot(collateral_plot_id) if plot is not None else None
    if (amount <= 0 or lender is cultivator or not getattr(lender, 'alive', True)
            or not getattr(cultivator, 'alive', True) or plot is None
            or cultivator.id not in getattr(plot, 'tenant_ids', []) or lender.cash < amount):
        return None
    _trace_cash_write = _trace_public_begin(None, lender)
    lender.cash -= amount
    _trace_public_finish(_trace_cash_write, 'crop_credit:offer_advance',
                         inputs={"source_writer": 'crop_credit.py:offer_advance:6b56b0bd587cd89e:1'})
    _trace_cash_write = _trace_public_begin(None, cultivator)
    cultivator.cash += amount
    _trace_public_finish(_trace_cash_write, 'crop_credit:offer_advance',
                         inputs={"source_writer": 'crop_credit.py:offer_advance:451dfdb44c1f1275:1'})
    claim = assess_obligation(region, cultivator.id, lender.id, 'advance', amount,
                              due_turn, interest_rate, collateral_plot_id)
    if claim is None:
        _trace_cash_write = _trace_public_begin(None, cultivator)
        cultivator.cash -= amount
        _trace_public_finish(_trace_cash_write, 'crop_credit:offer_advance',
                             inputs={"source_writer": 'crop_credit.py:offer_advance:68a884f95aff552b:1'})
        _trace_cash_write = _trace_public_begin(None, lender)
        lender.cash += amount
        _trace_public_finish(_trace_cash_write, 'crop_credit:offer_advance',
                             inputs={"source_writer": 'crop_credit.py:offer_advance:b344461b34efa662:1'})
        return None
    claim.lien_share = max(0.0, min(1.0, float(lien_share)))
    claim.lien_good = getattr(cultivator, 'output', None)
    claim.lien_settled_turn = -1
    if offtake_quantity > 0 and offtake_price is not None:
        price = max(0.01, float(offtake_price))
        quantity = max(0, int(offtake_quantity))
        contract = {
            'id': getattr(region, '_next_offtake_id', 1), 'lender_id': lender.id,
            'grower_id': cultivator.id, 'plot_id': collateral_plot_id,
            'good': getattr(claim.lien_good, 'name', str(claim.lien_good)),
            'quantity': quantity, 'remaining': quantity, 'unit_price': price,
            'due_turn': int(due_turn), 'claim_id': claim.id, 'status': 'active',
            'fallback_lien_share': max(0.0, min(1.0, float(lien_share))),
            'created_turn': getattr(region, '_last_turn', 0),
        }
        region._next_offtake_id = contract['id'] + 1
        if not hasattr(region, 'offtake_contracts'):
            region.offtake_contracts = []
        region.offtake_contracts.append(contract)
        claim.lien_share = 0.0  # contract delivery supersedes the generic crop lien
    region.obligation_events = (getattr(region, 'obligation_events', []) + [
        {'turn': getattr(region, '_last_turn', 0), 'event': 'advance', 'claim_id': claim.id,
         'lender_id': lender.id, 'cultivator_id': cultivator.id, 'amount': amount}
    ])[-500:]
    from economy.actor_accounts import record as record_economic_event
    record_economic_event(region, 'advance', payer_id=lender.id,
                          recipient_id=cultivator.id, amount=amount,
                          asset_id=claim.id,
                          detail={'due_turn': int(due_turn), 'plot_id': collateral_plot_id,
                                  'offtake_quantity': int(offtake_quantity)})
    return claim


def settle_offtake_contracts(region, turn):
    """Settle contracted harvest before spot-market asks; deliver only actual crop."""
    agents = {a.id: a for a in getattr(region, 'agents', [])}
    receipts = getattr(region, 'production_receipts', [])
    events = []
    for contract in sorted(getattr(region, 'offtake_contracts', []), key=lambda c: c['id']):
        if contract.get('status') != 'active' or contract.get('due_turn', turn) > turn:
            continue
        grower, buyer = agents.get(contract['grower_id']), agents.get(contract['lender_id'])
        good_name = contract['good']
        good = next((g for g in region.recipes if getattr(g, 'name', str(g)) == good_name), None)
        if grower is None or buyer is None or good is None or not grower.alive or not buyer.alive:
            continue
        available = sum(max(0, int(r['quantity'])) for r in receipts
                        if r['person_id'] == grower.id and r['good'] == good)
        take = min(available, int(contract.get('remaining', 0)))
        if good_name == 'food':
            take = min(take, max(0, int(grower.inv_get(good, 0)) - 4))
        claim = next((c for c in getattr(region, 'cash_obligations', [])
                      if c.id == contract['claim_id']), None)
        if take <= 0:
            if turn > contract.get('due_turn', turn):
                contract['status'] = 'defaulted'
                if claim:
                    claim.lien_share = float(contract.get('fallback_lien_share', 0.0))
            continue
        due_value = take * float(contract['unit_price'])
        credit = min(due_value, max(0.0, float(claim.balance))) if claim else 0.0
        cash_due = due_value - credit
        paid = min(cash_due, max(0.0, float(buyer.cash)))
        # The prepaid portion is the contracted crop purchase; buyer cannot take
        # more crop than its remaining cash plus the grower's outstanding credit.
        deliver = min(take, int((credit + paid) // max(0.01, float(contract['unit_price']))))
        if deliver <= 0:
            continue
        value = deliver * float(contract['unit_price'])
        credit_used = min(value, max(0.0, float(claim.balance))) if claim else 0.0
        cash_paid = value - credit_used
        _trace_cash_write = _trace_public_begin(None, buyer)
        buyer.cash -= cash_paid
        _trace_public_finish(_trace_cash_write, 'crop_credit:settle_offtake_contracts',
                             inputs={"source_writer": 'crop_credit.py:settle_offtake_contracts:b0e25aed50ef90d0:1'})
        _trace_cash_write = _trace_public_begin(None, grower)
        grower.cash += cash_paid
        _trace_public_finish(_trace_cash_write, 'crop_credit:settle_offtake_contracts',
                             inputs={"source_writer": 'crop_credit.py:settle_offtake_contracts:30a0900f10b0196f:1'})
        grower.inv_add(good, -deliver)
        if hasattr(buyer, 'cost_get') and hasattr(buyer, 'cost_set'):
            old_stock = buyer.inv_get(good, 0)
            old_cost = buyer.cost_get(good, 0)
            buyer.cost_set(good, ((old_stock * old_cost + value) /
                                  max(1, old_stock + deliver)))
        buyer.inv_add(good, deliver)
        if claim:
            claim.balance = max(0.0, claim.balance - credit_used)
            if claim.balance <= 1e-9:
                claim.balance = 0.0
                claim.status = 'paid'
        left = deliver
        for receipt in receipts:
            if receipt['person_id'] == grower.id and receipt['good'] == good and left:
                used = min(left, int(receipt['quantity']))
                receipt['quantity'] -= used
                left -= used
        contract['remaining'] -= deliver
        if contract['remaining'] <= 0:
            contract['status'] = 'fulfilled'
        events.append({'turn': turn, 'contract_id': contract['id'], 'grower_id': grower.id,
                       'buyer_id': buyer.id, 'good': good_name, 'quantity': deliver,
                       'unit_price': float(contract['unit_price']), 'cash_paid': round(cash_paid, 2),
                       'advance_credit': round(credit_used, 2), 'status': contract['status']})
        from economy.actor_accounts import record as record_economic_event
        record_economic_event(region, 'contract_delivery', turn=turn, payer_id=buyer.id,
                              recipient_id=grower.id, good=good, quantity=deliver,
                              amount=cash_paid, debt_credit=credit_used,
                              asset_id=contract['id'],
                              detail={'unit_price': float(contract['unit_price']),
                                      'claim_id': contract['claim_id']})
    region.offtake_events = (getattr(region, 'offtake_events', []) + events)[-500:]
    from run_trace import emit
    for event in events:
        emit(region, kind='offtake_settlement', record_class='outcome',
             subject={'type': 'contract', 'id': event['contract_id']},
             metric_id='contract.crop_delivery', unit=event['good'], after=event['quantity'],
             formula_id='supply.offtake.fixed_price.v1', inputs=event)
    return events


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
        balance_before = float(claim.balance)
        tenant.inv_add(good, -take)
        creditor.inv_add(good, take)
        unit_price = float(region.recipes.get(good, {}).get('price', 1.0))
        transferred_reference_value = take * unit_price
        debt_credit = min(balance_before, transferred_reference_value)
        claim.balance = max(0.0, balance_before - transferred_reference_value)
        claim.lien_settled_turn = turn
        if claim.balance <= 1e-9:
            claim.balance = 0.0
            claim.status = 'paid'
        event = {'turn': turn, 'claim_id': claim.id, 'debtor_id': tenant.id,
                 'creditor_id': creditor.id, 'good': getattr(good, 'value', str(good)),
                 'quantity': take, 'unit_price': unit_price,
                 'reference_value': transferred_reference_value,
                 'debt_credit': debt_credit,
                 'uncredited_value': max(0.0, transferred_reference_value - debt_credit),
                 'balance_before': balance_before, 'balance': round(claim.balance, 2),
                 'status': claim.status}
        events.append(event)
        transfer_id = f'crop-lien:{turn}:{claim.id}:{tenant.id}:{creditor.id}'
        from economy.actor_accounts import record as record_economic_event
        journal_event = record_economic_event(
            region, 'crop_lien_settlement', turn=turn, payer_id=tenant.id,
            recipient_id=creditor.id, good=good, quantity=take,
            amount=debt_credit, debt_credit=debt_credit,
            asset_id=claim.id, source_id=transfer_id,
            currency=getattr(region, 'home_currency', None),
            detail={**event, 'transfer_id': transfer_id,
                    'lien_share': float(getattr(claim, 'lien_share', 0.0)),
                    'valuation_basis': 'displayed_recipe_reference_price'})
        from run_trace import emit
        emit(region, kind='crop_lien_settlement', record_class='transfer',
             phase='settlement',
             subject={'type': 'crop_lien', 'id': claim.id,
                      'tile': region.name},
             metric_id='finance.crop_lien_settlement',
             unit=getattr(region, 'home_currency', None),
             before=balance_before, after=float(claim.balance),
             formula_id='crop.lien.reference_value.v1',
             inputs={**event, 'lien_share': float(getattr(claim, 'lien_share', 0.0)),
                     'available_harvest': int(available),
                     'valuation_basis': 'displayed_recipe_reference_price',
                     'economic_event_id': journal_event['id']})
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
        unit_price = float(region.recipes.get(good, {}).get('price', 1.0))
        reference_value = take * unit_price
        events.append({'turn': turn, 'tenant_id': tenant.id, 'landlord_id': landlord.id,
                       'plot_id': agreement.plot_id, 'good': getattr(good, 'value', str(good)),
                       'quantity': take, 'unit_price': unit_price,
                       'reference_value': reference_value})
        transfer_id = f'crop-share:{turn}:{agreement.plot_id}:{tenant.id}:{landlord.id}'
        from economy.actor_accounts import record as record_economic_event
        event = record_economic_event(
            region, 'crop_share_rent', turn=turn, payer_id=tenant.id,
            recipient_id=landlord.id, good=good, quantity=take,
            amount=reference_value, asset_id=agreement.plot_id,
            source_id=transfer_id,
            currency=getattr(region, 'home_currency', None),
            detail={'transfer_id': transfer_id, 'plot_id': agreement.plot_id,
                    'crop_share': float(agreement.crop_share),
                    'unit_price': unit_price,
                    'reference_value': reference_value,
                    'valuation_basis': 'displayed_recipe_reference_price'})
        from run_trace import emit
        emit(region, kind='crop_share_rent_settlement', record_class='transfer',
             phase='settlement',
             subject={'type': 'tenancy', 'id': transfer_id,
                      'tile': region.name},
             metric_id='land.crop_share', unit=getattr(good, 'name', str(good)),
             after=take, formula_id='tenancy.crop_share.harvest.v1',
             inputs={'tenant_id': tenant.id, 'landlord_id': landlord.id,
                     'plot_id': agreement.plot_id, 'crop': getattr(good, 'name', str(good)),
                     'available_harvest': int(quantity), 'quantity_transferred': take,
                     'crop_share': float(agreement.crop_share),
                     'reference_price': unit_price,
                     'reference_value': reference_value,
                     'valuation_basis': 'displayed_recipe_reference_price',
                     'economic_event_id': event['id']})
    region.crop_share_events = (getattr(region, 'crop_share_events', []) + events)[-500:]
    return events
