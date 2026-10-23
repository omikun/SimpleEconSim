"""
Demographics estate: death determination, corporate succession, debt resolution,
bad debt forgiveness & write-downs, wealth inheritance, and escheat.
"""
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
from treasury_trace import begin_public_change, finish_public_change

import sys
import traceback
from goods import Goods
import econsim_trade_money as trade
from logger import logdebug, loginfo, logwarning
from random_cache import rand
import forex as fx


def is_last_of_profession(agent, agents, ctx):
    """Return True if agent is the sole producer of their profession."""
    if agent.is_trader or agent.is_corporation or agent.is_government:
        return False
    output = agent.output
    if output == Goods.gov:
        return False
    count = sum(1 for a in agents if a.alive and a.output == output and not a.is_trader)
    return count <= 1


def living_descendants_recursive(agent):
    """All living descendants (children + grandchildren per branch, BFS)."""
    seen = set()
    out = []
    queue = list(getattr(agent, 'descendants', []))
    while queue:
        d = queue.pop(0)
        if d.id in seen:
            continue
        seen.add(d.id)
        if getattr(d, 'alive', False):
            out.append(d)
        queue.extend(getattr(d, 'descendants', []))
    return out


def cleanup_dead_agent_links(agent, region=None, t=0):
    """Clean up corporation/employee links for a dying agent."""
    if getattr(agent, 'employer', None) is not None:
        employer = agent.employer
        if hasattr(employer, 'employees') and agent in employer.employees:
            employer.employees.remove(agent)
        agent.employer = None
    if getattr(agent, 'is_corporation', False) and hasattr(agent, 'employees'):
        if region is not None:
            from region_finance import liquidate_wage_arrears
            liquidate_wage_arrears(region, t, agent, reason='corporation_death')
        for emp in agent.employees:
            emp.employer = None
        agent.employees = []
        agent.is_corporation = False
        if agent.owner is not None:
            agent.owner.company_owned = None
            agent.owner = None


def _estate_trace(region, **event):
    """Emit optional probate evidence without changing settlement state."""
    if region is None:
        return None
    from run_trace import emit
    return emit(region, **event)


def _estate_cash_allocation_trace(region, t, decedent, recipient, amount,
                                  currency, operation_id, settlement,
                                  source_cash_before, recipient_before,
                                  recipient_after, *, recipient_type='agent',
                                  cause_event_ids=None, economic_event_id=None,
                                  extra_inputs=None):
    if region is None or amount <= 0:
        return None
    from finance_trace import account_ref, transfer_contract

    source_ref = account_ref(
        'estate_cash', str(decedent.id), currency,
        balance_before=float(source_cash_before),
        balance_after=float(source_cash_before),
        source_closeout='deferred_until_zero_out_dead_agent')
    recipient_ref = account_ref(
        recipient_type, str(getattr(recipient, 'id', recipient)), currency,
        balance_before=float(recipient_before),
        balance_after=float(recipient_after))
    contract = transfer_contract(
        operation_id, 'death_estate_cash_allocation', side='payee',
        amount=amount, amount_currency=currency,
        payer_account=source_ref, payee_account=recipient_ref,
        local_cash_leg_amount=amount, local_cash_leg_currency=currency,
        counterparty_leg_status='source_cash_closeout_deferred',
        settlement=settlement)
    inputs = {
        'turn': t, 'decedent_id': decedent.id,
        'recipient_id': getattr(recipient, 'id', recipient),
        'settlement': settlement, 'economic_event_id': economic_event_id,
        'source_cash_balance_before': float(source_cash_before),
        'source_cash_balance_not_yet_cleared': True,
        'transfer_contract': contract,
    }
    inputs.update(extra_inputs or {})
    return _estate_trace(
        region, kind='estate_cash_allocated', record_class='outcome',
        phase='demographics',
        subject={'type': 'estate/beneficiary', 'id': operation_id,
                 'tile': region.name,
                 'decedent_id': decedent.id,
                 'beneficiary_id': getattr(recipient, 'id', recipient)},
        metric_id='finance.inheritance', unit=currency,
        before=float(recipient_before), after=float(recipient_after),
        formula_id='estate.cash_share.v1', inputs=inputs,
        cause_event_ids=cause_event_ids or None)


def _estate_deposit_allocation_trace(region, t, decedent, recipient, amount,
                                     currency, operation_id, bank,
                                     source_deposit_before, recipient_before,
                                     recipient_after, *, recipient_type='agent',
                                     source_deposit_after=None,
                                     extra_inputs=None):
    if region is None or amount <= 0:
        return None
    from finance_trace import account_ref, transfer_contract

    source_after = (float(source_deposit_before)
                    if source_deposit_after is None
                    else float(source_deposit_after))
    source_closeout = source_deposit_after is None
    contract = transfer_contract(
        operation_id, 'death_estate_deposit_allocation', side='payee',
        amount=amount, amount_currency=currency,
        payer_account=account_ref(
            'bank_deposit', str(decedent.id), currency,
            balance_before=float(source_deposit_before),
            balance_after=source_after,
            source_closeout=('captured_by_estate_deposit_closeout'
                             if source_closeout else None)),
        payee_account=account_ref(
            recipient_type, str(getattr(recipient, 'id', recipient)), currency,
            balance_before=float(recipient_before),
            balance_after=float(recipient_after)),
        local_cash_leg_amount=0.0, local_cash_leg_currency=currency,
        counterparty_leg_status=(
            'beneficiary_credit_captured_source_closeout_follows'
            if source_closeout else 'source_and_beneficiary_balances_captured'),
        cash_movement=False)
    inputs = {
        'turn': t, 'decedent_id': decedent.id,
        'recipient_id': getattr(recipient, 'id', recipient),
        'source_deposit_balance_before': float(source_deposit_before),
        'source_deposit_balance_after': source_after,
        'bank_total_deposits_after': float(
            getattr(bank, 'total_deposits', 0.0)),
        'bank_deposit_account_sum_after': sum(
            float(value) for value in bank.deposits.values()),
        'transfer_contract': contract,
    }
    inputs.update(extra_inputs or {})
    return _estate_trace(
        region, kind='estate_deposit_allocated', record_class='transfer',
        phase='demographics',
        subject={'type': 'estate/beneficiary', 'id': operation_id,
                 'tile': region.name,
                 'decedent_id': decedent.id,
                 'beneficiary_id': getattr(recipient, 'id', recipient)},
        metric_id='finance.estate_deposit', unit=currency,
        before=float(recipient_before), after=float(recipient_after),
        formula_id='estate.deposit_share.v1', inputs=inputs)


def _estate_inventory_trace(region, t, decedent, good, amount, allocations,
                            operation_id, destination_rule):
    if region is None or amount <= 0:
        return None
    return _estate_trace(
        region, kind='estate_inventory_allocated', record_class='outcome',
        phase='demographics',
        subject={'type': 'agent/good', 'id': str(decedent.id),
                 'good': good.name, 'tile': region.name},
        metric_id='goods.inheritance_transfer', unit='units',
        before=amount, after=amount,
        formula_id='estate.inventory_share.v1',
        inputs={'turn': t, 'operation_id': operation_id,
                'decedent_id': decedent.id, 'good': good.name,
                'source_inventory_before': amount,
                'source_inventory_after_allocation': amount,
                'source_inventory_debited': False,
                'destination_rule': destination_rule,
                'allocations': allocations,
                'allocated_units': sum(row['units'] for row in allocations),
                'conservation_status':
                    'decedent_inventory_remains_after_allocation'})


def handle_company_inheritance(t, agent, region=None):
    """Pass company to heir when founder dies."""
    if getattr(agent, 'company_owned', None) is None:
        return
    company = agent.company_owned
    company_id = getattr(company, 'id',
                         getattr(company, 'company_name', 'unknown-company'))
    previous_owner = getattr(company, 'owner', None)
    living_descendants = living_descendants_recursive(agent)
    if len(living_descendants) > 0:
        heir = max(living_descendants, key=lambda d: d.cash)
        company.owner = heir
        heir.company_owned = company
        _estate_trace(
            region, kind='estate_company_inherited', record_class='outcome',
            phase='demographics',
            subject={'type': 'company', 'id': str(company_id),
                     'tile': getattr(region, 'name', None)},
            metric_id='society.company_succession',
            before=getattr(previous_owner, 'id', None),
            after=heir.id, unit='owner_id',
            formula_id='estate.company_owner_descendant_with_highest_cash.v1',
            inputs={'turn': t, 'decedent_id': agent.id,
                    'previous_owner_id': getattr(previous_owner, 'id', None),
                    'new_owner_id': heir.id,
                    'living_descendant_ids': [d.id for d in living_descendants],
                    'selected_by': 'highest_current_cash'})
        logdebug(t, agent.name(), 'company', company.name(),
                 'inherited by', heir.name())
    elif company.alive and company.is_corporation and len(company.employees) > 0:
        oldest_emp = min(company.employees, key=lambda e: e.hired_at)
        company.owner = oldest_emp
        oldest_emp.company_owned = company
        _estate_trace(
            region, kind='estate_company_inherited', record_class='outcome',
            phase='demographics',
            subject={'type': 'company', 'id': str(company_id),
                     'tile': getattr(region, 'name', None)},
            metric_id='society.company_succession',
            before=getattr(previous_owner, 'id', None),
            after=oldest_emp.id, unit='owner_id',
            formula_id='estate.company_owner_oldest_employee.v1',
            inputs={'turn': t, 'decedent_id': agent.id,
                    'previous_owner_id': getattr(previous_owner, 'id', None),
                    'new_owner_id': oldest_emp.id,
                    'employee_ids': [e.id for e in company.employees],
                    'selected_by': 'earliest_hired_employee'})
        logdebug(t, agent.name(), 'company', company.name(),
                 'inherited by oldest employee', oldest_emp.name())
    elif company.alive and company.is_corporation:
        logdebug(t, agent.name(), 'company', company.name(),
                 'dissolved (no heirs, no employees)')
        if region is not None:
            from region_finance import liquidate_wage_arrears
            liquidate_wage_arrears(region, t, company,
                                   reason='company_owner_estate_dissolution')
        for emp in company.employees:
            emp.employer = None
        company.employees = []
        company.is_corporation = False
        company.owner = None
        _estate_trace(
            region, kind='estate_company_dissolved', record_class='outcome',
            phase='demographics',
            subject={'type': 'company', 'id': str(company_id),
                     'tile': getattr(region, 'name', None)},
            metric_id='society.company_succession',
            before=getattr(previous_owner, 'id', None), after=None,
            unit='owner_id', formula_id='estate.company_dissolution_no_successor.v1',
            inputs={'turn': t, 'decedent_id': agent.id,
                    'previous_owner_id': getattr(previous_owner, 'id', None),
                    'reason': 'no_living_descendants_or_employees'})
    agent.company_owned = None


def handle_wage_claim_inheritance(region, t, agent, living_descendants,
                                  government=None, charity=None):
    """Transfer unpaid wage receivables through the worker's estate."""
    if region is None:
        return []
    from economy.actor_accounts import (
        _wage_liability_totals, record as record_economic_event,
        transfer_wage_arrear_claim, writeoff_wage_arrear,
    )
    outcomes = []
    gov_agent = getattr(government, 'agent', None)
    charity_agent = getattr(charity, 'agent', None)
    province = getattr(region, 'province', None)
    claim_regions = getattr(province, 'tiles', ()) or (region,)
    firms = {int(firm.id): firm for claim_region in claim_regions
             for firm in getattr(claim_region, 'agents', ())
             if getattr(firm, 'is_corporation', False)}
    for firm_id, firm in (getattr(agent, 'wage_claim_creditors', {}) or {}).items():
        firms[int(firm_id)] = firm
    for firm in firms.values():
        _, claims = _wage_liability_totals(firm)
        claim = float(claims.get(int(agent.id), 0.0))
        if claim <= 1e-9:
            continue
        beneficiaries = []
        living_heirs = [heir for heir in living_descendants
                        if getattr(heir, 'alive', False)]
        if living_heirs:
            share = claim / len(living_heirs)
            beneficiaries = [(heir, share, 'heir') for heir in living_heirs]
        else:
            probate = (min(1.0, max(0.0, float(
                getattr(government, 'probate_fee_rate', 0.0))))
                if gov_agent is not None else 0.0)
            if gov_agent is not None and charity_agent is not None:
                if claim * probate > 1e-9:
                    beneficiaries.append((gov_agent, claim * probate,
                                          'government_probate'))
                if claim * (1.0 - probate) > 1e-9:
                    beneficiaries.append((charity_agent, claim * (1.0 - probate),
                                          'charity_escheat'))
            elif gov_agent is not None:
                beneficiaries.append((gov_agent, claim, 'government_escheat'))
            elif charity_agent is not None:
                beneficiaries.append((charity_agent, claim, 'charity_escheat'))

        if not beneficiaries:
            total_before, total_after, claim_before, claim_after, amount = (
                writeoff_wage_arrear(firm, agent.id, claim))
            if amount <= 1e-9:
                continue
            event = record_economic_event(
                region, 'wage_arrears_written_off', turn=t,
                payer_id=firm.id, recipient_id=agent.id, amount=amount,
                asset_id=f'wage-arrears:{firm.id}:{agent.id}',
                source_id=f'wage-arrears:{firm.id}:{agent.id}',
                currency=getattr(region, 'home_currency', None),
                detail={'employer_id': firm.id, 'worker_id': agent.id,
                        'employer_payable_before': float(total_before),
                        'employer_payable_after': float(total_after),
                        'claim_before': float(claim_before),
                        'claim_after': float(claim_after),
                        'reason': 'no_estate_beneficiary',
                        'settlement': 'unclaimed_wage_claim_writeoff'})
            from run_trace import emit
            emit(region, kind='wage_arrears_claim_escheated',
                 record_class='outcome', phase='demographics',
                 subject={'type': 'employment_wage_claim',
                          'id': f'{firm.id}:{agent.id}', 'tile': region.name,
                          'employer_id': firm.id, 'worker_id': agent.id},
                 metric_id='finance.wage_arrears',
                 unit=getattr(region, 'home_currency', None) or 'local_currency',
                 before=float(claim_before), after=float(claim_after),
                 formula_id='estate.wage_claim.no_beneficiary_writeoff.v1',
                 inputs={'event_id': event['id'], 'amount': float(amount),
                         'reason': 'no_government_or_charity_beneficiary'})
            outcomes.append({'firm_id': firm.id, 'kind': 'written_off',
                             'amount': amount})
            continue

        transfer_rows = []
        for beneficiary, share, settlement in beneficiaries:
            total_before, total_after, source_before, source_after, amount = (
                transfer_wage_arrear_claim(
                    firm, agent.id, beneficiary.id, share, t,
                    target_worker=beneficiary, source_worker=agent))
            if amount <= 1e-9:
                continue
            event = record_economic_event(
                region, 'wage_arrears_claim_inherited', turn=t,
                payer_id=agent.id, recipient_id=beneficiary.id,
                amount=amount, asset_id=f'wage-arrears:{firm.id}:{agent.id}',
                source_id=f'wage-arrears:{firm.id}:{agent.id}',
                currency=getattr(region, 'home_currency', None),
                detail={'employer_id': firm.id, 'deceased_worker_id': agent.id,
                        'heir_id': beneficiary.id, 'settlement': settlement,
                        'employer_payable_before': float(total_before),
                        'employer_payable_after': float(total_after),
                        'source_claim_before': float(source_before),
                        'source_claim_after': float(source_after),
                        'beneficiary_share': float(amount)})
            transfer_rows.append({'beneficiary_id': beneficiary.id,
                                  'amount': float(amount),
                                  'settlement': settlement,
                                  'event_id': event['id']})
        if transfer_rows:
            from run_trace import emit
            emit(region, kind='wage_arrears_claim_inherited',
                 record_class='transfer', phase='demographics',
                 subject={'type': 'employment_wage_claim',
                          'id': f'{firm.id}:{agent.id}', 'tile': region.name,
                          'employer_id': firm.id, 'worker_id': agent.id},
                 metric_id='finance.wage_arrears',
                 unit=getattr(region, 'home_currency', None) or 'local_currency',
                 before=claim, after=0.0,
                 formula_id='estate.wage_claim.transfer_to_beneficiaries.v1',
                 inputs={'employer_id': firm.id, 'deceased_worker_id': agent.id,
                         'beneficiaries': transfer_rows,
                         'claim_transferred': sum(row['amount']
                                                  for row in transfer_rows)})
            outcomes.append({'firm_id': firm.id, 'kind': 'inherited',
                             'amount': sum(row['amount'] for row in transfer_rows),
                             'beneficiaries': transfer_rows})
    return outcomes


def deposit_pool(bank):
    """True deposit pool = sum of deposits dict."""
    return sum(bank.deposits.values())


def _record_debt_event(region, kind, t, *, payer=None, recipient=None,
                       amount, currency=None, bank=None, detail=None):
    if region is None or amount <= 0:
        return None
    from economy.actor_accounts import record as record_economic_event
    bank_agent = getattr(getattr(bank, 'gov', None), 'agent', None)
    return record_economic_event(
        region, kind, turn=t,
        payer_id=getattr(payer, 'id', None),
        recipient_id=getattr(recipient, 'id', None),
        amount=float(amount), currency=currency or getattr(region, 'home_currency', None),
        asset_id=f'bank:{bank_agent.id}' if bank_agent is not None else None,
        detail=detail or {})


def forgive_bad_debt(bank, amount, t, *, region=None, debtor=None):
    """Conservation-safe heirless bad-debt forgiveness in seniority order."""
    if amount <= 0:
        return True

    bank_agent = getattr(getattr(bank, 'gov', None), 'agent', None)
    bank_id = getattr(bank_agent, 'id', getattr(region, 'name', 'bank'))
    debtor_id = getattr(debtor, 'id', None)
    tile_id = getattr(region, 'name', 'untraced')
    operation_id = f'estate-bank-writeoff:{tile_id}:{int(t)}:{bank_id}:{debtor_id}'
    owner_nation = getattr(region, 'owner_nation', None) if region is not None else None
    currency = (getattr(bank_agent, 'home_currency', None)
                or getattr(owner_nation, 'currency', None)
                or getattr(region, 'home_currency', None) or 'local_currency')
    component_event_ids = []

    # 1. Shareholders absorb first.
    capital_before = float(bank.capital)
    capital_absorb = min(amount, max(0.0, bank.capital))
    if capital_absorb > 0:
        from bank_trace import begin_change, finish_change
        bank_trace_change = begin_change(bank, region)
        bank.capital -= capital_absorb
        finish_change(bank, bank_trace_change, 'estate_shareholder_loss',
                      inputs={'operation_id': operation_id, 'debtor_id': debtor_id, 'amount': capital_absorb})
        from run_trace import emit
        event_id = emit(
            region, kind='estate_bank_shareholder_loss_absorption',
            record_class='outcome', phase='demographics',
            subject={'type': 'tile', 'id': tile_id,
                     'bank_id': bank_id, 'agent_id': debtor_id},
            metric_id='finance.bank_capital', unit=currency,
            before=capital_before, after=float(bank.capital),
            formula_id='estate.bad_debt_shareholder_first_loss.v1',
            inputs={'operation_id': operation_id,
                    'principal_loss_absorbed': float(capital_absorb),
                    'debtor_id': debtor_id})
        if event_id is not None:
            component_event_ids.append(event_id)
    remaining = amount - capital_absorb
    deposit_absorb = 0.0
    treasury_absorb = 0.0
    deposits_before = float(bank.total_deposits)

    # 2. Depositors bailed in pro-rata.
    if remaining > 0:
        pool = deposit_pool(bank)
        dep_absorb = min(remaining, pool)
        if dep_absorb > 0:
            deposit_absorb = dep_absorb
            for owner, bal in list(bank.deposits.items()):
                if bal <= 0:
                    continue
                share = bal * (dep_absorb / pool)
                deposit_after = max(0.0, bal - share)
                public_change = begin_public_change(region, owner, bank=bank, cash=False, deposit=True)
                bank.deposits[owner] = deposit_after
                finish_public_change(public_change, 'estate_deposit_loss')
                bank._record_account_event(owner, 'bank_deposit_haircut',
                                           float(share), payer=True,
                                           detail={'bad_debt_bail_in': True,
                                                   'operation_id': operation_id,
                                                   'debtor_id': debtor_id})
                from finance_trace import account_ref
                from run_trace import emit
                deposit_account = account_ref(
                    'depositor_bank_deposit', getattr(owner, 'id', None), currency,
                    balance_before=float(bal), balance_after=float(deposit_after),
                    balance_scope='depositor_bank_deposit')
                event_id = emit(
                    region, kind='estate_bank_depositor_bail_in',
                    record_class='transfer', phase='demographics',
                    subject={'type': 'tile', 'id': tile_id,
                             'bank_id': bank_id,
                             'depositor_id': getattr(owner, 'id', None),
                             'agent_id': debtor_id},
                    metric_id='finance.bank_debt_bailin', unit=currency,
                    after=float(share),
                    formula_id='estate.bad_debt_prorata_depositor_loss.v1',
                    inputs={'operation_id': operation_id,
                            'transfer_contract': {
                                'contract_version': 'bank_debt_bailin.v1',
                                'operation_id': operation_id,
                                'operation_type': 'deposit_loss_applied_to_estate_bad_debt',
                                'amount': float(share),
                                'amount_currency': currency,
                                'side': 'depositor_asset_loss',
                                'payer_account': deposit_account,
                                'cash_movement': False,
                                'currency_conversion_applied': False,
                                'counterparty_leg_status':
                                    'deposit_reduction_allocated_to_bank_bad_debt',
                                'covered_bad_debt_amount': float(share),
                                'mutation_reference': {
                                    'bank_tile': tile_id,
                                    'bank_id': bank_id,
                                    'depositor_id': getattr(owner, 'id', None),
                                    'debtor_id': debtor_id}},
                            'deposit_before': float(bal),
                            'deposit_after': float(deposit_after),
                            'bad_debt_covered': float(share),
                            'bad_debt_operation_id': operation_id})
                if event_id is not None:
                    component_event_ids.append(event_id)
            from bank_trace import begin_change, finish_change
            bank_trace_change = begin_change(bank, region)
            bank.total_deposits -= dep_absorb
            finish_change(bank, bank_trace_change, 'estate_depositor_loss',
                          inputs={'operation_id': operation_id, 'debtor_id': debtor_id, 'amount': dep_absorb})
            logwarning(t, f"DEPOSITOR BAIL-IN: ${dep_absorb:.2f} of "
                          f"${amount:.2f} bad debt absorbed by depositors "
                          f"(shareholders took ${capital_absorb:.2f})")
        remaining -= dep_absorb

    # 3. Tile treasury recapitalization.
    if remaining > 0:
        treasury_absorb, recap_event_ids = recapitalize(
            bank, remaining, t, region=region, debtor=debtor,
            operation_id=f'{operation_id}:treasury', return_event_ids=True)
        component_event_ids.extend(event_id for event_id in recap_event_ids
                                   if event_id is not None)
        remaining -= treasury_absorb

    # 4. Genuine bank failure -> negative equity.
    if remaining > 1e-9:
        residual_capital_before = float(bank.capital)
        from bank_trace import begin_change, finish_change
        bank_trace_change = begin_change(bank, region)
        bank.capital -= remaining
        finish_change(bank, bank_trace_change, 'estate_unabsorbed_loss',
                      inputs={'operation_id': operation_id, 'debtor_id': debtor_id, 'amount': remaining})
        from run_trace import emit
        event_id = emit(
            region, kind='estate_bank_unabsorbed_loss',
            record_class='outcome', phase='demographics',
            subject={'type': 'tile', 'id': tile_id,
                     'bank_id': bank_id, 'agent_id': debtor_id},
            metric_id='finance.bank_capital', unit=currency,
            before=residual_capital_before, after=float(bank.capital),
            formula_id='estate.bad_debt_residual_negative_equity.v1',
            inputs={'operation_id': operation_id,
                    'unabsorbed_bank_loss': float(remaining),
                    'debtor_id': debtor_id})
        if event_id is not None:
            component_event_ids.append(event_id)
        logwarning(t, f"BANK FAILURE: ${remaining:.2f} heirless bad debt "
                      f"unabsorbed after seniority order — equity goes "
                      f"negative (capital ${bank.capital:.2f}).")
    _record_debt_event(
        region, 'bank_debt_writeoff', t, payer=debtor, amount=amount,
        currency=currency, bank=bank, detail={
            'operation_id': operation_id,
            'principal_written_off': float(amount),
            'shareholder_capital_absorbed': float(capital_absorb),
            'depositor_bail_in': float(deposit_absorb),
            'treasury_recapitalization': float(treasury_absorb),
            'unabsorbed_bank_loss': float(max(0.0, remaining)),
            'bank_capital_after': float(bank.capital),
            'bank_deposits_after': float(bank.total_deposits),
            'debtor_id': debtor_id})
    if region is not None:
        from run_trace import emit
        writeoff_event_id = emit(
             region, kind='bank_estate_debt_writeoff', record_class='outcome',
             phase='demographics',
             subject={'type': 'tile', 'id': region.name,
                      'bank_id': bank_id, 'agent_id': debtor_id},
             metric_id='finance.bank_debt_writeoff',
             unit=currency, before=float(amount), after=0.0,
             formula_id='estate.bank_bad_debt_seniority_waterfall.v1',
             inputs={'operation_id': operation_id,
                     'shareholder_capital_absorbed': float(capital_absorb),
                     'depositor_bail_in': float(deposit_absorb),
                     'treasury_recapitalization': float(treasury_absorb),
                     'unabsorbed_bank_loss': float(max(0.0, remaining)),
                     'bank_capital_before': capital_before,
                     'bank_capital_after': float(bank.capital),
                     'bank_deposits_before': deposits_before,
                     'bank_deposits_after': float(bank.total_deposits),
                     'debtor_id': debtor_id},
             cause_event_ids=component_event_ids or None)
    return True


def recapitalize(bank, shortfall, t, *, region=None, debtor=None,
                 operation_id=None, return_event_ids=False):
    """Tile treasury lender-of-last-resort recapitalization (conserved)."""
    gov = getattr(bank, 'gov', None)
    if gov is None:
        return (0.0, []) if return_event_ids else 0.0
    take = min(max(0.0, shortfall), max(0.0, gov.agent.cash))
    if take <= 0:
        return (0.0, []) if return_event_ids else 0.0
    treasury_before = float(gov.agent.cash)
    capital_before = float(bank.capital)
    public_change = begin_public_change(region, gov.agent)
    gov.agent.cash -= take
    finish_public_change(public_change, 'estate_treasury_bank_recapitalization')
    from bank_trace import begin_change, finish_change
    bank_trace_change = begin_change(bank, region)
    bank.capital += take
    finish_change(bank, bank_trace_change, 'estate_treasury_recapitalization',
                  inputs={'debtor_id': getattr(debtor, 'id', None), 'treasury_debit': take})
    if operation_id is None:
        operation_id = (f'estate-bank-recapitalization:{getattr(region, "name", "untraced")}:'
                        f'{int(t)}:{getattr(gov.agent, "id", None)}:'
                        f'{getattr(debtor, "id", None)}')
    _record_debt_event(
        region, 'bank_recapitalization', t, payer=gov.agent, amount=take,
        currency=getattr(gov.agent, 'home_currency', None), bank=bank,
        detail={'operation_id': operation_id,
                'capital_injected': float(take),
                'bank_capital_after': float(bank.capital),
                'cause': 'heirless_estate_bad_debt',
                'debtor_id': getattr(debtor, 'id', None)})
    event_ids = []
    if region is not None:
        from finance_trace import account_ref, emit_treasury_leg, transfer_contract
        from run_trace import emit
        owner_nation = getattr(region, 'owner_nation', None)
        currency = (getattr(owner_nation, 'currency', None)
                    or getattr(gov.agent, 'home_currency', None)
                    or getattr(region, 'home_currency', None) or 'local_currency')
        bank_event_id = emit(region, kind='estate_bank_recapitalization',
             record_class='transfer', phase='demographics',
             subject={'type': 'tile', 'id': region.name,
                      'agent_id': gov.agent.id},
             metric_id='finance.bank_recapitalization', unit=currency,
             before=capital_before, after=float(bank.capital),
             inputs={'operation_id': operation_id,
                     'capital_injected': float(take),
                     'debtor_id': getattr(debtor, 'id', None),
                     'bank_capital_before': capital_before,
                     'bank_capital_after': float(bank.capital)})
        if bank_event_id is not None:
            event_ids.append(bank_event_id)
        payer = account_ref(
            'government_treasury', getattr(gov, 'name', gov.agent.id), currency,
            subaccount='government_agent.cash', balance_before=treasury_before,
            balance_after=float(gov.agent.cash), balance_scope='government_agent.cash')
        payee = account_ref(
            'bank_capital', region.name, currency,
            balance_before=capital_before, balance_after=float(bank.capital),
            balance_scope='capital')
        contract = transfer_contract(
            operation_id, 'estate_bank_recapitalization', side='payer',
            amount=take, amount_currency=currency,
            payer_account=payer, payee_account=payee,
            local_cash_leg_amount=take, local_cash_leg_currency=currency,
            counterparty_leg_status='bank_capital_balance_captured',
            mutation_reference={'turn': int(t), 'bank_tile': region.name,
                                'debtor_id': getattr(debtor, 'id', None),
                                'cause': 'heirless_estate_bad_debt'})
        flow_event_id = emit_treasury_leg(
            region, kind='estate_bank_recapitalization_funding',
            nation_name=(getattr(owner_nation, 'name', None)
                         or getattr(gov, 'name', region.name)),
            currency=currency, signed_amount=-float(take), contract=contract,
            phase='demographics',
            cause_event_ids=([bank_event_id] if bank_event_id is not None else None),
            subject_type='nation' if owner_nation is not None else 'tile',
            inputs={'bank_tile': region.name,
                    'debtor_id': getattr(debtor, 'id', None),
                    'treasury_before': treasury_before,
                    'treasury_after': float(gov.agent.cash),
                    'bank_capital_before': capital_before,
                    'bank_capital_after': float(bank.capital)})
        if flow_event_id is not None:
            event_ids.append(flow_event_id)
    logwarning(t, f"RECAPITALIZATION: ${take:.2f} treasury capital injected "
                  f"into bank (capital ${bank.capital:.2f})")
    return (take, event_ids) if return_event_ids else take


def loan_bank_currency(loan):
    """Currency of the BANK that issued loan."""
    bank = getattr(loan, 'bank', None)
    if bank is None:
        return None
    gov = getattr(bank, 'gov', None)
    if gov is None:
        return None
    return getattr(getattr(gov, 'agent', None), 'home_currency', None)


def reclaim_dead_route_cargo(ctx, agent):
    """Return a dying trader's in-transit cargo to its export inventory."""
    src = getattr(ctx, 'source_region', None)
    if src is None:
        return
    for rt in src._all_routes():
        rt.reclaim(agent)


def escheat_dead_parked_goods(ctx, agent):
    """A dead trader's parked goods escheat to the tile holding them."""
    if not getattr(agent, 'parked_foreign', None):
        return
    src = getattr(ctx, 'source_region', None)
    if src is None:
        agent.parked_foreign = {}
        return
    for reg_name, bucket in list(agent.parked_foreign.items()):
        tile = src.neighbors.get(reg_name)
        if tile is None:
            continue
        for g in (Goods.food, Goods.wood, Goods.furniture):
            qty = bucket[g.value]
            if qty <= 0:
                continue
            if getattr(tile, 'gov', None) is not None:
                if g == Goods.food:
                    tile.gov.receive_food(qty)
                else:
                    tile.gov.agent.inv_add(g, qty)
        bucket[:] = [0] * len(bucket)
    agent.parked_foreign = {}


def handle_debt_inheritance(ctx, t, agent, living_descendants):
    """Repay debt from agent's cash/deposits; remainder passed to heirs or bank."""
    region = getattr(ctx, 'source_region', None)
    for loan in list(agent.loans):
        lcur = loan_bank_currency(loan)
        if lcur is None or lcur == getattr(ctx.source_region, 'home_currency', None):
            continue
        amount_to_clear = (loan.principle - loan.principle_paid) + loan.getInterest()
        if amount_to_clear <= 0:
            continue
        w = getattr(agent, 'wallets', None) or {}
        bal = w.get(lcur, 0.0)
        if bal <= 0:
            continue
        amt = min(bal, amount_to_clear)
        principal_before = float(loan.principle_paid)
        interest_before = float(loan.interest_paid)
        w[lcur] -= amt
        loan.pay(amt)
        principal_paid = float(loan.principle_paid) - principal_before
        interest_paid = float(loan.interest_paid) - interest_before
        _record_debt_event(
            region, 'foreign_wallet_debt_payment', t, payer=agent, amount=amt,
            currency=lcur, bank=loan.bank,
            detail={'settlement': 'death_estate_wallet',
                    'bank_currency': lcur,
                    'principal_paid': principal_paid,
                    'interest_paid': interest_paid,
                    'wallet_balance_after': float(w[lcur])})
        if region is not None:
            from run_trace import emit
            emit(region, kind='bank_foreign_wallet_repayment',
                 record_class='transfer', phase='demographics',
                 subject={'type': 'agent', 'id': agent.id, 'tile': region.name},
                 metric_id='finance.foreign_wallet_debt_payment', unit=lcur,
                 after=float(amt),
                 inputs={'bank_currency': lcur,
                         'principal_paid': principal_paid,
                         'interest_paid': interest_paid,
                         'wallet_balance_after': float(w[lcur])})

    total_wealth = agent.cash + ctx.bank.deposits.get(agent, 0)
    remaining_wealth = total_wealth
    total_paid = 0
    principal_paid = 0.0
    interest_paid = 0.0
    for loan in agent.loans:
        if getattr(loan, 'bank', None) is not ctx.bank:
            continue
        amount_to_clear = (loan.principle - loan.principle_paid) + loan.getInterest()
        payment = min(remaining_wealth, amount_to_clear)
        if payment > 0:
            principal_before = float(loan.principle_paid)
            interest_before = float(loan.interest_paid)
            loan.pay(payment)
            principal_paid += float(loan.principle_paid) - principal_before
            interest_paid += float(loan.interest_paid) - interest_before
            total_paid += payment
            remaining_wealth -= payment
    if total_paid > 0:
        if total_paid > agent.cash:
            needed_from_bank = total_paid - agent.cash
            ctx.bank.Withdraw(agent, needed_from_bank, trace_region=region, t=t,
                              reason='estate_bank_debt_service')
        _trace_cash_write = _trace_public_begin(None, agent)
        agent.cash -= total_paid
        _trace_public_finish(_trace_cash_write, 'demographics_estate:handle_debt_inheritance',
                             inputs={"source_writer": 'demographics_estate.py:handle_debt_inheritance:8ed2e00ea9df08b4:1'})
        bank_currency = loan_bank_currency(next(
            (loan for loan in agent.loans if getattr(loan, 'bank', None) is ctx.bank), None))
        _record_debt_event(
            region, 'bank_loan_repayment', t, payer=agent, amount=total_paid,
            currency=bank_currency,
            bank=ctx.bank,
            detail={'settlement': 'death_estate_cash_and_deposits',
                    'principal_paid': principal_paid,
                    'interest_paid': interest_paid,
                    'cash_after': float(agent.cash),
                    'deposit_after': float(ctx.bank.deposits.get(agent, 0.0))})
        if region is not None:
            from run_trace import emit
            emit(region, kind='estate_bank_loan_repayment',
                 record_class='transfer', phase='demographics',
                 subject={'type': 'agent', 'id': agent.id, 'tile': region.name},
                 metric_id='finance.bank_loan_repayment', unit='local_currency',
                 after=float(total_paid),
                 inputs={'principal_paid': principal_paid,
                         'interest_paid': interest_paid,
                         'cash_after': float(agent.cash),
                         'deposit_after': float(ctx.bank.deposits.get(agent, 0.0)),
                         'settlement': 'death_estate_cash_and_deposits'})
    agent.loans = [l for l in agent.loans if not l.isPaid()]

    loans_by_bank = {}
    for _l in agent.loans:
        _b = getattr(_l, 'bank', None) or ctx.bank
        loans_by_bank.setdefault(_b, []).append(_l)

    for bank, blist in loans_by_bank.items():
        remaining_principle = sum(l.principle - l.principle_paid for l in blist)
        if remaining_principle <= 0:
            continue
        from bank_trace import begin_change, finish_change
        bank_trace_change = begin_change(bank, region)
        bank.total_liabilities -= remaining_principle
        finish_change(bank, bank_trace_change, 'estate_deceased_debt_removal',
                      inputs={'debtor_id': agent.id, 'principal': remaining_principle})
        bank.loans = [l for l in bank.loans if l not in blist]
        if len(living_descendants) > 0:
            principle_share = remaining_principle / len(living_descendants)
            unpaid_interest = sum(float(loan.getInterest()) for loan in blist)
            for descendent in living_descendants:
                new_loan = trade.Loan(bank, descendent, principle_share,
                                      bank.interest_rate)
                descendent.loans.append(new_loan)
                bank.loans.append(new_loan)
                from bank_trace import begin_change, finish_change
                bank_trace_change = begin_change(bank, region)
                bank.total_liabilities += principle_share
                finish_change(bank, bank_trace_change, 'estate_heir_debt_transfer',
                              inputs={'debtor_id': agent.id, 'heir_id': descendent.id, 'principal': principle_share})
                _record_debt_event(
                    region, 'bank_debt_inheritance', t, payer=agent,
                    recipient=descendent, amount=principle_share,
                    currency=loan_bank_currency(blist[0]), bank=bank,
                    detail={'inherited_principal': float(principle_share),
                            'bank_currency': loan_bank_currency(blist[0]),
                            'source_loan_count': len(blist),
                            'unpaid_interest_not_carried':
                                unpaid_interest / len(living_descendants),
                            'debtor_id': agent.id})
            if region is not None:
                from run_trace import emit
                emit(region, kind='bank_debt_inherited_by_heirs',
                     record_class='outcome', phase='demographics',
                     subject={'type': 'agent', 'id': agent.id, 'tile': region.name},
                     metric_id='finance.bank_debt_inheritance',
                     unit='local_currency', before=float(remaining_principle),
                     after=float(remaining_principle),
                     formula_id='estate.bank_debt_transfer_to_living_heirs.v1',
                     inputs={'heir_ids': [heir.id for heir in living_descendants],
                             'bank_currency': loan_bank_currency(blist[0]),
                             'unpaid_interest_not_carried': unpaid_interest,
                             'loan_count': len(blist)})
        else:
            forgive_bad_debt(bank, remaining_principle, t,
                             region=region, debtor=agent)


def _record_wallet_estate_flow(region, t, agent, recipient_id, currency, amount,
                               kind, settlement, detail=None,
                               payer_is_decedent=True):
    if region is None or amount <= 0:
        return None
    from economy.actor_accounts import record as record_economic_event
    record_economic_event(
        region, kind, turn=t,
        payer_id=agent.id if payer_is_decedent else None,
        recipient_id=recipient_id,
        amount=amount, currency=currency,
        detail={'settlement': settlement, **(detail or {})})
    from run_trace import emit
    return emit(
        region, kind=f'estate_{kind}', record_class='transfer',
        phase='demographics',
        subject={'type': 'agent', 'id': agent.id, 'tile': region.name},
        metric_id=f'finance.{kind}', unit=currency, after=float(amount),
        inputs={'payer_id': agent.id if payer_is_decedent else None,
                'recipient_id': recipient_id, 'currency': currency,
                'amount': float(amount), 'settlement': settlement,
                **(detail or {})})


def handle_wealth_inheritance(ctx, t, agent, living_descendants):
    """Distribute remaining cash, deposits, and inventory to heirs or government/charity."""
    inheritance_cash = agent.cash
    inheritance_deposits = ctx.bank.deposits.get(agent, 0)
    government = ctx.default_gov
    region = getattr(ctx, 'source_region', None)
    operation_root = f'estate-wealth:{getattr(region, "name", "untraced")}:{t}:{agent.id}'
    trace_event_ids = []
    deposit_withdrawal_event_ids = []
    deposit_withdrawal_settled = 0.0
    source_cash_opening = float(agent.cash)
    if len(living_descendants) > 0:
        if inheritance_deposits > 0:
            deposit_withdrawal_settled = ctx.bank.Withdraw(
                agent, inheritance_deposits,
                trace_region=region, t=t,
                reason='estate_deposit_distribution',
                trace_event_ids=deposit_withdrawal_event_ids)
            trace_event_ids.extend(deposit_withdrawal_event_ids)
            inheritance_cash += deposit_withdrawal_settled
        num_heirs = len(living_descendants)
        cash_share = int(inheritance_cash // num_heirs)
        cash_remainder = inheritance_cash - (cash_share * num_heirs)
        for i, descendent in enumerate(living_descendants):
            extra_cash = cash_remainder if i == 0 else 0
            decedent_currency = getattr(ctx.source_region, 'home_currency', None) if getattr(ctx, 'source_region', None) else None
            if decedent_currency is None:
                decedent_currency = getattr(agent, 'home_currency', None)
            inherited_cash = cash_share + extra_cash
            recipient_cash_before = float(getattr(descendent, 'cash', 0.0))
            recipient_wallet_before = (fx.fx_balance(descendent, decedent_currency)
                                       if decedent_currency else 0.0)
            if getattr(descendent, '_bank_ref', None) is ctx.bank and ctx.bank is not None:
                public_change = begin_public_change(region, descendent)
                descendent.cash += inherited_cash
                finish_public_change(public_change, 'estate_public_cash_receipt')
                settlement = 'cash'
            elif decedent_currency:
                wallet_before = fx.fx_balance(descendent, decedent_currency)
                fx.fx_add(descendent, decedent_currency, inherited_cash)
                wallet_after = fx.fx_balance(descendent, decedent_currency)
                settlement = 'foreign_wallet'
            else:
                public_change = begin_public_change(region, descendent)
                descendent.cash += inherited_cash
                finish_public_change(public_change, 'estate_public_cash_receipt')
                settlement = 'cash'
            recipient_cash_after = float(getattr(descendent, 'cash', 0.0))
            recipient_wallet_after = (fx.fx_balance(descendent, decedent_currency)
                                      if decedent_currency else 0.0)
            cash_event = None
            wallet_trace_id = None
            if inherited_cash > 0 and getattr(ctx, 'source_region', None) is not None:
                from economy.actor_accounts import record as record_economic_event
                if settlement == 'foreign_wallet':
                    # The decedent pays cash while the heir receives a wallet
                    # asset; separate legs keep the cash bridge from counting
                    # that wallet balance as cash income.
                    cash_event = record_economic_event(
                        ctx.source_region, 'inheritance', turn=t,
                        payer_id=agent.id, amount=inherited_cash,
                        currency=decedent_currency,
                        detail={'heir_count': num_heirs,
                                'settlement': 'cash_to_foreign_wallet',
                                'intended_recipient_id': descendent.id})
                    wallet_trace_id = _record_wallet_estate_flow(
                        ctx.source_region, t, agent, descendent.id, decedent_currency,
                        wallet_after - wallet_before, 'foreign_wallet_inheritance',
                        'cash_to_foreign_wallet',
                        {'heir_count': num_heirs,
                         'source_cash_event_id': cash_event['id'],
                         'recipient_wallet_before': wallet_before,
                         'recipient_wallet_after': wallet_after},
                        payer_is_decedent=False)
                else:
                    cash_event = record_economic_event(
                        ctx.source_region, 'inheritance', turn=t,
                        payer_id=agent.id, recipient_id=descendent.id,
                        amount=inherited_cash, currency=decedent_currency,
                        detail={'heir_count': num_heirs, 'settlement': 'cash'})
            allocation_id = _estate_cash_allocation_trace(
                region, t, agent, descendent, inherited_cash,
                decedent_currency or 'local_currency',
                f'{operation_root}:cash:{descendent.id}', settlement,
                source_cash_opening,
                recipient_wallet_before if settlement == 'foreign_wallet'
                else recipient_cash_before,
                recipient_wallet_after if settlement == 'foreign_wallet'
                else recipient_cash_after,
                recipient_type=('wallet' if settlement == 'foreign_wallet'
                                else 'agent_cash'),
                cause_event_ids=deposit_withdrawal_event_ids,
                economic_event_id=(cash_event.get('id') if cash_event else None),
                extra_inputs={
                    'cash_pool_before_distribution': float(inheritance_cash),
                    'deposit_balance_before_withdrawal': float(inheritance_deposits),
                    'deposit_withdrawal_requested': float(inheritance_deposits),
                    'deposit_withdrawal_settled': float(deposit_withdrawal_settled),
                    'allocation_includes_requested_deposit_balance': True,
                    'share_rule': 'integer_floor_equal_shares_first_heir_receives_remainder',
                    'heir_count': num_heirs})
            if allocation_id is not None:
                trace_event_ids.append(allocation_id)
            if wallet_trace_id is not None:
                trace_event_ids.append(wallet_trace_id)

        remaining_deposit = float(ctx.bank.deposits.get(agent, 0.0))
        if remaining_deposit > 0.0:
            deposit_currency = (getattr(region, 'home_currency', None)
                                or getattr(agent, 'home_currency', None)
                                or 'local_currency')
            num_heirs = len(living_descendants)
            for index, descendent in enumerate(living_descendants):
                source_before = float(ctx.bank.deposits.get(agent, 0.0))
                deposit_share = (source_before if index == num_heirs - 1
                                 else remaining_deposit / num_heirs)
                source_after = source_before - deposit_share
                recipient_before = float(ctx.bank.deposits.get(descendent, 0.0))
                recipient_after = recipient_before + deposit_share
                recipient_bank_before = getattr(descendent, '_bank_ref', None)
                bank_total_before = float(ctx.bank.total_deposits)
                ctx.bank.deposits[agent] = source_after
                ctx.bank.deposits[descendent] = recipient_after
                if getattr(descendent, '_bank_ref', None) is None:
                    descendent._bank_ref = ctx.bank
                if hasattr(descendent, 'clear_wealth_cache'):
                    descendent.clear_wealth_cache()
                deposit_event = None
                if region is not None:
                    from economy.actor_accounts import record as record_economic_event
                    deposit_event = record_economic_event(
                        region, 'bank_deposit_inheritance', turn=t,
                        payer_id=agent.id, recipient_id=descendent.id,
                        amount=deposit_share, asset_id=f'bank:{region.name}',
                        source_id=f'estate:{agent.id}', currency=deposit_currency,
                        detail={'settlement': 'deposit_reassignment',
                                'operation_id':
                                    f'{operation_root}:deposit:{descendent.id}:{index}',
                                'bank_total_deposits_before': bank_total_before,
                                'bank_total_deposits_after':
                                    float(ctx.bank.total_deposits),
                                'cash_movement': False})
                allocation_id = _estate_deposit_allocation_trace(
                    region, t, agent, descendent, deposit_share,
                    deposit_currency,
                    f'{operation_root}:deposit:{descendent.id}:{index}',
                    ctx.bank, source_before, recipient_before, recipient_after,
                    recipient_type='bank_deposit',
                    source_deposit_after=source_after,
                    extra_inputs={
                        'destination': 'heir_deposit_reassignment',
                        'frozen_bank': bool(getattr(ctx.bank, 'is_frozen', False)),
                        'recipient_bank_reference_before': getattr(
                            recipient_bank_before, 'name', None),
                        'economic_event_id': (deposit_event['id']
                                              if deposit_event else None),
                        'cash_movement': False})
                if allocation_id is not None:
                    trace_event_ids.append(allocation_id)

        dead_w = getattr(agent, 'wallets', None)
        if dead_w:
            for currency, bal in list(dead_w.items()):
                if bal <= 0:
                    continue
                remaining = float(bal)
                for index, descendent in enumerate(living_descendants):
                    wallet_share = (remaining if index == num_heirs - 1
                                    else float(bal) / num_heirs)
                    wallet_before = fx.fx_balance(descendent, currency)
                    fx.fx_add(descendent, currency, wallet_share)
                    transferred = fx.fx_balance(descendent, currency) - wallet_before
                    wallet_trace_id = _record_wallet_estate_flow(
                        getattr(ctx, 'source_region', None), t, agent, descendent.id,
                        currency, transferred, 'foreign_wallet_inheritance',
                        'death_estate_wallet',
                        {'heir_count': num_heirs,
                         'decedent_wallet_before': float(bal),
                         'recipient_wallet_before': wallet_before,
                         'recipient_wallet_after': fx.fx_balance(descendent, currency)})
                    if wallet_trace_id is not None:
                        trace_event_ids.append(wallet_trace_id)
                    remaining -= wallet_share
                dead_w[currency] = 0.0

        for g_enum in Goods:
            if g_enum == Goods.none:
                continue
            amount = agent.inventory[g_enum.value]
            if amount == 0:
                continue
            target_heirs = [d for d in living_descendants if d.output == g_enum]
            destination_rule = 'matching_output_heirs'
            if not target_heirs:
                target_heirs = living_descendants
                destination_rule = 'all_living_descendants_no_matching_output'
            inv_share = int(amount // len(target_heirs))
            inv_remainder = amount - (inv_share * len(target_heirs))
            allocations = []
            for i, descendent in enumerate(target_heirs):
                extra_inv = inv_remainder if i == 0 else 0
                quantity = inv_share + extra_inv
                before = descendent.inventory[g_enum.value]
                descendent.inventory[g_enum.value] += quantity
                allocations.append({'recipient_id': descendent.id,
                                    'inventory_before': before,
                                    'units': quantity,
                                    'inventory_after':
                                        descendent.inventory[g_enum.value],
                                    'received_remainder': bool(extra_inv)})
            inventory_event_id = _estate_inventory_trace(
                region, t, agent, g_enum, amount, allocations,
                f'{operation_root}:good:{g_enum.name}', destination_rule)
            if inventory_event_id is not None:
                trace_event_ids.append(inventory_event_id)
    else:
        probate = getattr(government, 'probate_fee_rate', 0.0) if government else 0.0
        gov_share = inheritance_cash * probate
        charity_share = inheritance_cash - gov_share
        cash_currency = (getattr(agent, 'home_currency', None)
                         or getattr(region, 'home_currency', None)
                         or 'local_currency')
        if government is not None:
            gov_cash_before = float(getattr(government.agent, 'cash', 0.0))
            public_change = begin_public_change(region, government.agent)
            government.agent.cash += gov_share
            finish_public_change(public_change, 'estate_public_cash_receipt')
            gov_cash_after = float(getattr(government.agent, 'cash', 0.0))
            cash_event = None
            if gov_share > 0:
                government.record_income(t, 'inheritance', gov_share)
                if region is not None:
                    from economy.actor_accounts import record as record_economic_event
                    cash_event = record_economic_event(
                        region, 'inheritance', turn=t,
                        payer_id=agent.id, recipient_id=government.agent.id,
                        amount=gov_share, currency=cash_currency,
                        detail={'probate_share': probate})
                event_id = _estate_cash_allocation_trace(
                    region, t, agent, government.agent, gov_share, cash_currency,
                    f'{operation_root}:cash:government-probate', 'cash',
                    source_cash_opening, gov_cash_before, gov_cash_after,
                    cause_event_ids=deposit_withdrawal_event_ids,
                    economic_event_id=(cash_event.get('id') if cash_event else None),
                    extra_inputs={'probate_share': probate,
                                  'destination': 'government'})
                if event_id is not None:
                    trace_event_ids.append(event_id)
        charity = getattr(ctx, 'charity', None)
        if charity is not None and charity_share > 0:
            charity_cash_before = float(getattr(charity.agent, 'cash', 0.0))
            _trace_cash_write = _trace_public_begin(None, charity.agent)
            charity.agent.cash += charity_share
            _trace_public_finish(_trace_cash_write, 'demographics_estate:handle_wealth_inheritance',
                                 inputs={"source_writer": 'demographics_estate.py:handle_wealth_inheritance:277a2a6f71a453a4:1'})
            charity_cash_after = float(getattr(charity.agent, 'cash', 0.0))
            cash_event = None
            if region is not None:
                from economy.actor_accounts import record as record_economic_event
                cash_event = record_economic_event(
                    region, 'inheritance', turn=t,
                    payer_id=agent.id, recipient_id=charity.agent.id,
                    amount=charity_share, currency=cash_currency,
                    detail={'destination': 'charity', 'probate_share': 1.0 - probate})
            event_id = _estate_cash_allocation_trace(
                region, t, agent, charity.agent, charity_share, cash_currency,
                f'{operation_root}:cash:charity', 'cash', source_cash_opening,
                charity_cash_before, charity_cash_after,
                cause_event_ids=deposit_withdrawal_event_ids,
                economic_event_id=(cash_event.get('id') if cash_event else None),
                extra_inputs={'probate_share': 1.0 - probate,
                              'destination': 'charity'})
            if event_id is not None:
                trace_event_ids.append(event_id)
        elif charity is None:
            if government is not None and charity_share > 0:
                gov_cash_before = float(getattr(government.agent, 'cash', 0.0))
                public_change = begin_public_change(region, government.agent)
                government.agent.cash += charity_share
                finish_public_change(public_change, 'estate_public_cash_receipt')
                gov_cash_after = float(getattr(government.agent, 'cash', 0.0))
                government.record_income(t, 'inheritance', charity_share)
                cash_event = None
                if region is not None:
                    from economy.actor_accounts import record as record_economic_event
                    cash_event = record_economic_event(
                        region, 'inheritance', turn=t,
                        payer_id=agent.id, recipient_id=government.agent.id,
                        amount=charity_share, currency=cash_currency,
                        detail={'destination': 'government',
                                'probate_share': 1.0 - probate})
                event_id = _estate_cash_allocation_trace(
                    region, t, agent, government.agent, charity_share,
                    cash_currency,
                    f'{operation_root}:cash:government-charity-share', 'cash',
                    source_cash_opening, gov_cash_before, gov_cash_after,
                    cause_event_ids=deposit_withdrawal_event_ids,
                    economic_event_id=(cash_event.get('id')
                                       if cash_event else None),
                    extra_inputs={'probate_share': 1.0 - probate,
                                  'destination': 'government_fallback'})
                if event_id is not None:
                    trace_event_ids.append(event_id)
            elif charity_share > 0:
                from ledger import record as _rec_dest
                _rec_dest(t, getattr(agent, 'home_currency', None),
                          charity_share, 'heirless-no-state-cash')
                event_id = _estate_cash_allocation_trace(
                    region, t, agent, 'unattributed-ledger', charity_share,
                    cash_currency, f'{operation_root}:cash:ledger',
                    'ledger_escheat', source_cash_opening, 0.0, 0.0,
                    recipient_type='ledger',
                    extra_inputs={'destination': 'no_government_or_charity'})
                if event_id is not None:
                    trace_event_ids.append(event_id)

        dead_w = getattr(agent, 'wallets', None)
        if dead_w:
            for currency, bal in list(dead_w.items()):
                if bal <= 0:
                    continue
                if government is not None:
                    wallet_before = fx.fx_balance(government.agent, currency)
                    fx.fx_add(government.agent, currency, bal)
                    transferred = fx.fx_balance(government.agent, currency) - wallet_before
                    wallet_trace_id = _record_wallet_estate_flow(
                        getattr(ctx, 'source_region', None), t, agent,
                        government.agent.id, currency, transferred,
                        'foreign_wallet_inheritance', 'heirless_estate_wallet',
                        {'destination': 'government',
                         'recipient_wallet_before': wallet_before,
                         'recipient_wallet_after': fx.fx_balance(government.agent, currency)})
                else:
                    from ledger import record as _rec_dest2
                    _rec_dest2(t, currency, bal, 'heirless-no-state-wallet')
                    wallet_trace_id = _record_wallet_estate_flow(
                        getattr(ctx, 'source_region', None), t, agent, None,
                        currency, bal, 'foreign_wallet_escheat',
                        'heirless-no-state-wallet', {'destination': 'ledger'})
                if wallet_trace_id is not None:
                    trace_event_ids.append(wallet_trace_id)
                dead_w[currency] = 0.0

        if inheritance_deposits > 0:
            deposit_gov = inheritance_deposits * probate
            deposit_charity = inheritance_deposits - deposit_gov
            deposit_allocations = []
            deposit_event_ids = []
            deposit_currency = (getattr(agent, 'home_currency', None)
                                or getattr(region, 'home_currency', None)
                                or 'local_currency')
            bank_total_before = float(getattr(ctx.bank, 'total_deposits', 0.0))
            bank_account_sum_before = sum(
                float(value) for value in ctx.bank.deposits.values())
            if government is None and charity is None:
                from ledger import record as _rec_dep
                _rec_dep(t, getattr(agent, 'home_currency', None),
                         inheritance_deposits, 'heirless-no-state-deposit')
            if government is not None and deposit_gov > 0:
                recipient_before = float(ctx.bank.deposits.get(government.agent, 0.0))
                public_change = begin_public_change(region, government.agent, bank=ctx.bank, cash=False, deposit=True)
                ctx.bank.deposits[government.agent] = \
                    ctx.bank.deposits.get(government.agent, 0) + deposit_gov
                finish_public_change(public_change, 'estate_probate_deposit_receipt')
                recipient_after = float(ctx.bank.deposits[government.agent])
                deposit_allocations.append({
                    'recipient': government.agent, 'amount': deposit_gov,
                    'before': recipient_before, 'after': recipient_after,
                    'destination': 'government_probate'})
                government.record_income(t, 'inheritance', deposit_gov)
            if charity is not None and deposit_charity > 0:
                recipient_before = float(ctx.bank.deposits.get(charity.agent, 0.0))
                ctx.bank.deposits[charity.agent] = \
                    ctx.bank.deposits.get(charity.agent, 0) + deposit_charity
                recipient_after = float(ctx.bank.deposits[charity.agent])
                deposit_allocations.append({
                    'recipient': charity.agent, 'amount': deposit_charity,
                    'before': recipient_before, 'after': recipient_after,
                    'destination': 'charity'})
            elif charity is None and government is not None and deposit_charity > 0:
                recipient_before = float(ctx.bank.deposits.get(government.agent, 0.0))
                public_change = begin_public_change(region, government.agent, bank=ctx.bank, cash=False, deposit=True)
                ctx.bank.deposits[government.agent] = \
                    ctx.bank.deposits.get(government.agent, 0) + deposit_charity
                finish_public_change(public_change, 'estate_fallback_deposit_receipt')
                recipient_after = float(ctx.bank.deposits[government.agent])
                deposit_allocations.append({
                    'recipient': government.agent, 'amount': deposit_charity,
                    'before': recipient_before, 'after': recipient_after,
                    'destination': 'government_charity_share_fallback'})
                government.record_income(t, 'inheritance', deposit_charity)
            ctx.bank.deposits[agent] = 0
            bank_total_after = float(getattr(ctx.bank, 'total_deposits', 0.0))
            bank_account_sum_after = sum(
                float(value) for value in ctx.bank.deposits.values())
            for index, allocation in enumerate(deposit_allocations):
                beneficiary = allocation['recipient']
                event_id = _estate_deposit_allocation_trace(
                    region, t, agent, beneficiary, allocation['amount'],
                    deposit_currency,
                    f'{operation_root}:deposit:{beneficiary.id}:{index}',
                    ctx.bank, inheritance_deposits,
                    allocation['before'], allocation['after'],
                    recipient_type='bank_deposit',
                    extra_inputs={
                        'destination': allocation['destination'],
                        'bank_total_deposits_before': bank_total_before,
                        'bank_total_deposits_after': bank_total_after,
                        'bank_deposit_account_sum_before': bank_account_sum_before,
                        'bank_deposit_account_sum_after': bank_account_sum_after})
                if event_id is not None:
                    trace_event_ids.append(event_id)
                    deposit_event_ids.append(event_id)
            deposit_closeout_id = _estate_trace(
                region, kind='estate_decedent_deposit_closed',
                record_class='outcome', phase='demographics',
                subject={'type': 'agent', 'id': agent.id,
                         'tile': getattr(region, 'name', None)},
                metric_id='finance.estate_deposit', unit=deposit_currency,
                before=float(inheritance_deposits), after=0.0,
                formula_id='estate.heirless_deposit_closeout.v1',
                inputs={'turn': t, 'decedent_id': agent.id,
                        'bank_total_deposits_before': bank_total_before,
                        'bank_total_deposits_after': bank_total_after,
                        'bank_deposit_account_sum_before': bank_account_sum_before,
                        'bank_deposit_account_sum_after': bank_account_sum_after,
                        'allocated_amount': sum(row['amount']
                                                for row in deposit_allocations),
                        'unallocated_amount': max(
                            0.0, float(inheritance_deposits)
                            - sum(row['amount'] for row in deposit_allocations)),
                        'deposit_recipient_count': len(deposit_allocations)},
                cause_event_ids=deposit_event_ids or None)
            if deposit_closeout_id is not None:
                trace_event_ids.append(deposit_closeout_id)

        for g_enum in Goods:
            if g_enum == Goods.none:
                continue
            amount = agent.inventory[g_enum.value]
            if amount <= 0:
                continue
            allocations = []
            if g_enum == Goods.food and charity is not None:
                before = float(charity.food_inventory)
                charity.receive_food(amount)
                allocations.append({'recipient_id': charity.agent.id,
                                    'recipient_type': 'charity_food_stock',
                                    'inventory_before': before,
                                    'units': amount,
                                    'inventory_after':
                                        float(charity.food_inventory)})
            elif government is not None:
                before = government.agent.inventory[g_enum.value]
                government.agent.inventory[g_enum.value] += amount
                allocations.append({'recipient_id': government.agent.id,
                                    'recipient_type': 'government_inventory',
                                    'inventory_before': before,
                                    'units': amount,
                                    'inventory_after':
                                        government.agent.inventory[g_enum.value]})
            inventory_event_id = _estate_inventory_trace(
                region, t, agent, g_enum, amount, allocations,
                f'{operation_root}:good:{g_enum.name}',
                'charity_food_then_government_inventory'
                if charity is not None and g_enum == Goods.food
                else 'government_inventory' if government is not None
                else 'no_government_or_charity_receiver')
            if inventory_event_id is not None:
                trace_event_ids.append(inventory_event_id)
    return trace_event_ids


def zero_out_dead_agent(ctx, agent, *, t=None, cause_event_ids=None):
    """Clear dead agent's assets so they don't leak from the cash sum."""
    region = getattr(ctx, 'source_region', None) or ctx
    turn = t if t is not None else getattr(region, '_last_turn', 0)
    currency = (getattr(agent, 'home_currency', None)
                or getattr(region, 'home_currency', None) or 'local_currency')
    cash_before = float(getattr(agent, 'cash', 0.0))
    _trace_cash_write = _trace_public_begin(None, agent)
    agent.cash = 0
    _trace_public_finish(_trace_cash_write, 'demographics_estate:zero_out_dead_agent',
                         inputs={"source_writer": 'demographics_estate.py:zero_out_dead_agent:d8f880e148708ac6:1'})
    if cash_before != 0.0:
        _estate_trace(
            region, kind='estate_decedent_cash_closed', record_class='outcome',
            phase='demographics',
            subject={'type': 'agent', 'id': agent.id,
                     'tile': getattr(region, 'name', None)},
            metric_id='finance.estate_cash_closeout', unit=currency,
            before=cash_before, after=0.0,
            formula_id='estate.decedent_cash_zeroed.v1',
            inputs={'turn': turn, 'agent_id': agent.id,
                    'reason': 'terminal_estate_cleanup'},
            cause_event_ids=cause_event_ids or None)
    if agent in ctx.bank.deposits:
        deposit_before = float(ctx.bank.deposits.get(agent, 0.0))
        total_before = float(getattr(ctx.bank, 'total_deposits', 0.0))
        account_sum_before = sum(float(value)
                                 for value in ctx.bank.deposits.values())
        del ctx.bank.deposits[agent]
        total_after = float(getattr(ctx.bank, 'total_deposits', 0.0))
        account_sum_after = sum(float(value)
                                for value in ctx.bank.deposits.values())
        if deposit_before != 0.0:
            _estate_trace(
                region, kind='estate_decedent_deposit_closed',
                record_class='outcome', phase='demographics',
                subject={'type': 'agent', 'id': agent.id,
                         'tile': getattr(region, 'name', None)},
                metric_id='finance.estate_deposit_closeout', unit=currency,
                before=deposit_before, after=0.0,
                formula_id='estate.decedent_deposit_zeroed.v1',
                inputs={'turn': turn, 'agent_id': agent.id,
                        'bank_total_deposits_before': total_before,
                        'bank_total_deposits_after': total_after,
                        'bank_deposit_account_sum_before': account_sum_before,
                        'bank_deposit_account_sum_after': account_sum_after,
                        'bank_liability_adjustment': total_after - total_before},
                cause_event_ids=cause_event_ids or None)
    dead_w = getattr(agent, 'wallets', None)
    if dead_w is not None:
        wallet_balances = {str(curr): float(amount)
                           for curr, amount in dead_w.items()
                           if float(amount) != 0.0}
        dead_w.clear()
        for wallet_currency, wallet_before in wallet_balances.items():
            _estate_trace(
                region, kind='estate_decedent_wallet_closed',
                record_class='outcome', phase='demographics',
                subject={'type': 'agent', 'id': agent.id,
                         'tile': getattr(region, 'name', None),
                         'currency': wallet_currency},
                metric_id='finance.estate_wallet_closeout',
                unit=wallet_currency, before=wallet_before, after=0.0,
                formula_id='estate.decedent_wallet_zeroed.v1',
                inputs={'turn': turn, 'agent_id': agent.id,
                        'currency': wallet_currency,
                        'reason': 'terminal_estate_cleanup'},
                cause_event_ids=cause_event_ids or None)
    inventory = getattr(agent, 'inventory', None)
    if inventory is not None:
        for good in Goods:
            if good == Goods.none:
                continue
            inventory_before = inventory[good.value]
            if inventory_before <= 0:
                continue
            inventory[good.value] = 0
            _estate_trace(
                region, kind='estate_decedent_inventory_closed',
                record_class='outcome', phase='demographics',
                subject={'type': 'agent/good', 'id': str(agent.id),
                         'good': good.name,
                         'tile': getattr(region, 'name', None)},
                metric_id='goods.inheritance_transfer', unit='units',
                before=inventory_before, after=0,
                formula_id='estate.decedent_inventory_zeroed.v1',
                inputs={'turn': turn, 'agent_id': agent.id,
                        'good': good.name,
                        'inventory_removed': inventory_before,
                        'reason': 'terminal_estate_cleanup'},
                cause_event_ids=cause_event_ids or None)


def settle_external_death(region, t, agent, cause, *, death_trace_event_ids=None,
                          death_trace_inputs=None):
    """Record and probate a death caused by combat or political violence."""
    from types import SimpleNamespace
    from person_death import record_person_death
    if not record_person_death(
            region, agent, t, cause, phase='politics',
            inputs=death_trace_inputs,
            trace_event_ids=death_trace_event_ids):
        return False
    cleanup_dead_agent_links(agent, region, t)
    handle_company_inheritance(t, agent, region)
    heirs = living_descendants_recursive(agent)
    handle_wage_claim_inheritance(region, t, agent, heirs,
                                  getattr(region, 'gov', None),
                                  getattr(region, 'charity', None))
    if getattr(region, 'bank', None) is None:
        # Minimal scenario/test tiles have no probate ledger.
        charity = getattr(region, 'charity', None)
        if charity is not None:
            _trace_cash_write = _trace_public_begin(None, charity.agent)
            charity.agent.cash += agent.cash
            _trace_public_finish(_trace_cash_write, 'demographics_estate:settle_external_death',
                                 inputs={"source_writer": 'demographics_estate.py:settle_external_death:7e8331e4b14d0ae1:1'})
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash = 0.0
            _trace_public_finish(_trace_cash_write, 'demographics_estate:settle_external_death',
                                 inputs={"source_writer": 'demographics_estate.py:settle_external_death:8a52b84e15fd57d1:1'})
        return True
    ctx = SimpleNamespace(bank=region.bank, default_gov=getattr(region, 'gov', None),
                          charity=getattr(region, 'charity', None), source_region=region)
    reclaim_dead_route_cargo(ctx, agent)
    escheat_dead_parked_goods(ctx, agent)
    handle_debt_inheritance(ctx, t, agent, heirs)
    estate_trace_event_ids = handle_wealth_inheritance(ctx, t, agent, heirs)
    zero_out_dead_agent(ctx, agent, t=t,
                        cause_event_ids=estate_trace_event_ids)
    return True


def handle_death(ctx, t, agent, agents):
    """Determine if agent dies (starvation or old age). Clean up assets."""
    if not agent.alive:
        return False
    from nutrition import starvation_hazard
    trace_region = getattr(ctx, 'source_region', None) or ctx
    agent.died_of_starvation = False
    hazard = starvation_hazard(agent)
    starvation_draw = rand.random() if hazard > 0 else None
    starved = hazard > 0 and starvation_draw < hazard
    if not starved:
        base_death_prob = [0.0002, 0.0003, 0.0007, 0.0013, 0.0025,
                            0.006, 0.013, 0.027, 0.06, 0.13]
        import government as govmod
        government = govmod.find_government_for_agent(agent)
        age_base_prob = base_death_prob[min(agent.age(t) // 15, 9)]
        if government is not None:
            adjusted_prob = government.get_death_probability(
                agent, age_base_prob)
        else:
            adjusted_prob = age_base_prob

        agent_age = agent.age(t)
        wealth_discount = 1.0
        if agent_age < 105 and adjusted_prob > 0:
            col = ctx.cost_of_living
            wealth = agent.wealth()
            if wealth > col:
                age_weight = max(0.0, 1.0 - (agent_age / 105.0) ** 6)
                wealth_factor = (col / max(0.01, wealth)) ** 2
                wealth_factor = max(0.01, min(1.0, wealth_factor))
                if hasattr(agent, '_birth_parent_wealth') and t < getattr(agent, '_birth_protection_until', 0):
                    parent_wealth_factor = (col / max(0.01, agent._birth_parent_wealth)) ** 2
                    parent_wealth_factor = max(0.01, min(1.0, parent_wealth_factor))
                    fade = max(0.0, min(1.0, (agent._birth_protection_until - t) / 25.0))
                    wealth_factor = wealth_factor * (1 - fade) + parent_wealth_factor * fade
                mortality_discount = 1.0 - (1.0 - wealth_factor) * age_weight
                adjusted_prob *= mortality_discount
                wealth_discount = mortality_discount

        current_pop = len(agents)
        threshold = ctx.carrying_capacity * 0.85
        crowding_factor = 1.0
        if current_pop > threshold:
            overage = current_pop - threshold
            crowding_factor = 1.0 + (overage / (ctx.carrying_capacity * 0.15)) * 4.0
            adjusted_prob *= crowding_factor

        # P2: Physiological health attrition increases mortality from industrial disease / wear
        attrition = getattr(agent, 'health_attrition', 0.0)
        if attrition > 0.0:
            adjusted_prob *= (1.0 + min(3.0, attrition * 1.5))

        # Preserve the risk immediately before disease modifiers so the trace
        # can distinguish disease being present from it changing this death
        # outcome. This observation must not alter the existing probability or
        # random draw.
        probability_without_disease = adjusted_prob

        # P3: Active epidemic diseases compound mortality risk
        active_dis = getattr(agent, 'diseases', []) or []
        if active_dis:
            if 'pestilence' in active_dis:
                # Acute lethal plague: 35% base mortality per turn, scaled by hunger
                plague_mortality = 0.35 * (1.0 + 0.35 * getattr(agent, 'hungry_steps', 0))
                adjusted_prob = max(adjusted_prob, min(0.65, plague_mortality))
            else:
                adjusted_prob *= (1.0 + min(4.0, 0.45 * len(active_dis)))

        if is_last_of_profession(agent, agents, ctx):
            return False
        death_draw = rand.random()
        died = death_draw <= adjusted_prob
        disease_attributed = bool(
            died and active_dis
            and death_draw > probability_without_disease
            and death_draw <= adjusted_prob)
        if active_dis or attrition > 0.0 or died:
            from run_trace import emit
            mortality_event_id = emit(trace_region, kind='mortality_assessment', record_class='outcome',
                 subject={'type': 'tile', 'id': getattr(trace_region, 'name', 'unknown'),
                          'agent_id': getattr(agent, 'id', None)},
                 metric_id='health.mortality_risk', unit='probability',
                 before=age_base_prob, after=adjusted_prob,
                 formula_id='mortality.age_wealth_crowding_health.v1',
                 inputs={'age': agent_age, 'age_base_probability': age_base_prob,
                         'wealth': float(agent.wealth()), 'cost_of_living': ctx.cost_of_living,
                         'wealth_discount': wealth_discount,
                         'population': current_pop, 'crowding_threshold': threshold,
                         'crowding_factor': crowding_factor, 'health_attrition': attrition,
                         'probability_without_disease': probability_without_disease,
                         'active_diseases': list(active_dis),
                         'hungry_steps': getattr(agent, 'hungry_steps', 0),
                         'death_draw': death_draw, 'died': died,
                         'disease_attributed_by_threshold_crossing': disease_attributed})
        if not died:
            return False
        agent.alive = False
        if disease_attributed and hasattr(trace_region, 'disease_fatalities_this_turn'):
            trace_region.disease_fatalities_this_turn += 1
            if mortality_event_id is not None:
                from health_trace import remember_fatality
                remember_fatality(trace_region, agent, t, mortality_event_id,
                                  death_draw, probability_without_disease,
                                  adjusted_prob, active_dis)
        loginfo(t, agent.name(), 'has died due to age')
    else:
        from run_trace import emit
        from nutrition import effective_calorie_need, metabolic_need_factor
        emit(trace_region, kind='starvation_death_assessment', record_class='outcome',
             subject={'type': 'tile', 'id': getattr(trace_region, 'name', 'unknown'),
                      'agent_id': getattr(agent, 'id', None)},
             metric_id='health.starvation_hazard', unit='probability',
             after=hazard, formula_id='mortality.starvation_hazard.v2',
             inputs={'starvation_draw': starvation_draw,
                     'hungry_steps': getattr(agent, 'hungry_steps', 0),
                     'calorie_deficit_kcal': getattr(agent, 'calorie_deficit_kcal', 0.0),
                     'baseline_calorie_need_kcal': getattr(agent, 'calorie_need_kcal', 2000.0),
                     'effective_calorie_need_kcal': effective_calorie_need(agent),
                     'metabolic_need_factor': metabolic_need_factor(agent),
                     'energy_reserve_kcal': getattr(agent, 'energy_reserve_kcal', 0.0),
                     'food_inventory': agent.inv_get(Goods.food, 0),
                     'food_aid_received_this_turn': getattr(agent, 'food_aid_received_this_turn', 0),
                     'livelihood': getattr(getattr(agent, 'primary_livelihood', None), 'name',
                                           getattr(agent, 'primary_livelihood', None)),
                     'died': True})
        logdebug(t, agent.name(), 'has starved to death')
        agent.alive = False
        agent.died_of_starvation = True

    death_cause = ('starvation' if starved else
                   'disease' if disease_attributed else 'age_or_health')
    from person_death import record_person_death
    record_person_death(trace_region, agent, t, death_cause,
                        inputs={'age': agent.age(t),
                                'active_diseases': list(getattr(agent, 'diseases', []) or []),
                                'health_attrition': getattr(agent, 'health_attrition', 0.0),
                                'starvation_hazard': hazard if starved else 0.0,
                                'probability_without_disease': (
                                    probability_without_disease if not starved else None),
                                'disease_attributed_by_threshold_crossing': (
                                    disease_attributed if not starved else False)})

    cleanup_dead_agent_links(agent, trace_region, t)
    handle_company_inheritance(t, agent, trace_region)
    living_descendants = living_descendants_recursive(agent)
    handle_wage_claim_inheritance(
        trace_region, t, agent, living_descendants,
        getattr(ctx, 'default_gov', None), getattr(ctx, 'charity', None))
    logdebug(t, agent.name(), 'died, has', agent.cash,
             ' #descendants:', len(living_descendants),
             [a.name() for a in living_descendants])

    reclaim_dead_route_cargo(ctx, agent)
    escheat_dead_parked_goods(ctx, agent)
    handle_debt_inheritance(ctx, t, agent, living_descendants)
    estate_trace_event_ids = handle_wealth_inheritance(
        ctx, t, agent, living_descendants)
    zero_out_dead_agent(ctx, agent, t=t,
                        cause_event_ids=estate_trace_event_ids)
    return True
