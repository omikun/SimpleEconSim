"""Public-account evidence for private equity and direct inventory sales."""
import math


def _trace_government_company_equity(
        region, *, founder, company, turn, amount, founder_cash_before,
        founder_cash_after, company_cash_before, company_cash_after,
        public_write_event_ids, investment_event_id, investment_kind):
    """Record public cash invested into a private company as a treasury outflow."""
    government = getattr(region, 'gov', None)
    owner_nation = getattr(region, 'owner_nation', None)
    public_write_event_ids = list(public_write_event_ids or ())
    if (government is None or getattr(government, 'agent', None) is not founder
            or owner_nation is None or not public_write_event_ids):
        return None
    founder_debit = float(founder_cash_before) - float(founder_cash_after)
    company_receipt = float(company_cash_after) - float(company_cash_before)
    if founder_debit <= 0.0:
        return None

    from finance_trace import account_ref, emit_treasury_leg, transfer_contract

    currency = (getattr(owner_nation, 'currency', None)
                or getattr(region, 'home_currency', None) or 'local_currency')
    payer_account = account_ref(
        'government_treasury', government.name, currency,
        nation_id=owner_nation.name, subaccount='government_agent.cash',
        balance_before=float(founder_cash_before),
        balance_after=float(founder_cash_after),
        balance_scope='government_agent.cash')
    payee_account = account_ref(
        'agent', company.id, currency,
        balance_before=float(company_cash_before),
        balance_after=float(company_cash_after), balance_scope='cash')
    matches = math.isclose(
        founder_debit, company_receipt, rel_tol=1e-10, abs_tol=1e-8)
    operation_id = (
        f'government-company-equity:{investment_kind}:{turn}:'
        f'{founder.id}:{company.id}')
    contract = transfer_contract(
        operation_id, 'government_company_equity_investment', side='payer',
        amount=founder_debit, amount_currency=currency,
        payer_account=payer_account, payee_account=payee_account,
        local_cash_leg_amount=founder_debit,
        local_cash_leg_currency=currency,
        counterparty_leg_status=(
            'company_cash_balance_captured' if matches
            else 'company_cash_balance_differs_from_public_debit'),
        company_equity_event=investment_event_id,
        investment_kind=investment_kind)
    causes = [*public_write_event_ids]
    if investment_event_id is not None:
        causes.append(investment_event_id)
    return emit_treasury_leg(
        region, kind='government_company_equity_investment',
        nation_name=owner_nation.name, currency=currency,
        signed_amount=-founder_debit, contract=contract, phase='local',
        subject_type='nation', cause_event_ids=causes,
        inputs={'founder_id': founder.id, 'company_id': company.id,
                'company_sector': getattr(company.output, 'name', str(company.output)),
                'investment_kind': investment_kind,
                'amount': float(amount), 'treasury_debit': founder_debit,
                'company_cash_receipt': company_receipt, 'turn': int(turn)})

def _trace_government_inventory_liquidation(
        region, *, seller, buyer, good, quantity, amount, turn,
        seller_cash_before, seller_cash_after, seller_write_event_ids,
        buyer_cash_before, buyer_cash_after, buyer_write_event_ids,
        decision_event_id):
    """Record counted public-account legs in elite direct inventory sales."""
    owner_nation = getattr(region, 'owner_nation', None)
    if owner_nation is None or decision_event_id is None:
        return []
    from finance_trace import account_ref, emit_treasury_leg, transfer_contract

    currency = (getattr(owner_nation, 'currency', None)
                or getattr(region, 'home_currency', None) or 'local_currency')

    def account(agent, balance_before, balance_after):
        if getattr(agent, 'is_government', False):
            return account_ref(
                'government_treasury', agent.id, currency,
                nation_id=owner_nation.name,
                subaccount='government_agent.cash',
                balance_before=float(balance_before),
                balance_after=float(balance_after),
                balance_scope='government_agent.cash')
        return account_ref(
            'agent', agent.id, currency,
            balance_before=float(balance_before),
            balance_after=float(balance_after), balance_scope='cash')

    emitted = []
    seller_receipt = float(seller_cash_after) - float(seller_cash_before)
    seller_writes = list(seller_write_event_ids or ())
    if (getattr(seller, 'is_government', False) and seller_writes
            and seller_receipt > 0.0):
        buyer_debit = float(buyer_cash_before) - float(buyer_cash_after)
        matches = math.isclose(
            buyer_debit, seller_receipt, rel_tol=1e-10, abs_tol=1e-8)
        operation_id = (
            f'government-inventory-sale:{turn}:{seller.id}:{buyer.id}:{good.name}')
        contract = transfer_contract(
            operation_id, 'government_direct_inventory_sale', side='payee',
            amount=seller_receipt, amount_currency=currency,
            payer_account=account(buyer, buyer_cash_before, buyer_cash_after),
            payee_account=account(seller, seller_cash_before, seller_cash_after),
            local_cash_leg_amount=seller_receipt,
            local_cash_leg_currency=currency,
            counterparty_leg_status=(
                'buyer_cash_balance_captured' if matches
                else 'buyer_cash_balance_differs_from_public_receipt'),
            decision_event_id=decision_event_id)
        emitted.append(emit_treasury_leg(
            region, kind='government_direct_inventory_sale_receipt',
            nation_name=owner_nation.name, currency=currency,
            signed_amount=seller_receipt, contract=contract, phase='local',
            subject_type='nation',
            cause_event_ids=[*seller_writes, decision_event_id],
            inputs={'seller_id': seller.id, 'buyer_id': buyer.id,
                    'good': good.name, 'quantity': int(quantity),
                    'amount': float(amount), 'receipt': seller_receipt,
                    'turn': int(turn)}))

    buyer_debit = float(buyer_cash_before) - float(buyer_cash_after)
    buyer_writes = list(buyer_write_event_ids or ())
    if (getattr(buyer, 'is_government', False) and buyer_writes
            and buyer_debit > 0.0):
        matches = math.isclose(
            buyer_debit, seller_receipt, rel_tol=1e-10, abs_tol=1e-8)
        operation_id = (
            f'government-inventory-purchase:{turn}:{buyer.id}:{seller.id}:{good.name}')
        contract = transfer_contract(
            operation_id, 'government_direct_inventory_purchase', side='payer',
            amount=buyer_debit, amount_currency=currency,
            payer_account=account(buyer, buyer_cash_before, buyer_cash_after),
            payee_account=account(seller, seller_cash_before, seller_cash_after),
            local_cash_leg_amount=buyer_debit,
            local_cash_leg_currency=currency,
            counterparty_leg_status=(
                'seller_cash_balance_captured' if matches
                else 'seller_cash_balance_differs_from_public_debit'),
            decision_event_id=decision_event_id)
        emitted.append(emit_treasury_leg(
            region, kind='government_direct_inventory_purchase',
            nation_name=owner_nation.name, currency=currency,
            signed_amount=-buyer_debit, contract=contract, phase='local',
            subject_type='nation',
            cause_event_ids=[*buyer_writes, decision_event_id],
            inputs={'buyer_id': buyer.id, 'seller_id': seller.id,
                    'good': good.name, 'quantity': int(quantity),
                    'amount': float(amount), 'debit': buyer_debit,
                    'turn': int(turn)}))
    return emitted
