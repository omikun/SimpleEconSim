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


def forgive_bad_debt(bank, amount, t):
    """Conservation-safe heirless bad-debt forgiveness in seniority order."""
    if amount <= 0:
        return True

    # 1. Shareholders absorb first.
    capital_absorb = min(amount, max(0.0, bank.capital))
    if capital_absorb > 0:
        bank.capital -= capital_absorb
    remaining = amount - capital_absorb

    # 2. Depositors bailed in pro-rata.
    if remaining > 0:
        pool = deposit_pool(bank)
        dep_absorb = min(remaining, pool)
        if dep_absorb > 0:
            for owner, bal in list(bank.deposits.items()):
                if bal <= 0:
                    continue
                share = bal * (dep_absorb / pool)
                bank.deposits[owner] = max(0.0, bal - share)
            bank.total_deposits -= dep_absorb
            logwarning(t, f"DEPOSITOR BAIL-IN: ${dep_absorb:.2f} of "
                          f"${amount:.2f} bad debt absorbed by depositors "
                          f"(shareholders took ${capital_absorb:.2f})")
        remaining -= dep_absorb

    # 3. Tile treasury recapitalization.
    if remaining > 0:
        remaining -= recapitalize(bank, remaining, t)

    # 4. Genuine bank failure -> negative equity.
    if remaining > 1e-9:
        bank.capital -= remaining
        logwarning(t, f"BANK FAILURE: ${remaining:.2f} heirless bad debt "
                      f"unabsorbed after seniority order — equity goes "
                      f"negative (capital ${bank.capital:.2f}).")
    return True


def recapitalize(bank, shortfall, t):
    """Tile treasury lender-of-last-resort recapitalization (conserved)."""
    gov = getattr(bank, 'gov', None)
    if gov is None:
        return 0.0
    take = min(max(0.0, shortfall), max(0.0, gov.agent.cash))
    if take <= 0:
        return 0.0
    gov.agent.cash -= take
    bank.capital += take
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
        w[lcur] -= amt
        loan.pay(amt)

    total_wealth = agent.cash + ctx.bank.deposits.get(agent, 0)
    remaining_wealth = total_wealth
    total_paid = 0
    for loan in agent.loans:
        if getattr(loan, 'bank', None) is not ctx.bank:
            continue
        amount_to_clear = (loan.principle - loan.principle_paid) + loan.getInterest()
        payment = min(remaining_wealth, amount_to_clear)
        if payment > 0:
            loan.pay(payment)
            total_paid += payment
            remaining_wealth -= payment
    if total_paid > 0:
        if total_paid > agent.cash:
            needed_from_bank = total_paid - agent.cash
            ctx.bank.Withdraw(agent, needed_from_bank)
        agent.cash -= total_paid
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
            for descendent in living_descendants:
                new_loan = trade.Loan(bank, descendent, principle_share,
                                      bank.interest_rate)
                descendent.loans.append(new_loan)
                bank.loans.append(new_loan)
                bank.total_liabilities += principle_share
        else:
            forgive_bad_debt(bank, remaining_principle, t)


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
            if getattr(descendent, '_bank_ref', None) is ctx.bank and ctx.bank is not None:
                descendent.cash += cash_share + extra_cash
            elif decedent_currency:
                fx.fx_add(descendent, decedent_currency,
                          cash_share + extra_cash)
            else:
                descendent.cash += cash_share + extra_cash

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
        charity = getattr(ctx, 'charity', None)
        if charity is not None and charity_share > 0:
            charity.agent.cash += charity_share
        elif charity is None:
            if government is not None and charity_share > 0:
                government.agent.cash += charity_share
                government.record_income(t, 'inheritance', charity_share)
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
