"""Settled economic transfers and small per-actor turn statements.

This journal observes settlement; it never moves money or goods.  Its IDs remain
stable when optional causal tracing is disabled and survive pickle save/load.
"""
from __future__ import annotations

from goods import Goods


_NONCASH_EVENTS = {'production', 'input_consumed', 'scrip_wage',
                   'scrip_store_sale', 'scrip_food_credit', 'bank_deposit_haircut',
                   'bank_debt_inheritance', 'bank_debt_writeoff',
                   'company_debt_writeoff',
                   'tax_arrears_writeoff', 'cash_obligation_writeoff',
                   'wage_arrears_accrued', 'foreign_wallet_grant',
                   'wallet_transfer_in', 'wallet_transfer_out',
                   'wilderness_goods_advance',
                   'wilderness_goods_collection',
                   'crop_lien_settlement', 'crop_share_rent',
                   'bank_fx_deposit_conversion',
                   'foreign_wallet_debt_payment', 'foreign_wallet_inheritance',
                   'foreign_wallet_escheat'}


def _wage_liability_totals(firm):
    """Return outstanding employer arrears and the matching worker claims."""
    saved_total = getattr(firm, 'wage_arrears_balance', None)
    saved_claims = getattr(firm, 'wage_arrears_by_worker', None)
    if saved_total is not None and saved_claims is not None:
        return (max(0.0, float(saved_total)),
                {int(worker_id): max(0.0, float(amount))
                 for worker_id, amount in saved_claims.items()
                 if float(amount) > 0})

    total = 0.0
    claims = {}
    for liability in getattr(firm, 'wage_liabilities', ()):
        status = str(liability.get('status', 'unpaid')).lower()
        if status in {'paid', 'settled', 'written_off', 'forgiven', 'cancelled',
                      'inherited'}:
            continue
        amount = max(0.0, float(liability.get('amount', 0.0))
                     - float(liability.get('paid_amount', 0.0)))
        worker_id = liability.get('worker_id')
        if amount <= 0 or worker_id is None:
            continue
        worker_id = int(worker_id)
        total += amount
        claims[worker_id] = claims.get(worker_id, 0.0) + amount
    return total, claims


def accrue_wage_arrear(firm, worker_id, amount):
    """Update persisted liability totals while retaining only recent detail rows."""
    amount = max(0.0, float(amount))
    if amount <= 0:
        return 0.0, 0.0, 0.0, 0.0
    total, claims = _wage_liability_totals(firm)
    worker_id = int(worker_id)
    claim_before = claims.get(worker_id, 0.0)
    claims[worker_id] = claim_before + amount
    firm.wage_arrears_balance = total + amount
    firm.wage_arrears_by_worker = claims
    return total, total + amount, claim_before, claim_before + amount


def settle_wage_arrear(firm, worker_id, amount):
    """Reduce one worker's wage claim and the matching firm liability."""
    total, claims = _wage_liability_totals(firm)
    worker_id = int(worker_id)
    claim_before = claims.get(worker_id, 0.0)
    settled = min(max(0.0, float(amount)), claim_before)
    if settled <= 0:
        return total, total, claim_before, claim_before, 0.0
    claim_after = max(0.0, claim_before - settled)
    if claim_after <= 1e-9:
        claims.pop(worker_id, None)
    else:
        claims[worker_id] = claim_after
    firm.wage_arrears_balance = max(0.0, total - settled)
    firm.wage_arrears_by_worker = claims

    remaining_payment = settled
    liabilities = list(getattr(firm, 'wage_liabilities', ()))
    matching = sorted(
        (row for row in liabilities
         if int(row.get('worker_id', -1)) == worker_id
         and str(row.get('status', 'unpaid')).lower()
         not in {'paid', 'settled', 'written_off', 'forgiven', 'cancelled',
                 'inherited'}),
        key=lambda row: (int(row.get('turn', 0)),))
    for row in matching:
        original = max(0.0, float(row.get('amount', 0.0)))
        already_paid = max(0.0, float(row.get('paid_amount', 0.0)))
        outstanding = max(0.0, original - already_paid)
        applied = min(remaining_payment, outstanding)
        if applied <= 0:
            continue
        row['paid_amount'] = already_paid + applied
        remaining_payment -= applied
        row['status'] = 'paid' if row['paid_amount'] + 1e-9 >= original else 'partial'
        if remaining_payment <= 1e-9:
            break
    firm.wage_liabilities = liabilities[-500:]
    return total, firm.wage_arrears_balance, claim_before, claim_after, settled


def _wage_arrears_by_actor(region):
    payable = {}
    claims = {}
    for firm in getattr(region, 'agents', ()):
        if not getattr(firm, 'is_corporation', False):
            continue
        total, worker_claims = _wage_liability_totals(firm)
        payable[firm.id] = total
        for worker_id, amount in worker_claims.items():
            claims[worker_id] = claims.get(worker_id, 0.0) + amount
    return payable, claims


def recorded_cash_delta(events, actor_id):
    """Return cash movement represented by journal events for one actor."""
    delta = 0.0
    for event in events:
        if event['kind'] in _NONCASH_EVENTS:
            continue
        if event['recipient_id'] == actor_id:
            if event['kind'] == 'spot_sale':
                seller_tile = event['detail'].get('seller_account_tile')
                is_remote_receipt = (seller_tile is not None
                                     and event.get('tile') is not None
                                     and seller_tile != event['tile'])
                if not is_remote_receipt:
                    delta += event['detail'].get(
                        'cash_receipt',
                        event['detail'].get('seller_receipt', event['amount']))
            else:
                delta += event['amount']
        if event['payer_id'] == actor_id:
            delta -= event['amount']
    return delta


def _name(good):
    return getattr(good, 'name', str(good)) if good is not None else None


def record(region, kind, *, turn=None, payer_id=None, recipient_id=None,
           good=None, quantity=0, amount=0.0, debt_credit=0.0,
           asset_id=None, source_id=None, currency=None, detail=None):
    ident = int(getattr(region, '_next_economic_event_id', 1))
    region._next_economic_event_id = ident + 1
    event = {'id': ident, 'turn': int(turn if turn is not None else getattr(region, '_last_turn', 0)),
             'tile': region.name, 'kind': kind, 'payer_id': payer_id,
             'recipient_id': recipient_id, 'good': _name(good),
             'quantity': float(quantity), 'amount': float(amount),
             'debt_credit': float(debt_credit), 'asset_id': asset_id,
             'source_id': source_id,
             'currency': currency or getattr(region, 'home_currency', None),
             'detail': detail or {}}
    history = getattr(region, 'economic_events', [])
    history.append(event)
    region.economic_events = history[-2000:]
    return event


def begin_turn(region, turn):
    if (getattr(region, '_economic_opening_turn', None) == int(turn)
            and getattr(region, '_economic_opening', None) is not None):
        return
    if getattr(region, 'tenure', None) is not None:
        from supply_rights import _seed_water_rights
        _seed_water_rights(region)
    region._economic_opening_turn = int(turn)
    bank = getattr(region, 'bank', None)
    wage_arrears_payable, wage_arrears_claims = _wage_arrears_by_actor(region)
    region._economic_opening = {
        a.id: {'cash': float(getattr(a, 'cash', 0.0)),
               'scrip': float(getattr(a, 'scrip_wallet', 0.0)),
               'wallets': {str(currency): float(amount)
                           for currency, amount in
                           (getattr(a, 'wallets', None) or {}).items()},
               'bank_deposit': float(bank.deposits.get(a, 0.0)) if bank else 0.0,
               'bank_debt': sum(max(0.0, float(loan.principle) - float(loan.principle_paid))
                                for loan in getattr(bank, 'loans', [])
                                if loan.agent is a) if bank else 0.0,
               'owner_loan': float(getattr(a, 'owner_loan', 0.0)),
               'company_debt': float(getattr(a, 'company_debt', 0.0)),
               'food': int(a.inv_get(Goods.food, 0)),
               'inventory': {g.name: int(a.inv_get(g, 0)) for g in getattr(region, 'recipes', {})},
               'debt': sum(float(c.balance) for c in getattr(region, 'cash_obligations', [])
                           if c.debtor_id == a.id and c.status == 'active'),
               'wage_arrears_payable': wage_arrears_payable.get(a.id, 0.0),
               'wage_arrears_claim': wage_arrears_claims.get(a.id, 0.0),
               'title_plots': [p.plot_id for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                               if p.lord_id == a.id],
               'water_units': sum(float(r.units) for r in getattr(region, 'water_rights', [])
                                  if r.holder_id == a.id)}
        for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)}


def seal_turn(region, turn, event_regions=None):
    """Seal observable results once; repeated snapshots cannot alter accounts."""
    if getattr(region, '_economic_sealed_turn', -1) == turn:
        return getattr(region, 'actor_turn_accounts', [])
    opening = getattr(region, '_economic_opening', {})
    events = [e for e in getattr(region, 'economic_events', []) if e['turn'] == turn]
    if event_regions is None:
        province = getattr(region, 'province', None)
        event_regions = getattr(province, 'tiles', ()) or (region,)
    unique_event_regions = []
    for event_region in event_regions:
        if all(event_region is not existing for existing in unique_event_regions):
            unique_event_regions.append(event_region)
    if all(region is not event_region for event_region in unique_event_regions):
        unique_event_regions.append(region)
    cash_events = [event for event_region in unique_event_regions
                   for event in getattr(event_region, 'economic_events', [])
                   if event['turn'] == turn]
    wage_arrears_payable, wage_arrears_claims = _wage_arrears_by_actor(region)
    by_actor = {}
    for event in events:
        for ident in {event['payer_id'], event['recipient_id']} - {None}:
            by_actor.setdefault(ident, []).append(event)
    cash_by_actor = {}
    for event in cash_events:
        for ident in {event['payer_id'], event['recipient_id']} - {None}:
            cash_by_actor.setdefault(ident, []).append(event)
    accounts = []
    for actor in getattr(region, 'agents', []):
        own = by_actor.get(actor.id, [])
        cash_own = cash_by_actor.get(actor.id, own)
        receipts = sum((e['detail'].get(
                            'cash_receipt', e['detail'].get('seller_receipt', e['amount']))
                        if e['kind'] == 'spot_sale' else e['amount'])
                       for e in own if e['recipient_id'] == actor.id
                       and e['kind'] in ('spot_sale', 'contract_delivery',
                                         'market_sale_cash_receipt'))
        crop_value = sum(e['amount'] + e['debt_credit'] for e in own
                         if e['recipient_id'] == actor.id
                         and e['kind'] in ('spot_sale', 'contract_delivery'))
        purchases = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                        and e['kind'] in ('spot_sale', 'contract_delivery'))
        recipe_input = getattr(region, 'recipes', {}).get(getattr(actor, 'output', None), {}).get('input')
        delivered_imports = [e for e in own if e['payer_id'] == actor.id
                             and e['kind'] == 'spot_sale'
                             and e['good'] == _name(recipe_input)
                             and e['detail'].get('imported', False)]
        delivered_input_spend = sum(e['amount'] for e in delivered_imports)
        delivered_input_units = sum(e['quantity'] for e in delivered_imports)
        wages = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                    and e['kind'] == 'wage')
        other_costs = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                          and e['kind'] in ('freight', 'petition_fee', 'rent', 'tax', 'cash_tax'))
        # Purchases are working inventory. Cost of goods sold needs the later
        # production-consumption posting; never expense purchases twice.
        input_used = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                         and e['kind'] == 'input_consumed')
        prior = opening.get(actor.id, {
            'cash': 0.0, 'scrip': 0.0, 'bank_deposit': 0.0,
            'bank_debt': 0.0, 'company_debt': 0.0, 'food': 0,
            'owner_loan': 0.0,
            'wallets': {}, 'inventory': {}, 'debt': 0.0, 'title_plots': [],
            'water_units': 0.0,
        })
        closing_wallets = {str(currency): float(amount)
                           for currency, amount in
                           (getattr(actor, 'wallets', None) or {}).items()}
        wallet_change_by_currency = {
            currency: round(closing_wallets.get(currency, 0.0)
                            - prior.get('wallets', {}).get(currency, 0.0), 2)
            for currency in sorted(set(closing_wallets) | set(prior.get('wallets', {})))
            if round(closing_wallets.get(currency, 0.0)
                     - prior.get('wallets', {}).get(currency, 0.0), 2) != 0
        }
        cash_in = 0.0
        for event in cash_own:
            if (event['recipient_id'] != actor.id
                    or event['kind'] in _NONCASH_EVENTS):
                continue
            if event['kind'] == 'spot_sale':
                seller_tile = event['detail'].get('seller_account_tile')
                if (seller_tile is not None and event.get('tile') is not None
                        and seller_tile != event['tile']):
                    continue
                cash_in += event['detail'].get(
                    'cash_receipt',
                    event['detail'].get('seller_receipt', event['amount']))
            else:
                cash_in += event['amount']
        cash_out = sum(e['amount'] for e in cash_own if e['payer_id'] == actor.id
                       and e['kind'] not in _NONCASH_EVENTS)
        observed_cash_change = float(actor.cash) - prior['cash']
        financing = sum(e['amount'] for e in own if e['recipient_id'] == actor.id
                        and e['kind'] == 'owner_financing')
        fx_received = sum(e['amount'] for e in own if e['recipient_id'] == actor.id
                          and e['kind'] == 'fx_conversion')
        fx_paid = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                      and e['kind'] in ('fx_conversion', 'bank_fx_deposit_conversion'))
        bank_deposit_fx_converted_out = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id
            and e['kind'] == 'bank_fx_deposit_conversion')
        bank_loan_repayment = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                                  and e['kind'] == 'bank_loan_repayment')
        bank_debt_inherited = {}
        for event in own:
            if (event['recipient_id'] == actor.id
                    and event['kind'] == 'bank_debt_inheritance'):
                currency = event.get('currency') or 'unknown'
                bank_debt_inherited[currency] = (
                    bank_debt_inherited.get(currency, 0.0) + event['amount'])
        bank_debt_written_off = {}
        for event in own:
            if (event['payer_id'] == actor.id
                    and event['kind'] == 'bank_debt_writeoff'):
                currency = event.get('currency') or 'unknown'
                bank_debt_written_off[currency] = (
                    bank_debt_written_off.get(currency, 0.0) + event['amount'])
        company_debt_written_off = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'company_debt_writeoff')
        company_receivable_written_off = sum(
            e['amount'] for e in own
            if e['recipient_id'] == actor.id and e['kind'] == 'company_debt_writeoff')
        tax_arrears_written_off = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'tax_arrears_writeoff')
        tax_receivable_written_off = sum(
            e['amount'] for e in own
            if e['recipient_id'] == actor.id and e['kind'] == 'tax_arrears_writeoff')
        cash_obligation_written_off = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'cash_obligation_writeoff')
        obligation_receivable_written_off = sum(
            e['amount'] for e in own
            if e['recipient_id'] == actor.id and e['kind'] == 'cash_obligation_writeoff')
        crop_lien_debt_settled = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'crop_lien_settlement')
        crop_lien_receivable_settled = sum(
            e['amount'] for e in own
            if e['recipient_id'] == actor.id and e['kind'] == 'crop_lien_settlement')
        crop_lien_goods_paid = sum(
            e['quantity'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'crop_lien_settlement')
        crop_lien_goods_received = sum(
            e['quantity'] for e in own
            if e['recipient_id'] == actor.id and e['kind'] == 'crop_lien_settlement')
        crop_share_rent_paid = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'crop_share_rent')
        crop_share_rent_received = sum(
            e['amount'] for e in own
            if e['recipient_id'] == actor.id and e['kind'] == 'crop_share_rent')
        crop_share_goods_paid = sum(
            e['quantity'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'crop_share_rent')
        crop_share_goods_received = sum(
            e['quantity'] for e in own
            if e['recipient_id'] == actor.id and e['kind'] == 'crop_share_rent')
        wage_arrears_accrued = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'wage_arrears_accrued')
        wage_arrears_claim_accrued = sum(
            e['amount'] for e in own
            if e['recipient_id'] == actor.id and e['kind'] == 'wage_arrears_accrued')
        wage_arrears_payable_paid = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'wage_arrears_paid')
        wage_arrears_claim_paid = sum(
            e['amount'] for e in own
            if (e['recipient_id'] == actor.id and e['kind'] == 'wage_arrears_paid')
            or (e['recipient_id'] == actor.id
                and e['kind'] == 'wallet_transfer_in'
                and e['detail'].get('payment_kind') == 'wage_arrears_paid'))
        foreign_wallet_debt_paid = {}
        for event in own:
            if (event['payer_id'] == actor.id
                    and event['kind'] == 'foreign_wallet_debt_payment'):
                currency = event.get('currency') or 'unknown'
                foreign_wallet_debt_paid[currency] = (
                    foreign_wallet_debt_paid.get(currency, 0.0) + event['amount'])
        foreign_wallet_inherited = {}
        for event in cash_own:
            if (event['recipient_id'] == actor.id
                    and event['kind'] == 'foreign_wallet_inheritance'):
                currency = event.get('currency') or 'unknown'
                foreign_wallet_inherited[currency] = (
                    foreign_wallet_inherited.get(currency, 0.0) + event['amount'])
        foreign_wallet_escheated = {}
        for event in cash_own:
            if (event['payer_id'] == actor.id
                    and event['kind'] == 'foreign_wallet_escheat'):
                currency = event.get('currency') or 'unknown'
                foreign_wallet_escheated[currency] = (
                    foreign_wallet_escheated.get(currency, 0.0) + event['amount'])
        bank_deposit_loss = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                                and e['kind'] == 'bank_deposit_haircut')
        bank_cash_deposited = sum(e['amount'] for e in cash_own
                                  if e['payer_id'] == actor.id
                                  and e['kind'] == 'bank_deposit')
        bank_cash_withdrawn = sum(e['amount'] for e in cash_own
                                  if e['recipient_id'] == actor.id
                                  and e['kind'] == 'bank_withdrawal')
        wallet_transfer_in_by_currency = {}
        for event in own:
            if (event['recipient_id'] == actor.id
                    and event['kind'] in ('wallet_transfer_in',
                                          'foreign_wallet_grant')):
                currency = event.get('currency') or 'unknown'
                wallet_transfer_in_by_currency[currency] = (
                    wallet_transfer_in_by_currency.get(currency, 0.0)
                    + event['amount'])
        wallet_transfer_out_by_currency = {}
        for event in own:
            if (event['payer_id'] == actor.id
                    and event['kind'] == 'wallet_transfer_out'):
                currency = event.get('currency') or 'unknown'
                wallet_transfer_out_by_currency[currency] = (
                    wallet_transfer_out_by_currency.get(currency, 0.0)
                    + event['amount'])
        owner_loan_repaid = sum(
            e['amount'] for e in own
            if e['payer_id'] == actor.id and e['kind'] == 'owner_loan_repayment')
        owner_loan_repayment_received = sum(
            e['amount'] for e in own
            if (e['recipient_id'] == actor.id
                and e['kind'] == 'owner_loan_repayment')
            or (e['recipient_id'] == actor.id
                and e['kind'] == 'wallet_transfer_in'
                and e['detail'].get('payment_kind') == 'owner_loan_repayment'))
        for_lease = [p.plot_id for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                     if getattr(p, 'controlled_by_id', None) == actor.id]
        debt = sum(float(c.balance) for c in getattr(region, 'cash_obligations', [])
                   if c.debtor_id == actor.id and c.status == 'active')
        bank = getattr(region, 'bank', None)
        bank_deposit = float(bank.deposits.get(actor, 0.0)) if bank else 0.0
        bank_debt = sum(max(0.0, float(loan.principle) - float(loan.principle_paid))
                        for loan in getattr(bank, 'loans', []) if loan.agent is actor) if bank else 0.0
        company_debt = float(getattr(actor, 'company_debt', 0.0))
        output = getattr(actor, 'output', None)
        output_name = _name(output)
        produced = sum(e['quantity'] for e in events if e['recipient_id'] == actor.id
                       and e['kind'] == 'production' and e['good'] == output_name)
        accounts.append({
            'turn': int(turn), 'tile': region.name, 'actor_id': actor.id,
            'actor_name': getattr(actor, 'company_name', None) or
                          getattr(actor, 'display_name', None) or f'Actor {actor.id}',
            'type': 'corporation' if getattr(actor, 'is_corporation', False) else
                    'grower' if output in (Goods.food, Goods.cotton, Goods.sugar, Goods.tobacco) else 'other',
            'output': output_name, 'opening_cash': round(prior['cash'], 2),
            'closing_cash': round(float(actor.cash), 2),
            'opening_scrip': round(prior['scrip'], 2),
            'closing_scrip': round(float(getattr(actor, 'scrip_wallet', 0.0)), 2),
            'scrip_change': round(float(getattr(actor, 'scrip_wallet', 0.0)) - prior['scrip'], 2),
            'opening_wallets': dict(sorted(prior.get('wallets', {}).items())),
            'closing_wallets': dict(sorted(closing_wallets.items())),
            'wallet_change_by_currency': wallet_change_by_currency,
            'wallet_transfer_in_by_currency': {
                currency: round(amount, 2)
                for currency, amount in sorted(wallet_transfer_in_by_currency.items())},
            'wallet_transfer_out_by_currency': {
                currency: round(amount, 2)
                for currency, amount in sorted(wallet_transfer_out_by_currency.items())},
            'cash_change': round(float(actor.cash) - prior['cash'], 2),
            'posted_cash_change': round(cash_in - cash_out, 2),
            'unposted_cash_change': round(observed_cash_change - (cash_in - cash_out), 2),
            'cash_phase_changes': list(
                getattr(region, '_actor_cash_phase_changes', {}).get(actor.id, ())),
            'owner_financing_received': round(financing, 2),
            'fx_converted_in': round(fx_received, 2),
            'fx_converted_out': round(fx_paid, 2),
            'bank_deposit_fx_converted_out': round(
                bank_deposit_fx_converted_out, 2),
            'bank_loan_repayment_cash': round(bank_loan_repayment, 2),
            'bank_debt_inherited': {
                currency: round(amount, 2)
                for currency, amount in sorted(bank_debt_inherited.items())},
            'bank_debt_written_off': {
                currency: round(amount, 2)
                for currency, amount in sorted(bank_debt_written_off.items())},
            'foreign_wallet_debt_paid': {
                currency: round(amount, 2)
                for currency, amount in sorted(foreign_wallet_debt_paid.items())},
            'foreign_wallet_inherited': {
                currency: round(amount, 2)
                for currency, amount in sorted(foreign_wallet_inherited.items())},
            'foreign_wallet_escheated': {
                currency: round(amount, 2)
                for currency, amount in sorted(foreign_wallet_escheated.items())},
            'bank_deposit_loss': round(bank_deposit_loss, 2),
            'opening_food': prior['food'], 'closing_food': int(actor.inv_get(Goods.food, 0)),
            'food_intake': round(float(getattr(actor, 'last_calories_eaten', 0.0)) / 500.0, 2),
            'opening_debt': round(prior['debt'], 2), 'closing_debt': round(debt, 2),
            'opening_wage_arrears_payable': round(
                prior.get('wage_arrears_payable', 0.0), 2),
            'closing_wage_arrears_payable': round(
                wage_arrears_payable.get(actor.id, 0.0), 2),
            'wage_arrears_accrued': round(wage_arrears_accrued, 2),
            'wage_arrears_payable_paid': round(wage_arrears_payable_paid, 2),
            'opening_wage_arrears_claim': round(
                prior.get('wage_arrears_claim', 0.0), 2),
            'closing_wage_arrears_claim': round(
                wage_arrears_claims.get(actor.id, 0.0), 2),
            'wage_arrears_claim_accrued': round(wage_arrears_claim_accrued, 2),
            'wage_arrears_claim_paid': round(wage_arrears_claim_paid, 2),
            'opening_bank_deposit': round(prior['bank_deposit'], 2),
            'closing_bank_deposit': round(bank_deposit, 2),
            'bank_cash_deposited': round(bank_cash_deposited, 2),
            'bank_cash_withdrawn': round(bank_cash_withdrawn, 2),
            'opening_bank_debt': round(prior['bank_debt'], 2),
            'closing_bank_debt': round(bank_debt, 2),
            'opening_company_debt': round(prior['company_debt'], 2),
            'closing_company_debt': round(company_debt, 2),
            'opening_owner_loan': round(prior.get('owner_loan', 0.0), 2),
            'closing_owner_loan': round(float(getattr(actor, 'owner_loan', 0.0)), 2),
            'owner_loan_repaid': round(owner_loan_repaid, 2),
            'owner_loan_repayment_received': round(owner_loan_repayment_received, 2),
            'company_debt_written_off': round(company_debt_written_off, 2),
            'company_receivable_written_off': round(company_receivable_written_off, 2),
            'tax_arrears_written_off': round(tax_arrears_written_off, 2),
            'tax_receivable_written_off': round(tax_receivable_written_off, 2),
            'cash_obligation_written_off': round(cash_obligation_written_off, 2),
            'obligation_receivable_written_off': round(obligation_receivable_written_off, 2),
            'crop_lien_debt_settled': round(crop_lien_debt_settled, 2),
            'crop_lien_receivable_settled': round(crop_lien_receivable_settled, 2),
            'crop_lien_goods_paid': round(crop_lien_goods_paid, 2),
            'crop_lien_goods_received': round(crop_lien_goods_received, 2),
            'crop_share_rent_paid': round(crop_share_rent_paid, 2),
            'crop_share_rent_received': round(crop_share_rent_received, 2),
            'crop_share_goods_paid': round(crop_share_goods_paid, 2),
            'crop_share_goods_received': round(crop_share_goods_received, 2),
            'sales_cash': round(receipts, 2), 'crop_value': round(crop_value, 2),
            'purchases_cash': round(purchases, 2), 'wages_cash': round(wages, 2),
            'delivered_input_purchase_cash': round(delivered_input_spend, 2),
            'delivered_input_purchase_units': round(delivered_input_units, 2),
            'delivered_input_unit_price': round(delivered_input_spend / delivered_input_units, 2)
            if delivered_input_units else None,
            'delivered_input_currency': delivered_imports[0].get('currency')
            if delivered_imports else None,
            'delivered_input_lots': [
                {'event_id': e['id'], 'shipment_id': e['detail'].get('shipment_id'),
                 'quantity': e['quantity'], 'paid_unit_price': e['detail'].get('unit_price'),
                 'source_unit_cost': e['detail'].get('source_unit_cost'),
                 'freight_per_unit': e['detail'].get('freight_per_unit'),
                 'source_currency': e['detail'].get('source_currency'),
                 'destination_currency': e['detail'].get('destination_currency'),
                 'source_cost_currency': e['detail'].get('source_cost_currency'),
                 'source_cost_destination_currency': e['detail'].get('source_cost_destination_currency'),
                 'freight_destination_currency': e['detail'].get('freight_destination_currency'),
                 'landed_cost_source_currency': e['detail'].get('landed_cost_source_currency'),
                 'landed_cost_destination_currency': e['detail'].get('landed_cost_destination_currency'),
                 'fx_source_to_destination_rate': e['detail'].get('fx_source_to_destination_rate'),
                 'fx_valuation_method': e['detail'].get('fx_valuation_method'),
                 'fx_valuation_basis': e['detail'].get('fx_valuation_basis'),
                 'import_tariff_assessed_per_unit': e['detail'].get('import_tariff_assessed_per_unit'),
                 'import_tariff_rebate_per_unit': e['detail'].get('import_tariff_rebate_per_unit'),
                 'import_tariff_paid_per_unit': e['detail'].get('import_tariff_paid_per_unit'),
                 'seller_net_receipt_per_unit': e['detail'].get('seller_net_receipt_per_unit'),
                 'trader_landed_margin_per_unit': e['detail'].get('trader_landed_margin_per_unit'),
                 'source_cost_status': e['detail'].get('source_cost_status'),
                 'source_shipment_id': e['detail'].get('source_shipment_id'),
                 'source_region': e['detail'].get('source_region'),
                 'route_history': list(e['detail'].get('route_history') or []),
                 'source_acquisitions': list(
                     e['detail'].get('source_acquisitions') or [])}
                for e in delivered_imports],
            'other_costs_cash': round(other_costs, 2),
            'input_consumed_cost': round(input_used, 2),
            'operating_result_recorded': round(receipts - wages - other_costs - input_used, 2),
            'operating_result_complete': False,
            'produced_units': produced,
            'opening_output_stock': prior['inventory'].get(output_name, 0),
            'closing_output_stock': int(actor.inv_get(output, 0)) if output is not None else 0,
            'opening_title_plots': prior['title_plots'],
            'closing_title_plots': [p.plot_id for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                                    if p.lord_id == actor.id],
            'leased_control_plots': for_lease,
            'opening_water_units': round(prior['water_units'], 3),
            'closing_water_units': round(sum(float(r.units) for r in getattr(region, 'water_rights', [])
                                             if r.holder_id == actor.id), 3),
            'event_ids': [e['id'] for e in own[-30:]],
            'cash_event_refs': [{'tile': e['tile'], 'id': e['id']}
                                for e in cash_own[-30:]],
        })
    region.actor_turn_accounts = accounts
    region._economic_sealed_turn = int(turn)
    history = getattr(region, 'actor_account_history', [])
    history.extend(accounts)
    region.actor_account_history = history[-600:]
    return accounts
