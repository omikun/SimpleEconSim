"""
Demographics estate: death determination, corporate succession, debt resolution,
bad debt forgiveness & write-downs, wealth inheritance, and escheat.
"""

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


def cleanup_dead_agent_links(agent):
    """Clean up corporation/employee links for a dying agent."""
    if getattr(agent, 'employer', None) is not None:
        employer = agent.employer
        if hasattr(employer, 'employees') and agent in employer.employees:
            employer.employees.remove(agent)
        agent.employer = None
    if getattr(agent, 'is_corporation', False) and hasattr(agent, 'employees'):
        for emp in agent.employees:
            emp.employer = None
        agent.employees = []
        agent.is_corporation = False
        if agent.owner is not None:
            agent.owner.company_owned = None
            agent.owner = None


def handle_company_inheritance(t, agent):
    """Pass company to heir when founder dies."""
    if getattr(agent, 'company_owned', None) is None:
        return
    company = agent.company_owned
    living_descendants = living_descendants_recursive(agent)
    if len(living_descendants) > 0:
        heir = max(living_descendants, key=lambda d: d.cash)
        company.owner = heir
        heir.company_owned = company
        logdebug(t, agent.name(), 'company', company.name(),
                 'inherited by', heir.name())
    elif company.alive and company.is_corporation and len(company.employees) > 0:
        oldest_emp = min(company.employees, key=lambda e: e.hired_at)
        company.owner = oldest_emp
        oldest_emp.company_owned = company
        logdebug(t, agent.name(), 'company', company.name(),
                 'inherited by oldest employee', oldest_emp.name())
    elif company.alive and company.is_corporation:
        logdebug(t, agent.name(), 'company', company.name(),
                 'dissolved (no heirs, no employees)')
        for emp in company.employees:
            emp.employer = None
        company.employees = []
        company.is_corporation = False
        company.owner = None
    agent.company_owned = None


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

    # 1. Shareholders absorb first.
    capital_absorb = min(amount, max(0.0, bank.capital))
    if capital_absorb > 0:
        bank.capital -= capital_absorb
    remaining = amount - capital_absorb
    deposit_absorb = 0.0
    treasury_absorb = 0.0

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
                bank.deposits[owner] = max(0.0, bal - share)
                bank._record_account_event(owner, 'bank_deposit_haircut',
                                           float(share), payer=True,
                                           detail={'bad_debt_bail_in': True})
            bank.total_deposits -= dep_absorb
            logwarning(t, f"DEPOSITOR BAIL-IN: ${dep_absorb:.2f} of "
                          f"${amount:.2f} bad debt absorbed by depositors "
                          f"(shareholders took ${capital_absorb:.2f})")
        remaining -= dep_absorb

    # 3. Tile treasury recapitalization.
    if remaining > 0:
        treasury_absorb = recapitalize(
            bank, remaining, t, region=region, debtor=debtor)
        remaining -= treasury_absorb

    # 4. Genuine bank failure -> negative equity.
    if remaining > 1e-9:
        bank.capital -= remaining
        logwarning(t, f"BANK FAILURE: ${remaining:.2f} heirless bad debt "
                      f"unabsorbed after seniority order — equity goes "
                      f"negative (capital ${bank.capital:.2f}).")
    bank_currency = getattr(getattr(getattr(bank, 'gov', None), 'agent', None),
                             'home_currency', None)
    _record_debt_event(
        region, 'bank_debt_writeoff', t, payer=debtor, amount=amount,
        currency=bank_currency, bank=bank, detail={
            'principal_written_off': float(amount),
            'shareholder_capital_absorbed': float(capital_absorb),
            'depositor_bail_in': float(deposit_absorb),
            'treasury_recapitalization': float(treasury_absorb),
            'unabsorbed_bank_loss': float(max(0.0, remaining)),
            'bank_capital_after': float(bank.capital),
            'bank_deposits_after': float(bank.total_deposits),
            'debtor_id': getattr(debtor, 'id', None)})
    if region is not None:
        from run_trace import emit
        emit(region, kind='bank_estate_debt_writeoff', record_class='outcome',
             phase='demographics',
             subject={'type': 'tile', 'id': region.name,
                      'agent_id': getattr(debtor, 'id', None)},
             metric_id='finance.bank_debt_writeoff',
             unit='local_currency', before=float(amount), after=0.0,
             formula_id='estate.bank_bad_debt_seniority_waterfall.v1',
             inputs={'shareholder_capital_absorbed': float(capital_absorb),
                     'depositor_bail_in': float(deposit_absorb),
                     'treasury_recapitalization': float(treasury_absorb),
                     'unabsorbed_bank_loss': float(max(0.0, remaining)),
                     'bank_capital_after': float(bank.capital),
                     'bank_deposits_after': float(bank.total_deposits),
                     'debtor_id': getattr(debtor, 'id', None)})
    return True


def recapitalize(bank, shortfall, t, *, region=None, debtor=None):
    """Tile treasury lender-of-last-resort recapitalization (conserved)."""
    gov = getattr(bank, 'gov', None)
    if gov is None:
        return 0.0
    take = min(max(0.0, shortfall), max(0.0, gov.agent.cash))
    if take <= 0:
        return 0.0
    capital_before = float(bank.capital)
    gov.agent.cash -= take
    bank.capital += take
    _record_debt_event(
        region, 'bank_recapitalization', t, payer=gov.agent, amount=take,
        currency=getattr(gov.agent, 'home_currency', None), bank=bank,
        detail={'capital_injected': float(take),
                'bank_capital_after': float(bank.capital),
                'cause': 'heirless_estate_bad_debt',
                'debtor_id': getattr(debtor, 'id', None)})
    if region is not None:
        from run_trace import emit
        emit(region, kind='estate_bank_recapitalization',
             record_class='transfer', phase='demographics',
             subject={'type': 'tile', 'id': region.name,
                      'agent_id': gov.agent.id},
             metric_id='finance.bank_recapitalization', unit='local_currency',
             before=capital_before, after=float(bank.capital),
             inputs={'capital_injected': float(take),
                     'debtor_id': getattr(debtor, 'id', None),
                     'bank_capital_before': capital_before,
                     'bank_capital_after': float(bank.capital)})
    logwarning(t, f"RECAPITALIZATION: ${take:.2f} treasury capital injected "
                  f"into bank (capital ${bank.capital:.2f})")
    return take


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
            ctx.bank.Withdraw(agent, needed_from_bank)
        agent.cash -= total_paid
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
        bank.total_liabilities -= remaining_principle
        bank.loans = [l for l in bank.loans if l not in blist]
        if len(living_descendants) > 0:
            principle_share = remaining_principle / len(living_descendants)
            unpaid_interest = sum(float(loan.getInterest()) for loan in blist)
            for descendent in living_descendants:
                new_loan = trade.Loan(bank, descendent, principle_share,
                                      bank.interest_rate)
                descendent.loans.append(new_loan)
                bank.loans.append(new_loan)
                bank.total_liabilities += principle_share
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


def handle_wealth_inheritance(ctx, t, agent, living_descendants):
    """Distribute remaining cash, deposits, and inventory to heirs or government/charity."""
    inheritance_cash = agent.cash
    inheritance_deposits = ctx.bank.deposits.get(agent, 0)
    government = ctx.default_gov
    if len(living_descendants) > 0:
        if inheritance_deposits > 0:
            ctx.bank.Withdraw(agent, inheritance_deposits)
            inheritance_cash += inheritance_deposits
        num_heirs = len(living_descendants)
        cash_share = int(inheritance_cash // num_heirs)
        cash_remainder = inheritance_cash - (cash_share * num_heirs)
        for i, descendent in enumerate(living_descendants):
            extra_cash = cash_remainder if i == 0 else 0
            decedent_currency = getattr(ctx.source_region, 'home_currency', None) if getattr(ctx, 'source_region', None) else None
            if decedent_currency is None:
                decedent_currency = getattr(agent, 'home_currency', None)
            inherited_cash = cash_share + extra_cash
            if getattr(descendent, '_bank_ref', None) is ctx.bank and ctx.bank is not None:
                descendent.cash += inherited_cash
            elif decedent_currency:
                fx.fx_add(descendent, decedent_currency, inherited_cash)
            else:
                descendent.cash += inherited_cash
            if inherited_cash > 0 and getattr(ctx, 'source_region', None) is not None:
                from economy.actor_accounts import record as record_economic_event
                record_economic_event(
                    ctx.source_region, 'inheritance', turn=t,
                    payer_id=agent.id, recipient_id=descendent.id,
                    amount=inherited_cash, currency=decedent_currency,
                    detail={'heir_count': num_heirs,
                            'settlement': 'cash' if getattr(descendent, '_bank_ref', None)
                            is ctx.bank and ctx.bank is not None else 'foreign_wallet'})

        dead_w = getattr(agent, 'wallets', None)
        if dead_w:
            for currency, bal in list(dead_w.items()):
                if bal <= 0:
                    continue
                wallet_share = bal / num_heirs
                for descendent in living_descendants:
                    fx.fx_add(descendent, currency, wallet_share)
                dead_w[currency] = 0.0

        for g_enum in Goods:
            if g_enum == Goods.none:
                continue
            amount = agent.inventory[g_enum.value]
            if amount == 0:
                continue
            target_heirs = [d for d in living_descendants if d.output == g_enum]
            if not target_heirs:
                target_heirs = living_descendants
            inv_share = int(amount // len(target_heirs))
            inv_remainder = amount - (inv_share * len(target_heirs))
            for i, descendent in enumerate(target_heirs):
                extra_inv = inv_remainder if i == 0 else 0
                descendent.inventory[g_enum.value] += inv_share + extra_inv
    else:
        probate = getattr(government, 'probate_fee_rate', 0.0) if government else 0.0
        gov_share = inheritance_cash * probate
        charity_share = inheritance_cash - gov_share
        if government is not None:
            government.agent.cash += gov_share
            if gov_share > 0:
                government.record_income(t, 'inheritance', gov_share)
                if getattr(ctx, 'source_region', None) is not None:
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(
                        ctx.source_region, 'inheritance', turn=t,
                        payer_id=agent.id, recipient_id=government.agent.id,
                        amount=gov_share, currency=getattr(agent, 'home_currency', None),
                        detail={'probate_share': probate})
        charity = getattr(ctx, 'charity', None)
        if charity is not None and charity_share > 0:
            charity.agent.cash += charity_share
            if getattr(ctx, 'source_region', None) is not None:
                from economy.actor_accounts import record as record_economic_event
                record_economic_event(
                    ctx.source_region, 'inheritance', turn=t,
                    payer_id=agent.id, recipient_id=charity.agent.id,
                    amount=charity_share, currency=getattr(agent, 'home_currency', None),
                    detail={'destination': 'charity', 'probate_share': 1.0 - probate})
        elif charity is None:
            if government is not None and charity_share > 0:
                government.agent.cash += charity_share
                government.record_income(t, 'inheritance', charity_share)
                if getattr(ctx, 'source_region', None) is not None:
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(
                        ctx.source_region, 'inheritance', turn=t,
                        payer_id=agent.id, recipient_id=government.agent.id,
                        amount=charity_share, currency=getattr(agent, 'home_currency', None),
                        detail={'destination': 'government',
                                'probate_share': 1.0 - probate})
            elif charity_share > 0:
                from ledger import record as _rec_dest
                _rec_dest(t, getattr(agent, 'home_currency', None),
                          charity_share, 'heirless-no-state-cash')

        dead_w = getattr(agent, 'wallets', None)
        if dead_w:
            for currency, bal in list(dead_w.items()):
                if bal <= 0:
                    continue
                if government is not None:
                    fx.fx_add(government.agent, currency, bal)
                else:
                    from ledger import record as _rec_dest2
                    _rec_dest2(t, currency, bal, 'heirless-no-state-wallet')
                dead_w[currency] = 0.0

        if inheritance_deposits > 0:
            deposit_gov = inheritance_deposits * probate
            deposit_charity = inheritance_deposits - deposit_gov
            if government is None and charity is None:
                from ledger import record as _rec_dep
                _rec_dep(t, getattr(agent, 'home_currency', None),
                         inheritance_deposits, 'heirless-no-state-deposit')
            if government is not None and deposit_gov > 0:
                ctx.bank.deposits[government.agent] = \
                    ctx.bank.deposits.get(government.agent, 0) + deposit_gov
                government.record_income(t, 'inheritance', deposit_gov)
            if charity is not None and deposit_charity > 0:
                ctx.bank.deposits[charity.agent] = \
                    ctx.bank.deposits.get(charity.agent, 0) + deposit_charity
            elif charity is None and government is not None and deposit_charity > 0:
                ctx.bank.deposits[government.agent] = \
                    ctx.bank.deposits.get(government.agent, 0) + deposit_charity
                government.record_income(t, 'inheritance', deposit_charity)
            ctx.bank.deposits[agent] = 0

        for g_enum in Goods:
            if g_enum == Goods.none:
                continue
            amount = agent.inventory[g_enum.value]
            if amount <= 0:
                continue
            if g_enum == Goods.food and charity is not None:
                charity.receive_food(amount)
            elif government is not None:
                government.agent.inventory[g_enum.value] += amount


def zero_out_dead_agent(ctx, agent):
    """Clear dead agent's assets so they don't leak from the cash sum."""
    agent.cash = 0
    if agent in ctx.bank.deposits:
        del ctx.bank.deposits[agent]
    dead_w = getattr(agent, 'wallets', None)
    if dead_w is not None:
        dead_w.clear()


def settle_external_death(region, t, agent, cause):
    """Record and probate a death caused by combat or political violence."""
    from types import SimpleNamespace
    from person_death import record_person_death
    if not record_person_death(region, agent, t, cause, phase='politics'):
        return False
    if getattr(region, 'bank', None) is None:
        # Minimal scenario/test tiles have no probate ledger.
        charity = getattr(region, 'charity', None)
        if charity is not None:
            charity.agent.cash += agent.cash
            agent.cash = 0.0
        return True
    ctx = SimpleNamespace(bank=region.bank, default_gov=getattr(region, 'gov', None),
                          charity=getattr(region, 'charity', None), source_region=region)
    cleanup_dead_agent_links(agent)
    handle_company_inheritance(t, agent)
    heirs = living_descendants_recursive(agent)
    reclaim_dead_route_cargo(ctx, agent)
    escheat_dead_parked_goods(ctx, agent)
    handle_debt_inheritance(ctx, t, agent, heirs)
    handle_wealth_inheritance(ctx, t, agent, heirs)
    zero_out_dead_agent(ctx, agent)
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
        if active_dis or attrition > 0.0 or died:
            from run_trace import emit
            emit(trace_region, kind='mortality_assessment', record_class='outcome',
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
                         'active_diseases': list(active_dis),
                         'hungry_steps': getattr(agent, 'hungry_steps', 0),
                         'death_draw': death_draw, 'died': died})
        if not died:
            return False
        agent.alive = False
        if active_dis and hasattr(ctx, 'disease_fatalities_this_turn'):
            ctx.disease_fatalities_this_turn += 1
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
                   'disease' if getattr(agent, 'diseases', None) else 'age_or_health')
    from person_death import record_person_death
    record_person_death(trace_region, agent, t, death_cause,
                        inputs={'age': agent.age(t),
                                'active_diseases': list(getattr(agent, 'diseases', []) or []),
                                'health_attrition': getattr(agent, 'health_attrition', 0.0),
                                'starvation_hazard': hazard if starved else 0.0})

    cleanup_dead_agent_links(agent)
    handle_company_inheritance(t, agent)
    living_descendants = living_descendants_recursive(agent)
    logdebug(t, agent.name(), 'died, has', agent.cash,
             ' #descendants:', len(living_descendants),
             [a.name() for a in living_descendants])

    reclaim_dead_route_cargo(ctx, agent)
    escheat_dead_parked_goods(ctx, agent)
    handle_debt_inheritance(ctx, t, agent, living_descendants)
    handle_wealth_inheritance(ctx, t, agent, living_descendants)
    zero_out_dead_agent(ctx, agent)
    return True
