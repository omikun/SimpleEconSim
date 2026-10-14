"""Inspectible, deterministic nation-level war forecasts.

Battle resolution remains in army.py.  This module reads the resulting state
once per turn so AI decisions use the same evidence as the player.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass
class WarAim:
    kind: str = 'limited'  # limited | border_tile | regime_change
    target: str | None = None
    value: float = 1.0

    @property
    def existential_cost(self) -> float:
        return 0.85 if self.kind == 'regime_change' else 0.0


@dataclass
class PeaceOffer:
    proposer: str
    recipient: str
    turn: int
    # A ceasefire recognizes the current map.  No territory or money changes
    # hands implicitly; future terms must name and execute their transfers.
    terms: str = 'current_control'


@dataclass
class WarSide:
    aims: list[WarAim] = field(default_factory=list)
    initial_tiles: set[str] = field(default_factory=set)
    initial_enemy_tiles: set[str] = field(default_factory=set)
    initial_regime: tuple[str, str | None] = ('', None)
    casualties: int = 0
    recent_losses: int = 0
    cohesion: float = 0.6
    posture: str = 'viable'
    pending_political_shock: float = 0.0
    last_offer_turn: int = -100
    last_posture_change_turn: int = -100
    last_lost_tile_count: int = 0
    reason: str = ''


@dataclass
class WarRecord:
    nations: tuple[str, str]
    declared_turn: int
    sides: dict[str, WarSide]
    pending_offer: PeaceOffer | None = None
    battle_losses: dict[str, int] = field(default_factory=dict)

    def enemy_of(self, nation_name: str) -> str:
        return self.nations[1] if self.nations[0] == nation_name else self.nations[0]


def payroll_runway(nation) -> float:
    units = [u for u in nation.military_units if u.soldiers > 0]
    wages = sum(u.soldiers * u.wage_per_soldier for u in units)
    if not wages:
        return 99.0
    return nation.treasury()['total'] / wages


def ration_runway(nation) -> float:
    units = [u for u in nation.military_units if u.soldiers > 0]
    rations = sum(u.soldiers * u.food_per_soldier for u in units)
    if not rations:
        return 99.0
    return getattr(nation.government, 'food_inventory', 0) / rations


def supply_runway(nation) -> float:
    return min(payroll_runway(nation), ration_runway(nation))


def effective_strength(nation) -> float:
    runway = supply_runway(nation)
    supply_factor = clamp(runway / 2.0)
    return sum(u.strength for u in nation.military_units if u.soldiers > 0) * supply_factor


def aim_secured(nation, enemy, side: WarSide) -> bool:
    for aim in side.aims:
        if aim.kind == 'border_tile' and aim.target:
            if any(tile.name == aim.target for tile in nation.tiles):
                return True
        elif aim.kind == 'regime_change':
            if (enemy.regime_type, enemy.ruling_faction) != side.initial_regime:
                return True
        elif aim.kind == 'limited':
            if any(tile.name in side.initial_enemy_tiles for tile in nation.tiles):
                return True
    return False


def attack_forecasts(nation, enemy, side: WarSide) -> list[dict]:
    """Forecast reachable attacks from actual units, adjacency and supply."""
    forecasts = []
    runway = supply_runway(nation)
    for home in nation.tiles:
        units = [u for u in nation.military_units
                 if u.region_name == home.name and u.soldiers > 0 and not u.is_garrison]
        if not units:
            continue
        for target in home.neighbors.values():
            if getattr(target, 'owner_nation', None) is not enemy:
                continue
            if (any(a.kind == 'defend' for a in side.aims)
                    and target.name not in side.initial_tiles):
                continue
            defenders = [u for u in enemy.military_units
                         if u.region_name == target.name and u.soldiers > 0]
            # Scenario-personnel combat commits the local force together;
            # ordinary MoveArmyIntent fights with its selected unit alone.
            candidates = [units[:]] if getattr(nation, 'scenario_personnel', False) else [
                [unit] for unit in units]
            for force in candidates:
                attack = sum(u.strength for u in force) * clamp(runway / 2.0)
                defense = sum(u.strength for u in defenders) * 1.2
                if attack <= 0:
                    continue
                advantage = attack / max(1.0, attack + defense)
                # The shared battle resolver cannot award an attacking
                # victory at or below a 0.55 ratio.
                if advantage <= 0.55:
                    continue
                desired = (target.name in side.initial_tiles or
                           any(a.kind == 'border_tile' and a.target == target.name
                               for a in side.aims))
                progress = (1.5 if desired else 0.75) * advantage
                cost = 0.20 + 0.65 * (1.0 - advantage)
                if runway < 2.0:
                    cost += 0.35
                forecasts.append({'unit_id': force[0].unit_id,
                                  'from': home.name, 'to': target.name,
                                  'progress': progress, 'cost': cost,
                                  'runway': runway, 'advantage': advantage})
    return sorted(forecasts, key=lambda f: f['progress'] - f['cost'], reverse=True)


def classify_posture(nation, enemy, side: WarSide) -> str:
    forecasts = attack_forecasts(nation, enemy, side)
    if not forecasts or forecasts[0]['runway'] < 2.0:
        return 'culminated'
    margin = forecasts[0]['progress'] - forecasts[0]['cost']
    if margin <= 0:
        return 'culminated'
    if margin <= 0.15:
        return 'strained'
    return 'viable'


def governing_support(nation, existential_threat: bool = False) -> float:
    legitimacy = clamp(getattr(nation, 'legitimacy', 0.6))
    units = [u for u in nation.military_units if u.soldiers > 0]
    loyalty = sum(u.morale for u in units) / len(units) if units else 0.6
    return clamp(0.70 * legitimacy + 0.30 * loyalty
                 + (0.10 if existential_threat else 0.0))


def update_wars(diplomacy, nations: list, turn: int) -> None:
    by_name = {n.name: n for n in nations}
    for key, war in list(diplomacy.war_records.items()):
        if key not in diplomacy.active_wars:
            del diplomacy.war_records[key]
            continue
        for name in war.nations:
            nation, enemy = by_name.get(name), by_name.get(war.enemy_of(name))
            if nation is None or enemy is None:
                continue
            side = war.sides[name]
            losses = war.battle_losses.get(name, 0)
            side.recent_losses = losses
            side.casualties += losses
            new_posture = classify_posture(nation, enemy, side)
            if new_posture != side.posture and turn - side.last_posture_change_turn >= 2:
                side.posture = new_posture
                side.last_posture_change_turn = turn
                side.reason = (f'Offensive {new_posture}: '
                               f'{supply_runway(nation):.1f} turns of supply runway.')
                diplomacy.diplomacy_log.append({
                    't': turn, 'event': 'WAR_POSTURE', 'nation': name,
                    'enemy': war.enemy_of(name), 'message': side.reason})
            starting_force = max(1, sum(u.soldiers for u in nation.military_units) + side.casualties)
            shock = min(0.45, losses / starting_force * 0.65)
            lost_homeland = len(side.initial_tiles - {r.name for r in nation.tiles})
            shock += min(0.20, 0.08 * max(0, lost_homeland - side.last_lost_tile_count))
            side.last_lost_tile_count = lost_homeland
            threatened = any(a.kind == 'regime_change'
                             for a in war.sides[war.enemy_of(name)].aims)
            side.cohesion = clamp(0.65 * side.cohesion +
                                  0.35 * governing_support(nation, threatened) - shock)
            if side.cohesion < 0.30 and shock >= 0.08:
                side.pending_political_shock = max(side.pending_political_shock,
                                                   min(0.25, shock))
                side.reason = 'Battlefield losses threaten the governing coalition.'
        war.battle_losses.clear()


def apply_political_shocks(diplomacy, nation, turn: int) -> None:
    shocks = []
    for war in diplomacy.war_records.values():
        side = war.sides.get(nation.name)
        if side and side.pending_political_shock:
            shocks.append(side.pending_political_shock)
            side.pending_political_shock = 0.0
    if shocks:
        loss = min(0.30, sum(shocks))
        nation.legitimacy = clamp(nation.legitimacy - loss)
        nation.regime_log.append({'t': turn, 'kind': 'war_government_crisis',
                                  'legitimacy_loss': loss})
