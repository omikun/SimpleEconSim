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

        # 1. Procure funds from government (conserved transfer)
        gov = nation.government
        rgov = getattr(region, 'gov', gov)
        funding_gov = rgov if (rgov.agent.cash + (region.bank.deposits.get(rgov.agent, 0.0) if hasattr(region, 'bank') else 0.0)) >= cost else gov

        if funding_gov.agent.cash < cost:
            bank = getattr(region, 'bank', None) or getattr(funding_gov, '_bank_ref', None)
            if bank is not None:
                needed = cost - funding_gov.agent.cash
                withdrawable = min(needed, bank.deposits.get(funding_gov.agent, 0.0))
                if withdrawable > 0:
                    bank.Withdraw(funding_gov.agent, withdrawable)

        if funding_gov.agent.cash < cost:
            self.status = 'rejected'
            return False, f"BuildIntent failed: Unable to withdraw sufficient cash (${funding_gov.agent.cash:.2f} < ${cost:.2f})."

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
            if hasattr(gov, '_add_citizen'):
                gov._add_citizen(contractor)

        # 3. Conserved transfer: Gov pays contractor
        funding_gov.agent.cash -= cost
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
