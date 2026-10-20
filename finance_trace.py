"""Shared versioned evidence shape for account-to-account cash movements."""


def account_ref(account_type, account_id, currency, **details):
    """Return an account identity with optional balance evidence."""
    return {'type': account_type, 'id': account_id, 'currency': currency,
            **details}


def transfer_contract(operation_id, operation_type, *, side, amount,
                       amount_currency, payer_account, payee_account,
                       local_cash_leg_amount, local_cash_leg_currency,
                       currency_conversion_applied=False,
                       counterparty_leg_status='not_recorded', **details):
    """Build a consistent transfer contract without implying missing legs."""
    contract = {
        'contract_version': 'treasury_transfer.v1',
        'operation_id': operation_id,
        'operation_type': operation_type,
        'side': side,
        'amount': float(amount),
        'amount_currency': amount_currency,
        'payer_account': payer_account,
        'payee_account': payee_account,
        'local_cash_leg_amount': float(local_cash_leg_amount),
        'local_cash_leg_currency': local_cash_leg_currency,
        'currency_conversion_applied': bool(currency_conversion_applied),
        'unconverted_currency_mismatch': bool(
            amount_currency and local_cash_leg_currency
            and amount_currency != local_cash_leg_currency
            and not currency_conversion_applied),
        'counterparty_leg_status': counterparty_leg_status,
    }
    contract.update(details)
    return contract


def cash_transfer_contract(operation_id, operation_type, *, amount, currency,
                           payer_account, payee_account,
                           counterparty_leg_status='both_cash_balances_captured',
                           **details):
    """Build a versioned contract for cash movements between non-treasury actors."""
    payer_currency = (payer_account or {}).get('currency')
    payee_currency = (payee_account or {}).get('currency')
    currency_mismatch = bool(payer_currency and payee_currency
                             and payer_currency != payee_currency)
    contract = {
        'contract_version': 'cash_transfer.v1',
        'operation_id': operation_id,
        'operation_type': operation_type,
        'side': 'payer',
        'amount': float(amount),
        'amount_currency': currency,
        'payer_account': payer_account,
        'payee_account': payee_account,
        'local_cash_leg_amount': float(amount),
        'local_cash_leg_currency': currency,
        'currency_conversion_applied': False,
        'counterparty_currency_mismatch': currency_mismatch,
        'unconverted_currency_mismatch': bool(
            currency and payee_currency and currency != payee_currency),
        'counterparty_leg_status': counterparty_leg_status,
    }
    contract.update(details)
    return contract


def emit_cash_transfer(region, *, kind, contract, inputs=None,
                       phase='economy', subject=None, cause_event_ids=None):
    """Emit one actor-to-actor cash transfer with both account identities."""
    from run_trace import emit

    return emit(
        region, kind=kind, record_class='transfer', phase=phase,
        subject=subject or {'type': 'tile', 'id': region.name},
        metric_id='finance.cash_transfer', unit=contract['amount_currency'],
        after=float(contract['amount']),
        inputs={**(inputs or {}), 'operation_id': contract['operation_id'],
                'transfer_contract': contract},
        cause_event_ids=cause_event_ids)


def emit_treasury_leg(region, *, kind, nation_name, currency, signed_amount,
                      contract, phase='finance', inputs=None,
                      subject_type='nation', cause_event_ids=None):
    """Emit one signed nation cash leg using the shared contract format."""
    from run_trace import emit

    return emit(
        region, kind=kind, record_class='transfer', phase=phase,
        subject={'type': subject_type, 'id': nation_name},
        metric_id='finance.treasury_flow', unit=currency,
        after=float(signed_amount),
        inputs={'operation_id': contract['operation_id'],
                'transfer_contract': contract, **(inputs or {})},
        cause_event_ids=cause_event_ids)


def emit_tax_distribution(region, *, turn, closing, receipts=(), opening=None,
                          reason, phase='finance', cause_event_ids=None):
    """Explain each component of the current-turn tax distribution history."""
    from run_trace import emit

    tiers = ('total', 'municipal', 'provincial', 'national')
    opening = {tier: float((opening or {}).get(tier, 0.0)) for tier in tiers}
    receipts = list(receipts)
    recorder = getattr(region, '_run_trace', None)
    latest = (getattr(recorder, 'latest_metric_calculation_event_id', None)
              or getattr(recorder, 'latest_metric_event_id', None))
    event_ids = []
    for tier in tiers:
        subject = {'type': 'tile', 'id': region.name, 'tax_tier': tier}
        causes = list(cause_event_ids or ())
        previous_id = latest('finance.tax_distribution', subject) if callable(latest) else None
        if previous_id is not None:
            causes.append(previous_id)
        event_id = emit(
            region, kind='tax_revenue_distribution_calculation',
            record_class='calculation', phase=phase, subject=subject,
            metric_id='finance.tax_distribution',
            unit=getattr(region, 'home_currency', None) or 'local_currency',
            before=opening[tier], after=float(closing.get(tier, 0.0)),
            formula_id='fiscal.tax_distribution.v1',
            inputs={'turn': int(turn), 'reason': reason, 'tax_tier': tier,
                    'opening_components': opening, 'receipts': receipts,
                    'aggregation_rule': 'opening plus receipt allocations; total uses receipt amount'},
            cause_event_ids=list(dict.fromkeys(causes)) or None)
        if event_id is not None:
            event_ids.append(event_id)
    return event_ids
