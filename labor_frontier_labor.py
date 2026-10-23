"""Bounded owner choices and targeted commons policy for the rivalry scenario."""

from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change

from goods import Goods
from labor_laws import submit_law_petition
from labor_frontier_market import start_machinery_project


PATROL_COST = 3.0
PETITION_FEE = 5.0
RELIEF_UNITS = 6


def _districts(world, nation_name):
    owned = [r for r in world['tiles'] if r.owner_nation.name == nation_name]
    capital = next((r for r in owned if r.scenario_location == 'capital'), None)
    border = next((r for r in owned if r.scenario_location == 'borderland'), None)
    return capital, border


def _firm(region, good):
    if region is None:
        return None
    return next((a for a in region.agents if a.alive and a.is_corporation
                 and a.output == good and ('Textile Mill' if good == Goods.cloth else 'Cotton Estate')
                 in str(a.company_name)), None)


def initialize_labor(world):
    state = world['scenario_state']
    state['restrictions'] = {}
    state['owner_goals'] = {nation.name: 'retain buyers' for nation in world['nations']}
    state['owner_decisions'] = []
    state['timeline'] = []
    state['major_action_turn'] = -1


def _event(world, turn, kind, text, **data):
    row = {'turn': turn, 'kind': kind, 'text': text, **data}
    from collective_trace_clock import stamp
    stamp(world['tiles'][0], row)
    state = world['scenario_state']
    state['timeline'].append(row)
    return row


def _right_rows(border):
    rows = []
    for person_id, rights in border.access_rights.items():
        for right in rights:
            if right.resource == 'commons_food' and right.usable_share > 0:
                rows.append((person_id, right))
    return rows


def _find_right(border, person_id, plot_id):
    return next((right for right in border.access_rights.get(person_id, [])
                 if right.plot_id == plot_id and right.resource == 'commons_food'), None)


def _snapshot_usable_access(border, record):
    total = 0.0
    for row in record.get('rights_snapshot', []):
        right = _find_right(border, row['person_id'], row['plot_id'])
        if right is not None:
            total += float(right.usable_share)
    return total


def _submit_petition(world, nation_name, turn):
    _, border = _districts(world, nation_name)
    estate = _firm(border, Goods.cotton)
    if estate is None or estate.cash < PETITION_FEE or not _right_rows(border):
        return False
    old = world['scenario_state']['restrictions'].get(nation_name)
    if old and old['status'] in ('proposed', 'approved', 'active', 'suspended'):
        return False
    if old and turn < old.get('retry_after', 0):
        return False
    petition = submit_law_petition(estate, border, 'gathering_restriction', PETITION_FEE, turn)
    if petition is None:
        return False
    # The normal regional auto-decision must not preempt the scenario player's
    # response window; this petition is decided only by the shared action layer.
    petition['decision_turn'] = 10**9
    petition['deadline_turn'] = turn + 2
    target_plot_id = sorted({right.plot_id for _, right in _right_rows(border)})[0]
    record = {'nation': nation_name, 'region': border.name,
              'plot_id': target_plot_id, 'petition_id': petition['id'],
              'sponsor_id': estate.id, 'requested_turn': turn,
              'deadline_turn': turn + 2, 'status': 'proposed',
              'fee': PETITION_FEE, 'rights_snapshot': [], 'officer_id': None}
    world['scenario_state']['restrictions'][nation_name] = record
    _event(world, turn, 'PETITION',
           f'{nation_name} cotton estate pays {PETITION_FEE:g} to seek closure of '
           f'{border.name} commons.', region=border.name)
    return True


def _set_petition_status(border, record, status):
    for petition in getattr(border, 'labor_law_petitions', []):
        if petition['id'] == record['petition_id']:
            petition['status'] = status
            break


def _approve(world, nation_name, turn):
    record = world['scenario_state']['restrictions'].get(nation_name)
    if record is None or record['status'] != 'proposed' or turn > record['deadline_turn']:
        return False, 'No petition within its response window.'
    border = world['by_name'][record['region']]
    rights = [(person_id, right) for person_id, right in _right_rows(border)
              if right.plot_id == record['plot_id']]
    if not rights:
        return False, 'The named commons rights are no longer usable.'
    record['rights_snapshot'] = [
        {'person_id': person_id, 'plot_id': right.plot_id,
         'legal': right.legal_share, 'usable': right.usable_share}
        for person_id, right in rights]
    for _, right in rights:
        right.legal_share = 0.0
    record['status'] = 'approved'
    record['effective_turn'] = turn + 1
    _set_petition_status(border, record, 'approved')
    _event(world, turn, 'LAW', f'{nation_name} approves closure of named commons rights; '
           'paid enforcement can begin next turn.', affected=len(rights))
    return True, f'Approved for {len(rights)} rights; patrol costs {PATROL_COST:g} cash per turn.'


def _restore_officer(border, record, *, cause_event_ids=None):
    officer_id = record.get('officer_id')
    if officer_id is None:
        return
    officer = next((a for a in border.agents if a.id == officer_id), None)
    if officer is not None:
        officer.output = Goods[record['officer_prior_output']]
        officer.social_class = record['officer_prior_class']
        from labor_choice import record_labor_status
        record_labor_status(border, officer, int(getattr(border, '_last_turn', 0) or 0),
                            before='constable', after='independent',
                            reason='enforcement_appointment_ended',
                            cause_event_ids=cause_event_ids)
    border.police_employed = 0
    record['officer_id'] = None


def _restore_rights(border, record, *, legal):
    for row in record.get('rights_snapshot', []):
        right = _find_right(border, row['person_id'], row['plot_id'])
        if right is None:
            continue
        if legal and right.legal_share == 0:
            right.legal_share = row['legal']
        if right.usable_share == 0:
            right.usable_share = row['usable']


def _protect(world, nation_name, turn):
    record = world['scenario_state']['restrictions'].get(nation_name)
    if record is None or record['status'] not in ('proposed', 'approved', 'active', 'suspended'):
        return False, 'No pending or active targeted restriction.'
    border = world['by_name'][record['region']]
    prior = record['status']
    if prior != 'proposed':
        _restore_rights(border, record, legal=True)
        _restore_officer(border, record)
    record['status'] = 'rejected' if prior == 'proposed' else 'repealed'
    record['retry_after'] = turn + 4
    _set_petition_status(border, record, record['status'])
    _event(world, turn, 'ACCESS', f'{nation_name} protects the named commons rights.',
           region=border.name)
    return True, 'Commons access protected; the sponsor may seek another review later.'


def _officer_candidate(border, record):
    if record.get('officer_id') is not None:
        officer = next((a for a in border.agents
                        if a.id == record['officer_id'] and a.alive), None)
        return officer, ('assigned_officer_available' if officer is not None
                         else 'assigned_officer_unavailable')
    officer = next((a for a in sorted(border.agents, key=lambda a: a.id)
                    if a.alive and not a.is_trader and not a.is_corporation
                    and not a.is_government and not getattr(a, 'is_lord', False)
                    and a.employer is None), None)
    return officer, ('new_constable_available' if officer is not None
                     else 'no_eligible_constable')


def _choose_officer(border, record, *, cause_event_ids=None):
    officer, _reason = _officer_candidate(border, record)
    if officer is None:
        return None
    if record.get('officer_id') is not None:
        return officer
    record['officer_id'] = officer.id
    record['officer_prior_output'] = officer.output.name
    record['officer_prior_class'] = officer.social_class
    officer.output = Goods.gov
    officer.social_class = 'constable'
    from labor_choice import record_labor_status
    record_labor_status(border, officer, int(getattr(border, '_last_turn', 0) or 0),
                        before='independent', after='constable',
                        reason='paid_enforcement_appointment',
                        cause_event_ids=cause_event_ids)
    border.police_employed = 1
    return officer


def _advance_restriction(world, nation_name, turn):
    record = world['scenario_state']['restrictions'].get(nation_name)
    if record is None:
        return
    border = world['by_name'][record['region']]
    if record['status'] == 'proposed' and turn > record['deadline_turn']:
        record['status'] = 'expired'
        record['retry_after'] = turn + 4
        _set_petition_status(border, record, 'expired')
        _event(world, turn, 'PETITION', f'{nation_name} petition expires without approval.')
        return
    if record['status'] not in ('approved', 'active', 'suspended'):
        return
    if turn < record.get('effective_turn', turn):
        return
    status_before = record['status']
    treasury = border.gov.agent
    treasury_cash_before = float(treasury.cash)
    bank = border.bank
    bank_deposit_before = float(bank.deposits.get(treasury, 0.0))
    bank_total_before = float(bank.total_deposits)
    withdrawal_event_ids = []
    withdrawal_requested = max(0.0, PATROL_COST - treasury_cash_before)
    withdrawal_settled = 0.0
    # Local tax receipts are routinely deposited during the economy tick.
    # A patrol should not lapse while its public account can pay for it.
    if treasury.cash < PATROL_COST:
        withdrawal_settled = float(bank.Withdraw(
            treasury, withdrawal_requested, trace_region=border, t=turn,
            reason='commons_patrol_payroll',
            trace_event_ids=withdrawal_event_ids))
    treasury_cash_after_funding = float(treasury.cash)
    bank_deposit_after = float(bank.deposits.get(treasury, 0.0))
    bank_total_after = float(bank.total_deposits)
    candidate, candidate_reason = _officer_candidate(border, record)
    enough_treasury_cash = treasury_cash_after_funding >= PATROL_COST
    if not enough_treasury_cash:
        gate_reason = 'treasury_cash_below_patrol_cost'
    elif candidate is None:
        gate_reason = candidate_reason
    else:
        gate_reason = 'funded_constable_available'
    from run_trace import emit
    gate_event_id = emit(
        border, kind='commons_patrol_funding_decision',
        record_class='decision', phase='scenario_labor',
        subject={'type': 'tile', 'id': border.name,
                 'nation': nation_name},
        metric_id='labor.enforcement_patrol', unit='status',
        before=status_before, after=gate_reason,
        formula_id='labor.commons_patrol_gate.v1',
        inputs={'turn': int(turn), 'nation': nation_name,
                'tile': border.name, 'reason': gate_reason,
                'patrol_cost': float(PATROL_COST),
                'treasury_cash_before': treasury_cash_before,
                'treasury_cash_after_funding': treasury_cash_after_funding,
                'bank_withdrawal_requested': withdrawal_requested,
                'bank_withdrawal_settled': withdrawal_settled,
                'bank_deposit_before': bank_deposit_before,
                'bank_deposit_after': bank_deposit_after,
                'bank_total_deposits_before': bank_total_before,
                'bank_total_deposits_after': bank_total_after,
                'candidate_officer_id': getattr(candidate, 'id', None),
                'candidate_reason': candidate_reason},
        cause_event_ids=withdrawal_event_ids or None)
    officer = (_choose_officer(
        border, record,
        cause_event_ids=([gate_event_id] if gate_event_id else None))
        if enough_treasury_cash else None)
    if officer is None:
        usable_before = _snapshot_usable_access(border, record)
        _restore_rights(border, record, legal=False)
        _restore_officer(
            border, record,
            cause_event_ids=([gate_event_id] if gate_event_id else None))
        record['status'] = 'suspended'
        usable_after = _snapshot_usable_access(border, record)
        emit(
            border, kind='commons_patrol_outcome', record_class='outcome',
            phase='scenario_labor',
            subject={'type': 'tile', 'id': border.name,
                     'nation': nation_name},
            metric_id='labor.enforcement_patrol', unit='status',
            before=status_before, after=record['status'],
            formula_id='labor.commons_patrol_outcome.v1',
            inputs={'turn': int(turn), 'nation': nation_name,
                    'reason': gate_reason if enough_treasury_cash
                    else 'treasury_cash_below_patrol_cost',
                    'patrol_paid': False,
                    'patrol_cost': float(PATROL_COST),
                    'treasury_cash_before': treasury_cash_before,
                    'treasury_cash_after_funding': treasury_cash_after_funding,
                    'bank_withdrawal_requested': withdrawal_requested,
                    'bank_withdrawal_settled': withdrawal_settled,
                    'officer_candidate_id': getattr(candidate, 'id', None),
                    'rights_snapshot_count': len(record['rights_snapshot']),
                    'usable_access_before': usable_before,
                    'usable_access_after': usable_after,
                    'restriction_status_after': record['status']},
            cause_event_ids=[event_id for event_id in
                             [gate_event_id, *withdrawal_event_ids]
                             if event_id] or None)
        return
    treasury_cash_before_payment = float(treasury.cash)
    officer_cash_before_payment = float(officer.cash)
    _public_write = begin_public_change(None, treasury)
    treasury.cash -= PATROL_COST
    finish_public_change(_public_write, 'labor_frontier_labor:_advance_restriction',
                         inputs={'source_writer': 'labor_frontier_labor.py:_advance_restriction:3968fa87c79fdeba:1', 'semantic_operation_id': locals().get('operation_id')})
    _public_write = begin_public_change(None, officer)
    officer.cash += PATROL_COST
    finish_public_change(_public_write, 'labor_frontier_labor:_advance_restriction',
                         inputs={'source_writer': 'labor_frontier_labor.py:_advance_restriction:1ebf13cd1b3e292c:1', 'semantic_operation_id': locals().get('operation_id')})
    operation_id = f'commons-patrol:{nation_name}:{border.name}:{turn}:{officer.id}'
    currency = getattr(border, 'home_currency', None) or border.owner_nation.currency
    from finance_trace import (account_ref, cash_transfer_contract,
                               emit_cash_transfer)
    transfer_contract = cash_transfer_contract(
        operation_id, 'commons_patrol_payroll', amount=PATROL_COST,
        currency=currency,
        payer_account=account_ref(
            'government', treasury.id, currency,
            balance_before=treasury_cash_before_payment,
            balance_after=float(treasury.cash), balance_scope='cash'),
        payee_account=account_ref(
            'agent', officer.id, currency,
            balance_before=officer_cash_before_payment,
            balance_after=float(officer.cash), balance_scope='cash'),
        mutation_reference={'turn': int(turn), 'tile': border.name,
                            'officer_id': int(officer.id)})
    payment_event_id = emit_cash_transfer(
        border, kind='commons_patrol_cash_payment', contract=transfer_contract,
        phase='scenario_labor',
        subject={'type': 'tile/operation', 'id': operation_id,
                 'tile': border.name, 'nation': nation_name},
        inputs={'turn': int(turn), 'officer_id': int(officer.id),
                'rights_affected': len(record['rights_snapshot'])},
        cause_event_ids=([gate_event_id] if gate_event_id else None))
    treasury_event_id = emit(
        border, kind='commons_patrol_payroll', record_class='transfer',
         phase='scenario_labor', subject={'type': 'nation', 'id': nation_name},
         metric_id='finance.treasury_flow', unit=border.owner_nation.currency,
         after=-PATROL_COST,
         inputs={'tile': border.name, 'officer_id': officer.id,
                 'rights_affected': len(record['rights_snapshot']),
                 'operation_id': operation_id,
                 'signed_cash_change': -PATROL_COST,
                 'transfer_event_id': payment_event_id,
                 'treasury_cash_before': treasury_cash_before_payment,
                 'treasury_cash_after': float(treasury.cash)},
         cause_event_ids=([gate_event_id] if gate_event_id else None))
    usable_before = _snapshot_usable_access(border, record)
    for row in record['rights_snapshot']:
        right = _find_right(border, row['person_id'], row['plot_id'])
        if right is not None and right.legal_share == 0:
            right.usable_share = 0.0
    usable_after = _snapshot_usable_access(border, record)
    if record['status'] != 'active':
        _event(world, turn, 'ENFORCEMENT',
               f'{nation_name} pays a constable; named commons food access closes.',
               affected=len(record['rights_snapshot']))
    record['status'] = 'active'
    record['last_patrol_paid_turn'] = turn
    emit(
        border, kind='commons_patrol_outcome', record_class='outcome',
        phase='scenario_labor',
        subject={'type': 'tile', 'id': border.name, 'nation': nation_name},
        metric_id='labor.enforcement_patrol', unit='status',
        before=status_before, after=record['status'],
        formula_id='labor.commons_patrol_outcome.v1',
        inputs={'turn': int(turn), 'nation': nation_name,
                'reason': 'patrol_funded_and_enforced',
                'patrol_paid': True, 'patrol_cost': float(PATROL_COST),
                'officer_id': int(officer.id),
                'treasury_cash_before': treasury_cash_before,
                'treasury_cash_after_funding': treasury_cash_after_funding,
                'treasury_cash_before_payment': treasury_cash_before_payment,
                'treasury_cash_after_payment': float(treasury.cash),
                'bank_withdrawal_requested': withdrawal_requested,
                'bank_withdrawal_settled': withdrawal_settled,
                'bank_deposit_before': bank_deposit_before,
                'bank_deposit_after': bank_deposit_after,
                'rights_snapshot_count': len(record['rights_snapshot']),
                'usable_access_before': usable_before,
                'usable_access_after': usable_after,
                'last_patrol_paid_turn': int(record['last_patrol_paid_turn'])},
        cause_event_ids=[event_id for event_id in
                         [gate_event_id, payment_event_id, treasury_event_id,
                          *withdrawal_event_ids]
                         if event_id] or None)


def _fair_terms(world, nation_name, turn):
    capital, _ = _districts(world, nation_name)
    firm = _firm(capital, Goods.cloth)
    if firm is None or firm.owner is None:
        return False, 'No textile mill can accept terms.'
    gov = capital.owner_nation.government.agent
    if firm.owner.cash < 20 or gov.cash < 10:
        return False, 'Owner needs 20 cash and treasury needs 10.'
    if not firm.employees:
        return False, 'No workers are available to agree to terms.'
    offer = max(2.55, firm.wage + 0.15)
    from labor_choice import evaluate_offer
    decisions = [evaluate_offer(worker, firm, capital, turn, wage=offer)
                 for worker in firm.employees if worker.alive]
    if not decisions or not all(d.accepted for d in decisions):
        return False, 'Workers did not accept the funded offer.'
    _public_write = begin_public_change(None, firm.owner)
    firm.owner.cash -= 20
    finish_public_change(_public_write, 'labor_frontier_labor:_fair_terms',
                         inputs={'source_writer': 'labor_frontier_labor.py:_fair_terms:a6c0a4ee7564c5df:1', 'semantic_operation_id': locals().get('operation_id')})
    _public_write = begin_public_change(None, gov)
    gov.cash -= 10
    finish_public_change(_public_write, 'labor_frontier_labor:_fair_terms',
                         inputs={'source_writer': 'labor_frontier_labor.py:_fair_terms:968f458c7c6b26e3:1', 'semantic_operation_id': locals().get('operation_id')})
    _public_write = begin_public_change(None, firm)
    firm.cash += 30
    finish_public_change(_public_write, 'labor_frontier_labor:_fair_terms',
                         inputs={'source_writer': 'labor_frontier_labor.py:_fair_terms:a5fc793e452f2532:1', 'semantic_operation_id': locals().get('operation_id')})
    from run_trace import emit
    emit(capital, kind='fair_terms_public_funding', record_class='transfer',
         phase='scenario_labor', subject={'type': 'nation', 'id': nation_name},
         metric_id='finance.treasury_flow', unit=capital.owner_nation.currency,
         after=-10.0,
         inputs={'tile': capital.name, 'firm_id': firm.id,
                 'owner_contribution': 20.0, 'new_wage': offer})
    firm.wage = offer
    from labor_contract import ensure_labor_agreement
    for worker in firm.employees:
        if worker.alive:
            worker.wage = offer
            ensure_labor_agreement(worker, firm, turn).pay_rate = offer
    _event(world, turn, 'AGREEMENT', f'{nation_name} owner and workers agree to '
           f'{offer:.2f} pay; owner funds 20, treasury 10.')
    return True, f'{len(decisions)} workers accept {offer:.2f} pay; 30 cash funds the mill.'


def _relief(world, nation_name, turn):
    _, border = _districts(world, nation_name)
    nation = next(n for n in world['nations'] if n.name == nation_name)
    if border is None or nation.government.food_inventory < RELIEF_UNITS:
        return False, 'Sovereign food reserve needs six units and a held borderland.'
    eligible = [a for a in border.agents if a.alive and not a.is_corporation
                and not a.is_trader and not a.is_government and not getattr(a, 'is_lord', False)]
    eligible.sort(key=lambda a: (a.inv_get(Goods.food, 0), a.cash, a.id))
    if len(eligible) < 3:
        return False, 'Fewer than three eligible residents.'
    nation.government.food_inventory -= RELIEF_UNITS
    for person in eligible[:3]:
        person.inv_add(Goods.food, 2)
    _event(world, turn, 'RELIEF', f'{nation_name} releases six stored food units '
           f'to three {border.name} residents.', person_ids=[a.id for a in eligible[:3]])
    return True, 'Three residents receive two food units each; reserve falls by six.'


def _support_strikers(world, nation_name, turn):
    from collective_action import transfer_public_food
    nation = next(n for n in world['nations'] if n.name == nation_name)
    candidates = []
    for region in nation.tiles:
        for firm_id, org in getattr(region, 'collective_organizations', {}).items():
            if org.active_strike_id:
                candidates.append((org.strikes[-1].started_turn, region.name, firm_id, region))
    if not candidates:
        return False, 'No active corporate strike in your territory.'
    if nation.government.food_inventory <= 0:
        return False, 'The public food reserve is empty.'
    _, _, firm_id, region = min(candidates)
    moved = transfer_public_food(region, nation, turn, firm_id, maximum=6)
    if not moved:
        return False, 'No current participant can receive food.'
    _event(world, turn, 'RELIEF', f'{nation_name} delivers {moved} public food to '
           f'workers striking at {region.name}.', firm_id=firm_id, food_units=moved)
    return True, f'{moved} stored food units reach named strikers; reserve falls by {moved}.'


def apply_action(world, action_id, nation_name=None):
    """One major player decision per turn, shared by desktop and server."""
    if world.get('scenario_id') != 'labor_frontier_rivalry':
        return False, 'This action belongs to the labor rivalry scenario.'
    state = world['scenario_state']
    turn = int(world['turn'])
    if state.get('ending'):
        return False, 'The scenario has ended.'
    nation_name = nation_name or world['player_nation_name']
    if nation_name != world['player_nation_name']:
        return False, 'Only the player nation can use this action.'
    if state.get('major_action_turn') == turn:
        return False, 'One major decision has already been made this turn.'
    handlers = {
        'approve_petition': lambda: _approve(world, nation_name, turn),
        'protect_access': lambda: _protect(world, nation_name, turn),
        'fair_terms': lambda: _fair_terms(world, nation_name, turn),
        'cofund_machinery': lambda: start_machinery_project(world, nation_name, turn),
        'release_relief': lambda: _relief(world, nation_name, turn),
        'support_strikers': lambda: _support_strikers(world, nation_name, turn),
    }
    from labor_frontier_rivalry import apply_border_action
    for border_action in ('recruit_border', 'declare_border_war', 'attack_border',
                          'propose_standstill', 'offer_peace'):
        handlers[border_action] = lambda selected=border_action: apply_border_action(
            world, selected, nation_name, turn)
    if action_id not in handlers:
        return False, f'Unknown scenario action: {action_id}'
    success, message = handlers[action_id]()
    if success:
        state['major_action_turn'] = turn
        state['actions_taken'].append({'turn': turn, 'id': action_id, 'nation': nation_name})
    return success, message


def _owner_decision(world, nation_name, turn):
    state = world['scenario_state']
    capital, border = _districts(world, nation_name)
    mill, estate = _firm(capital, Goods.cloth), _firm(border, Goods.cotton)
    if mill is None or estate is None:
        return
    own = state.get('market_summary', {}).get(nation_name, {}).get('units_sold', 0)
    rival = sum(row.get('units_sold', 0) for name, row in state.get('market_summary', {}).items()
                if name != nation_name)
    owner = mill.owner
    decision = 'wait'
    reason = 'Buyer demand and payroll are stable enough to observe.'
    if own < rival and len(estate.employees) < 2 and _submit_petition(world, nation_name, turn):
        decision = 'petition'
        reason = 'Lost cloth orders and unfilled cotton estate jobs.'
    elif (own < rival and owner is not None and owner.cash >= 600 and
          not any(p['nation'] == nation_name and p['status'] in ('active', 'complete')
                  for p in state['machinery_projects'])):
        ok, _ = start_machinery_project(world, nation_name, turn, public_contribution=0)
        if ok:
            decision = 'machinery'
            reason = 'Lost orders justify owner-funded productivity work.'
    elif len(mill.employees) < 4 and owner is not None and owner.cash >= 20:
        _public_write = begin_public_change(None, owner)
        owner.cash -= 20
        finish_public_change(_public_write, 'labor_frontier_labor:_owner_decision',
                             inputs={'source_writer': 'labor_frontier_labor.py:_owner_decision:cdfb14a5c6e72454:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, mill)
        mill.cash += 20
        finish_public_change(_public_write, 'labor_frontier_labor:_owner_decision',
                             inputs={'source_writer': 'labor_frontier_labor.py:_owner_decision:b565e03e9342356d:1', 'semantic_operation_id': locals().get('operation_id')})
        mill.wage = round(mill.wage + 0.25, 3)
        decision = 'better_wage'
        reason = 'Vacancies justify a funded wage offer.'
    elif mill.cash < len(mill.employees) * mill.wage and owner is not None and owner.cash >= 20:
        _public_write = begin_public_change(None, owner)
        owner.cash -= 20
        finish_public_change(_public_write, 'labor_frontier_labor:_owner_decision',
                             inputs={'source_writer': 'labor_frontier_labor.py:_owner_decision:426f7518c45ea994:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, mill)
        mill.cash += 20
        finish_public_change(_public_write, 'labor_frontier_labor:_owner_decision',
                             inputs={'source_writer': 'labor_frontier_labor.py:_owner_decision:d8700d22c5ab8955:1', 'semantic_operation_id': locals().get('operation_id')})
        decision = 'payroll_bridge'
        reason = 'Owner funds another payroll from private wealth.'
    elif own == 0 and mill.cash < len(mill.employees) * mill.wage:
        decision = 'contraction'
        reason = 'No settled orders or liquid payroll.'
    state['owner_decisions'] = (state['owner_decisions'] + [
        {'turn': turn, 'nation': nation_name, 'decision': decision,
         'reason': reason, 'goal': state['owner_goals'][nation_name]}])[-80:]
    if decision != 'wait':
        _event(world, turn, 'OWNER', f'{nation_name} owner chooses {decision}: {reason}')


def advance_labor_and_owner(world, turn):
    for nation in world['nations']:
        _advance_restriction(world, nation.name, turn)
        _owner_decision(world, nation.name, turn)
