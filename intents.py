"""
intents.py — Modular Player and AI Intent (Command) Engine for REGNUM.

Provides a unified Command Pattern architecture:
- Human players (via UI / client) and AI brains submit `Intent` instances.
- Democracy regime enforces a 1-turn parliamentary approval delay (stub logic);
  autocracy has no delay (immediate execution).
- `BuildIntent` hires a corporate contractor in the target region, transfers
  treasury funds to them, and initiates a multi-turn `ConstructionProject`
  with weather/accident overruns.
- `RecruitArmyIntent` recruits soldiers from unemployed/poor agents, reducing protest energy.
- `MoveArmyIntent` repositions military units across adjacent tiles or initiates combat.
- `ProposeTreatyIntent`, `BreakTreatyIntent`, `DeclareWarIntent` drive bilateral diplomacy.
- All actions obey the conserved-money principle (0 LEAK / pure transfers).
"""

from __future__ import annotations
import uuid
from typing import TYPE_CHECKING
from goods import Goods
from buildings import BUILDING_RECIPES, ConstructionProject
from agent import Agent, seed_traits, initialize_agent
from army import MilitaryUnit, recruit_unit, resolve_battle
from diplomacy import get_diplomacy, TreatyType

if TYPE_CHECKING:
    from region import Region
    from nation import Nation


class Intent:
    """Base Command class for all strategic decisions."""

    def __init__(self, nation_name: str, intent_type: str, submitted_turn: int = 0,
                 regime_type: str = 'autocracy'):
        self.intent_id = str(uuid.uuid4())[:8]
        self.nation_name = nation_name
        self.intent_type = intent_type
        self.submitted_turn = submitted_turn
        
        # Government type approval logic:
        # Democracy requires parliament approval (1-turn delay stub).
        # Autocracy has no delay (immediate execution).
        if regime_type == 'democracy':
            self.approval_delay = 1
            self.status = 'pending_approval'
        else:
            self.approval_delay = 0
            self.status = 'approved'

        self.logs: list[str] = []

    def validate(self, tiles_by_name: dict[str, Region],
                 nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        """Validate if this intent can legally be executed."""
        if self.nation_name not in nations_by_name:
            return False, f"Nation '{self.nation_name}' not found."
        return True, "Valid"

    def execute(self, tiles_by_name: dict[str, Region],
                nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        """Execute the intent, applying state changes and conserved transfers."""
        raise NotImplementedError("Subclasses must implement execute()")

    def step(self, tiles_by_name: dict[str, Region],
             nations_by_name: dict[str, Nation], t: int) -> list[dict]:
        """Step intent state; handle parliamentary approval countdown and execution."""
        events = []
        if self.status == 'pending_approval':
            if self.approval_delay > 0:
                self.approval_delay -= 1
            else:
                self.status = 'approved'
                events.append({
                    't': t,
                    'intent_id': self.intent_id,
                    'event': 'APPROVED',
                    'message': f"Parliament of {self.nation_name} approved {self.intent_type} (ID {self.intent_id})."
                })
                ok, msg = self.execute(tiles_by_name, nations_by_name, t)
                events.append({
                    't': t,
                    'intent_id': self.intent_id,
                    'event': 'EXEC_RESULT',
                    'success': ok,
                    'message': msg
                })
        elif self.status == 'approved':
            ok, msg = self.execute(tiles_by_name, nations_by_name, t)
            events.append({
                't': t,
                'intent_id': self.intent_id,
                'event': 'EXEC_RESULT',
                'success': ok,
                'message': msg
            })

        return events


class BuildIntent(Intent):
    """Intent to construct a building in a region by hiring and funding a contractor corp."""

    def __init__(self, nation_name: str, region_name: str, building_type: str,
                 submitted_turn: int = 0, regime_type: str = 'autocracy'):
        super().__init__(nation_name, 'BUILD', submitted_turn, regime_type)
        self.region_name = region_name
        self.building_type = building_type
        self.project: ConstructionProject | None = None

    def validate(self, tiles_by_name: dict[str, Region],
                 nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        ok, msg = super().validate(tiles_by_name, nations_by_name, t)
        if not ok:
            return False, msg

        nation = nations_by_name[self.nation_name]
        if self.region_name not in tiles_by_name:
            return False, f"Region '{self.region_name}' not found."

        region = tiles_by_name[self.region_name]
        if region not in nation.tiles and getattr(region, 'owner_nation', None) is not nation:
            return False, f"Nation '{self.nation_name}' does not own tile '{self.region_name}'."

        if self.building_type not in BUILDING_RECIPES:
            return False, f"Unknown building recipe '{self.building_type}'."

        recipe = BUILDING_RECIPES[self.building_type]
        
        # Check treasury cash
        treasury = nation.treasury()
        if treasury['total'] < recipe.cost:
            return False, (f"Insufficient funds for {recipe.display_name}: "
                           f"requires ${recipe.cost:.2f}, treasury total is ${treasury['total']:.2f}.")

        return True, "Valid"

    def execute(self, tiles_by_name: dict[str, Region],
                nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        valid, reason = self.validate(tiles_by_name, nations_by_name, t)
        if not valid:
            self.status = 'rejected'
            return False, f"BuildIntent rejected: {reason}"

        nation = nations_by_name[self.nation_name]
        region = tiles_by_name[self.region_name]
        recipe = BUILDING_RECIPES[self.building_type]
        cost = recipe.cost

        # 1. Procure funds from government (conserved transfer across sovereign treasury pool)
        treasury = nation.treasury()
        remaining_needed = cost
        funding_sources = []

        # Try tile regional government first, then national government, then sister tiles
        rgov = getattr(region, 'gov', None)
        gov_pool = []
        if rgov is not None:
            gov_pool.append(rgov)
        if nation.government not in gov_pool:
            gov_pool.append(nation.government)
        for tile in nation.tiles:
            tgov = getattr(tile, 'gov', None)
            if tgov and tgov not in gov_pool:
                gov_pool.append(tgov)

        for g in gov_pool:
            if remaining_needed <= 0.001:
                break
            # Cash on hand
            if g.agent.cash > 0:
                take = min(remaining_needed, g.agent.cash)
                g.agent.cash -= take
                remaining_needed -= take
                funding_sources.append((g.agent, take))

            # Bank deposits
            if remaining_needed > 0.001:
                for b_tile in nation.tiles:
                    bank = getattr(b_tile, 'bank', None)
                    if bank is not None and g.agent in getattr(bank, 'deposits', {}):
                        dep = bank.deposits[g.agent]
                        take_dep = min(remaining_needed, dep)
                        if take_dep > 0:
                            bank.Withdraw(g.agent, take_dep)
                            g.agent.cash -= take_dep
                            remaining_needed -= take_dep
                            funding_sources.append((g.agent, take_dep))
                    if remaining_needed <= 0.001:
                        break

        # If slightly short but regional bank exists, allow deficit overdraft/borrowing
        if remaining_needed > 0.01:
            bank = getattr(region, 'bank', None)
            if bank is not None and getattr(bank, 'capital', 0.0) >= remaining_needed:
                bank.capital -= remaining_needed
                remaining_needed = 0.0
            else:
                # Rollback partial withdrawals
                for src_agent, amt in funding_sources:
                    src_agent.cash += amt
                self.status = 'rejected'
                return False, f"BuildIntent failed: Insufficient treasury cash (${treasury['total']:.2f} < ${cost:.2f})."

        # 2. Hire or incorporate contractor corporation
        existing_corps = [a for a in region.agents if getattr(a, 'is_corporation', False) and getattr(a, 'alive', True)]
        if existing_corps:
            contractor = existing_corps[0]
        else:
            contractor = Agent(t)
            contractor.is_corporation = True
            contractor.output = Goods.wood
            contractor._bank_ref = getattr(region, 'bank', None)
            contractor.home_currency = region.home_currency
            contractor.region = region.name
            seed_traits(contractor)
            initialize_agent(contractor, Goods.wood, 0, 0, 0.0)
            region.agents.append(contractor)
            gov = nation.government
            if hasattr(gov, '_add_citizen'):
                gov._add_citizen(contractor)

        # 3. Conserved transfer: Gov pays contractor
        contractor.cash += cost

        # 4. Spawn ConstructionProject
        project = ConstructionProject(
            project_id=f"proj_{self.intent_id}",
            nation_name=nation.name,
            region=region,
            recipe=recipe,
            contractor=contractor,
            started_turn=t
        )
        self.project = project

        if not hasattr(region, 'construction_projects'):
            region.construction_projects = []
        region.construction_projects.append(project)

        if not hasattr(nation, 'construction_projects'):
            nation.construction_projects = []
        nation.construction_projects.append(project)

        self.status = 'in_progress'
        msg = (f"Commissioned {recipe.display_name} in {region.name}: paid ${cost:.2f} to contractor. "
               f"Estimated duration: {project.total_turns} turns ({project.base_turns} base + {project.overrun_turns} weather/accidents).")
        self.logs.append(msg)
        return True, msg


# =====================================================================
# Military & Diplomatic Intents (M5)
# =====================================================================

class RecruitArmyIntent(Intent):
    """Intent to recruit soldiers from a region into a new military unit."""

    def __init__(self, nation_name: str, region_name: str, soldier_count: int,
                 wage: float = 1.0, equipment: float = 1.0,
                 submitted_turn: int = 0, regime_type: str = 'autocracy'):
        super().__init__(nation_name, 'RECRUIT_ARMY', submitted_turn, regime_type)
        self.region_name = region_name
        self.soldier_count = soldier_count
        self.wage = wage
        self.equipment = equipment

    def validate(self, tiles_by_name: dict[str, Region],
                 nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        ok, msg = super().validate(tiles_by_name, nations_by_name, t)
        if not ok:
            return False, msg

        nation = nations_by_name[self.nation_name]
        if self.region_name not in tiles_by_name:
            return False, f"Region '{self.region_name}' not found."

        region = tiles_by_name[self.region_name]
        if region not in nation.tiles and getattr(region, 'owner_nation', None) is not nation:
            return False, f"Nation '{self.nation_name}' does not control region '{self.region_name}'."

        if self.soldier_count <= 0:
            return False, "Soldier count must be positive."

        # Check treasury cash for first-turn upkeep
        treasury = nation.treasury()
        needed = self.soldier_count * self.wage
        if treasury['total'] < needed:
            return False, f"Insufficient funds: need ${needed:.2f} for recruitment/wages, treasury has ${treasury['total']:.2f}."

        return True, "Valid"

    def execute(self, tiles_by_name: dict[str, Region],
                nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        valid, reason = self.validate(tiles_by_name, nations_by_name, t)
        if not valid:
            self.status = 'rejected'
            return False, f"RecruitArmyIntent rejected: {reason}"

        nation = nations_by_name[self.nation_name]
        region = tiles_by_name[self.region_name]

        unit = recruit_unit(nation, region, self.soldier_count, wage=self.wage,
                            equipment=self.equipment, t=t)
        if unit is None:
            self.status = 'failed'
            return False, f"Failed to recruit soldiers in {self.region_name}: insufficient population."

        self.status = 'completed'
        msg = f"Recruited unit {unit.unit_id} ({unit.soldiers} soldiers, str: {unit.strength:.1f}) in {self.region_name}."
        self.logs.append(msg)
        return True, msg


class MoveArmyIntent(Intent):
    """Intent to move a military unit to an adjacent tile (or attack if enemy)."""

    def __init__(self, nation_name: str, unit_id: str, from_region: str,
                 to_region: str, submitted_turn: int = 0, regime_type: str = 'autocracy'):
        super().__init__(nation_name, 'MOVE_ARMY', submitted_turn, regime_type)
        self.unit_id = unit_id
        self.from_region = from_region
        self.to_region = to_region

    def validate(self, tiles_by_name: dict[str, Region],
                 nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        ok, msg = super().validate(tiles_by_name, nations_by_name, t)
        if not ok:
            return False, msg

        nation = nations_by_name[self.nation_name]
        if self.from_region not in tiles_by_name or self.to_region not in tiles_by_name:
            return False, "Origin or destination tile not found."

        from_tile = tiles_by_name[self.from_region]
        to_tile = tiles_by_name[self.to_region]

        if to_tile.name not in from_tile.neighbors:
            return False, f"Tiles {self.from_region} and {self.to_region} are not adjacent."

        # Find unit
        units = getattr(nation, 'military_units', [])
        unit = next((u for u in units if u.unit_id == self.unit_id), None)
        if unit is None:
            return False, f"Unit '{self.unit_id}' not found in nation's army."

        return True, "Valid"

    def execute(self, tiles_by_name: dict[str, Region],
                nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        valid, reason = self.validate(tiles_by_name, nations_by_name, t)
        if not valid:
            self.status = 'rejected'
            return False, f"MoveArmyIntent rejected: {reason}"

        nation = nations_by_name[self.nation_name]
        from_tile = tiles_by_name[self.from_region]
        to_tile = tiles_by_name[self.to_region]
        unit = next(u for u in nation.military_units if u.unit_id == self.unit_id)

        target_owner = getattr(to_tile, 'owner_nation', None)
        diplomacy = get_diplomacy()

        # Case 1: Friendly move (own tile or wilderness)
        if target_owner is None or target_owner is nation:
            if hasattr(from_tile, 'military_units') and unit in from_tile.military_units:
                from_tile.military_units.remove(unit)
            if not hasattr(to_tile, 'military_units'):
                to_tile.military_units = []
            to_tile.military_units.append(unit)
            unit.region_name = to_tile.name
            self.status = 'completed'
            msg = f"Unit {unit.unit_id} moved from {self.from_region} to {self.to_region}."
            self.logs.append(msg)
            return True, msg

        # Case 2: Foreign tile
        if not diplomacy.are_at_war(nation.name, target_owner.name):
            self.status = 'rejected'
            return False, f"Cannot move troops into foreign tile {to_tile.name} of {target_owner.name} without a state of war."

        # Combat resolution
        defenders = [u for u in getattr(target_owner, 'military_units', []) if u.region_name == to_tile.name]
        battle = resolve_battle([unit], defenders)

        if battle['conquered']:
            # Territorial transfer
            target_owner.transfer_tile(to_tile, nation)
            if hasattr(from_tile, 'military_units') and unit in from_tile.military_units:
                from_tile.military_units.remove(unit)
            if not hasattr(to_tile, 'military_units'):
                to_tile.military_units = []
            to_tile.military_units.append(unit)
            unit.region_name = to_tile.name
            self.status = 'completed'
            msg = f"VICTORY: Unit {unit.unit_id} conquered {self.to_region} from {target_owner.name} (Casualties: Atk -{battle['atk_losses']}, Def -{battle['def_losses']})."
        elif battle['winner'] == 'attacker':
            self.status = 'completed'
            msg = f"BATTLE: Unit {unit.unit_id} won engagement at {self.to_region}, but garrison holds."
        else:
            self.status = 'completed'
            msg = f"REPULSED: Attack on {self.to_region} repulsed by {target_owner.name} defenders."

        self.logs.append(msg)
        return True, msg


class ProposeTreatyIntent(Intent):
    """Intent to propose a bilateral treaty (Trade Pact, NAP, Defensive Alliance)."""

    def __init__(self, nation_name: str, target_nation_name: str, treaty_type: str,
                 submitted_turn: int = 0, regime_type: str = 'autocracy'):
        super().__init__(nation_name, 'PROPOSE_TREATY', submitted_turn, regime_type)
        self.target_nation_name = target_nation_name
        self.treaty_type = treaty_type

    def execute(self, tiles_by_name: dict[str, Region],
                nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        if self.target_nation_name not in nations_by_name:
            self.status = 'rejected'
            return False, f"Target nation '{self.target_nation_name}' not found."

        diplomacy = get_diplomacy()
        ok, msg = diplomacy.propose_treaty(self.nation_name, self.target_nation_name,
                                           self.treaty_type, t=t)
        self.status = 'completed' if ok else 'rejected'
        self.logs.append(msg)
        return ok, msg


class BreakTreatyIntent(Intent):
    """Intent to break / betray an active treaty."""

    def __init__(self, nation_name: str, target_nation_name: str, treaty_type: str,
                 submitted_turn: int = 0, regime_type: str = 'autocracy'):
        super().__init__(nation_name, 'BREAK_TREATY', submitted_turn, regime_type)
        self.target_nation_name = target_nation_name
        self.treaty_type = treaty_type

    def execute(self, tiles_by_name: dict[str, Region],
                nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        diplomacy = get_diplomacy()
        res = diplomacy.break_treaty(self.nation_name, self.target_nation_name,
                                     self.treaty_type, t=t)
        ok = res['success']
        msg = res['message']
        self.status = 'completed' if ok else 'failed'
        self.logs.append(msg)
        return ok, msg


class DeclareWarIntent(Intent):
    """Intent to declare war against a foreign nation."""

    def __init__(self, nation_name: str, target_nation_name: str, reason: str = "",
                 submitted_turn: int = 0, regime_type: str = 'autocracy'):
        super().__init__(nation_name, 'DECLARE_WAR', submitted_turn, regime_type)
        self.target_nation_name = target_nation_name
        self.reason = reason or "Geopolitical confrontation"

    def execute(self, tiles_by_name: dict[str, Region],
                nations_by_name: dict[str, Nation], t: int) -> tuple[bool, str]:
        if self.target_nation_name not in nations_by_name:
            self.status = 'rejected'
            return False, f"Target nation '{self.target_nation_name}' not found."

        diplomacy = get_diplomacy()
        events = diplomacy.declare_war(self.nation_name, self.target_nation_name,
                                       t=t, reason=self.reason)
        self.status = 'completed'
        msg = f"War declared on {self.target_nation_name} by {self.nation_name}."
        self.logs.append(msg)
        return True, msg


# =====================================================================
# Main Intent & Project Stepping Orchestrator
# =====================================================================

def step_intents_and_construction(t: int, tiles: list, nations: list, on_event=None) -> list[dict]:
    """Canonical turn step for all pending/active intents and construction projects across nations."""
    tiles_by_name = {r.name: r for r in tiles}
    nations_by_name = {n.name: n for n in nations}
    events = []

    # 1. Step pending/active intents for each nation
    for n in nations:
        intents = getattr(n, 'intents', [])
        for intent in list(intents):
            sub_events = intent.step(tiles_by_name, nations_by_name, t)
            events.extend(sub_events)
            if on_event:
                for ev in sub_events:
                    on_event(t, ev['event'], ev['message'])
            # Remove completed or rejected intents from active queue
            if intent.status in ('completed', 'rejected', 'failed'):
                intents.remove(intent)

    # 2. Step active construction projects across all tiles
    for r in tiles:
        projects = getattr(r, 'construction_projects', [])
        for p in list(projects):
            completed_building = p.step(t)
            # Emit project events
            for ev in p.events:
                if ev['t'] == t:
                    events.append(ev)
                    if on_event:
                        on_event(t, ev['event'], ev['message'])
            # Clean up completed projects from active list
            if p.status == 'completed':
                projects.remove(p)

    return events


# =====================================================================
# Inter-Governmental Fiscal Transfer & Shortfall Resolution
# =====================================================================

def execute_fiscal_transfer_and_build(world, nation_name: str, region_name: str, building_type: str,
                                      transfer_source: str, transfer_amount: float, t: int) -> tuple[bool, str]:
    """Execute a fiscal grant or bank loan to fund a construction project shortfall."""
    tiles_by_name = {r.name: r for r in world.get('tiles', [])}
    nations_by_name = {n.name: n for n in world.get('nations', [])}

    if nation_name not in nations_by_name or region_name not in tiles_by_name:
        return False, "Nation or Region not found."

    nation = nations_by_name[nation_name]
    region = tiles_by_name[region_name]
    rgov = getattr(region, 'gov', None)
    if rgov is None:
        return False, f"Region {region_name} has no municipal government."

    recipe = BUILDING_RECIPES.get(building_type)
    if not recipe:
        return False, f"Unknown building recipe '{building_type}'."

    transfer_amount = max(0.0, float(transfer_amount))

    # 1. Execute the source transfer
    if transfer_source == 'province_grant':
        province = getattr(region, 'province', None)
        prov_siblings = [t for t in getattr(province, 'tiles', []) if t != region and getattr(t, 'gov', None)]
        nation_siblings = [t for t in nation.tiles if t != region and t not in prov_siblings and getattr(t, 'gov', None)]
        pool_tiles = prov_siblings + nation_siblings
        gathered = 0.0
        for ot in pool_tiles:
            ogov = getattr(ot, 'gov', None)
            if ogov is not None and ogov is not rgov:
                # 1. Cash on hand
                if ogov.agent.cash > 0:
                    take = min(transfer_amount - gathered, ogov.agent.cash)
                    ogov.agent.cash -= take
                    rgov.agent.cash += take
                    gathered += take
                    if gathered >= transfer_amount - 0.01:
                        break
                # 2. Bank deposits
                bank = getattr(ot, 'bank', None)
                if bank and ogov.agent in getattr(bank, 'deposits', {}):
                    dep = bank.deposits[ogov.agent]
                    take_dep = min(transfer_amount - gathered, dep)
                    if take_dep > 0:
                        bank.Withdraw(ogov.agent, take_dep)
                        ogov.agent.cash -= take_dep
                        rgov.agent.cash += take_dep
                        gathered += take_dep
                        if gathered >= transfer_amount - 0.01:
                            break
        if gathered < transfer_amount - 0.01 and pool_tiles:
            return False, f"Province grant shortfall: only collected ${gathered:.2f} of ${transfer_amount:.2f}."

    elif transfer_source == 'national_bailout':
        nat_gov = nation.government
        if nat_gov.agent.cash < transfer_amount:
            # Check national bank deposits
            return False, f"National sovereign treasury has insufficient cash (${nat_gov.agent.cash:.2f} < ${transfer_amount:.2f})."
        nat_gov.agent.cash -= transfer_amount
        rgov.agent.cash += transfer_amount

    elif transfer_source == 'bank_loan':
        bank = getattr(region, 'bank', None)
        if bank is None or getattr(bank, 'capital', 0.0) < transfer_amount:
            return False, f"Municipal bank has insufficient capital for loan (${getattr(bank, 'capital', 0.0):.2f} < ${transfer_amount:.2f})."
        bank.capital -= transfer_amount
        rgov.agent.cash += transfer_amount

    # 2. Now execute BuildIntent
    intent = BuildIntent(nation_name, region_name, building_type, submitted_turn=t, regime_type=nation.regime_type)
    nation.submit_intent(intent, t)
    ok, msg = intent.execute(tiles_by_name, nations_by_name, t)
    if ok:
        from worldview_engine import ticker_push
        transfer_desc = {
            'province_grant': f"funded via Provincial Grant (${transfer_amount:.0f})",
            'national_bailout': f"funded via Sovereign National Bailout (${transfer_amount:.0f})",
            'bank_loan': f"funded via Municipal Bank Loan (${transfer_amount:.0f})",
        }.get(transfer_source, "")
        ticker_push(world, t, 'CONSTRUCT', f"Commissioned {recipe.display_name} in {region_name} ({transfer_desc}).", (245, 180, 50))
    return ok, msg

