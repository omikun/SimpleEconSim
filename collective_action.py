"""Persistent, inspectable collective bargaining for every corporation.

Records refer to existing people and firms by ID. Cash and food stay in their
owners' accounts; this module only transfers existing stocks. All public events
are appended to a region's ordered collective_log for later run inspection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from goods import Goods


def _clamp(value):
    return max(0.0, min(1.0, float(value)))


@dataclass
class CollectiveStrike:
    id: str
    firm_id: int
    started_turn: int
    eligible_ids: tuple[int, ...]
    participant_ids: tuple[int, ...]
    baseline_wage: float
    target_wage: float
    baseline_hours: float
    target_hours: float
    baseline_food_price: float
    status: str = 'active'
    ended_turn: int | None = None
    review_turn: int | None = None
    participation_sum: float = 0.0
    support_periods: int = 0
    hardship_periods: int = 0
    person_periods: int = 0
    paid_real_sum: float = 0.0
    payable_person_periods: int = 0
    delivered_hours_sum: float = 0.0
    delivered_hours_periods: int = 0
    resolution_applied: bool = False
    settlement_applied: bool = False
    offered_wage: float | None = None
    offered_hours: float | None = None
    victory: float | None = None


@dataclass
class CollectiveOrganization:
    firm_id: int
    firm_name: str = ''
    member_ids: set[int] = field(default_factory=set)
    organization: float = 0.25
    confidence: float = 0.25
    strikes: list[CollectiveStrike] = field(default_factory=list)
    active_strike_id: str | None = None
    next_vote_turn: int = 0


def _records(region):
    if not hasattr(region, 'collective_organizations'):
        region.collective_organizations = {}
    if not hasattr(region, 'collective_log'):
        region.collective_log = []
    if not hasattr(region, '_next_collective_event_id'):
        region._next_collective_event_id = 1
    return region.collective_organizations


def _event(region, t, kind, firm, *, strike_id=None, message='', **facts):
    _records(region)
    event_id = f'{region.name}:collective:{region._next_collective_event_id}'
    region._next_collective_event_id += 1
    firm_id = firm if isinstance(firm, int) else firm.id
    firm_name = ('Public authority' if firm_id == 0 else next((org.firm_name for org in region.collective_organizations.values()
                       if org.firm_id == firm_id), '') if isinstance(firm, int)
                 else str(getattr(firm, 'company_name', '') or firm.id))
    row = {'id': event_id, 'turn': int(t), 'kind': kind, 'region': region.name,
           'firm_id': int(firm_id), 'firm_name': firm_name or str(firm_id),
           'strike_id': strike_id, 'message': message, 'facts': facts}
    region.collective_log.append(row)
    return row


def _firm(region, firm_id):
    return next((agent for agent in region.agents if agent.id == firm_id
                 and agent.alive and agent.is_corporation), None)


def _people(region):
    return {person.id: person for person in region.agents if person.alive}


def _active(org):
    return next((strike for strike in org.strikes
                 if strike.id == org.active_strike_id and strike.status == 'active'), None)


def _pressure(worker, firm, region):
    food_price = max(0.01, float(region.recipes.get(Goods.food, {}).get('price', 1.0)))
    shift = float(getattr(worker, 'shift_hours', getattr(firm, 'shift_hours', 8.0)))
    statute = bool(getattr(region, 'statute_of_laborers', False))
    wage_cap = float(getattr(region, 'maximum_wage_cap', 1.20))
    law_pressure = (0.40 if food_price > wage_cap else 0.25) if statute else 0.0
    return (float(getattr(worker, 'class_consciousness', 0.0)) * .5
            + float(getattr(worker, 'alienation', 0.0)) * .4
            + (.3 if shift > 10.0 else 0.0) + law_pressure
            + (.15 if float(getattr(firm, 'wage', 0.0)) < food_price else 0.0))


def _can_endure(person, region):
    food_price = max(.01, float(region.recipes.get(Goods.food, {}).get('price', 1.0)))
    return (person.hungry_steps == 0 or person.inv_get(Goods.food, 0) >= 2
            or person.cash >= food_price * 2)


def _start(region, firm, org, employees, supporters, t):
    food_price = max(.01, float(region.recipes.get(Goods.food, {}).get('price', 1.0)))
    baseline_wage = max(0.0, float(firm.wage))
    baseline_hours = float(getattr(firm, 'shift_hours', 8.0))
    strike = CollectiveStrike(
        id=f'{region.name}:firm:{firm.id}:turn:{t}', firm_id=firm.id,
        started_turn=t, eligible_ids=tuple(p.id for p in employees),
        participant_ids=tuple(p.id for p in supporters),
        baseline_wage=baseline_wage,
        target_wage=max(baseline_wage * 1.20, food_price * 1.25),
        baseline_hours=baseline_hours, target_hours=min(10.0, baseline_hours),
        baseline_food_price=food_price)
    org.strikes.append(strike)
    org.active_strike_id = strike.id
    for person in supporters:
        person.is_striking = True
    firm.is_on_strike = True
    _event(region, t, 'strike_started', firm, strike_id=strike.id,
           message=f'{len(supporters)} workers at {getattr(firm, "company_name", firm.id)} withhold labor.',
           eligible_ids=list(strike.eligible_ids), participant_ids=list(strike.participant_ids),
           baseline_wage=baseline_wage, target_wage=strike.target_wage,
           baseline_hours=baseline_hours, target_hours=strike.target_hours,
           food_price=food_price)
    return strike


def _resolve_org(region, firm, org, strike, t, reason):
    if strike.resolution_applied:
        return
    strike.resolution_applied = True
    strike.ended_turn = t
    org.active_strike_id = None
    org.next_vote_turn = t + 5
    periods = max(1, t - strike.started_turn + 1)
    participation = _clamp(strike.participation_sum / periods)
    support = strike.support_periods / strike.person_periods if strike.person_periods else 0.0
    before = org.organization
    org.organization = _clamp(before + .20 * participation * support * (1 - before))
    if reason != 'agreement':
        org.confidence = _clamp(org.confidence * (1 - .20 - .10 * (1 - support)))
    _event(region, t, 'strike_ended', firm, strike_id=strike.id,
           message=f'Strike ended: {reason}. The organization retains its members.',
           reason=reason, participation=round(participation, 4),
           supported_period_share=round(support, 4),
           organization_before=round(before, 4),
           organization_after=round(org.organization, 4),
           confidence_after=round(org.confidence, 4))


def _offer(region, firm, org, strike, employees, t):
    """Firm offers terms when expected lost output exceeds affordable extra pay."""
    recipe = region.recipes.get(firm.output, {})
    price = max(0.0, float(recipe.get('price', 0.0)))
    expected_units = max(0.0, float(recipe.get('production', 0.0))) * len(strike.participant_ids)
    estimated_lost_revenue = price * expected_units
    proposed_wage = max(float(firm.wage), strike.target_wage)
    proposed_hours = strike.target_hours
    extra_payroll = max(0.0, proposed_wage - float(firm.wage)) * len(employees)
    required_cash = proposed_wage * len(employees) * 2
    affordable = firm.cash >= required_cash
    worthwhile = estimated_lost_revenue > extra_payroll * 2
    _event(region, t, 'owner_decision', firm, strike_id=strike.id,
           message=('Firm offers funded terms.' if affordable and worthwhile
                    else 'Firm waits; proposed terms are unaffordable or exceed forecast benefit.'),
           cash=round(firm.cash, 3), required_cash=round(required_cash, 3),
           proposed_wage=round(proposed_wage, 3), proposed_hours=round(proposed_hours, 3),
           estimated_lost_revenue=round(estimated_lost_revenue, 3),
           estimated_extra_payroll=round(extra_payroll, 3),
           forecast_is_not_booked_loss=True)
    if not affordable or not worthwhile:
        return False
    people = _people(region)
    participants = [people[pid] for pid in strike.participant_ids
                    if pid in people and people[pid].employer is firm]
    acceptors = [person for person in participants
                 if proposed_wage + 1e-9 >= strike.target_wage
                 and proposed_hours <= strike.target_hours + 1e-9]
    if len(acceptors) * 2 < max(1, len(participants)) or not participants:
        _event(region, t, 'offer_rejected', firm, strike_id=strike.id,
               message='Workers reject the offer.',
               participant_ids=[p.id for p in participants],
               acceptor_ids=[p.id for p in acceptors])
        return False
    firm.wage = proposed_wage
    firm.shift_hours = proposed_hours
    firm.pay_mode = 'cash'
    from labor_contract import ensure_labor_agreement
    for person in employees:
        person.shift_hours = proposed_hours
        agreement = ensure_labor_agreement(person, firm, t)
        agreement.pay_rate = proposed_wage
        agreement.hours = proposed_hours
        agreement.pay_mode = 'cash'
        person.is_striking = False
    firm.is_on_strike = False
    strike.status = 'review'
    strike.review_turn = t + 2
    strike.offered_wage = proposed_wage
    strike.offered_hours = proposed_hours
    _resolve_org(region, firm, org, strike, t, 'agreement')
    _event(region, t, 'agreement_signed', firm, strike_id=strike.id,
           message=f'Workers accept {proposed_wage:.2f} wage and {proposed_hours:.1f} hours; delivery is due for review.',
           acceptor_ids=[p.id for p in acceptors], review_turn=strike.review_turn,
           payer_id=firm.id, promised_wage=proposed_wage,
           promised_hours=proposed_hours)
    return True


def step_collectives(region, t):
    """Call after hiring and before production. Every corporation is eligible."""
    records = _records(region)
    if getattr(region, '_last_collective_step_turn', None) == t:
        return
    region._last_collective_step_turn = t
    people = _people(region)
    for firm_id, old_org in list(records.items()):
        if _firm(region, firm_id) is not None:
            continue
        previous = _active(old_org)
        if previous is None:
            continue
        for pid in previous.participant_ids:
            if pid in people:
                people[pid].is_striking = False
        previous.status = 'ended'
        _resolve_org(region, firm_id, old_org, previous, t, 'firm_closed')
    for firm in sorted((a for a in region.agents if a.alive and a.is_corporation),
                       key=lambda a: a.id):
        employees = sorted((e for e in firm.employees if e.alive and e.employer is firm),
                           key=lambda e: e.id)
        org = records.get(firm.id)
        active = _active(org) if org is not None else None
        if active is None:
            if len(employees) < 2:
                continue
            voted = [e for e in employees if _pressure(e, firm, region) > .55]
            check = {'eligible_ids': [e.id for e in employees],
                     'yes_ids': [e.id for e in voted],
                     'pressure_by_person': {e.id: round(_pressure(e, firm, region), 4)
                                            for e in employees},
                     'next_vote_turn': org.next_vote_turn if org is not None else t}
            if org is not None and t < org.next_vote_turn:
                _event(region, t, 'organization_check', firm,
                       message='Workers remain in the recorded vote cooldown.',
                       decision='cooldown', **check)
                continue
            if len(voted) * 2 < len(employees):
                _event(region, t, 'organization_check', firm,
                       message='Too few employees support collective action.',
                       decision='insufficient_votes', **check)
                continue
            _event(region, t, 'organization_check', firm,
                   message='A strike vote is authorized by employee support.',
                   decision='vote', **check)
            if org is None:
                org = CollectiveOrganization(firm_id=firm.id,
                                             firm_name=str(getattr(firm, 'company_name', '') or firm.id))
                records[firm.id] = org
            org.member_ids.update(e.id for e in voted)
            supporters = [e for e in voted if _can_endure(e, region)]
            _event(region, t, 'strike_vote', firm,
                   message=f'{len(voted)}/{len(employees)} employees vote to strike; {len(supporters)} can join.',
                   eligible_ids=[e.id for e in employees], yes_ids=[e.id for e in voted],
                   join_ids=[e.id for e in supporters], threshold=.5)
            if len(supporters) < 2:
                org.next_vote_turn = t + 2
                continue
            active = _start(region, firm, org, employees, supporters, t)
        else:
            people = _people(region)
            continuing = []
            for pid in active.participant_ids:
                person = people.get(pid)
                if person is None or person.employer is not firm:
                    continue
                if not person.is_striking:
                    _event(region, t, 'participant_left', firm, strike_id=active.id,
                           message=f'Worker {pid} no longer withholds labor.',
                           person_id=pid, reason='external_change')
                    continue
                if not _can_endure(person, region):
                    person.is_striking = False
                    _event(region, t, 'participant_left', firm, strike_id=active.id,
                           message=f'Worker {pid} returns under material pressure.',
                           person_id=pid, reason='needs_shortfall')
                    continue
                continuing.append(pid)
            active.participant_ids = tuple(continuing)
            firm.is_on_strike = bool(continuing)
            if not continuing:
                active.status = 'ended'
                _resolve_org(region, firm, org, active, t, 'participants_withdrew')
                continue
        active.participation_sum += len(active.participant_ids) / max(1, len(active.eligible_ids))
        _event(region, t, 'participation', firm, strike_id=active.id,
               message=f'{len(active.participant_ids)} employees withhold labor this turn.',
               participant_ids=list(active.participant_ids),
               eligible_count=len(active.eligible_ids),
               working_count=sum(e.id not in active.participant_ids for e in employees))
        _share_existing_support(region, firm, active, t)


def _share_existing_support(region, firm, strike, t):
    """Willing neighbors help strikers with their own surplus food or cash."""
    people = _people(region)
    food_price = max(.01, float(region.recipes.get(Goods.food, {}).get('price', 1.0)))
    donors = [person for person in sorted(people.values(), key=lambda p: p.id)
              if (not person.is_corporation and not person.is_government
                  and not person.is_trader and not getattr(person, 'is_lord', False)
                  and person.id not in strike.participant_ids
                  and getattr(person, 'class_consciousness', 0.0) >= .65)]
    for pid in strike.participant_ids:
        recipient = people.get(pid)
        if recipient is None or recipient.employer is not firm:
            continue
        if recipient.inv_get(Goods.food, 0) >= 4 or recipient.cash >= food_price * 4:
            continue
        for donor in donors:
            if donor.inv_get(Goods.food, 0) >= 5:
                transfer_support(region, t, donor.id, pid, food=1)
                break
            if donor.cash >= food_price * 5:
                transfer_support(region, t, donor.id, pid, cash=food_price)
                break


def record_production(region, t, before):
    """Log observed inventory changes just after production, before trade."""
    if getattr(region, '_last_collective_production_turn', None) == t:
        return
    region._last_collective_production_turn = t
    for org in _records(region).values():
        strike = _active(org)
        if strike is None:
            continue
        firm = _firm(region, org.firm_id)
        if firm is None:
            continue
        prior = before.get(firm.id, firm.inv_get(firm.output, 0))
        after = firm.inv_get(firm.output, 0)
        _event(region, t, 'production_observed', firm, strike_id=strike.id,
               message=f'Firm output inventory changes from {prior} to {after} during production.',
               output_good=firm.output.name, inventory_before=prior,
               inventory_after=after, observed_change=after - prior,
               causal_limit='Inventory change is observed; no lost-sale amount is inferred.')


def transfer_support(region, t, donor_id, recipient_id, *, cash=0.0, food=0):
    """Transfer existing cash/food to a participant and log both accounts."""
    people = _people(region)
    donor, recipient = people.get(donor_id), people.get(recipient_id)
    if donor is None or recipient is None or donor is recipient:
        return False
    firm = recipient.employer
    if firm is None or not firm.is_corporation:
        return False
    org = _records(region).get(firm.id)
    strike = _active(org) if org else None
    if strike is None or recipient.id not in strike.participant_ids:
        return False
    cash, food = float(cash), int(food)
    if cash < 0 or food < 0 or cash + food <= 0:
        return False
    if donor.cash + 1e-9 < cash or donor.inv_get(Goods.food, 0) < food:
        return False
    donor.cash -= cash
    recipient.cash += cash
    if food:
        donor.inv_add(Goods.food, -food)
        recipient.inv_add(Goods.food, food)
    _event(region, t, 'support_transfer', firm, strike_id=strike.id,
           message=f'Existing cash and food move from {donor_id} to striker {recipient_id}.',
           donor_id=donor_id, recipient_id=recipient_id,
           cash=round(cash, 4), food=food)
    return True


def transfer_public_food(region, nation, t, firm_id, maximum=6):
    """Move existing sovereign reserve food to named active strikers."""
    org = _records(region).get(firm_id)
    strike = _active(org) if org else None
    firm = _firm(region, firm_id)
    if strike is None or firm is None or region.owner_nation is not nation:
        return 0
    available = min(int(maximum), int(nation.government.food_inventory))
    if available <= 0:
        return 0
    people = _people(region)
    recipients = [people[pid] for pid in strike.participant_ids if pid in people]
    recipients.sort(key=lambda person: (person.inv_get(Goods.food, 0), person.cash, person.id))
    moved = 0
    received_ids = []
    for recipient in recipients:
        if moved >= available:
            break
        nation.government.food_inventory -= 1
        recipient.inv_add(Goods.food, 1)
        moved += 1
        received_ids.append(recipient.id)
    if moved:
        _event(region, t, 'public_support_transfer', firm, strike_id=strike.id,
               message=f'Public reserve delivers {moved} food to named strikers.',
               donor_nation=nation.name, recipient_ids=received_ids,
               food_units=moved, reserve_after=nation.government.food_inventory)
    return moved


def record_payroll_and_review(region, t, cash_before):
    """Call after actual payroll, before other cash movements."""
    if getattr(region, '_last_collective_payroll_turn', None) == t:
        return
    region._last_collective_payroll_turn = t
    people = _people(region)
    for org in _records(region).values():
        firm = _firm(region, org.firm_id)
        for strike in org.strikes:
            if strike.status != 'review' or strike.settlement_applied:
                continue
            if firm is None:
                strike.settlement_applied = True
                strike.status = 'closed'
                strike.victory = 0.0
                before = org.confidence
                org.confidence = _clamp(before * .8)
                _event(region, t, 'settlement_review', org.firm_id, strike_id=strike.id,
                       message='Firm closed before delivering the accepted terms.',
                       victory=0.0, confidence_before=round(before, 4),
                       confidence_after=round(org.confidence, 4),
                       reason='firm_closed')
                continue
            if t > (strike.ended_turn or t) and t <= (strike.review_turn or t):
                paid = {}
                shortfall = {}
                cash_after_payroll = round(firm.cash, 4)
                for pid in strike.eligible_ids:
                    person = people.get(pid)
                    if person is None or person.employer is not firm:
                        continue
                    amount = max(0.0, person.cash - cash_before.get(pid, person.cash))
                    food_price = max(.01, float(region.recipes.get(Goods.food, {}).get('price', 1.0)))
                    strike.paid_real_sum += amount / food_price
                    strike.payable_person_periods += 1
                    strike.delivered_hours_sum += float(getattr(person, 'shift_hours', 0.0))
                    strike.delivered_hours_periods += 1
                    paid[pid] = round(amount, 4)
                    promised = float(strike.offered_wage or strike.target_wage)
                    if amount + 1e-9 < promised:
                        shortfall[pid] = round(promised - amount, 4)
                _event(region, t, 'payroll_observed', firm, strike_id=strike.id,
                       message='Actual cash wages and hours recorded for settlement review.',
                       paid_cash_by_person=paid, food_price=round(region.food_price, 4),
                       firm_cash_after_payroll=cash_after_payroll,
                       pay_mode=getattr(firm, 'pay_mode', 'cash'))
                if shortfall:
                    _event(region, t, 'payroll_breach', firm, strike_id=strike.id,
                           message=f'Cash wages promised in the agreement fall short for {len(shortfall)} workers.',
                           cash_shortfall_by_person=shortfall,
                           promised_cash_per_person=round(float(strike.offered_wage or strike.target_wage), 4),
                           pay_mode=getattr(firm, 'pay_mode', 'cash'))
            if t >= (strike.review_turn or 10**9):
                base_real = strike.baseline_wage / max(.01, strike.baseline_food_price)
                target_real = strike.target_wage / max(.01, strike.baseline_food_price)
                actual_real = (strike.paid_real_sum / strike.payable_person_periods
                               if strike.payable_person_periods else 0.0)
                wage_gap = max(.01, target_real - base_real)
                wage_result = _clamp((actual_real - base_real) / wage_gap)
                if strike.target_hours < strike.baseline_hours and strike.delivered_hours_periods:
                    avg_hours = strike.delivered_hours_sum / strike.delivered_hours_periods
                    hours_result = _clamp((strike.baseline_hours - avg_hours)
                                          / (strike.baseline_hours - strike.target_hours))
                    victory = .7 * wage_result + .3 * hours_result
                else:
                    hours_result = None
                    victory = wage_result
                before = org.confidence
                hardship = (strike.hardship_periods / strike.person_periods
                            if strike.person_periods else 0.0)
                org.confidence = _clamp(before + .35 * victory * (1 - before)
                                        - .20 * (1 - victory) * before
                                        - .10 * hardship * before)
                strike.settlement_applied = True
                strike.status = 'closed'
                strike.victory = victory
                _event(region, t, 'settlement_review', firm, strike_id=strike.id,
                       message='Delivered terms assessed against the original demands.',
                       actual_real_wage=round(actual_real, 4),
                       target_real_wage=round(target_real, 4),
                       wage_fulfillment=round(wage_result, 4),
                       hours_fulfillment=None if hours_result is None else round(hours_result, 4),
                       victory=round(victory, 4), confidence_before=round(before, 4),
                       confidence_after=round(org.confidence, 4))


def record_essential_needs(region, t):
    """Call after normal food consumption, once per person and turn."""
    if getattr(region, '_last_collective_needs_turn', None) == t:
        return
    region._last_collective_needs_turn = t
    people = _people(region)
    for org in _records(region).values():
        strike = _active(org)
        if strike is None:
            continue
        firm = _firm(region, org.firm_id)
        if firm is None:
            continue
        short = []
        supported = []
        for pid in strike.participant_ids:
            person = people.get(pid)
            strike.person_periods += 1
            if person is None or person.hungry_steps > 0:
                strike.hardship_periods += 1
                short.append(pid)
            else:
                strike.support_periods += 1
                supported.append(pid)
        _event(region, t, 'needs_observed', firm, strike_id=strike.id,
               message=f'{len(supported)} strikers meet essential food needs; {len(short)} fall short.',
               supported_ids=supported, shortfall_ids=short)
        if t > strike.started_turn:
            employees = sorted((e for e in firm.employees if e.alive and e.employer is firm),
                               key=lambda e: e.id)
            _offer(region, firm, org, strike, employees, t)


def recent_collective_events(region, limit=40, *, include_checks=False):
    limit = max(0, int(limit))
    if limit == 0:
        return []
    rows = getattr(region, 'collective_log', ())
    if not include_checks:
        rows = [row for row in rows if row['kind'] != 'organization_check']
    return list(rows[-limit:])


def organization_summary(region):
    records = getattr(region, 'collective_organizations', {})
    living = set(_people(region))
    rows = []
    for firm_id, org in sorted(records.items()):
        strike = org.strikes[-1] if org.strikes else None
        latest = ({'id': strike.id, 'status': strike.status,
                   'participants': len(strike.participant_ids),
                   'eligible': len(strike.eligible_ids),
                   'target_wage': round(strike.target_wage, 4),
                   'target_hours': round(strike.target_hours, 4),
                   'offered_wage': strike.offered_wage,
                   'offered_hours': strike.offered_hours,
                   'review_turn': strike.review_turn,
                   'victory': None if strike.victory is None else round(strike.victory, 4),
                   'needs_met_share': round(strike.support_periods / strike.person_periods, 4)
                   if strike.person_periods else None} if strike else None)
        rows.append({'firm_id': firm_id, 'firm_name': org.firm_name or str(firm_id),
                     'members': len(org.member_ids & living),
                     'organization': round(org.organization, 4),
                     'confidence': round(org.confidence, 4),
                     'active_strike_id': org.active_strike_id,
                     'latest_strike_status': strike.status if strike else None,
                     'latest_strike': latest})
    return rows
