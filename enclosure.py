"""
enclosure.py — Feudal Enclosure & Dispossession Engine for Call of Capital.

Under the Enclosure Act, a lord petitions the crown to strip customary
usufruct rights from their feudal estate. The crown grants an enclosure
charter in exchange for a charter fee (conserved transfer: lord -> crown).

Consequences of enclosure:
  1. Plot tenure changes from FEUDAL to ENCLOSED.
  2. The plot ceases paying in-kind tribute and will charge cash rent.
  3. Serfs lose access to the enclosed commons (commons_access decreases).
  4. Dispossessed serfs receive persistent 'mem_eviction' trauma.
  5. Grievances spike on identity and class factions, raising protest energy.
  6. Dispossessed serfs become dependent on the wage-labor market.
"""
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
from treasury_trace import begin_public_change, finish_public_change

from goods import Goods
from land_tenure import TenureStatus, LandPlot
from livelihood_access import (assess_obligation, effective_access, grant_access,
                               remove_access)

# Charter fee per 10% (0.10) fraction of tile enclosed (nominal administrative filing fee)
CHARTER_FEE_PER_TENTH = 5.0
DEFAULT_CASH_RENT = 3.0
STATUTORY_SURVEY_FEE = 15.0


def _record_enclosure_cash_transfer(tile, *, kind, operation_type, payer,
                                    payee, amount, payer_before,
                                    payee_before, turn, plot_id, detail,
                                    cause_event_ids=None):
    """Journal and trace one already-settled enclosure payment."""
    from economy.actor_accounts import record as record_economic_event
    from finance_trace import (account_ref, cash_transfer_contract,
                               emit_cash_transfer)

    amount = float(amount)
    payer_id = str(payer.id)
    payee_id = str(payee.id)
    currency = (getattr(payer, 'home_currency', None)
                or getattr(tile, 'home_currency', None) or 'local_currency')
    payee_currency = (getattr(payee, 'home_currency', None)
                      or getattr(tile, 'home_currency', None) or currency)
    operation_id = (f'{operation_type}:{tile.name}:{int(turn)}:{plot_id}:'
                    f'{payer_id}:{payee_id}')

    journal_event = record_economic_event(
        tile, kind, turn=turn, payer_id=payer.id, recipient_id=payee.id,
        amount=amount, asset_id=plot_id, source_id=operation_id,
        currency=currency, detail=detail)
    contract = cash_transfer_contract(
        operation_id, operation_type, amount=amount, currency=currency,
        payer_account=account_ref(
            'agent_wallet', payer_id, currency, agent_id=payer_id,
            tile=tile.name, balance_before=float(payer_before),
            balance_after=float(payer.cash), balance_scope='cash_wallet'),
        payee_account=account_ref(
            'government_wallet' if getattr(payee, 'is_government', False)
            else 'agent_wallet', payee_id, payee_currency,
            agent_id=payee_id, tile=tile.name,
            balance_before=float(payee_before),
            balance_after=float(payee.cash), balance_scope='cash_wallet'),
        counterparty_leg_status='both_cash_balances_captured',
        mutation_reference={'turn': int(turn), 'tile': tile.name,
                            'plot_id': plot_id},
        currency_conversion_applied=False,
        unconverted_currency_mismatch=(currency != payee_currency))
    transfer_event_id = emit_cash_transfer(
        tile, kind=kind, contract=contract, phase='policy_action',
        subject={'type': 'tile/plot', 'id': str(plot_id), 'tile': tile.name},
        inputs={'turn': int(turn), 'plot_id': str(plot_id),
                'actor_account_event_id': journal_event['id'],
                'detail': detail},
        cause_event_ids=cause_event_ids)
    from finance_trace import emit_public_account_flow
    causes = [transfer_event_id] if transfer_event_id else None
    emit_public_account_flow(tile, payer, kind=f'{kind}_treasury_payment',
                             signed_amount=float(payer.cash) - float(payer_before),
                             inputs={'operation_id': operation_id, 'plot_id': str(plot_id)},
                             cause_event_ids=causes)
    emit_public_account_flow(tile, payee, kind=f'{kind}_treasury_receipt',
                             signed_amount=float(payee.cash) - float(payee_before),
                             inputs={'operation_id': operation_id, 'plot_id': str(plot_id)},
                             cause_event_ids=causes)
    return transfer_event_id


def calculate_charter_fee(plot: LandPlot) -> float:
    """Calculate the crown charter fee required to enclose this plot."""
    return round((plot.fraction / 0.10) * CHARTER_FEE_PER_TENTH, 2)


def dispossess_commoners(tile, plot: LandPlot, t: int) -> list[dict]:
    """Apply dispossession trauma and grievance to serfs on the enclosed tile.

    - Pushes 'mem_eviction' memory to serfs on the tile.
    - Increases grievance and protest energy.
    - Returns event records for logging / UI ticker.
    """
    events = []
    serfs = [a for a in tile.agents if a.id in getattr(plot, 'tenant_ids', [])
             and not a.is_trader and not a.is_government
             and not getattr(a, 'is_lord', False) and a.alive]

    if not serfs:
        return events

    # Number of serfs directly dispossessed by this plot's enclosure
    dispossessed_count = len(serfs)
    for serf in serfs:
        serf.mem_push('mem_eviction', 1.0)
        rights = getattr(tile, 'access_rights', {}).get(serf.id, [])
        before = effective_access(serf, tile, 'commons_food')
        for right in rights:
            if right.plot_id == plot.plot_id and right.resource == 'commons_food':
                right.usable_share = 0.0
        after = effective_access(serf, tile, 'commons_food')
        tile.access_events.append({'turn': t, 'person_id': serf.id, 'plot_id': plot.plot_id,
                                   'before': round(before, 3), 'after': round(after, 3),
                                   'cause': 'enclosure'})

    # Spike protest energy on tile
    protest_bump = round(plot.fraction * 5.0, 2)
    current_energy = getattr(tile, 'protest_energy_log', [])
    if current_energy:
        current_energy[-1] = min(10.0, current_energy[-1] + protest_bump)

    events.append({
        't': t,
        'event': 'ENCLOSURE_DISPOSSESSION',
        'tile': tile.name,
        'plot_id': plot.plot_id,
        'dispossessed_count': dispossessed_count,
        'message': (f"Enclosure of plot {plot.plot_id} on {tile.name}: "
                    f"{dispossessed_count} serfs dispossessed of customary rights.")
    })
    return events


def execute_enclosure(tile, plot_id: str, t: int, rent_rate: float = DEFAULT_CASH_RENT) -> tuple[bool, str, list[dict]]:
    """Execute legal enclosure of a FEUDAL plot on *tile*.

    Conserved transfer:
      lord.cash -= fee
      gov.agent.cash += fee

    State transition:
      plot.tenure: FEUDAL -> ENCLOSED
    """
    tenure = getattr(tile, 'tenure', None)
    if tenure is None:
        return False, f"Tile '{tile.name}' has no land tenure system.", []

    plot = tenure.find_plot(plot_id)
    if plot is None:
        return False, f"Plot '{plot_id}' not found on tile '{tile.name}'.", []

    if plot.tenure != TenureStatus.FEUDAL:
        return False, f"Plot '{plot_id}' is already {plot.tenure.value}.", []

    # Find the lord owning this plot
    lord = None
    for a in tile.agents:
        if a.id == plot.lord_id:
            lord = a
            break

    if lord is None or not lord.alive:
        return False, f"Lord for plot '{plot_id}' is deceased or absent.", []

    fee = calculate_charter_fee(plot)
    if lord.cash < fee:
        return False, f"Lord cash (${lord.cash:.1f}) insufficient for charter fee (${fee:.1f}).", []

    gov = tile.gov
    if gov is None or gov.agent is None:
        return False, f"No government authority seated to issue enclosure charter on '{tile.name}'.", []

    # Coercive force check for enclosure:
    # Commoners will not let their customary commons be fenced off passively
    # if protest energy is elevated, unless backed by armed bailiffs, constables, or garrison troops.
    pe = tile.protest_energy_log[-1] if (hasattr(tile, 'protest_energy_log') and tile.protest_energy_log) else 0.0
    has_garrison = any(getattr(u, 'strength', 0) > 5.0 for u in getattr(tile, 'military_units', []))
    police_count = getattr(tile, 'police_employed', 0)

    # Check if lord hires armed bailiffs ($10.0 conserved transfer) when commoners are militant
    bailiff_hired = False
    force_decision_event_id = None
    if pe >= 3.0 and not has_garrison and police_count == 0:
        bailiff_cost = 10.0
        bailiff_recipients = [
            a for a in tile.agents
            if getattr(a, 'alive', True)
            and not getattr(a, 'is_government', False)
            and a.id != lord.id]
        bailiff_payee = (bailiff_recipients[0] if bailiff_recipients
                         else gov.agent)
        can_fund_bailiff = lord.cash >= fee + bailiff_cost
        from run_trace import emit as emit_trace
        force_decision_event_id = emit_trace(
            tile, kind='enclosure_bailiff_force_decision',
            record_class='decision', phase='policy_action',
            subject={'type': 'tile/plot', 'id': str(plot.plot_id),
                     'tile': tile.name},
            metric_id='land.enclosure_force_decision', unit='boolean',
            before=False, after=bool(can_fund_bailiff),
            formula_id='enclosure.bailiff_cash_gate.v1',
            inputs={
                'reason_code': ('bailiff_affordable' if can_fund_bailiff
                                else 'insufficient_cash_for_bailiff'),
                'plot_id': str(plot.plot_id), 'lord_id': str(lord.id),
                'protest_energy': float(pe), 'protest_threshold': 3.0,
                'garrison_present': bool(has_garrison),
                'police_count': int(police_count),
                'lord_cash_before': float(lord.cash),
                'charter_fee': float(fee), 'bailiff_cost': bailiff_cost,
                'required_cash': float(fee + bailiff_cost),
                'selected_recipient_id': str(bailiff_payee.id),
                'recipient_is_government': bool(
                    getattr(bailiff_payee, 'is_government', False)),
            })
        if can_fund_bailiff:
            lord_cash_before = float(lord.cash)
            recipient_cash_before = float(bailiff_payee.cash)
            _trace_cash_write = _trace_public_begin(None, lord)
            lord.cash -= 10.0
            _trace_public_finish(_trace_cash_write, 'enclosure:execute_enclosure',
                                 inputs={"source_writer": 'enclosure.py:execute_enclosure:46ea9978612a0cce:1'})
            bailiff_hired = True
            _trace_cash_write = _trace_public_begin(None, bailiff_payee)
            bailiff_payee.cash += bailiff_cost
            _trace_public_finish(_trace_cash_write, 'enclosure:execute_enclosure',
                                 inputs={"source_writer": 'enclosure.py:execute_enclosure:ab13702d27b8bfd3:1'})
            bailiff_event_id = _record_enclosure_cash_transfer(
                tile, kind='bailiff_service',
                operation_type='enclosure_bailiff_service', payer=lord,
                payee=bailiff_payee, amount=bailiff_cost,
                payer_before=lord_cash_before,
                payee_before=recipient_cash_before, turn=t,
                plot_id=plot.plot_id,
                detail={'reason': 'enclosure enforcement'},
                cause_event_ids=([force_decision_event_id]
                                 if force_decision_event_id else None))
        else:
            bailiff_event_id = None
    else:
        bailiff_event_id = None

    if pe >= 3.0 and not has_garrison and police_count == 0 and not bailiff_hired:
        # Enclosure defied by commoners!
        from run_trace import emit as emit_trace
        emit_trace(
            tile, kind='enclosure_attempt_outcome', record_class='outcome',
            phase='policy_action',
            subject={'type': 'tile/plot', 'id': str(plot.plot_id),
                     'tile': tile.name},
            metric_id='land.enclosure_transition', unit='tenure_status',
            before=plot.tenure.value, after=plot.tenure.value,
            inputs={'success': False,
                    'reason_code': 'commoner_resistance_without_funded_force',
                    'plot_id': str(plot.plot_id), 'lord_id': str(lord.id),
                    'protest_energy': float(pe), 'charter_fee': float(fee),
                    'lord_cash_after_gate': float(lord.cash),
                    'tenure_status_after': plot.tenure.value},
            cause_event_ids=([force_decision_event_id]
                             if force_decision_event_id else None))
        return False, (f"Enclosure of plot {plot_id} on {tile.name} DEFIED by commoners! "
                       f"Protest energy is {pe:.1f} and landlord lacks armed bailiffs or garrison to enforce fencing."), []

    # Conserved financial transfer: lord pays the crown
    lord_cash_before = float(lord.cash)
    government_cash_before = float(gov.agent.cash)
    lord.cash -= fee
    public_change = begin_public_change(tile, gov.agent, cash=True)
    gov.agent.cash += fee
    finish_public_change(public_change, 'enclosure_charter_receipt')
    charter_event_id = _record_enclosure_cash_transfer(
        tile, kind='enclosure_charter_fee',
        operation_type='enclosure_charter_fee', payer=lord,
        payee=gov.agent, amount=fee, payer_before=lord_cash_before,
        payee_before=government_cash_before, turn=t, plot_id=plot.plot_id,
        detail={'fraction': float(plot.fraction)},
        cause_event_ids=([force_decision_event_id]
                         if force_decision_event_id else None))

    # Enclose the plot
    tenure_before = plot.tenure.value
    commons_access_before = float(getattr(tenure, 'commons_access', 0.0))
    tenure.enclose_plot(plot_id, turn=t, rent_rate=rent_rate)

    # Survey claims name only actual holders of this plot.
    plot_tenants = [a for a in tile.agents if a.id in getattr(plot, 'tenant_ids', []) and a.alive]
    for tenant in plot_tenants:
        assess_obligation(tile, tenant.id, gov.agent.id, 'survey', STATUTORY_SURVEY_FEE,
                          t + 3, collateral_plot_id=plot_id)

    # Dispossess serfs and log events
    events = dispossess_commoners(tile, plot, t)
    msg = (f"Enclosure Charter granted on {tile.name}: Plot {plot_id} enclosed. "
           f"Charter fee ${fee:.1f} paid to crown. Commons access reduced to {tenure.commons_access:.1%}.")

    events.append({
        't': t,
        'event': 'ENCLOSURE_COMPLETED',
        'tile': tile.name,
        'plot_id': plot_id,
        'fee': fee,
        'message': msg
    })
    from run_trace import emit as emit_trace
    emit_trace(
        tile, kind='enclosure_charter_granted', record_class='outcome',
        phase='policy_action',
        subject={'type': 'tile/plot', 'id': str(plot.plot_id),
                 'tile': tile.name},
        metric_id='land.enclosure_transition', unit='tenure_status',
        before=tenure_before, after=plot.tenure.value,
        inputs={'success': True, 'reason_code': 'charter_granted',
                'plot_id': str(plot.plot_id), 'lord_id': str(lord.id),
                'charter_fee': float(fee),
                'rent_rate': float(rent_rate),
                'plot_fraction': float(plot.fraction),
                'commons_access_before': commons_access_before,
                'commons_access_after': float(
                    getattr(tenure, 'commons_access', 0.0)),
                'survey_claim_tenant_ids': [str(a.id) for a in plot_tenants],
                'bailiff_hired': bool(bailiff_hired)},
        cause_event_ids=[event_id for event_id in
                         (force_decision_event_id, bailiff_event_id,
                          charter_event_id) if event_id])
    return True, msg, events


def step_enclosure_survey_debts(tile, t: int) -> list[dict]:
    """Process statutory surveying and hedging fee debts for enclosed plots.

    Tenants have 3 turns to pay the statutory fee ($15.0).
    - If tenant has cash >= fee: fee paid to municipal government (conserved transfer).
    - If t < deadline: tenant suffers debt anxiety (mem_promises).
    - If t >= deadline and unpaid: customary claim is legally foreclosed!
      An auction is held on the tile: the wealthiest bidder pays the auction price
      to the municipal treasury, and the defaulting tenant is evicted into
      SocialClass.DISPOSSESSED with mem_debt_trap and mem_eviction.
    """
    # Legacy saves may contain the old list. Migrate once into named claims;
    # deadlines are not foreclosures until the case system is active.
    if not hasattr(tile, 'enclosure_survey_debts') or not tile.enclosure_survey_debts:
        return []
    for debt in tile.enclosure_survey_debts:
        assess_obligation(tile, debt.get('tenant_id'), tile.gov.agent.id, 'survey',
                          debt.get('fee', STATUTORY_SURVEY_FEE), debt.get('deadline', t),
                          collateral_plot_id=debt.get('plot_id'))
    tile.enclosure_survey_debts = []
    return []

    events = []
    gov = getattr(tile, 'gov', None)
    gov_agent = gov.agent if gov else None
    remaining_debts = []

    for debt in tile.enclosure_survey_debts:
        tenant_id = debt.get('tenant_id')
        fee = debt.get('fee', 0.0)
        deadline = debt.get('deadline', t)
        plot_id = debt.get('plot_id')

        tenant = None
        if tenant_id is not None:
            for a in tile.agents:
                if a.id == tenant_id:
                    tenant = a
                    break

        if tenant is None or not tenant.alive:
            continue

        if tenant.cash >= fee:
            # Solvent tenant pays survey fee (conserved transfer)
            _trace_cash_write = _trace_public_begin(None, tenant)
            tenant.cash -= fee
            _trace_public_finish(_trace_cash_write, 'enclosure:step_enclosure_survey_debts',
                                 inputs={"source_writer": 'enclosure.py:step_enclosure_survey_debts:9810ca10c4fe93ed:1'})
            if gov_agent:
                _trace_cash_write = _trace_public_begin(None, gov_agent)
                gov_agent.cash += fee
                _trace_public_finish(_trace_cash_write, 'enclosure:step_enclosure_survey_debts',
                                     inputs={"source_writer": 'enclosure.py:step_enclosure_survey_debts:38b677e68706d365:1'})
            events.append({
                't': t,
                'event': 'SURVEY_FEE_PAID',
                'tile': tile.name,
                'tenant_id': tenant_id,
                'plot_id': plot_id,
                'fee': fee,
                'message': f"Tenant {tenant_id} paid statutory surveying fee ${fee:.1f} on {tile.name}."
            })
        elif t < deadline:
            # Under legal debt pressure
            tenant.mem_push('mem_promises', 0.5)
            remaining_debts.append(debt)
        else:
            # Check coercive enforcement for physical eviction:
            pe = tile.protest_energy_log[-1] if (hasattr(tile, 'protest_energy_log') and tile.protest_energy_log) else 0.0
            has_force = any(getattr(u, 'strength', 0) > 5.0 for u in getattr(tile, 'military_units', [])) or getattr(tile, 'police_employed', 0) > 0
            if pe >= 3.5 and not has_force:
                # Tenants and community actively resist eviction without police/military
                tenant.mem_push('mem_promises', 1.0)
                tenant.mem_push('mem_debt_trap', 0.5)
                if hasattr(tile, 'protest_energy_log') and tile.protest_energy_log:
                    tile.protest_energy_log[-1] = min(10.0, tile.protest_energy_log[-1] + 0.5)
                remaining_debts.append(debt)
                events.append({
                    't': t,
                    'event': 'EVICTION_RESISTED',
                    'tile': tile.name,
                    'tenant_id': tenant_id,
                    'plot_id': plot_id,
                    'message': (f"EVICTION RESISTED: Tenant {tenant_id} and community resisted eviction on {tile.name}; "
                                f"authority lacks bailiffs/police to enforce foreclosure (protest: {pe:.1f}).")
                })
                continue

            # Insolvent at deadline -> Foreclosure & Auction enforced by state/bailiffs
            plot = tile.tenure.find_plot(plot_id) if hasattr(tile, 'tenure') else None

            # Find wealthy bidders on tile
            bidders = [a for a in tile.agents if a.id != tenant_id and a.alive and a.cash >= 10.0 and not a.is_government]
            bidders.sort(key=lambda a: a.cash, reverse=True)

            clearing_bid = 0.0
            winner_id = None
            if bidders and gov_agent:
                winner = bidders[0]
                winner_id = winner.id
                clearing_bid = min(winner.cash, 25.0)
                _trace_cash_write = _trace_public_begin(None, winner)
                winner.cash -= clearing_bid
                _trace_public_finish(_trace_cash_write, 'enclosure:step_enclosure_survey_debts',
                                     inputs={"source_writer": 'enclosure.py:step_enclosure_survey_debts:cb6c7559cb197019:1'})
                _trace_cash_write = _trace_public_begin(None, gov_agent)
                gov_agent.cash += clearing_bid
                _trace_public_finish(_trace_cash_write, 'enclosure:step_enclosure_survey_debts',
                                     inputs={"source_writer": 'enclosure.py:step_enclosure_survey_debts:ebed4b3c13e090d8:1'})

            # Evict the tenant from customary holding
            if plot and hasattr(plot, 'tenant_ids') and tenant.id in plot.tenant_ids:
                plot.tenant_ids.remove(tenant.id)
            tenant.assigned_plot_id = None
            tenant.social_class = 'dispossessed'
            tenant.mem_push('mem_debt_trap', 1.0)
            tenant.mem_push('mem_eviction', 1.0)

            # Raise tile protest energy
            if hasattr(tile, 'protest_energy_log') and tile.protest_energy_log:
                tile.protest_energy_log[-1] = min(10.0, tile.protest_energy_log[-1] + 1.0)

            msg = (f"Legal Foreclosure on {tile.name}: Tenant {tenant_id} unable to pay "
                   f"statutory surveying fee (${fee:.1f}). Holding auctioned"
                   f"{f' to agent {winner_id} for ${clearing_bid:.1f}' if winner_id else ' off'}."
                   f" Tenant dispossessed.")
            events.append({
                't': t,
                'event': 'SURVEY_DEBT_FORECLOSURE',
                'tile': tile.name,
                'tenant_id': tenant_id,
                'plot_id': plot_id,
                'winner_id': winner_id,
                'clearing_bid': clearing_bid,
                'message': msg
            })

    tile.enclosure_survey_debts = remaining_debts
    return events
