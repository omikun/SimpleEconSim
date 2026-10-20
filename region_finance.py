"""
Corporate wages, profit distributions, owner bailouts, taxation, and consumption multipliers.
"""

import math
import forex as _fx
from goods import Goods
from logger import loginfo, logwarning
from labor_contract import ensure_labor_agreement


def _trace_treasury_flow(region, kind, amount, inputs, cause_event_ids=None):
    nation = getattr(region, 'owner_nation', None)
    if nation is None or amount == 0:
        return
    from run_trace import emit
    return emit(region, kind=kind, record_class='transfer',
         subject={'type': 'nation', 'id': nation.name},
         metric_id='finance.treasury_flow', unit=nation.currency,
         after=amount, inputs={'tile': region.name, **inputs},
         cause_event_ids=cause_event_ids)


def pay_wages(region, t):
    """Firms pay wages to their employees (sovereign cash or company scrip under Truck System)."""
    owner = getattr(region, 'owner_nation', None)
    truck_act_enacted = getattr(owner, 'truck_act_enacted', False) if owner else False

    for a in region.agents:
        if a.is_corporation and len(a.employees) > 0:
            # If Truck Act enacted, pay_mode is legally mandated as 'cash'
            pay_mode = "cash" if truck_act_enacted else getattr(a, 'pay_mode', 'cash')

            # Cash-strapped firms adopt company scrip if Truck Act is not enacted
            if not truck_act_enacted and a.cash < len(a.employees) * getattr(a, 'wage', 1.0) and pay_mode == "cash":
                pay_mode = "scrip"
                a.pay_mode = "scrip"

            for e in a.employees:
                if getattr(e, 'is_striking', False) or getattr(e, 'in_revolt', False):
                    continue
                agreement = ensure_labor_agreement(e, a, t)
                wage_nominal = max(0.0, float(agreement.pay_rate))
                e.nominal_wage = wage_nominal
                e.authorized_deductions = 0.0
                e.wage_withheld = 0.0
                if pay_mode == "scrip":
                    # Truck System: paid in corporate company scrip vouchers
                    e.scrip_wallet += wage_nominal
                    e.wages_received = wage_nominal
                    e.realized_wage = wage_nominal
                    e.mem_push('mem_wages', wage_nominal)
                    a.scrip_issued += wage_nominal
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(region, 'scrip_wage', turn=t,
                                          payer_id=a.id, recipient_id=e.id,
                                          amount=wage_nominal,
                                          detail={'tender': 'company_scrip'})
                else:
                    # Legal tender cash payment
                    employer_cash_before = float(a.cash)
                    wage_to_pay = min(a.cash, wage_nominal)
                    a.cash -= wage_to_pay
                    e.cash += wage_to_pay
                    if wage_to_pay > 0:
                        from economy.actor_accounts import record as record_economic_event
                        record_economic_event(region, 'wage', turn=t,
                                              payer_id=a.id, recipient_id=e.id,
                                              amount=wage_to_pay)
                    e.wages_received = wage_to_pay
                    e.realized_wage = wage_to_pay
                    e.wage_withheld = wage_nominal - wage_to_pay
                    if e.wage_withheld > 1e-9:
                        from economy.actor_accounts import (accrue_wage_arrear,
                                                            record as record_economic_event)
                        payable_before, payable_after, claim_before, claim_after = (
                            accrue_wage_arrear(a, e.id, e.wage_withheld, worker=e))
                        liabilities = getattr(a, 'wage_liabilities', [])
                        liabilities.append({'worker_id': e.id, 'turn': t,
                                            'amount': e.wage_withheld, 'status': 'unpaid'})
                        a.wage_liabilities = liabilities[-500:]
                        record_economic_event(
                            region, 'wage_arrears_accrued', turn=t,
                            payer_id=a.id, recipient_id=e.id,
                            amount=e.wage_withheld,
                            currency=getattr(region, 'home_currency', None),
                            detail={'nominal_wage': wage_nominal,
                                    'cash_paid': wage_to_pay,
                                    'arrears_accrued': e.wage_withheld,
                                    'employer_cash_before': employer_cash_before,
                                    'employer_cash_after': float(a.cash),
                                    'employer_arrears_before': payable_before,
                                    'employer_arrears_after': payable_after,
                                    'worker_claim_before': claim_before,
                                    'worker_claim_after': claim_after,
                                    'reason': 'employer_cash_below_nominal_wage'})
                        from run_trace import emit
                        emit(region, kind='wage_arrears_accrued',
                             record_class='outcome', phase='finance',
                             subject={'type': 'employment_wage_claim',
                                      'id': f'{a.id}:{e.id}', 'tile': region.name,
                                      'employer_id': a.id, 'worker_id': e.id},
                             metric_id='finance.wage_arrears',
                             unit=getattr(region, 'home_currency', None)
                             or 'local_currency',
                             before=payable_before, after=payable_after,
                             formula_id='labor.wage_arrears_accrual.v1',
                             inputs={'employer_id': a.id, 'worker_id': e.id,
                                     'nominal_wage': wage_nominal,
                                     'cash_paid': wage_to_pay,
                                     'arrears_accrued': e.wage_withheld,
                                     'employer_cash_before': employer_cash_before,
                                     'employer_cash_after': float(a.cash),
                                     'worker_claim_before': claim_before,
                                     'worker_claim_after': claim_after,
                                     'truck_act_enacted': bool(truck_act_enacted),
                                     'pay_mode': pay_mode,
                                     'reason': 'employer_cash_below_nominal_wage'})
                    e.mem_push('mem_wages', wage_to_pay)


def settle_wage_arrears(region, t, *, firm_id=None, firm=None, liquidating=False):
    """Pay old wage claims from cash beyond the next payroll reserve.

    On liquidation, any available firm cash is available to wage claimants.
    The return value contains the settled claims; each transfer updates the
    employer's liability and the worker's cash or currency wallet.
    """
    from economy.actor_accounts import (
        _wage_liability_totals, record as record_economic_event,
        settle_wage_arrear,
    )
    by_id = {int(person.id): person for person in getattr(region, 'agents', ())}
    firms = [firm for firm in getattr(region, 'agents', ())
             if getattr(firm, 'is_corporation', False)
             and (liquidating or getattr(firm, 'alive', True))
             and (firm_id is None or firm.id == firm_id)]
    if firm_id is not None and not any(firm.id == firm_id for firm in firms):
        matched_firm = firm or by_id.get(int(firm_id))
        if (matched_firm is not None
                and int(matched_firm.id) == int(firm_id)
                and getattr(matched_firm, 'is_corporation', False)
                and (liquidating or getattr(matched_firm, 'alive', True))):
            firms.append(matched_firm)
    payments = []
    for firm in firms:
        total, claims = _wage_liability_totals(firm)
        if total <= 0 or not claims:
            continue
        payroll_reserve = 0.0
        if not liquidating:
            from labor_contract import ensure_labor_agreement
            for employee in getattr(firm, 'employees', ()):
                if not getattr(employee, 'alive', True) or getattr(employee, 'is_striking', False) or getattr(employee, 'in_revolt', False):
                    continue
                agreement = ensure_labor_agreement(employee, firm, t)
                payroll_reserve += max(0.0, float(agreement.pay_rate))
        available_cash = max(0.0, float(firm.cash) - payroll_reserve)
        if available_cash <= 1e-9:
            continue
        liability_rows = list(getattr(firm, 'wage_liabilities', ()))
        first_turn = {}
        for row in liability_rows:
            worker_id = int(row.get('worker_id', -1))
            if worker_id not in claims or str(row.get('status', 'unpaid')).lower() in {
                    'paid', 'settled', 'written_off', 'forgiven', 'cancelled', 'inherited'}:
                continue
            first_turn[worker_id] = min(first_turn.get(worker_id, int(row.get('turn', 0))),
                                        int(row.get('turn', 0)))
        for worker_id in sorted(claims, key=lambda ident: (first_turn.get(ident, t), ident)):
            if available_cash <= 1e-9:
                break
            worker = (by_id.get(int(worker_id))
                      or (getattr(firm, 'wage_arrears_claimants', {}) or {}).get(worker_id))
            if worker is None or not getattr(worker, 'alive', True):
                continue
            claim_before = float(claims[worker_id])
            paid = min(claim_before, available_cash)
            if paid <= 1e-9:
                continue
            firm_cash_before = float(firm.cash)
            worker_cash_before = float(worker.cash)
            currency = getattr(region, 'home_currency', None)
            local_institution_agents = {
                id(getattr(getattr(region, 'gov', None), 'agent', None)),
                id(getattr(getattr(region, 'charity', None), 'agent', None)),
            }
            is_local_worker = (by_id.get(int(worker_id)) is worker
                               or id(worker) in local_institution_agents)
            use_wallet = bool(currency and (
                not is_local_worker
                or getattr(worker, '_bank_ref', None) is not getattr(region, 'bank', None)))
            wallet_before = None
            if use_wallet:
                wallet_before = float(_fx.fx_balance(worker, currency))
                _fx.fx_add(worker, currency, paid)
            else:
                worker.cash += paid
            firm.cash -= paid
            total_before, total_after, claim_before, claim_after, settled = (
                settle_wage_arrear(firm, worker_id, paid))
            if settled <= 0:
                # State is checked before changing either balance, so this is
                # only a defensive guard for corrupt or stale claim records.
                firm.cash += paid
                if use_wallet:
                    _fx.fx_sub(worker, currency, paid)
                else:
                    worker.cash -= paid
                continue
            transfer_id = f'wage-arrears:{t}:{firm.id}:{worker.id}:{len(payments)}'
            detail = {
                'transfer_id': transfer_id, 'payment_kind': 'wage_arrears_paid',
                'employer_id': firm.id, 'worker_id': worker.id,
                'currency': currency, 'amount': float(settled),
                'employer_cash_before': firm_cash_before,
                'employer_cash_after': float(firm.cash),
                'worker_cash_before': worker_cash_before,
                'worker_cash_after': float(worker.cash),
                'claim_before': float(claim_before),
                'claim_after': float(claim_after),
                'employer_payable_before': float(total_before),
                'employer_payable_after': float(total_after),
                'payroll_reserve': float(payroll_reserve),
                'liquidation': bool(liquidating),
            }
            cash_event = record_economic_event(
                region, 'wage_arrears_paid', turn=t, payer_id=firm.id,
                recipient_id=None if use_wallet else worker.id,
                amount=settled, asset_id=transfer_id, source_id=transfer_id,
                currency=currency,
                detail={**detail, 'settlement': 'foreign_wallet' if use_wallet else 'cash'})
            wallet_event = None
            if use_wallet:
                wallet_event = record_economic_event(
                    region, 'wallet_transfer_in', turn=t,
                    recipient_id=worker.id, amount=settled,
                    asset_id=transfer_id, source_id=transfer_id,
                    currency=currency,
                    detail={**detail, 'payment_kind': 'wage_arrears_paid',
                            'wallet_before': wallet_before,
                            'wallet_after': float(_fx.fx_balance(worker, currency))})
            from run_trace import emit
            emit(region, kind='wage_arrears_repaid', record_class='transfer',
                 phase='finance',
                 subject={'type': 'employment_wage_claim',
                          'id': f'{firm.id}:{worker.id}', 'tile': region.name,
                          'employer_id': firm.id, 'worker_id': worker.id},
                 metric_id='finance.wage_arrears', unit=currency or 'local_currency',
                 before=float(claim_before), after=float(claim_after),
                 formula_id='labor.wage_arrears.repayment.v1',
                 inputs={**detail, 'cash_event': {'tile': region.name,
                                                  'event_id': cash_event['id']},
                         'wallet_event': ({'tile': region.name,
                                           'event_id': wallet_event['id']}
                                          if wallet_event else None),
                         'reason': ('firm_liquidation' if liquidating else
                                    'surplus_after_current_payroll')})
            payments.append({'firm_id': firm.id, 'worker_id': worker.id,
                             'amount': settled, 'claim_after': claim_after,
                             'transfer_id': transfer_id})
            available_cash -= settled
    return payments


def liquidate_wage_arrears(region, t, firm, *, reason='firm_exit'):
    """Use a departing firm's remaining cash for wage claims, then write off loss."""
    from economy.actor_accounts import (
        _wage_liability_totals, record as record_economic_event,
        writeoff_wage_arrear,
    )
    payments = settle_wage_arrears(
        region, t, firm_id=firm.id, firm=firm, liquidating=True)
    _, claims = _wage_liability_totals(firm)
    written_off = []
    for worker_id, claim_amount in sorted(claims.items()):
        total_before, total_after, claim_before, claim_after, amount = (
            writeoff_wage_arrear(firm, worker_id, claim_amount))
        if amount <= 0:
            continue
        event = record_economic_event(
            region, 'wage_arrears_written_off', turn=t,
            payer_id=firm.id, recipient_id=worker_id, amount=amount,
            asset_id=f'wage-arrears:{firm.id}:{worker_id}',
            source_id=f'wage-arrears:{firm.id}:{worker_id}',
            currency=getattr(region, 'home_currency', None),
            detail={'employer_id': firm.id, 'worker_id': worker_id,
                    'employer_payable_before': float(total_before),
                    'employer_payable_after': float(total_after),
                    'claim_before': float(claim_before),
                    'claim_after': float(claim_after),
                    'reason': reason, 'settlement': 'limited_liability_writeoff'})
        from run_trace import emit
        emit(region, kind='wage_arrears_written_off', record_class='outcome',
             phase='finance',
             subject={'type': 'employment_wage_claim',
                      'id': f'{firm.id}:{worker_id}', 'tile': region.name,
                      'employer_id': firm.id, 'worker_id': worker_id},
             metric_id='finance.wage_arrears',
             unit=getattr(region, 'home_currency', None) or 'local_currency',
             before=float(claim_before), after=float(claim_after),
             formula_id='labor.wage_arrears.employer_exit_writeoff.v1',
             inputs={'event_id': event['id'], 'employer_id': firm.id,
                     'worker_id': worker_id, 'amount': float(amount),
                     'reason': reason,
                     'cash_recovered': sum(row['amount'] for row in payments)})
        written_off.append({'worker_id': worker_id, 'amount': amount,
                            'event_id': event['id']})

    orphaned = max(0.0, float(getattr(firm, 'wage_arrears_balance', 0.0)))
    if orphaned > 1e-9:
        before = orphaned
        firm.wage_arrears_balance = 0.0
        event = record_economic_event(
            region, 'wage_arrears_written_off', turn=t, payer_id=firm.id,
            amount=orphaned, asset_id=f'wage-arrears:{firm.id}:orphaned',
            source_id=f'wage-arrears:{firm.id}:orphaned',
            currency=getattr(region, 'home_currency', None),
            detail={'employer_id': firm.id, 'employer_payable_before': before,
                    'employer_payable_after': 0.0, 'reason': reason,
                    'settlement': 'unmatched_liability_writeoff',
                    'claimant_id_missing': True})
        from run_trace import emit
        emit(region, kind='wage_arrears_writeoff_without_claimant',
             record_class='outcome', phase='finance',
             subject={'type': 'agent', 'id': firm.id, 'tile': region.name},
             metric_id='finance.wage_arrears',
             unit=getattr(region, 'home_currency', None) or 'local_currency',
             before=before, after=0.0,
             formula_id='labor.wage_arrears.orphan_liability_writeoff.v1',
             inputs={'event_id': event['id'], 'reason': reason,
                     'employer_id': firm.id})
    return {'payments': payments, 'written_off': written_off,
            'cash_recovered': sum(row['amount'] for row in payments),
            'claims_written_off': sum(row['amount'] for row in written_off)}


def redeem_company_scrip(region, t):
    """Workers redeem company scrip at the employer's company store ('Tommy Shop') for marked-up food.

    Strictly 100% money and goods conserved:
      - Food moves 1-for-1 from firm inventory to employee.
      - Scrip is retired (store credit settled). Zero sovereign currency leaked.
      - If worker is broke and unfed, company store issues emergency food on credit ('slate'),
        bonding the worker into debt peonage (company_debt).
    """
    food_price = getattr(region, 'food_price', 1.0)
    tommy_markup = 1.35  # Historical 35% Tommy Shop markup over open market

    for a in region.agents:
        if not a.is_corporation or not a.employees:
            continue

        for e in a.employees:
            if not getattr(e, 'alive', True):
                continue
            food_needed = max(0, 4 - e.inv_get(Goods.food, 0))
            if food_needed <= 0:
                continue

            tommy_price = round(food_price * tommy_markup, 2)

            # 1. Scrip Redemption at Tommy Shop
            if getattr(e, 'scrip_wallet', 0.0) >= tommy_price:
                can_buy = min(food_needed, int(e.scrip_wallet // tommy_price))
                if can_buy > 0:
                    firm_food = a.inv_get(Goods.food, 0)
                    if firm_food < can_buy and a.cash >= (can_buy - firm_food) * food_price:
                        needed_to_buy = can_buy - firm_food
                        for seller in region.agents:
                            if seller.id != a.id and seller.inv_get(Goods.food, 0) > 0 and not seller.is_corporation:
                                qty = min(needed_to_buy, seller.inv_get(Goods.food, 0))
                                cost = qty * food_price
                                if a.cash >= cost:
                                    a.cash -= cost
                                    seller.cash += cost
                                    seller.inv_add(Goods.food, -qty)
                                    a.inv_add(Goods.food, qty)
                                    from economy.actor_accounts import record as record_economic_event
                                    record_economic_event(region, 'store_inventory_purchase', turn=t,
                                                          payer_id=a.id, recipient_id=seller.id,
                                                          good=Goods.food, quantity=qty, amount=cost,
                                                          detail={'tender': 'cash', 'store_markup': tommy_markup})
                                    needed_to_buy -= qty
                                    if needed_to_buy <= 0:
                                        break

                    available = min(can_buy, a.inv_get(Goods.food, 0))
                    if available > 0:
                        total_cost = available * tommy_price
                        e.scrip_wallet -= total_cost
                        a.scrip_redeemed += total_cost
                        a.inv_add(Goods.food, -available)
                        e.inv_add(Goods.food, available)
                        from economy.actor_accounts import record as record_economic_event
                        record_economic_event(region, 'scrip_store_sale', turn=t,
                                              payer_id=e.id, recipient_id=a.id,
                                              good=Goods.food, quantity=available,
                                              amount=total_cost,
                                              detail={'tender': 'company_scrip',
                                                      'unit_price': tommy_price})
                        e.food_purchased = getattr(e, 'food_purchased', 0) + available
                        food_needed -= available

            # 2. Debt Peonage Credit Advance (The Slate)
            if food_needed > 0 and e.inv_get(Goods.food, 0) < 2 and e.cash < food_price and e.scrip_wallet < tommy_price:
                if a.inv_get(Goods.food, 0) > 0:
                    a.inv_add(Goods.food, -1)
                    e.inv_add(Goods.food, 1)
                    e.food_purchased = getattr(e, 'food_purchased', 0) + 1
                    e.company_debt += tommy_price
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(region, 'scrip_food_credit', turn=t,
                                          payer_id=a.id, recipient_id=e.id,
                                          good=Goods.food, quantity=1,
                                          amount=tommy_price, debt_credit=tommy_price,
                                          detail={'tender': 'company_store_credit',
                                                  'company_debt_after': e.company_debt})
                    e.despair = min(1.0, getattr(e, 'despair', 0.0) + 0.15)
                    e.alienation = min(1.0, getattr(e, 'alienation', 0.0) + 0.10)
                    try:
                        from economy.true_cost_ledger import get_true_cost_ledger
                        get_true_cost_ledger().record_bank(
                            bank=a, region=region, turn=t,
                            interest_and_discounts=0.0, funding_costs=0.0,
                            scrip_debt_issued=tommy_price
                        )
                    except Exception:
                        pass


def credit_owner_pay(region, owner, amount):
    """Credit an owner's share, routing through the FX wallet when
    the owner lives on a DIFFERENT (or wilderness) tile so the
    per-currency audit still counts the money."""
    if amount <= 0:
        return {'tender': 'none', 'currency': None,
                'balance_before': 0.0, 'balance_after': 0.0}
    if getattr(owner, '_bank_ref', None) is region.bank:
        balance_before = float(owner.cash)
        owner.cash += amount
        return {'tender': 'cash', 'currency': getattr(region, 'home_currency', None),
                'balance_before': balance_before,
                'balance_after': float(owner.cash)}
    else:
        if region.home_currency:
            balance_before = float(_fx.fx_balance(owner, region.home_currency))
            _fx.fx_add(owner, region.home_currency, amount)
            return {'tender': 'wallet', 'currency': region.home_currency,
                    'balance_before': balance_before,
                    'balance_after': float(_fx.fx_balance(owner, region.home_currency))}
        else:
            balance_before = float(owner.cash)
            owner.cash += amount
            return {'tender': 'cash', 'currency': None,
                    'balance_before': balance_before,
                    'balance_after': float(owner.cash)}


def _record_owner_payment(region, kind, payer, owner, amount, settlement, t=None,
                          owner_loan_before=None, owner_loan_after=None):
    """Post a firm's cash payment and the owner's cash or wallet receipt."""
    from economy.actor_accounts import record as record_economic_event

    turn = int(t if t is not None else getattr(region, '_last_turn', 0))
    currency = settlement.get('currency') or getattr(region, 'home_currency', None)
    transfer_id = f'owner-payment:{kind}:{turn}:{payer.id}:{owner.id}'
    detail = {'transfer_id': transfer_id, 'payment_kind': kind,
              'tender': settlement.get('tender', 'cash'),
              'payment_currency': currency,
              'owner_balance_before': settlement.get('balance_before', 0.0),
              'owner_balance_after': settlement.get('balance_after', 0.0),
              'payer_id': payer.id, 'owner_id': owner.id}
    if owner_loan_before is not None:
        detail['owner_loan_before'] = float(owner_loan_before)
    if owner_loan_after is not None:
        detail['owner_loan_after'] = float(owner_loan_after)
    if settlement.get('tender') == 'wallet':
        record_economic_event(
            region, kind, turn=turn, payer_id=payer.id, amount=amount,
            asset_id=transfer_id, currency=currency,
            detail={**detail, 'recipient_settlement': 'foreign_wallet'})
        record_economic_event(
            region, 'wallet_transfer_in', turn=turn, recipient_id=owner.id,
            amount=amount, asset_id=transfer_id, source_id=transfer_id,
            currency=currency, detail=detail)
    else:
        record_economic_event(
            region, kind, turn=turn, payer_id=payer.id,
            recipient_id=owner.id, amount=amount, asset_id=transfer_id,
            currency=currency, detail=detail)

    from run_trace import emit
    payer_cash_after = float(payer.cash)
    payer_cash_before = payer_cash_after + float(amount)
    value_before = (detail['owner_balance_before']
                    if settlement.get('tender') == 'wallet'
                    else payer_cash_before)
    value_after = (detail['owner_balance_after']
                   if settlement.get('tender') == 'wallet'
                   else payer_cash_after)
    emit(region, kind='owner_payment_settled', record_class='transfer',
         phase='finance',
         subject={'type': 'owner_payment', 'id': transfer_id,
                  'payer_id': payer.id, 'owner_id': owner.id,
                  'tile': region.name},
         metric_id='finance.owner_transfer', unit=currency or 'local_currency',
         before=value_before, after=value_after,
         inputs={**detail, 'amount': float(amount),
                 'payer_cash_before': payer_cash_before,
                 'payer_cash_after': payer_cash_after})


def _record_owner_funding(region, owner, firm, amount, tender, currency,
                          source_before, source_after, firm_cash_before,
                          firm_cash_after, owner_loan_before, owner_loan_after,
                          t):
    """Record an owner's cash or wallet loan into a firm."""
    from economy.actor_accounts import record as record_economic_event

    turn = int(t if t is not None else getattr(region, '_last_turn', 0))
    transfer_id = f'owner-financing:{turn}:{owner.id}:{firm.id}'
    detail = {'transfer_id': transfer_id, 'tender': tender,
              'currency': currency, 'amount': float(amount),
              'owner_id': owner.id, 'firm_id': firm.id,
              'source_balance_before': float(source_before),
              'source_balance_after': float(source_after),
              'firm_cash_before': float(firm_cash_before),
              'firm_cash_after': float(firm_cash_after),
              'owner_loan_before': float(owner_loan_before),
              'owner_loan_after': float(owner_loan_after),
              'reason': 'owner_payroll_bailout'}
    if tender == 'wallet':
        record_economic_event(
            region, 'owner_financing', turn=turn, recipient_id=firm.id,
            amount=amount, asset_id=transfer_id, currency=currency,
            detail={**detail, 'funding_source': 'owner_wallet'})
        record_economic_event(
            region, 'wallet_transfer_out', turn=turn, payer_id=owner.id,
            amount=amount, asset_id=transfer_id, source_id=transfer_id,
            currency=currency, detail=detail)
    else:
        record_economic_event(
            region, 'owner_financing', turn=turn, payer_id=owner.id,
            recipient_id=firm.id, amount=amount, asset_id=transfer_id,
            currency=currency, detail=detail)

    from run_trace import emit
    emit(region, kind='owner_financing_settled', record_class='transfer',
         phase='finance',
         subject={'type': 'owner_financing', 'id': transfer_id,
                  'owner_id': owner.id, 'firm_id': firm.id,
                  'tile': region.name},
         metric_id='finance.owner_transfer',
         unit=currency or 'local_currency',
         before=float(source_before), after=float(source_after),
         inputs=detail)


def repay_owner_loan(region, agent, owner, payroll, t=None):
    """Repay debt owed by corporation back to its owner."""
    if agent.owner_loan <= 0:
        return
    repay = min(agent.owner_loan, max(0, agent.cash - payroll * 2))
    if repay > 0:
        owner_loan_before = float(agent.owner_loan)
        agent.cash -= repay
        settlement = credit_owner_pay(region, owner, repay)
        agent.owner_loan -= repay
        _record_owner_payment(
            region, 'owner_loan_repayment', agent, owner, repay, settlement,
            t=t, owner_loan_before=owner_loan_before,
            owner_loan_after=agent.owner_loan)


def pay_base_salary(region, agent, owner, payroll, t=None):
    """Pay owner's executive base salary if cash reserve allows."""
    if agent.cash > payroll * 2 + agent.wage:
        agent.cash -= agent.wage
        settlement = credit_owner_pay(region, owner, agent.wage)
        _record_owner_payment(region, 'owner_salary', agent, owner, agent.wage,
                              settlement, t=t)


def pay_profit_share(region, agent, owner, payroll, t=None):
    """Distribute retained earnings / profit dividends to the owner."""
    if agent.retained_earnings <= 0 or agent.cash <= payroll * 2:
        return
    operating_expenses = payroll * 2
    ratio = agent.retained_earnings / operating_expenses
    share_rate = 0.25 * ratio / (ratio + 5)
    profit_draw = min(share_rate * agent.retained_earnings, max(0, agent.cash - payroll * 2))
    if profit_draw > 0:
        agent.cash -= profit_draw
        settlement = credit_owner_pay(region, owner, profit_draw)
        agent.retained_earnings -= profit_draw
        _record_owner_payment(region, 'dividend', agent, owner, profit_draw,
                              settlement, t=t)
        try:
            from economy.true_cost_ledger import get_true_cost_ledger
            get_true_cost_ledger().record_finance_deductions(
                agent, region, getattr(region, '_last_turn', 0), dividend_paid=profit_draw
            )
        except Exception:
            pass


def bailout_owner(region, agent, owner, payroll, t=None):
    """Owner injects cash into the firm to cover payroll shortfall."""
    if agent.cash >= payroll:
        return
    food_price = region.food_price
    if getattr(owner, '_bank_ref', None) is region.bank:
        avail = max(0.0, owner.cash - food_price * 4)
        inject = min(payroll - agent.cash, avail)
        if inject > 0:
            source_before = float(owner.cash)
            firm_cash_before = float(agent.cash)
            owner_loan_before = float(agent.owner_loan)
            owner.cash -= inject
            agent.cash += inject
            agent.owner_loan += inject
            _record_owner_funding(
                region, owner, agent, inject, 'cash',
                getattr(region, 'home_currency', None),
                source_before, owner.cash, firm_cash_before, agent.cash,
                owner_loan_before, agent.owner_loan, t)
    else:
        if region.home_currency:
            avail = _fx.fx_balance(owner, region.home_currency)
            inject = min(payroll - agent.cash, max(0.0, avail))
            if inject > 0:
                source_before = float(avail)
                firm_cash_before = float(agent.cash)
                owner_loan_before = float(agent.owner_loan)
                _fx.fx_add(owner, region.home_currency, -inject)
                agent.cash += inject
                agent.owner_loan += inject
                _record_owner_funding(
                    region, owner, agent, inject, 'wallet', region.home_currency,
                    source_before, _fx.fx_balance(owner, region.home_currency),
                    firm_cash_before, agent.cash, owner_loan_before,
                    agent.owner_loan, t)


def distribute_profits(region, t):
    """Distribute firm profits to owners, service owner loans, or execute bailouts."""
    for a in region.agents:
        if not a.is_corporation or not a.alive:
            continue
        if a.owner is None or not a.owner.alive:
            continue
        owner = a.owner
        payroll = max(1, len(a.employees) * a.wage)
        repay_owner_loan(region, a, owner, payroll, t=t)
        profit = max(0, a._delta_cash + a._delta_deposits)
        if profit > 0 or a.cash > payroll * 2:
            a.retained_earnings += profit
        pay_base_salary(region, a, owner, payroll, t=t)
        pay_profit_share(region, a, owner, payroll, t=t)
        bailout_owner(region, a, owner, payroll, t=t)


def collect_tax(region, t):
    """Budget-balanced taxation with deficit financing."""
    if getattr(region, 'province', None) is not None \
            and not getattr(region, '_seat_gov_agent', True):
        return
    gov = region.gov.agent
    bank = region.bank
    food_price = region.food_price

    # ---- 1. Service existing government debt ----
    debt_service_trace_ids = []
    for loan in gov.loans[:]:
        remaining = loan.principle - loan.principle_paid
        if remaining <= 0:
            gov.loans.remove(loan)
            if loan in bank.loans:
                bank.loans.remove(loan)
            continue
        amount_due = remaining + loan.getInterest()
        available = gov.cash + bank.deposits.get(gov, 0)
        payment = min(amount_due, available)
        if payment > 0:
            if gov.cash < payment:
                bank.Withdraw(gov, payment - gov.cash, trace_region=region, t=t,
                              reason='government_debt_service')
            gov.cash -= payment
            loan.pay(payment)
            from economy.actor_accounts import record as record_economic_event
            record_economic_event(region, 'bank_loan_repayment', turn=t,
                                  payer_id=gov.id, amount=payment,
                                  detail={'public_debt_service': True,
                                          'principal_remaining_before': remaining})
            service_id = _trace_treasury_flow(
                region, 'government_loan_service', -payment,
                {'loan_principal_remaining_before': remaining,
                 'amount_due': amount_due})
            if service_id is not None:
                debt_service_trace_ids.append(service_id)
        if loan.isPaid():
            gov.loans.remove(loan)
            if loan in bank.loans:
                bank.loans.remove(loan)

    # ---- 2. Compute deficit against target reserve ----
    loans_outstanding = sum(l.principle - l.principle_paid for l in gov.loans)
    net_worth = (gov.cash + bank.deposits.get(gov, 0)
                 + region.gov.food_inventory * food_price - loans_outstanding)
    reserve = region.gov.target_food_reserve * food_price * 2
    deficit = max(0.0, reserve - net_worth)
    from run_trace import emit
    budget_trace_id = emit(
        region, kind='government_reserve_deficit_calculation',
        record_class='calculation', phase='finance',
        subject={'type': 'tile', 'id': region.name},
        metric_id='finance.fiscal_deficit',
        unit=getattr(region, 'home_currency', None) or 'local_currency',
        after=deficit, formula_id='fiscal.reserve_deficit.v1',
        inputs={'government': region.gov.name, 'turn': int(t),
                'cash_after_debt_service': float(gov.cash),
                'deposits_after_debt_service': float(bank.deposits.get(gov, 0)),
                'food_inventory': float(region.gov.food_inventory),
                'food_price': float(food_price),
                'loans_outstanding': float(loans_outstanding),
                'target_food_reserve': float(region.gov.target_food_reserve),
                'reserve_multiplier': 2.0, 'net_worth': float(net_worth),
                'target_cash_reserve': float(reserve),
                'sample_point': 'after debt service, before income tax and borrowing'},
        cause_event_ids=debt_service_trace_ids or None)

    # ---- 3. Tax top 10% just enough to cover the deficit ----
    tax_collected = 0.0
    turn_nat_tax = 0.0
    turn_prov_tax = 0.0
    turn_tile_tax = 0.0
    top_count = 0
    if deficit > 0:
        living = [a for a in region.agents if a.alive]
        if len(living) > 10:
            sorted_agents = sorted(living, key=lambda a: a.wealth(), reverse=True)
            top_count = max(1, int(len(sorted_agents) * 0.1))
            top = sorted_agents[:top_count]
            tax_bills = []
            total_taxable = 0.0
            for a in top:
                net_income = a._delta_cash + a._delta_deposits
                taxable = max(0.0, net_income + a.tax_loss_carryforward)
                if hasattr(region.gov, 'compute_child_tax_deduction'):
                    taxable = max(0.0, taxable - region.gov.compute_child_tax_deduction(a))
                tax_bills.append((a, taxable, net_income))
                total_taxable += taxable
            if total_taxable > 0:
                effective_rate = min(region.gov.tax_rate, deficit / total_taxable)
                for a, taxable, net_income in tax_bills:
                    if taxable <= 0:
                        a.tax_loss_carryforward += net_income
                        continue
                    tax_amount = taxable * effective_rate
                    bank_balance = bank.deposits.get(a, 0)
                    actual = min(tax_amount, a.cash + bank_balance)
                    if actual > 0:
                        cash_taken = min(a.cash, actual)
                        a.cash -= cash_taken
                        deposit_taken = min(bank_balance, actual - cash_taken)
                        if deposit_taken > 0:
                            bank.Withdraw(a, deposit_taken, trace_region=region, t=t,
                                          reason='income_tax_payment')
                            a.cash -= deposit_taken
                        try:
                            from economy.true_cost_ledger import get_true_cost_ledger
                            get_true_cost_ledger().record_finance_deductions(
                                a, region, t, taxes_paid=actual
                            )
                        except Exception:
                            pass
                    a.tax_loss_carryforward = 0.0

                    # Multi-Tier Statutory Split: 50% National Sovereign, 30% Provincial, 20% Municipal
                    owner_nation = getattr(region, 'owner_nation', None)
                    province = getattr(region, 'province', None)
                    nat_gov = getattr(owner_nation, 'government', None) if owner_nation else None
                    prov_gov = getattr(province, 'gov', None) if province else None
                    tile_gov = region.gov
                    nat_share = prov_share = tile_share = 0.0

                    if nat_gov is not None and nat_gov is not tile_gov:
                        if prov_gov is not None and prov_gov is not tile_gov and prov_gov is not nat_gov:
                            nat_share = round(actual * 0.50, 6)
                            prov_share = round(actual * 0.30, 6)
                            tile_share = actual - nat_share - prov_share

                            nat_gov.agent.cash += nat_share
                            nat_gov.record_income(t, 'tax', nat_share)

                            prov_gov.agent.cash += prov_share
                            prov_gov.record_income(t, 'tax', prov_share)

                            tile_gov.agent.cash += tile_share
                            tile_gov.record_income(t, 'tax', tile_share)

                            turn_nat_tax += nat_share
                            turn_prov_tax += prov_share
                            turn_tile_tax += tile_share
                        else:
                            # 2-Tier: 50% National, 50% Local/Provincial
                            nat_share = round(actual * 0.50, 6)
                            tile_share = actual - nat_share

                            nat_gov.agent.cash += nat_share
                            nat_gov.record_income(t, 'tax', nat_share)

                            tile_gov.agent.cash += tile_share
                            tile_gov.record_income(t, 'tax', tile_share)

                            turn_nat_tax += nat_share
                            turn_tile_tax += tile_share
                    else:
                        # Single-Tier / Independent
                        tile_share = actual
                        tile_gov.agent.cash += actual
                        tile_gov.record_income(t, 'tax', actual)
                        turn_tile_tax += actual

                    from economy.actor_accounts import record as record_economic_event
                    for treasury, share in ((nat_gov, nat_share), (prov_gov, prov_share),
                                            (tile_gov, tile_share)):
                        if treasury is not None and share > 0:
                            record_economic_event(region, 'tax', turn=t, payer_id=a.id,
                                                  recipient_id=treasury.agent.id,
                                                  amount=share,
                                                  detail={'tax_base': taxable})

                    tax_collected += actual

    if not hasattr(region, 'tax_distribution_log'):
        region.tax_distribution_log = []
    region.tax_distribution_log.append({
        'total': tax_collected,
        'municipal': turn_tile_tax,
        'provincial': turn_prov_tax,
        'national': turn_nat_tax,
    })
    tax_trace_id = _trace_treasury_flow(region, 'income_tax_collected', tax_collected,
                         {'municipal': turn_tile_tax, 'provincial': turn_prov_tax,
                          'national': turn_nat_tax, 'tax_rate': region.gov.tax_rate,
                          'deficit_before_tax': deficit, 'taxpayer_count': top_count})

    # ---- 4. If still short, borrow from the bank ----
    gap = max(0.0, deficit - tax_collected)
    previous_gap = region.gov.borrow_log[-1] if region.gov.borrow_log else None
    region.gov.borrow_log.append(gap)
    gap_trace_id = emit(
        region, kind='government_remaining_financing_gap',
        record_class='calculation', phase='finance',
        subject={'type': 'tile', 'id': region.name},
        metric_id='finance.fiscal_gap',
        unit=getattr(region, 'home_currency', None) or 'local_currency',
        before=previous_gap, after=gap,
        formula_id='fiscal.remaining_tax_gap.v1',
        inputs={'government': region.gov.name, 'turn': int(t),
                'reserve_deficit': float(deficit),
                'tax_collected': float(tax_collected),
                'borrow_request_threshold': 0.01,
                'borrowing_requested': bool(gap > 0.01),
                'meaning': 'requested financing need before bank approval'},
        cause_event_ids=[event_id for event_id in (budget_trace_id, tax_trace_id)
                         if event_id is not None] or None)
    if gap > 0.01:
        before_liab = bank.total_liabilities
        bank.Borrow(t, gov, gap, trace_region=region)
        borrowed = bank.total_liabilities - before_liab
        _trace_treasury_flow(region, 'government_bank_borrowing', borrowed,
                             {'requested_gap': gap, 'bank_liabilities_before': before_liab,
                              'bank_liabilities_after': bank.total_liabilities},
                             cause_event_ids=([gap_trace_id] if gap_trace_id else None))
        if borrowed > 0:
            loginfo(t, f"Government({region.gov.name}) borrowed ${borrowed:.2f} "
                    f"to cover deficit (gap ${gap:.2f})")
        else:
            logwarning(t, f"Government({region.gov.name}) could not borrow "
                          f"${gap:.2f} (bank capacity exhausted)")

    # ---- 5. Re-evaluate tax rate every interval ----
    tax_rate_before = region.gov.tax_rate
    interval_due = t % region.gov.tax_adjust_interval == 0
    history_ready = len(region.gov.borrow_log) >= region.gov.tax_adjust_interval
    recent_gaps = []
    avg_gap = None
    new_rate = tax_rate_before
    rate_reason = 'interval_not_due' if not interval_due else 'insufficient_gap_history'
    if interval_due and history_ready:
        recent_gaps = region.gov.borrow_log[-region.gov.tax_adjust_interval:]
        avg_gap = sum(recent_gaps) / len(recent_gaps)
        if avg_gap > reserve * 0.1:
            new_rate = region.gov.tax_rate * 1.5
            rate_reason = 'persistent_financing_gap'
        elif avg_gap == 0 and net_worth > reserve * 2:
            new_rate = region.gov.tax_rate * 0.7
            rate_reason = 'zero_gap_and_large_reserve_surplus'
        else:
            new_rate = region.gov.tax_rate
            rate_reason = 'within_fiscal_band'
        region.gov.tax_rate = max(0.05, min(0.75, new_rate))
        region.gov.tax_rate_log.append((t, region.gov.tax_rate))
        print(f"  Region '{region.name}' fiscal: gov_net=${net_worth:.0f}, "
              f"reserve=${reserve:.0f}, avg_gap=${avg_gap:.2f}, "
              f"tax_rate={region.gov.tax_rate:.2f}")

    emit(region, kind='government_tax_rate_decision',
         record_class='calculation', phase='finance',
         subject={'type': 'tile', 'id': region.name},
         metric_id='finance.tax_rate', unit='ratio',
         before=tax_rate_before, after=region.gov.tax_rate,
         formula_id='fiscal.tax_rate_adjustment.v1',
         inputs={'government': region.gov.name, 'turn': int(t),
                 'prior_tax_rate': float(tax_rate_before),
                 'adjust_interval': int(region.gov.tax_adjust_interval),
                 'borrow_history_count': len(region.gov.borrow_log),
                 'interval_due': bool(interval_due),
                 'history_ready': bool(history_ready),
                 'recent_requested_gaps': list(recent_gaps),
                 'mean_requested_gap': avg_gap,
                 'target_cash_reserve': float(reserve),
                 'net_worth_before_tax_and_borrowing': float(net_worth),
                 'gap_threshold_fraction': 0.1, 'surplus_reserve_multiplier': 2.0,
                 'increase_multiplier': 1.5, 'decrease_multiplier': 0.7,
                 'unclamped_rate': float(new_rate),
                 'rate_floor': 0.05, 'rate_ceiling': 0.75,
                 'clamp_applied': bool(interval_due and history_ready),
                 'reason': rate_reason},
         cause_event_ids=[event_id for event_id in (budget_trace_id, gap_trace_id)
                          if event_id is not None] or None)

    if tax_collected > 0 and t % 50 == 0:
        print(f"  Region '{region.name}' TAX: ${tax_collected:.2f} from top "
              f"{top_count}, gov=${region.gov.agent.cash:.2f}, "
              f"debt=${loans_outstanding:.2f}")


def recalculate_multipliers(region):
    """Update consumption multipliers based on agent wealth vs cost of living."""
    cost_of_living = region.cost_of_living
    for a in region.agents:
        if not a.alive or a.is_corporation:
            continue
        wealth = a.wealth()
        a.consumption_multiplier = max(1.0, min(10.0, math.sqrt(wealth / cost_of_living))) if wealth > cost_of_living else 1.0
