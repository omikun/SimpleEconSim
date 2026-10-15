"""Bounded owner choices and targeted commons policy for the rivalry scenario."""

from __future__ import annotations

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


def _restore_officer(border, record):
    officer_id = record.get('officer_id')
    if officer_id is None:
        return
    officer = next((a for a in border.agents if a.id == officer_id), None)
    if officer is not None:
        officer.output = Goods[record['officer_prior_output']]
        officer.social_class = record['officer_prior_class']
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


def _choose_officer(border, record):
    if record.get('officer_id') is not None:
        return next((a for a in border.agents if a.id == record['officer_id'] and a.alive), None)
    officer = next((a for a in sorted(border.agents, key=lambda a: a.id)
                    if a.alive and not a.is_trader and not a.is_corporation
                    and not a.is_government and not getattr(a, 'is_lord', False)
                    and a.employer is None), None)
    if officer is None:
        return None
    record['officer_id'] = officer.id
    record['officer_prior_output'] = officer.output.name
    record['officer_prior_class'] = officer.social_class
    officer.output = Goods.gov
    officer.social_class = 'constable'
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
    officer = _choose_officer(border, record) if border.gov.agent.cash >= PATROL_COST else None
    if officer is None:
        _restore_rights(border, record, legal=False)
        _restore_officer(border, record)
        record['status'] = 'suspended'
        return
    border.gov.agent.cash -= PATROL_COST
    officer.cash += PATROL_COST
    for row in record['rights_snapshot']:
        right = _find_right(border, row['person_id'], row['plot_id'])
        if right is not None and right.legal_share == 0:
            right.usable_share = 0.0
    if record['status'] != 'active':
        _event(world, turn, 'ENFORCEMENT',
               f'{nation_name} pays a constable; named commons food access closes.',
               affected=len(record['rights_snapshot']))
    record['status'] = 'active'
    record['last_patrol_paid_turn'] = turn


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
    firm.owner.cash -= 20
    gov.cash -= 10
    firm.cash += 30
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
        owner.cash -= 20
        mill.cash += 20
        mill.wage = round(mill.wage + 0.25, 3)
        decision = 'better_wage'
        reason = 'Vacancies justify a funded wage offer.'
    elif mill.cash < len(mill.employees) * mill.wage and owner is not None and owner.cash >= 20:
        owner.cash -= 20
        mill.cash += 20
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
