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
        'unconverted_currency_mismatch': False,
        'counterparty_leg_status': counterparty_leg_status,
    }
    contract.update(details)
    return contract


def emit_cash_transfer(region, *, kind, contract, inputs=None,
                       phase='economy', subject=None):
    """Emit one actor-to-actor cash transfer with both account identities."""
    from run_trace import emit

    return emit(
        region, kind=kind, record_class='transfer', phase=phase,
        subject=subject or {'type': 'tile', 'id': region.name},
        metric_id='finance.cash_transfer', unit=contract['amount_currency'],
        after=float(contract['amount']),
        inputs={**(inputs or {}), 'operation_id': contract['operation_id'],
                'transfer_contract': contract})


def emit_treasury_leg(region, *, kind, nation_name, currency, signed_amount,
                      contract, phase='finance', inputs=None,
                      subject_type='nation'):
    """Emit one signed nation cash leg using the shared contract format."""
    from run_trace import emit

    return emit(
        region, kind=kind, record_class='transfer', phase=phase,
        subject={'type': subject_type, 'id': nation_name},
        metric_id='finance.treasury_flow', unit=currency,
        after=float(signed_amount),
        inputs={'operation_id': contract['operation_id'],
                'transfer_contract': contract, **(inputs or {})})
