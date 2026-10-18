"""
army.py — Military units, garrisons, recruitment, and battle resolution for Call of Capital (M4.5 / M5).

Provides:
- MilitaryUnit: represents a deployed army or garrison stationed on a tile.
- Strength formula: strength = soldiers * morale * equipment_quality.
- Recruitment from unemployed / poor agents, which drains protest energy.
- Conserved upkeep: wages paid from government treasury to soldiers (or regional economy),
  and food rations consumed from government food_inventory.
- Battle resolution: combat casualties, morale shifts, and tile contest resolution with 0 LEAK.
"""

from __future__ import annotations
import uuid
import math
from dataclasses import dataclass, field
from goods import Goods


@dataclass
class MilitaryUnit:
    """A military unit or garrison stationed on a Region tile."""
    unit_id: str
    nation_name: str
    region_name: str
    soldiers: int
    morale: float = 1.0             # 0.0 to 1.0 (drops on unpaid wages / heavy losses)
    equipment_quality: float = 1.0  # 0.5 to 2.0 (boosted by weapons / armor)
    wage_per_soldier: float = 1.0   # cash paid per soldier per turn
    food_per_soldier: float = 0.1   # food units consumed per soldier per turn
    veteran_xp: float = 0.0         # combat experience (0.0 to 1.0)
    is_garrison: bool = False       # True if stationary defensive garrison
    person_ids: list[int] = field(default_factory=list)
    prior_outputs: dict[int, str] = field(default_factory=dict)
    deserter_ids: list[int] = field(default_factory=list)
    casualty_ids: list[int] = field(default_factory=list)
    scenario_personnel: bool = False

    @property
    def strength(self) -> float:
        """Effective combat strength: soldiers * morale * equipment_quality * (1 + 0.5 * xp)."""
        if self.soldiers <= 0:
            return 0.0
        return self.soldiers * max(0.1, self.morale) * max(0.5, self.equipment_quality) * (1.0 + 0.5 * self.veteran_xp)

    def pay_and_feed(self, gov, bank, t: int = 0, people_by_id=None,
                     supply_access=True, trace_region=None,
                     funding_event_ids=None, upkeep_details=None) -> tuple[float, int, bool, int]:
        """Upkeep step: withdraws wages and consumes food rations.

        Returns (wages_paid, food_consumed, fully_supplied).
        Conserved: cash drawn from gov.agent.cash (or bank deposit), food from gov.food_inventory.
        """
        if self.soldiers <= 0:
            return 0.0, 0, True, 0

        if self.scenario_personnel:
            people_by_id = people_by_id or {}
            self.person_ids = [pid for pid in self.person_ids
                               if pid in people_by_id and people_by_id[pid].alive]
            self.soldiers = len(self.person_ids)
            if self.soldiers <= 0:
                if upkeep_details is not None:
                    cash = float(gov.agent.cash)
                    deposits = (float(getattr(bank, 'total_deposits', 0.0))
                                if bank is not None else 0.0)
                    food_inventory = int(getattr(gov, 'food_inventory', 0))
                    upkeep_details.update({
                        'unit_id': self.unit_id,
                        'scenario_personnel': True,
                        'soldiers_before': 0, 'soldiers_after': 0,
                        'requested_wages': 0.0, 'wages_paid': 0.0,
                        'unpaid_wages': 0.0,
                        'treasury_cash_before_funding': cash,
                        'treasury_cash_available_for_payroll': cash,
                        'treasury_cash_after_payroll': cash,
                        'bank_deposits_before': deposits,
                        'bank_deposits_after': deposits,
                        'food_inventory_before': food_inventory,
                        'food_inventory_after': food_inventory,
                        'food_needed': 0, 'food_consumed': 0, 'food_unmet': 0,
                        'supply_access': bool(supply_access),
                        'fully_supplied': True,
                        'morale_before': float(self.morale),
                        'morale_after': float(self.morale),
                        'wage_ratio': 1.0, 'food_ratio': 1.0,
                        'deserters': 0, 'deserter_agent_ids': [],
                        'recipient_cash_credits': [],
                    })
                return 0.0, 0, True, 0

        treasury_cash_before = float(gov.agent.cash)
        bank_deposits_before = (float(getattr(bank, 'total_deposits', 0.0))
                                if bank is not None else 0.0)
        food_inventory_before = int(getattr(gov, 'food_inventory', 0))
        morale_before = float(self.morale)
        soldiers_before = int(self.soldiers)
        total_wage = self.soldiers * self.wage_per_soldier
        wages_paid = 0.0

        # Procure wage cash
        if gov.agent.cash >= total_wage:
            cash_available_for_payroll = float(gov.agent.cash)
            gov.agent.cash -= total_wage
            wages_paid = total_wage
        else:
            # Try withdrawing from bank
            if bank is not None:
                needed = total_wage - gov.agent.cash
                bank.Withdraw(
                    gov.agent, min(needed, bank.deposits.get(gov.agent, 0.0)),
                    trace_region=trace_region, t=t, reason='military_payroll',
                    trace_event_ids=funding_event_ids)
            
            cash_available_for_payroll = float(gov.agent.cash)
            payout = min(gov.agent.cash, total_wage)
            gov.agent.cash -= payout
            wages_paid = payout
        cash_after_payroll = float(gov.agent.cash)

        # Food ration consumption
        needed_food = int(math.ceil(self.soldiers * self.food_per_soldier))
        available_food = getattr(gov, 'food_inventory', 0) if supply_access else 0
        food_consumed = min(needed_food, available_food)
        gov.food_inventory = max(0, getattr(gov, 'food_inventory', 0) - food_consumed)
        recipient_cash_credits = []
        if self.scenario_personnel and wages_paid > 0:
            share = wages_paid / self.soldiers
            for pid in self.person_ids:
                person = people_by_id[pid]
                cash_before = float(person.cash)
                person.cash += share
                recipient_cash_credits.append({
                    'agent_id': pid, 'amount': float(share),
                    'cash_before': cash_before,
                    'cash_after': float(person.cash)})

        # Morale updates based on fulfillment
        wage_ratio = wages_paid / max(0.01, total_wage)
        food_ratio = food_consumed / max(1, needed_food) if needed_food > 0 else 1.0

        if wage_ratio >= 0.99 and food_ratio >= 0.99:
            self.morale = min(1.0, self.morale + 0.05)
            fully_supplied = True
        else:
            # Deficit penalizes morale
            penalty = (1.0 - wage_ratio) * 0.2 + (1.0 - food_ratio) * 0.2
            self.morale = max(0.1, self.morale - penalty)
            fully_supplied = False

        # Desertion risk if morale drops below 0.3
        deserters = 0
        self.deserter_ids = []
        if self.morale < 0.3:
            deserters = (max(1, int(math.ceil(self.soldiers * 0.1)))
                         if self.scenario_personnel else int(self.soldiers * 0.1))
            self.soldiers = max(0, self.soldiers - deserters)
            if self.scenario_personnel:
                self.deserter_ids = self.person_ids[-deserters:]
                self.person_ids = self.person_ids[:-deserters]

        if upkeep_details is not None:
            upkeep_details.update({
                'unit_id': self.unit_id,
                'scenario_personnel': bool(self.scenario_personnel),
                'soldiers_before': soldiers_before,
                'soldiers_after': int(self.soldiers),
                'requested_wages': float(total_wage),
                'wages_paid': float(wages_paid),
                'unpaid_wages': float(max(0.0, total_wage - wages_paid)),
                'treasury_cash_before_funding': treasury_cash_before,
                'treasury_cash_available_for_payroll': cash_available_for_payroll,
                'treasury_cash_after_payroll': cash_after_payroll,
                'bank_deposits_before': bank_deposits_before,
                'bank_deposits_after': (float(getattr(bank, 'total_deposits', 0.0))
                                        if bank is not None else 0.0),
                'food_inventory_before': food_inventory_before,
                'food_inventory_after': int(getattr(gov, 'food_inventory', 0)),
                'food_needed': int(needed_food),
                'food_consumed': int(food_consumed),
                'food_unmet': int(max(0, needed_food - food_consumed)),
                'supply_access': bool(supply_access),
                'fully_supplied': bool(fully_supplied),
                'morale_before': morale_before,
                'morale_after': float(self.morale),
                'wage_ratio': float(wage_ratio),
                'food_ratio': float(food_ratio),
                'deserters': int(deserters),
                'deserter_agent_ids': list(self.deserter_ids),
                'recipient_cash_credits': recipient_cash_credits,
            })

        return wages_paid, food_consumed, fully_supplied, deserters


def recruit_unit(nation, region, soldier_count: int, wage: float = 1.0,
                 equipment: float = 1.0, t: int = 0) -> MilitaryUnit | None:
    """Recruit a new MilitaryUnit from the local region population.

    - Recruiting absorbs unemployed / low-wealth agents and lowers protest energy.
    - Upkeep is assigned to nation / region government.
    - Returns the created MilitaryUnit or None if population is insufficient.
    """
    if not hasattr(region, 'military_units'):
        region.military_units = []
    if not hasattr(nation, 'military_units'):
        nation.military_units = []

    bound = bool(getattr(nation, 'scenario_personnel', False))
    # Check available eligible population (non-corporations, alive)
    eligible = [a for a in getattr(region, 'agents', [])
                if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)]
    if bound:
        from livelihood_access import effective_access
        food_price = region.recipes[Goods.food]['price']
        eligible = [a for a in eligible if not a.is_trader and not getattr(a, 'is_lord', False)
                    and not getattr(a, 'military_unit_id', None) and a.employer is None
                    and a.social_class != 'constable'
                    and wage >= food_price * (1.25 + 0.5 * effective_access(a, region))]
        eligible.sort(key=lambda a: (a.output == Goods.cotton, a.cash, a.id))
        if (len(eligible) < soldier_count or
                nation.government.agent.cash < soldier_count * wage):
            return None
    
    if len(eligible) < soldier_count:
        soldier_count = max(5, len(eligible) // 4)
    if soldier_count <= 0:
        return None

    unit_id = (f"unit_{nation.name[:3]}_{region.name}_{t}_{len(nation.military_units) + 1}"
               if bound else f"unit_{nation.name[:3]}_{region.name}_{str(uuid.uuid4())[:6]}")
    unit = MilitaryUnit(
        unit_id=unit_id,
        nation_name=nation.name,
        region_name=region.name,
        soldiers=soldier_count,
        morale=1.0,
        equipment_quality=equipment,
        wage_per_soldier=wage
    )
    if bound:
        unit.scenario_personnel = True
        unit.food_per_soldier = 1.0
        unit.person_ids = [a.id for a in eligible[:soldier_count]]
        unit.prior_outputs = {a.id: a.output.name for a in eligible[:soldier_count]}
        for person in eligible[:soldier_count]:
            former_employer = getattr(person, 'employer', None)
            if former_employer is not None and person in getattr(former_employer, 'employees', []):
                former_employer.employees.remove(person)
            person.employer = None
            agreement = getattr(person, 'labor_agreement', None)
            if agreement is not None:
                agreement.active = False
            person.military_unit_id = unit_id
            person.output = Goods.gov
            from labor_choice import record_labor_status
            record_labor_status(region, person, t,
                                before='employed' if former_employer is not None else 'independent',
                                after='military', reason='enlisted',
                                employer_before=former_employer)

    region.military_units.append(unit)
    nation.military_units.append(unit)

    # Recruiting drains protest energy in the region (strategic unrest dampening)
    if not bound and hasattr(region, 'protest_energy_log') and region.protest_energy_log:
        drain = min(region.protest_energy_log[-1], soldier_count * 0.05)
        region.protest_energy_log[-1] = max(0.0, region.protest_energy_log[-1] - drain)

    return unit


def _friendly_supply_regions(nation, station):
    if station is None or station.owner_nation is not nation:
        return []
    regions = [station]
    for other in station.neighbors.values():
        if other.owner_nation is nation and other not in regions:
            regions.append(other)
    return regions


def _procure_rations(nation, unit, station, t=0, event_ids=None):
    """Move real food from reachable sellers to the sovereign reserve for pay day."""
    gov = nation.government
    needed = int(math.ceil(unit.soldiers * unit.food_per_soldier))
    target = needed * 2
    stock_before = int(getattr(gov, 'food_inventory', 0))
    missing = max(0, target - stock_before)
    if not missing:
        if station is not None:
            from run_trace import emit
            event_id = emit(
                station, kind='army_ration_procurement', record_class='outcome',
                phase='military', subject={'type': 'nation/unit',
                                           'id': unit.unit_id,
                                           'nation': nation.name},
                metric_id='military.supply_procurement', unit='food_units',
                before=stock_before, after=stock_before,
                inputs={'turn': int(t), 'unit_id': unit.unit_id,
                        'nation': nation.name, 'target_food_stock': target,
                        'stock_before': stock_before, 'stock_after': stock_before,
                        'food_purchased': 0, 'unfilled_target': 0,
                        'outcome': 'reserve_sufficient',
                        'reason': 'government_reserve_already_at_target',
                        'candidate_sellers': []})
            if event_ids is not None and event_id is not None:
                event_ids.append(event_id)
        return 0
    bought = 0
    total_cost = 0.0
    candidate_sellers = []
    procurement_event_ids = []
    purchase_index = 0
    for region in _friendly_supply_regions(nation, station):
        price = max(0.01, float(region.recipes[Goods.food]['price']))
        for seller in sorted(region.agents, key=lambda a: a.id):
            if not seller.alive or seller.output != Goods.food or seller.is_government:
                continue
            available = max(0, seller.inv_get(Goods.food, 0) - 2)
            affordable = int(gov.agent.cash / price)
            take = min(missing, available, affordable)
            if take <= 0:
                candidate_sellers.append({
                    'tile': region.name, 'seller_id': seller.id,
                    'available_above_reserve': available,
                    'unit_price': price, 'government_affordable_units': affordable,
                    'food_purchased': 0,
                    'reason': ('seller_has_no_surplus_food' if available <= 0 else
                               'government_cash_cannot_fund_one_unit')})
                continue
            source_food_before = int(seller.inv_get(Goods.food, 0))
            destination_food_before = int(getattr(gov, 'food_inventory', 0))
            seller_cash_before = float(seller.cash)
            treasury_cash_before = float(gov.agent.cash)
            amount = float(take * price)
            seller.inv_add(Goods.food, -take)
            seller.cash += amount
            gov.agent.cash -= amount
            gov.food_inventory += take
            source_food_after = int(seller.inv_get(Goods.food, 0))
            destination_food_after = int(getattr(gov, 'food_inventory', 0))
            seller_cash_after = float(seller.cash)
            treasury_cash_after = float(gov.agent.cash)
            missing -= take
            bought += take
            total_cost += amount
            purchase_index += 1
            operation_id = (f'army-ration:{int(t)}:{nation.name}:{unit.unit_id}:'
                            f'{region.name}:{seller.id}:{purchase_index}')
            cash_event_id = source_event_id = receipt_event_id = None
            if getattr(region, '_run_trace', None) is not None:
                from finance_trace import (account_ref, cash_transfer_contract,
                                           emit_cash_transfer)
                from run_trace import emit
                currency = (getattr(nation, 'currency', None)
                            or getattr(region, 'home_currency', None)
                            or 'local_currency')
                cash_contract = cash_transfer_contract(
                    operation_id, 'military_ration_procurement',
                    amount=amount, currency=currency,
                    payer_account=account_ref(
                        'government_agent_cash', str(gov.agent.id), currency,
                        balance_before=treasury_cash_before,
                        balance_after=treasury_cash_after,
                        balance_scope='cash', nation_id=nation.name),
                    payee_account=account_ref(
                        'agent_cash', str(seller.id), currency,
                        balance_before=seller_cash_before,
                        balance_after=seller_cash_after,
                        balance_scope='cash', tile=region.name))
                cash_event_id = emit_cash_transfer(
                    region, kind='army_ration_cash_payment',
                    contract=cash_contract, phase='military',
                    subject={'type': 'tile/operation', 'id': operation_id,
                             'tile': region.name, 'unit_id': unit.unit_id},
                    inputs={'turn': int(t), 'nation': nation.name,
                            'unit_id': unit.unit_id, 'seller_id': seller.id,
                            'food_units': int(take), 'unit_price': price})
                goods_contract = {
                    'contract_version': 'goods_transfer.v1',
                    'operation_id': operation_id,
                    'operation_type': 'military_ration_procurement',
                    'good': Goods.food.name, 'unit': 'food_units',
                    'amount': int(take),
                    'payer_account': account_ref(
                        'agent_inventory', str(seller.id), Goods.food.name,
                        balance_before=source_food_before,
                        balance_after=source_food_after,
                        balance_scope='inventory.food', tile=region.name),
                    'payee_account': account_ref(
                        'government_food_inventory', gov.name, Goods.food.name,
                        balance_before=destination_food_before,
                        balance_after=destination_food_after,
                        balance_scope='food_inventory', nation_id=nation.name),
                    'counterparty_leg_status': 'seller_and_government_food_balances_captured',
                }
                source_event_id = emit(
                    region, kind='army_ration_food_source',
                    record_class='transfer', phase='military',
                    subject={'type': 'tile/agent', 'id': seller.id,
                             'tile': region.name, 'good': Goods.food.name},
                    metric_id='goods.military_supply', unit='food_units',
                    before=source_food_before, after=source_food_after,
                    inputs={'turn': int(t), 'operation_id': operation_id,
                            'unit_id': unit.unit_id, 'nation': nation.name,
                            'transfer_contract': goods_contract, 'leg': 'source'},
                    cause_event_ids=[cash_event_id] if cash_event_id else None)
                receipt_event_id = emit(
                    region, kind='army_ration_food_receipt',
                    record_class='transfer', phase='military',
                    subject={'type': 'nation/unit', 'id': unit.unit_id,
                             'nation': nation.name, 'good': Goods.food.name},
                    metric_id='goods.military_supply', unit='food_units',
                    before=destination_food_before, after=destination_food_after,
                    inputs={'turn': int(t), 'operation_id': operation_id,
                            'seller_id': seller.id, 'unit_id': unit.unit_id,
                            'nation': nation.name,
                            'transfer_contract': goods_contract, 'leg': 'destination'},
                    cause_event_ids=[source_event_id] if source_event_id else None)
            candidate_sellers.append({
                'tile': region.name, 'seller_id': seller.id,
                'available_above_reserve': available,
                'unit_price': price, 'government_affordable_units': affordable,
                'food_purchased': int(take), 'cash_paid': amount,
                'reason': 'seller_selected_in_stable_id_order'})
            for event_id in (cash_event_id, source_event_id, receipt_event_id):
                if event_id is not None:
                    procurement_event_ids.append(event_id)
                    if event_ids is not None:
                        event_ids.append(event_id)
            if missing <= 0:
                break
        if missing <= 0:
            break
    if station is not None:
        from run_trace import emit
        outcome = ('target_funded' if missing <= 0 else
                   'partial_procurement' if bought > 0 else 'no_purchase_possible')
        reason = ('government_reserve_replenished_to_target' if missing <= 0 else
                  'remaining_target_blocked_by_seller_stock_or_treasury_cash'
                  if bought > 0 else
                  'no_surplus_seller_food_or_treasury_cash_for_one_unit')
        event_id = emit(
            station, kind='army_ration_procurement', record_class='outcome',
            phase='military', subject={'type': 'nation/unit',
                                       'id': unit.unit_id,
                                       'nation': nation.name},
            metric_id='military.supply_procurement', unit='food_units',
            before=stock_before, after=int(getattr(gov, 'food_inventory', 0)),
            formula_id='army.ration_procurement.v1',
            inputs={'turn': int(t), 'unit_id': unit.unit_id,
                    'nation': nation.name, 'target_food_stock': target,
                    'stock_before': stock_before,
                    'stock_after': int(getattr(gov, 'food_inventory', 0)),
                    'food_purchased': int(bought), 'cash_spent': total_cost,
                    'unfilled_target': int(missing), 'outcome': outcome,
                    'reason': reason, 'candidate_sellers': candidate_sellers},
            cause_event_ids=procurement_event_ids or None)
        if event_ids is not None and event_id is not None:
            event_ids.append(event_id)
    return bought


def discharge_unit(unit, tiles, nation):
    """Restore surviving enlisted people to civilian availability."""
    people = {a.id: a for region in tiles for a in region.agents}
    for person_id in list(unit.person_ids):
        person = people.get(person_id)
        if person is not None and person.alive:
            person.military_unit_id = None
            person.output = Goods[unit.prior_outputs.get(person_id, 'none')]
            from labor_choice import record_labor_status
            home = next((region for region in tiles if person in region.agents), None)
            if home is not None:
                record_labor_status(home, person, int(getattr(home, '_last_turn', 0) or 0),
                                    before='military', after='independent', reason='discharged')
    unit.person_ids.clear()
    unit.soldiers = 0
    if unit in nation.military_units:
        nation.military_units.remove(unit)
    for region in tiles:
        if unit in getattr(region, 'military_units', []):
            region.military_units.remove(unit)


def move_enlisted_people(unit, origin, destination):
    """Carry the unit's named people and their assets to its new station."""
    from migration import _withdraw_origin

    people = {person.id: person for person in origin.agents}
    for person_id in unit.person_ids:
        person = people.get(person_id)
        if person is None:
            raise ValueError(f'Enlisted person {person_id} is absent from {origin.name}')
        _withdraw_origin(origin, person)
        origin.agents.remove(person)
        origin.gov.citizen_ids.discard(person.id)
        destination.agents.append(person)
        destination.gov._add_citizen(person)
        person.region = destination.name
        person.home_currency = destination.home_currency
        person._bank_ref = destination.bank
        from run_trace import emit
        emit(origin, kind='enlisted_person_departure', record_class='outcome',
             phase='military', subject={'type': 'tile/agent', 'id': str(person.id)},
             metric_id='people.migration', unit='people', before=1, after=0,
             formula_id='army.enlisted_transfer.v1',
             inputs={'agent_id': person.id, 'origin': origin.name,
                     'destination': destination.name})
        emit(destination, kind='enlisted_person_arrival', record_class='outcome',
             phase='military', subject={'type': 'tile/agent', 'id': str(person.id)},
             metric_id='people.migration_in', unit='people', before=0, after=1,
             formula_id='army.enlisted_transfer.v1',
             inputs={'agent_id': person.id, 'origin': origin.name,
                     'destination': destination.name})


def settle_battle_casualties(units, tiles, nations, t):
    """Use the ordinary probate transfers for named battlefield deaths."""
    from types import SimpleNamespace
    from demographics_estate import (cleanup_dead_agent_links, handle_company_inheritance,
                                     handle_wage_claim_inheritance,
                                     living_descendants_recursive, handle_debt_inheritance,
                                     handle_wealth_inheritance, zero_out_dead_agent)

    dead = []
    by_id = {person.id: (person, region) for region in tiles for person in region.agents}
    for unit in units:
        for person_id in getattr(unit, 'casualty_ids', []):
            person, region = by_id[person_id]
            ctx = SimpleNamespace(bank=region.bank, default_gov=region.gov,
                                  charity=None, source_region=region)
            from person_death import record_person_death
            record_person_death(region, person, t, 'combat',
                                inputs={'military_unit_id': getattr(unit, 'id', None)},
                                phase='military')
            cleanup_dead_agent_links(person, region, t)
            handle_company_inheritance(t, person, region)
            heirs = living_descendants_recursive(person)
            handle_wage_claim_inheritance(region, t, person, heirs,
                                          region.gov, region.charity)
            handle_debt_inheritance(ctx, t, person, heirs)
            handle_wealth_inheritance(ctx, t, person, heirs)
            zero_out_dead_agent(ctx, person)
            person.military_unit_id = None
            region.agents.remove(person)
            region.gov.citizen_ids.discard(person.id)
            for nation in nations:
                nation.government.citizen_ids.discard(person.id)
            dead.append(person_id)
        unit.casualty_ids.clear()
    return dead


def step_armies(tiles: list, nations: list, t: int = 0) -> list[dict]:
    """Process per-turn upkeep, supply, desertion reabsorption, and cleanup for military units."""
    import random
    from agent import Agent, seed_traits, initialize_agent
    import wilderness as wd

    events = []
    people_by_id = {a.id: a for region in tiles for a in region.agents}
    for n in nations:
        gov = n.government
        units = getattr(n, 'military_units', [])
        for unit in list(units):
            if unit.soldiers <= 0:
                units.remove(unit)
                # Remove from region list as well
                for r in tiles:
                    if r.name == unit.region_name and hasattr(r, 'military_units') and unit in r.military_units:
                        r.military_units.remove(unit)
                continue

            # Find matching region
            matching_regions = [r for r in tiles if r.name == unit.region_name]
            region = matching_regions[0] if matching_regions else None
            bank = getattr(region, 'bank', None) if region else getattr(gov, '_bank_ref', None)

            supply_access = bool(_friendly_supply_regions(n, region)) if unit.scenario_personnel else True
            ration_event_ids = []
            if unit.scenario_personnel and supply_access:
                _procure_rations(n, unit, region, t=t,
                                 event_ids=ration_event_ids)
            funding_event_ids = []
            upkeep_details = {}
            wages, food, supplied, deserters = unit.pay_and_feed(
                gov, bank, t, people_by_id=people_by_id, supply_access=supply_access,
                trace_region=region, funding_event_ids=funding_event_ids,
                upkeep_details=upkeep_details)
            payroll_event_id = None
            ration_consumption_event_id = None
            if region is not None and getattr(region, '_run_trace', None) is not None:
                from finance_trace import account_ref, emit_treasury_leg, transfer_contract
                from run_trace import emit
                currency = (getattr(n, 'currency', None)
                            or getattr(region, 'home_currency', None)
                            or 'local_currency')
                operation_id = f'army-payroll:{int(t)}:{n.name}:{unit.unit_id}'
                if wages > 0:
                    payee_status = ('person_wallet_credits_recorded_separately'
                                    if unit.scenario_personnel else
                                    'abstract_military_service_has_no_person_wallet')
                    payroll_contract = transfer_contract(
                        operation_id, 'military_payroll', side='payer',
                        amount=wages, amount_currency=currency,
                        payer_account=account_ref(
                            'government_agent_cash', str(gov.agent.id), currency,
                            balance_before=upkeep_details[
                                'treasury_cash_available_for_payroll'],
                            balance_after=upkeep_details[
                                'treasury_cash_after_payroll'],
                            balance_scope='cash', nation_id=n.name),
                        payee_account=account_ref(
                            'military_payroll_service', unit.unit_id, currency,
                            nation_id=n.name,
                            wallet_balance_status=payee_status),
                        local_cash_leg_amount=wages,
                        local_cash_leg_currency=currency,
                        counterparty_leg_status=payee_status,
                        requested_wages=upkeep_details['requested_wages'],
                        unpaid_wages=upkeep_details['unpaid_wages'])
                    payroll_event_id = emit_treasury_leg(
                        region, kind='army_payroll', nation_name=n.name,
                        currency=currency, signed_amount=-wages,
                        contract=payroll_contract, phase='military',
                        inputs={'turn': int(t), 'unit_id': unit.unit_id,
                                'soldiers': upkeep_details['soldiers_before'],
                                'wages_paid': wages,
                                'unpaid_wages': upkeep_details['unpaid_wages'],
                                'treasury_cash_before_funding': upkeep_details[
                                    'treasury_cash_before_funding'],
                                'treasury_cash_available_for_payroll': upkeep_details[
                                    'treasury_cash_available_for_payroll'],
                                'treasury_cash_after_payroll': upkeep_details[
                                    'treasury_cash_after_payroll'],
                                'bank_deposits_before': upkeep_details[
                                    'bank_deposits_before'],
                                'bank_deposits_after': upkeep_details[
                                    'bank_deposits_after'],
                                'funding_event_ids': list(funding_event_ids),
                                'recipient_cash_credit_count': len(
                                    upkeep_details['recipient_cash_credits']),
                                'fully_supplied': supplied},
                        cause_event_ids=funding_event_ids or None)
                    for credit in upkeep_details['recipient_cash_credits']:
                        emit(
                            region, kind='army_payroll_recipient',
                            record_class='transfer', phase='military',
                            subject={'type': 'tile/agent', 'id': credit['agent_id'],
                                     'tile': region.name},
                            metric_id='finance.cash_transfer', unit=currency,
                            before=credit['cash_before'], after=credit['cash_after'],
                            inputs={'turn': int(t), 'operation_id': operation_id,
                                    'unit_id': unit.unit_id,
                                    'agent_id': credit['agent_id'],
                                    'wage_share': credit['amount'],
                                    'aggregate_payroll_event_id': payroll_event_id,
                                    'payer_leg_status':
                                    'included_in_aggregate_treasury_payroll'},
                            cause_event_ids=[payroll_event_id]
                            if payroll_event_id else None)
                elif upkeep_details['requested_wages'] <= 0.0:
                    payroll_event_id = emit(
                        region, kind='army_payroll_skipped',
                        record_class='outcome', phase='military',
                        subject={'type': 'nation/unit', 'id': unit.unit_id,
                                 'nation': n.name},
                        metric_id='military.upkeep',
                        inputs={'turn': int(t), 'unit_id': unit.unit_id,
                                'requested_wages': 0.0, 'wages_paid': 0.0,
                                'reason': 'no_active_soldiers'
                                if upkeep_details['soldiers_before'] <= 0 else
                                'no_wage_obligation'},
                        cause_event_ids=funding_event_ids or None)
                else:
                    payroll_event_id = emit(
                        region, kind='army_payroll_unpaid',
                        record_class='outcome', phase='military',
                        subject={'type': 'nation/unit', 'id': unit.unit_id,
                                 'nation': n.name},
                        metric_id='military.upkeep',
                        inputs={'turn': int(t), 'unit_id': unit.unit_id,
                                'requested_wages': upkeep_details.get(
                                    'requested_wages', 0.0),
                                'wages_paid': 0.0,
                                'reason': 'government_cash_and_bank_funding_unavailable',
                                'funding_event_ids': list(funding_event_ids)},
                        cause_event_ids=funding_event_ids or None)
                ration_consumption_event_id = emit(
                    region, kind='army_ration_consumption',
                    record_class='outcome', phase='military',
                    subject={'type': 'nation/unit', 'id': unit.unit_id,
                             'nation': n.name, 'good': Goods.food.name},
                    metric_id='goods.military_supply', unit='food_units',
                    before=upkeep_details['food_inventory_before'],
                    after=upkeep_details['food_inventory_after'],
                    formula_id='army.ration_consumption.v1',
                    inputs={'turn': int(t), 'unit_id': unit.unit_id,
                            'soldiers': upkeep_details['soldiers_before'],
                            'food_needed': upkeep_details['food_needed'],
                            'food_consumed': upkeep_details['food_consumed'],
                            'food_unmet': upkeep_details['food_unmet'],
                            'supply_access': supply_access,
                            'food_inventory_before': upkeep_details[
                                'food_inventory_before'],
                            'food_inventory_after': upkeep_details[
                                'food_inventory_after'],
                            'consumption_type': 'government_ration_stock_consumption'},
                    cause_event_ids=ration_event_ids or None)
                upkeep_event_id = emit(
                    region, kind='army_upkeep_outcome', record_class='outcome',
                    phase='military', subject={'type': 'nation/unit',
                                               'id': unit.unit_id,
                                               'nation': n.name},
                    metric_id='military.upkeep',
                    inputs={'turn': int(t), **upkeep_details,
                            'supply_access': supply_access,
                            'procurement_event_ids': list(ration_event_ids),
                            'payroll_event_id': payroll_event_id,
                            'ration_consumption_event_id': ration_consumption_event_id,
                            'supply_shortage_reason':
                            'supply_route_unavailable'
                            if not supply_access else
                            'rations_below_unit_need'
                            if not supplied else 'fully_supplied'},
                    cause_event_ids=[event_id for event_id in
                                     [*ration_event_ids, payroll_event_id,
                                      ration_consumption_event_id]
                                     if event_id is not None] or None)
            if unit.scenario_personnel:
                for person_id in unit.deserter_ids:
                    person = people_by_id.get(person_id)
                    if person is not None and person.alive:
                        person.military_unit_id = None
                        person.output = Goods[unit.prior_outputs.get(person_id, 'none')]
                        from labor_choice import record_labor_status
                        record_labor_status(region, person, t, before='military',
                                            after='independent', reason='deserted')
                        person.military_xp = max(person.military_xp, unit.veteran_xp)
                        events.append({'t': t, 'unit_id': unit.unit_id,
                                       'event': 'DESERTER_REABSORBED',
                                       'agent_id': person_id, 'region': person.region,
                                       'military_xp': person.military_xp})
                unit.deserter_ids.clear()
                events.append({'t': t, 'unit_id': unit.unit_id, 'nation': n.name,
                               'region': unit.region_name, 'event': 'ARMY_UPKEEP',
                               'wages_paid': wages, 'food_consumed': food,
                               'fully_supplied': supplied, 'soldiers': unit.soldiers})
            if not supplied:
                events.append({
                    't': t,
                    'unit_id': unit.unit_id,
                    'nation': n.name,
                    'region': unit.region_name,
                    'event': 'ARMY_SUPPLY_SHORTAGE',
                    'morale': unit.morale,
                    'soldiers': unit.soldiers
                })

            # Handle desertion reabsorption into civilian labor pool or wilderness homesteading
            if deserters > 0 and region is not None and not unit.scenario_personnel:
                # Look for adjacent wilderness tiles
                wild_neighbors = [other for other in region.neighbors.values()
                                  if getattr(other, 'wilderness', False) and not getattr(other, 'is_ocean', False) and getattr(other, 'elevation', 0.0) >= 0.0]

                for _ in range(deserters):
                    deserter_agent = Agent(t)
                    seed_traits(deserter_agent)
                    initialize_agent(deserter_agent, Goods.none, 0, 0, 0.0)
                    deserter_agent.origin_nation = n.name
                    # Record combat experience for future private military / mercenary hiring (M5.8 / M6)
                    deserter_agent.military_xp = min(1.0, max(0.2, unit.veteran_xp + 0.2))
                    deserter_agent.mem_push('promises', 1.0)

                    if wild_neighbors and random.random() < 0.5:
                        # Become homesteader in adjacent wilderness
                        wild_tile = random.choice(wild_neighbors)
                        deserter_agent.region = wild_tile.name
                        deserter_agent.home_currency = region.home_currency
                        from labor_choice import apply_career_switch
                        apply_career_switch(wild_tile, deserter_agent, Goods.food, t,
                                            kind='deserter_livelihood_entry',
                                            reason='homesteading', record_class='outcome')
                        wd.enter_wilderness(wild_tile, deserter_agent, t)
                        wild_tile.agents.append(deserter_agent)
                        events.append({
                            't': t,
                            'unit_id': unit.unit_id,
                            'event': 'DESERTER_HOMESTEAD',
                            'agent_id': deserter_agent.id,
                            'region': region.name,
                            'from_region': region.name,
                            'to_region': wild_tile.name,
                            'military_xp': deserter_agent.military_xp
                        })
                    else:
                        # Reabsorb into local region civilian labor pool
                        deserter_agent.region = region.name
                        deserter_agent.home_currency = region.home_currency
                        deserter_agent._bank_ref = getattr(region, 'bank', None)
                        from labor_choice import apply_career_switch
                        apply_career_switch(
                            region, deserter_agent,
                            random.choice([Goods.food, Goods.wood, Goods.furniture]), t,
                            kind='deserter_livelihood_entry', reason='civilian_reabsorption',
                            record_class='outcome')
                        region.agents.append(deserter_agent)
                        if hasattr(gov, '_add_citizen'):
                            gov._add_citizen(deserter_agent)
                        events.append({
                            't': t,
                            'unit_id': unit.unit_id,
                            'event': 'DESERTER_REABSORBED',
                            'agent_id': deserter_agent.id,
                            'region': region.name,
                            'military_xp': deserter_agent.military_xp
                        })
    return events


def resolve_battle(attackers: list[MilitaryUnit], defenders: list[MilitaryUnit],
                   defense_bonus: float = 1.2) -> dict:
    """Resolve combat between attacking units and defending garrison/units on a tile.

    Returns dict with winner, casualties, and conquest status.
    """
    atk_strength = sum(u.strength for u in attackers)
    def_strength = sum(u.strength for u in defenders) * defense_bonus

    if atk_strength <= 0 and def_strength <= 0:
        return {'winner': 'stalemate', 'atk_losses': 0, 'def_losses': 0, 'conquered': False}

    total_strength = atk_strength + def_strength
    atk_ratio = atk_strength / total_strength

    # Casualties scale with intensity
    atk_losses = 0
    def_losses = 0

    if atk_ratio > 0.55:
        # Attacker advantage
        winner = 'attacker'
        atk_loss_rate = max(0.05, 0.40 * (1.0 - atk_ratio))
        def_loss_rate = min(0.95, 0.50 * atk_ratio)
    elif atk_ratio < 0.45:
        # Defender advantage
        winner = 'defender'
        atk_loss_rate = min(0.95, 0.50 * (1.0 - atk_ratio))
        def_loss_rate = max(0.05, 0.40 * atk_ratio)
    else:
        # Close battle / stalemate
        winner = 'stalemate'
        atk_loss_rate = 0.25
        def_loss_rate = 0.25

    for u in attackers:
        lost = int(u.soldiers * atk_loss_rate)
        if u.scenario_personnel:
            u.casualty_ids = u.person_ids[-lost:] if lost else []
            if lost:
                u.person_ids = u.person_ids[:-lost]
        u.soldiers = max(0, u.soldiers - lost)
        u.morale = max(0.1, u.morale - (0.1 if winner != 'attacker' else 0.02))
        u.veteran_xp = min(1.0, u.veteran_xp + 0.1)
        atk_losses += lost

    for u in defenders:
        lost = int(u.soldiers * def_loss_rate)
        if u.scenario_personnel:
            u.casualty_ids = u.person_ids[-lost:] if lost else []
            if lost:
                u.person_ids = u.person_ids[:-lost]
        u.soldiers = max(0, u.soldiers - lost)
        u.morale = max(0.1, u.morale - (0.1 if winner != 'defender' else 0.02))
        u.veteran_xp = min(1.0, u.veteran_xp + 0.1)
        def_losses += lost

    remaining_def_strength = sum(u.strength for u in defenders)
    conquered = (winner == 'attacker' and remaining_def_strength < 5.0)

    return {
        'winner': winner,
        'atk_losses': atk_losses,
        'def_losses': def_losses,
        'remaining_atk_strength': sum(u.strength for u in attackers),
        'remaining_def_strength': remaining_def_strength,
        'conquered': conquered
    }
