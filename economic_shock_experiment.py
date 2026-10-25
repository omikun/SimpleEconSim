"""Run paired, trace-audited 20-turn economy shock screens.

Each control/treatment arm runs in a fresh process. The default screen uses the
same seed and compares complete canonical state (including RNG) after turn 7.

Example::

    venv/bin/python economic_shock_experiment.py --out-dir tmp/economic-shocks/seed-4242
    venv/bin/python economic_shock_experiment.py --seed 4242 \
        --out-dir tmp/economic-shocks/seed-4242 --reuse-existing --audit
    venv/bin/python economic_shock_experiment.py --scenario supply_rivalry \
        --seed 812 --out-dir tmp/economic-shocks/supply-rivalry/seed-812
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

from economic_shock_analysis import analyze_trace


TURN_COUNT = 20
SHOCK_START = 8
SHOCK_END = 11
RECOVERY_START = 12
PREFERRED_TARGET_TILE = "c50"
CORE_GOODS = ("food", "wood", "furniture", "cotton", "cloth")
MARKET_FIELDS = (
    "reference_price_after", "transaction_vwap", "demand_ratio",
    "funded_demand_units", "offered_supply_units", "submitted_bids",
    "offered_asks", "import_units", "units_sold", "cash_collected",
    "no_paid_sale",
)

EXPERIMENTS = {
    "wood_supply_reduction": {
        "title": "50% temporary wood recipe-output reduction",
        "kind": "physical_supply",
        "good": "wood",
        "factor": 0.5,
    },
    "furniture_demand_increase": {
        "title": "50% increase in household furniture inventory targets",
        "kind": "household_demand",
        "good": "furniture",
        "factor": 1.5,
    },
    "rivalry_cotton_supply_reduction": {
        "title": "50% temporary cotton recipe-output reduction",
        "scenario": "supply_rivalry",
        "target_region": "Cotton Fields",
        "kind": "physical_supply",
        "good": "cotton",
        "factor": 0.5,
    },
    "rivalry_mill_cotton_demand_increase": {
        "title": "50% increase in Meridian Mill's cotton inventory target",
        "scenario": "supply_rivalry",
        "target_region": "Cotton Fields",
        "kind": "input_demand",
        "good": "cotton",
        "factor": 1.5,
    },
}
DEFAULT_EXPERIMENTS = (
    "wood_supply_reduction", "furniture_demand_increase")
SCENARIO_EXPERIMENTS = {
    "default": DEFAULT_EXPERIMENTS,
    "supply_rivalry": (
        "rivalry_cotton_supply_reduction",
        "rivalry_mill_cotton_demand_increase"),
}

SNAPSHOT_METRICS = {
    "people.population", "people.residents", "people.hungry",
    "people.deaths", "people.births", "living.cost_of_living",
    "economy.gdp_nominal", "labor.surplus_value", "trade.export_value",
    "trade.import_value", "trade.net_value",
}
MARKET_SNAPSHOT_METRICS = {
    "goods.price", "goods.production", "goods.demand", "goods.supply",
    "goods.sold", "goods.producer_inventory",
}


def _git_info() -> dict:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(
        ["git", "diff", "--name-only"], text=True).strip())
    return {"source_commit": commit, "tracked_worktree_dirty": dirty}


def _canonical_digest(server) -> str:
    from simulation_semantics import canonical_state, state_digest

    extra = {
        "turn": server.turn,
        "pair_orders": server.pair_orders,
        "currencies": server.currencies,
        "scenario_state": getattr(server, "scenario_state", {}),
        "currency_totals": server.currency_totals,
        "violations": server.violations,
        "player_nation_name": server.player_nation_name,
        "nation_history": server._nation_history,
    }
    return state_digest(canonical_state(server.tiles, server.nations, extra=extra))


def _emit_intervention(server, tile, *, kind, turn, metric_id, unit,
                       before, after, formula_id, inputs):
    clock = tile._collective_trace_clock
    clock["turn"] = int(turn)
    clock["phase"] = "intervention"
    return server.run_trace.emit(
        clock,
        kind=kind,
        record_class="audit",
        phase="intervention",
        subject={"type": "tile", "id": tile.name,
                 "good": inputs.get("good")},
        metric_id=metric_id,
        unit=unit,
        before=before,
        after=after,
        formula_id=formula_id,
        inputs=inputs,
    )


def _default_target(region, good):
    if good == "furniture":
        return max(1, int(16 / max(1, region.recipes[next(
            item for item in region.recipes if item.name == good)]["price"])))
    if good == "cotton":
        return max(1, int(12 / max(1.0, region.recipes[next(
            item for item in region.recipes if item.name == good)]["price"])))
    raise ValueError(f"no base target formula registered for {good}")


def _eligible_demand_cohort(region):
    return sorted(
        (agent for agent in region.agents
         if getattr(agent, "alive", True)
         and not getattr(agent, "is_corporation", False)
         and not getattr(agent, "is_government", False)
         and not getattr(agent, "is_trader", False)
         and not getattr(agent, "military_unit_id", None)),
        key=lambda agent: int(agent.id),
    )


def _select_target_tile(server, experiment_id):
    """Choose an active tile, preferring c50 when it can receive this shock."""
    from goods import Goods

    config = EXPERIMENTS[experiment_id]
    if config.get("scenario") == "supply_rivalry":
        from region_market import input_good

        tile = next((item for item in server.tiles
                     if item.name == config["target_region"]), None)
        if tile is None:
            raise RuntimeError(
                f"scenario target region {config['target_region']} is missing")
        state = server.scenario_state
        if config["kind"] == "physical_supply":
            growers = [int(ident) for ident in state["grower_ids"]
                       if any(agent.id == ident and agent.alive
                              and agent.output == Goods.cotton
                              for agent in tile.agents)]
            if not growers or Goods.cotton not in tile.recipes:
                raise RuntimeError(
                    "supply_rivalry has no active cotton grower or cotton recipe")
            return tile, {
                "selection_rule": "scenario role: named cotton growers in Cotton Fields",
                "grower_agent_ids": growers,
                "cotton_grower_count": len(growers),
                "cotton_recipe_production": float(
                    tile.recipes[Goods.cotton].get("production", 0)),
            }
        if config["kind"] == "input_demand":
            mill_id = int(state["domestic_mill_id"])
            mill = next((agent for agent in tile.agents
                         if agent.id == mill_id and agent.alive), None)
            if (mill is None or not getattr(mill, "is_corporation", False)
                    or input_good(tile, mill) != Goods.cotton):
                raise RuntimeError(
                    "supply_rivalry domestic mill is not an active cotton-input buyer")
            return tile, {
                "selection_rule": "scenario role: Meridian Mill's cotton input demand",
                "target_agent_ids": [mill_id],
                "target_agent_name": getattr(mill, "company_name", None),
                "target_agent_role": "domestic_cotton_input_mill",
                "base_desired_target_units": _default_target(tile, "cotton"),
            }
    preferred = next((tile for tile in server.tiles
                      if tile.name == PREFERRED_TARGET_TILE), None)

    def counts(tile):
        alive = [agent for agent in tile.agents if getattr(agent, "alive", True)]
        return {
            "wood_producers": sum(agent.output == Goods.wood for agent in alive),
            "furniture_producers": sum(agent.output == Goods.furniture for agent in alive),
            "eligible_households": len(_eligible_demand_cohort(tile)),
        }

    if config["kind"] == "physical_supply":
        usable = [tile for tile in server.tiles
                  if Goods.wood in tile.recipes
                  and float(tile.recipes[Goods.wood].get("production", 0)) > 0
                  and counts(tile)["wood_producers"] > 0]
        if preferred in usable:
            tile = preferred
            rule = "prefer c50 when it has at least one active wood producer"
        elif usable:
            tile = max(usable, key=lambda item: (
                counts(item)["wood_producers"],
                counts(item)["furniture_producers"],
                counts(item)["eligible_households"], item.name))
            rule = "choose active tile with most wood producers; then downstream producers, households, name"
        else:
            raise RuntimeError("no tile has an active wood producer for this supply screen")
    else:
        usable = [tile for tile in server.tiles
                  if Goods.furniture in tile.recipes
                  and counts(tile)["eligible_households"] > 0]
        if preferred in usable:
            tile = preferred
            rule = "prefer c50 when it has eligible households"
        elif usable:
            tile = max(usable, key=lambda item: (
                counts(item)["eligible_households"],
                counts(item)["furniture_producers"], item.name))
            rule = "choose active tile with most eligible households; then furniture producers, name"
        else:
            raise RuntimeError("no tile has eligible households for this demand screen")
    return tile, {"selection_rule": rule, **counts(tile)}


def _apply_shock(server, experiment_id, tile, target_selection=None):
    from goods import Goods

    config = EXPERIMENTS[experiment_id]
    good = getattr(Goods, config["good"])
    if config["kind"] == "physical_supply":
        recipe = tile.recipes[good]
        before = float(recipe["production"])
        after = before * config["factor"]
        affected = sorted(int(agent.id) for agent in tile.agents
                          if getattr(agent, "alive", True) and agent.output == good)
        recipe["production"] = after
        event_id = _emit_intervention(
            server, tile, kind="economic_shock_applied", turn=SHOCK_START,
            metric_id="analysis.recipe_output_multiplier", unit="ratio",
            before=1.0, after=config["factor"],
            formula_id="analysis.recipe_output_multiplier.v1",
            inputs={"experiment": experiment_id, "good": config["good"],
                    "intervention_target": "region.recipes[good].production",
                    "recipe_production_before": before,
                    "recipe_production_after": after,
                    "affected_producer_agent_ids": affected,
                    "shock_turns_inclusive": [SHOCK_START, SHOCK_END],
                    "physical_inventory_destroyed": False})
        return {"tile": tile, "good": good, "event_id": event_id,
                "before": before, "after": after,
                "affected_agent_ids": affected}

    if config["kind"] == "household_demand":
        cohort = _eligible_demand_cohort(tile)
        affected = [agent for index, agent in enumerate(cohort)
                    if index % 2 == 0]
        base_target = _default_target(tile, config["good"])
        overrides = dict(getattr(
            tile, "_analysis_demand_target_overrides", {}) or {})
        overrides[good] = {int(agent.id): config["factor"]
                           for agent in affected}
        tile._analysis_demand_target_overrides = overrides
        metric_id = "analysis.household_inventory_target_multiplier"
        formula_id = "analysis.household_inventory_target_multiplier.v1"
        event_inputs = {
            "intervention_target": "household desired inventory target",
            "base_target_units_at_start": base_target,
            "treated_target_units_at_start": max(
                0, int(math.ceil(base_target * config["factor"]))),
            "eligible_household_count": len(cohort),
            "affected_agent_ids": [int(agent.id) for agent in affected],
            "assignment": "every other eligible resident by stable agent ID",
            "rounding": "ceil(base target multiplied by 1.5)",
            "direct_transfer_or_money_creation": False,
        }
        result_ids = {
            "eligible_agent_ids": [int(agent.id) for agent in cohort],
            "affected_agent_ids": [int(agent.id) for agent in affected],
        }
    elif config["kind"] == "input_demand":
        affected = list((target_selection or {}).get("target_agent_ids", ()))
        if len(affected) != 1:
            raise RuntimeError("input-demand intervention must target one named mill")
        base_target = int((target_selection or {}).get(
            "base_desired_target_units", _default_target(tile, config["good"])))
        overrides = dict(getattr(
            tile, "_analysis_demand_target_overrides", {}) or {})
        good_overrides = dict(overrides.get(good, {}) or {})
        good_overrides[int(affected[0])] = config["factor"]
        overrides[good] = good_overrides
        tile._analysis_demand_target_overrides = overrides
        metric_id = "analysis.input_inventory_target_multiplier"
        formula_id = "analysis.input_inventory_target_multiplier.v1"
        event_inputs = {
            "intervention_target": "named mill desired cotton input inventory target",
            "base_target_units_at_start": base_target,
            "treated_target_units_at_start": max(
                0, int(math.ceil(base_target * config["factor"]))),
            "target_agent_ids": [int(ident) for ident in affected],
            "target_agent_name": (target_selection or {}).get("target_agent_name"),
            "order_funding_and_fills_remain_endogenous": True,
            "direct_transfer_or_money_creation": False,
        }
        result_ids = {"affected_agent_ids": [int(ident) for ident in affected]}
    else:
        raise ValueError(f"unsupported demand shock kind {config['kind']}")
    event_id = _emit_intervention(
        server, tile, kind="economic_shock_applied", turn=SHOCK_START,
        metric_id=metric_id, unit="ratio", before=1.0,
        after=config["factor"], formula_id=formula_id,
        inputs={"experiment": experiment_id, "good": config["good"],
                **event_inputs,
                "shock_turns_inclusive": [SHOCK_START, SHOCK_END]})
    return {"tile": tile, "good": good, "event_id": event_id,
            "before": 1.0, "after": config["factor"],
            "base_target_units_at_start": base_target,
            **result_ids}


def _remove_shock(server, experiment_id, applied):
    config = EXPERIMENTS[experiment_id]
    tile, good = applied["tile"], applied["good"]
    if config["kind"] == "physical_supply":
        recipe = tile.recipes[good]
        before = float(recipe["production"])
        recipe["production"] = float(applied["before"])
        inputs = {"experiment": experiment_id, "good": config["good"],
                  "intervention_target": "region.recipes[good].production",
                  "recipe_production_before": before,
                  "recipe_production_after": recipe["production"],
                  "affected_producer_agent_ids": applied["affected_agent_ids"],
                  "shock_removed_before_turn": RECOVERY_START}
        metric_id = "analysis.recipe_output_multiplier"
        formula_id = "analysis.recipe_output_multiplier.v1"
    elif config["kind"] == "household_demand":
        overrides = dict(getattr(tile, "_analysis_demand_target_overrides", {}) or {})
        overrides.pop(good, None)
        if overrides:
            tile._analysis_demand_target_overrides = overrides
        else:
            tile.__dict__.pop("_analysis_demand_target_overrides", None)
        inputs = {"experiment": experiment_id, "good": config["good"],
                  "intervention_target": "household desired inventory target",
                  "eligible_household_count": len(applied["eligible_agent_ids"]),
                  "affected_agent_ids": applied["affected_agent_ids"],
                  "shock_removed_before_turn": RECOVERY_START}
        metric_id = "analysis.household_inventory_target_multiplier"
        formula_id = "analysis.household_inventory_target_multiplier.v1"
    elif config["kind"] == "input_demand":
        overrides = dict(getattr(tile, "_analysis_demand_target_overrides", {}) or {})
        good_overrides = dict(overrides.get(good, {}) or {})
        for ident in applied.get("affected_agent_ids", ()):
            good_overrides.pop(int(ident), None)
        if good_overrides:
            overrides[good] = good_overrides
        else:
            overrides.pop(good, None)
        if overrides:
            tile._analysis_demand_target_overrides = overrides
        else:
            tile.__dict__.pop("_analysis_demand_target_overrides", None)
        inputs = {"experiment": experiment_id, "good": config["good"],
                  "intervention_target": "named mill desired cotton input inventory target",
                  "affected_agent_ids": applied.get("affected_agent_ids", []),
                  "base_target_units_at_start": applied.get(
                      "base_target_units_at_start"),
                  "shock_removed_before_turn": RECOVERY_START}
        metric_id = "analysis.input_inventory_target_multiplier"
        formula_id = "analysis.input_inventory_target_multiplier.v1"
    else:
        raise ValueError(f"unsupported shock kind {config['kind']}")
    return _emit_intervention(
        server, tile, kind="economic_shock_removed", turn=RECOVERY_START,
        metric_id=metric_id, unit="ratio", before=config["factor"], after=1.0,
        formula_id=formula_id, inputs=inputs)


def _snapshot_rows(server, turn, target_tile, *, include_all_tiles=False):
    from trace_snapshots import sample

    rows = []
    for key, (subject, unit, value) in sample(server.tiles, server.nations).items():
        metric_id = key[0]
        if len(key) < 2:
            continue
        tile_name = key[1]
        good = subject.get("good")
        if metric_id in MARKET_SNAPSHOT_METRICS:
            if good not in CORE_GOODS:
                continue
            if subject.get("type") != "tile":
                continue
        elif metric_id in SNAPSHOT_METRICS:
            if not include_all_tiles and tile_name != target_tile:
                continue
        else:
            continue
        tile = next((item for item in server.tiles if item.name == tile_name), None)
        rows.append({"turn": turn, "metric_id": metric_id, "tile": tile_name,
                     "good": good, "unit": unit,
                     "currency": getattr(tile, "home_currency", None),
                     "value": value})
    return rows


def _scenario_actor_observations(server, turn):
    """Capture named supply-rivalry actors and settled trade by turn."""
    if server.scenario_id != "supply_rivalry":
        return None
    from goods import Goods

    state = server.scenario_state
    roles = {}
    for ident in state.get("grower_ids", ()):
        roles[int(ident)] = ("grower", "Cotton Fields")
    roles[int(state["domestic_mill_id"])] = ("domestic_mill", "Cotton Fields")
    roles[int(state["rival_mill_id"])] = ("rival_mill", "Rival Port")
    actor_rows = []
    for ident, (role, tile_name) in sorted(roles.items()):
        tile = server.by_name[tile_name]
        actor = next((item for item in tile.agents if int(item.id) == ident), None)
        if actor is None:
            actor_rows.append({"turn": turn, "actor_id": ident, "role": role,
                               "tile": tile_name, "present": False})
            continue
        account = next((row for row in getattr(tile, "actor_turn_accounts", ())
                        if int(row.get("actor_id", -1)) == ident
                        and int(row.get("turn", -1)) == turn), {})
        actor_rows.append({
            "turn": turn, "actor_id": ident, "role": role,
            "name": getattr(actor, "company_name", None)
                    or getattr(actor, "display_name", None) or f"Actor {ident}",
            "tile": tile_name, "present": True,
            "cash": round(float(getattr(actor, "cash", 0.0)), 4),
            "food_stock": int(actor.inv_get(Goods.food, 0)),
            "cotton_stock": int(actor.inv_get(Goods.cotton, 0)),
            "cloth_stock": int(actor.inv_get(Goods.cloth, 0)),
            "debt": round(float(getattr(actor, "debt", 0.0)), 4),
            "bank_debt": round(float(account.get("closing_bank_debt", 0.0)), 4),
            "cash_change": account.get("cash_change"),
            "crop_value": account.get("crop_value"),
            "sales_cash": account.get("sales_cash"),
            "purchases_cash": account.get("purchases_cash"),
            "wages_cash": account.get("wages_cash"),
            "input_consumed_cost": account.get("input_consumed_cost"),
            "produced_units": account.get("produced_units"),
            "food_intake": account.get("food_intake"),
        })
    trades = []
    for tile in server.tiles:
        for event in getattr(tile, "market_trade_events", ()):
            if int(event.get("turn", -1)) != turn or event.get("good") != "cotton":
                continue
            trades.append({"turn": turn, "tile": tile.name,
                           "buyer_id": event.get("buyer_id"),
                           "seller_id": event.get("seller_id"),
                           "quantity": event.get("quantity"),
                           "unit_price": event.get("unit_price"),
                           "total_paid": event.get("total_paid"),
                           "imported": event.get("imported"),
                           "shipment_id": event.get("shipment_id"),
                           "source_shipment_id": event.get("source_shipment_id"),
                           "source_region": event.get("source_region")})
    return {"turn": int(turn), "actors": actor_rows,
            "cotton_trade_events": trades}


def _scenario_household_cohort_roster(server):
    """Freeze the turn-7 resident cohort for paired household comparisons."""
    if server.scenario_id != "supply_rivalry":
        return []
    roster = []
    for tile in server.tiles:
        for actor in getattr(tile, "agents", ()):
            if (not getattr(actor, "alive", True)
                    or getattr(actor, "is_corporation", False)
                    or getattr(actor, "is_government", False)
                    or getattr(actor, "is_trader", False)
                    or getattr(actor, "military_unit_id", None)):
                continue
            roster.append({
                "actor_id": int(actor.id),
                "name": (getattr(actor, "display_name", None)
                         or f"Actor {actor.id}"),
                "baseline_tile": tile.name,
            })
    return sorted(roster, key=lambda row: row["actor_id"])


def _scenario_household_cohort_observations(server, turn, roster):
    """Sample a fixed resident cohort without adding later births or entrants."""
    if server.scenario_id != "supply_rivalry" or not roster:
        return None
    from goods import Goods

    actors = {int(actor.id): (tile, actor)
              for tile in server.tiles
              for actor in getattr(tile, "agents", ())}
    accounts = {int(row.get("actor_id")): row
                for tile in server.tiles
                for row in getattr(tile, "actor_turn_accounts", ())
                if row.get("actor_id") is not None
                and int(row.get("turn", -1)) == int(turn)}
    wage_income = {}
    for tile in server.tiles:
        for event in getattr(tile, "economic_events", ()):
            if (int(event.get("turn", -1)) == int(turn)
                    and event.get("kind") == "wage"
                    and event.get("recipient_id") is not None):
                ident = int(event["recipient_id"])
                wage_income[ident] = wage_income.get(ident, 0.0) + float(
                    event.get("amount", 0.0) or 0.0)

    members = []
    for base in roster:
        ident = int(base["actor_id"])
        found = actors.get(ident)
        if found is None:
            members.append({**base, "turn": int(turn), "present": False,
                            "alive": None})
            continue
        tile, actor = found
        account = accounts.get(ident, {})
        need = max(0.0, float(getattr(actor, "calorie_need_kcal", 0.0) or 0.0))
        eaten = max(0.0, float(getattr(actor, "last_calories_eaten", 0.0) or 0.0))
        employer = getattr(actor, "employer", None)
        debt = account.get("closing_debt")
        bank_debt = account.get("closing_bank_debt")
        total_debt = (float(debt or 0.0) + float(bank_debt or 0.0)
                      if debt is not None or bank_debt is not None else None)
        members.append({
            **base,
            "turn": int(turn),
            "present": True,
            "alive": bool(getattr(actor, "alive", True)),
            "tile": tile.name,
            "cash": round(float(getattr(actor, "cash", 0.0) or 0.0), 4),
            "food_stock": int(actor.inv_get(Goods.food, 0)),
            "calories_needed": round(need, 2),
            "calories_eaten": round(eaten, 2),
            "food_need_met_ratio": round(min(1.0, eaten / need), 6)
            if need > 0 else None,
            "food_shortfall": eaten + 1e-9 < need if need > 0 else None,
            "hungry_steps": round(float(getattr(actor, "hungry_steps", 0.0) or 0.0), 4),
            "debt": debt,
            "bank_debt": bank_debt,
            "total_debt": round(total_debt, 4) if total_debt is not None else None,
            "employer_id": getattr(employer, "id", None),
            "employer_linked": employer is not None,
            "occupation": getattr(getattr(actor, "output", None), "name", None),
            "wage_income_cash": round(wage_income.get(ident, 0.0), 4),
            "sales_cash": account.get("sales_cash"),
            "purchases_cash": account.get("purchases_cash"),
            "input_consumed_cost": account.get("input_consumed_cost"),
        })
    return {"turn": int(turn), "baseline_cohort_size": len(roster),
            "members": members}


def _default_resident_cohort_roster(server, turn):
    """Freeze every ordinary resident present at the default game's turn 7."""
    if server.scenario_id is not None:
        return []
    accounts = {int(row.get("actor_id")): row
                for tile in server.tiles
                for row in getattr(tile, "actor_turn_accounts", ())
                if row.get("actor_id") is not None
                and int(row.get("turn", -1)) == int(turn)}
    roster = []
    for tile in server.tiles:
        for actor in getattr(tile, "agents", ()):
            if (not getattr(actor, "alive", True)
                    or getattr(actor, "is_corporation", False)
                    or getattr(actor, "is_government", False)
                    or getattr(actor, "is_trader", False)
                    or getattr(actor, "military_unit_id", None)):
                continue
            account = accounts.get(int(actor.id), {})
            roster.append({
                "actor_id": int(actor.id),
                "baseline_tile": tile.name,
                "baseline_currency": getattr(tile, "home_currency", None),
                "baseline_cash": round(float(getattr(actor, "cash", 0.0) or 0.0), 4),
                "baseline_debt": account.get("closing_debt"),
                "baseline_bank_debt": account.get("closing_bank_debt"),
            })
    return sorted(roster, key=lambda row: row["actor_id"])


def _default_resident_cohort_observation(server, turn, roster):
    """Record compact welfare and account aggregates for the fixed roster."""
    if server.scenario_id is not None or not roster:
        return None
    actors = {int(actor.id): (tile, actor)
              for tile in server.tiles
              for actor in getattr(tile, "agents", ())}
    accounts = {int(row.get("actor_id")): row
                for tile in server.tiles
                for row in getattr(tile, "actor_turn_accounts", ())
                if row.get("actor_id") is not None
                and int(row.get("turn", -1)) == int(turn)}
    alive_count = present_count = need_count = need_met_count = 0
    eaten_total = shortfall_total = 0.0
    employer_linked_count = 0
    alive_resident_ids = set()
    cash_change_percent_values = []
    debt_change_cash_share_values = []
    resident_ids = {int(row["actor_id"]) for row in roster}
    cash_wage_recipients = set()
    scrip_wage_recipients = set()
    for tile in server.tiles:
        for event in getattr(tile, "economic_events", ()):
            if int(event.get("turn", -1)) != int(turn):
                continue
            recipient_id = event.get("recipient_id")
            if recipient_id is None or int(recipient_id) not in resident_ids:
                continue
            kind = event.get("kind")
            detail = event.get("detail") or {}
            if (kind in ("wage", "wage_arrears_paid")
                    or (kind == "wallet_transfer_in"
                        and detail.get("payment_kind") == "wage_arrears_paid")):
                cash_wage_recipients.add(int(recipient_id))
            elif kind == "scrip_wage":
                scrip_wage_recipients.add(int(recipient_id))

    for base in roster:
        found = actors.get(int(base["actor_id"]))
        if found is None:
            continue
        tile, actor = found
        present_count += 1
        if not getattr(actor, "alive", True):
            continue
        alive_count += 1
        alive_resident_ids.add(int(actor.id))
        cash = float(getattr(actor, "cash", 0.0) or 0.0)
        baseline_cash = base.get("baseline_cash")
        baseline_currency = base.get("baseline_currency")
        current_currency = getattr(tile, "home_currency", None)
        same_currency = (baseline_currency is not None
                         and current_currency == baseline_currency)
        if (same_currency and baseline_cash is not None
                and float(baseline_cash) > 0):
            cash_change_percent_values.append(
                (cash / float(baseline_cash) - 1.0) * 100.0)
        employer_linked_count += getattr(actor, "employer", None) is not None
        need = max(0.0, float(getattr(actor, "calorie_need_kcal", 0.0) or 0.0))
        eaten = max(0.0, float(getattr(actor, "last_calories_eaten", 0.0) or 0.0))
        if need > 0:
            need_count += 1
            eaten_total += eaten
            shortfall_total += max(0.0, need - eaten)
            need_met_count += eaten + 1e-9 >= need

        account = accounts.get(int(actor.id), {})
        debt = account.get("closing_debt")
        bank_debt = account.get("closing_bank_debt")
        base_debt = base.get("baseline_debt")
        base_bank_debt = base.get("baseline_bank_debt")
        if (same_currency and baseline_cash is not None
                and float(baseline_cash) > 0 and debt is not None
                and bank_debt is not None and base_debt is not None
                and base_bank_debt is not None):
            debt_change_cash_share_values.append((
                float(debt) + float(bank_debt)
                - float(base_debt) - float(base_bank_debt)) / float(baseline_cash))

    baseline_count = len(roster)
    roster_digest = hashlib.sha256(
        ",".join(str(row["actor_id"]) for row in roster).encode("ascii")
    ).hexdigest()
    return {
        "turn": int(turn),
        "baseline_member_count": baseline_count,
        "roster_sha256": roster_digest,
        "present_member_count": present_count,
        "missing_member_count": baseline_count - present_count,
        "alive_member_count": alive_count,
        "alive_share_of_baseline": round(alive_count / baseline_count, 6),
        "need_observed_member_count": need_count,
        "need_met_member_count": need_met_count,
        "need_met_share": round(need_met_count / need_count, 6)
        if need_count else None,
        "calories_eaten_total_kcal": round(eaten_total, 3),
        "calorie_shortfall_total_kcal": round(shortfall_total, 3),
        "median_cash_change_percent_from_turn7": round(
            statistics.median(cash_change_percent_values), 6)
        if cash_change_percent_values else None,
        "cash_change_percent_member_coverage": len(cash_change_percent_values),
        "employer_linked_member_count": int(employer_linked_count),
        "employer_linked_share_of_living": round(
            employer_linked_count / alive_count, 6) if alive_count else None,
        "median_debt_change_as_baseline_cash_share": round(
            statistics.median(debt_change_cash_share_values), 6)
        if debt_change_cash_share_values else None,
        "debt_change_cash_share_member_coverage": len(debt_change_cash_share_values),
        "cash_wage_recipient_member_count": len(
            cash_wage_recipients & alive_resident_ids),
        "scrip_wage_recipient_member_count": len(
            scrip_wage_recipients & alive_resident_ids),
    }


def _scenario_goods_stock_observation(server, turn):
    """Census enumerated physical goods holdings in the supply-rivalry world.

    This is a point-in-time holdings census, not a stock-flow conservation
    proof. All ordinary agents, trader pools, public food and granary stores,
    and route queues are included; category and object counts make the scope
    explicit.
    """
    if server.scenario_id != "supply_rivalry":
        return None
    from goods import Goods
    from region_logistics import all_routes

    totals = {}
    seen_public = set()
    seen_charities = set()
    granary_stores_scanned = 0
    scanned_agents = 0
    agent_categories = {}
    route_count = 0
    negative_holdings = []

    def add(tile_name, category, pool, good, quantity, route=None,
            holder_id=None):
        try:
            amount = float(quantity)
        except (TypeError, ValueError):
            return
        if not math.isfinite(amount) or abs(amount) <= 1e-12:
            return
        good_name = getattr(good, "name", str(good))
        if amount < -1e-9:
            negative_holdings.append({
                "tile": str(tile_name), "category": category, "pool": pool,
                "good": good_name, "quantity": round(amount, 6),
                "route": route, "holder_id": holder_id,
            })
        key = (str(tile_name), category, pool, good_name, route)
        totals[key] = totals.get(key, 0.0) + amount

    def add_array(tile_name, category, pool, values, *, holder_id=None):
        if values is None:
            return
        for good in Goods:
            if good == Goods.none:
                continue
            index = int(good.value)
            if index < len(values):
                add(tile_name, category, pool, good, values[index],
                    holder_id=holder_id)

    for tile in server.tiles:
        for actor in getattr(tile, "agents", ()):
            scanned_agents += 1
            if getattr(actor, "is_trader", False):
                category = "trader"
            elif getattr(actor, "is_government", False):
                category = "government_agent"
            elif getattr(actor, "is_corporation", False):
                category = "producer"
            else:
                category = "household"
            agent_categories[category] = agent_categories.get(category, 0) + 1
            add_array(tile.name, category, "inventory",
                      getattr(actor, "inventory", None),
                      holder_id=getattr(actor, "id", None))
            if category == "trader":
                add_array(tile.name, category, "export_inventory",
                          getattr(actor, "inventory_export", None),
                          holder_id=getattr(actor, "id", None))
                add_array(tile.name, category, "foreign_inventory",
                          getattr(actor, "inventory_foreign", None),
                          holder_id=getattr(actor, "id", None))
                for destination, values in (getattr(actor, "parked_foreign", {})
                                            or {}).items():
                    add_array(destination, category, "parked_foreign", values,
                              holder_id=getattr(actor, "id", None))
                for lot in getattr(actor, "transport_pipeline", ()) or ():
                    good = lot.get("good") if isinstance(lot, dict) else None
                    quantity = lot.get("quantity", 0) if isinstance(lot, dict) else 0
                    add(tile.name, "trader", "legacy_transport_pipeline",
                        good, quantity, holder_id=getattr(actor, "id", None))
            for good, quantity in (getattr(actor, "custom_inventory", {}) or {}).items():
                add(tile.name, category, "custom_inventory", good, quantity,
                    holder_id=getattr(actor, "id", None))

        government = (getattr(tile, "gov", None)
                      or getattr(getattr(tile, "owner_nation", None),
                                 "government", None))
        if government is not None and id(government) not in seen_public:
            seen_public.add(id(government))
            add(tile.name, "public", "government_food", Goods.food,
                getattr(government, "food_inventory", 0),
                holder_id=getattr(government, "name", "government"))
        charities = []
        charity = getattr(tile, "charity", None)
        if charity is not None:
            charities.append(charity)
        charities.extend(getattr(tile, "charities", ()) or ())
        for charity in charities:
            if id(charity) in seen_charities:
                continue
            seen_charities.add(id(charity))
            add(tile.name, "public", "charity_food", Goods.food,
                getattr(charity, "food_inventory", 0),
                holder_id=getattr(charity, "name", "charity"))

        granary_stores_scanned += 1
        add(tile.name, "public", "granary_food", Goods.food,
            getattr(tile, "granary_stock", 0),
            holder_id=f"{tile.name}:granary")

        for route in all_routes(tile):
            if route is None:
                continue
            route_count += 1
            for shipment in getattr(route, "pending", ()) or ():
                if len(shipment) >= 3:
                    add(tile.name, "in_transit", "route_pending",
                        shipment[1], shipment[2], route.name,
                        shipment[4] if len(shipment) > 4 else route.name)
            for shipment in getattr(route, "in_transit", ()) or ():
                if len(shipment) >= 3:
                    add(tile.name, "in_transit", "route_in_transit",
                        shipment[1], shipment[2], route.name,
                        shipment[5] if len(shipment) > 5 else route.name)

    rows = [{"tile": key[0], "category": key[1], "pool": key[2],
             "good": key[3], "quantity": round(value, 6), "route": key[4]}
            for key, value in sorted(totals.items())]
    negative_holdings.sort(key=lambda row: (
        row["tile"], row["category"], row["pool"], row["good"],
        str(row.get("holder_id"))))
    return {
        "turn": int(turn),
        "scope": "all supply-rivalry regions and their current route queues",
        "coverage": {
            "region_count": len(server.tiles),
            "agents_scanned": scanned_agents,
            "agent_counts_by_category": dict(sorted(agent_categories.items())),
            "distinct_government_stores": len(seen_public),
            "distinct_charity_stores": len(seen_charities),
            "granary_stores_scanned": granary_stores_scanned,
            "routes_scanned": route_count,
            "negative_stock_row_count": len(negative_holdings),
        },
        "negative_stock_rows": negative_holdings,
        "stocks": rows,
    }


def _scenario_route_events(trace_path, scenario_id):
    if scenario_id != "supply_rivalry":
        return []
    from trace_codec import iter_payloads

    events = []
    for payload in iter_payloads(trace_path):
        row = json.loads(payload)
        if row.get("kind") not in ("route_shipment_departure",
                                     "route_shipment_arrival"):
            continue
        inputs = row.get("inputs") or {}
        if inputs.get("good") != "cotton":
            continue
        events.append({
            "turn": row.get("turn"), "kind": row.get("kind"),
            "event_id": row.get("event_id"),
            "shipment_id": (row.get("subject") or {}).get("id"),
            "quantity": row.get("value_after"),
            "source_region": inputs.get("source_region"),
            "destination": inputs.get("destination"),
            "route": inputs.get("route"),
            "trader_id": inputs.get("trader_id"),
        })
    return events


def _scenario_mill_order_events(trace_path, scenario_id, mill_id):
    if scenario_id != "supply_rivalry":
        return []
    from trace_codec import iter_payloads

    events = []
    for payload in iter_payloads(trace_path):
        row = json.loads(payload)
        if (row.get("kind") != "market_buyer_order_submitted"
                or row.get("turn") is None):
            continue
        subject = row.get("subject") or {}
        inputs = row.get("inputs") or {}
        if (subject.get("good") != "cotton"
                or int(subject.get("buyer_id", -1)) != int(mill_id)):
            continue
        events.append({
            "turn": int(row["turn"]), "event_id": row.get("event_id"),
            "buyer_id": int(mill_id),
            "submitted_quantity": inputs.get("submitted_quantity",
                                             row.get("value_after")),
            "desired_target": inputs.get("current_desired"),
            "unshocked_desired_target": inputs.get("base_desired_target"),
            "target_override_applied": bool(
                inputs.get("analysis_demand_target_override")),
            "inventory_before_order": inputs.get("inventory_before_order"),
        })
    return events


def _intervention_hook_observation(server, config, target_tile, turn, arm,
                                   intervention):
    """Check a scenario hook leaves the treatment active and then restores it."""
    if (server.scenario_id != "supply_rivalry" or arm != "treatment"
            or intervention is None):
        return None
    from goods import Goods

    good = getattr(Goods, config["good"])
    active = SHOCK_START <= turn <= SHOCK_END
    if config["kind"] == "physical_supply":
        actual = float(target_tile.recipes[good]["production"])
        expected = (float(intervention["after"]) if active
                    else float(intervention["before"]))
        passed = math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)
        measured = actual
        expected_value = expected
        target = "cotton recipe production"
    elif config["kind"] == "input_demand":
        ident = int(intervention["affected_agent_ids"][0])
        overrides = getattr(target_tile, "_analysis_demand_target_overrides", {}) or {}
        factor = (overrides.get(good, {}) or {}).get(ident)
        passed = (factor == config["factor"]) if active else factor is None
        measured = factor
        expected_value = config["factor"] if active else None
        target = f"Meridian Mill {good.name} inventory-target multiplier"
    else:
        return None
    return {"turn": turn, "target": target, "passed": passed,
            "active": active, "expected": expected_value, "observed": measured}


def _run_child(experiment_id, arm, seed, out_path, audit_trace=False):
    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    from sim_server.sim_server import SimServer

    Path("tmp/traces").mkdir(parents=True, exist_ok=True)
    config = EXPERIMENTS[experiment_id]
    scenario_id = config.get("scenario")
    server = SimServer(seed=seed, terrain_seed=seed, nation_seed=seed,
                       topology="hex" if scenario_id else "voronoi",
                       scenario_id=scenario_id,
                       autoplay_nations=False, trace_enabled=True)
    if server.run_trace is None:
        raise RuntimeError("the experiment runner requires an enabled trace")

    intervention = None
    removal_event_id = None
    pre_shock_state_digest = None
    final_state_digest = None
    time_series = []
    scenario_actor_observations = []
    scenario_household_cohort_roster = []
    scenario_household_cohort_observations = []
    default_resident_cohort_roster = []
    default_resident_cohort_observations = []
    scenario_goods_stock_observations = []
    hook_observations = []
    target_tile, target_selection = _select_target_tile(server, experiment_id)
    for next_turn in range(1, TURN_COUNT + 1):
        if next_turn == SHOCK_START and arm == "treatment":
            intervention = _apply_shock(
                server, experiment_id, target_tile, target_selection)
        elif next_turn == RECOVERY_START and intervention is not None:
            removal_event_id = _remove_shock(server, experiment_id, intervention)
        server.step()
        if server.turn != next_turn:
            raise RuntimeError(
                f"simulation stopped at {server.turn} before requested turn {next_turn}")
        if server.turn == SHOCK_START - 1:
            pre_shock_state_digest = _canonical_digest(server)
        if server.turn == TURN_COUNT:
            final_state_digest = _canonical_digest(server)
        time_series.extend(_snapshot_rows(
            server, server.turn, target_tile.name,
            include_all_tiles=scenario_id == "supply_rivalry"))
        if scenario_id is None:
            if server.turn == SHOCK_START - 1:
                default_resident_cohort_roster = (
                    _default_resident_cohort_roster(server, server.turn))
            resident_observation = _default_resident_cohort_observation(
                server, server.turn, default_resident_cohort_roster)
            if resident_observation is not None:
                default_resident_cohort_observations.append(resident_observation)
        if scenario_id == "supply_rivalry":
            if server.turn == SHOCK_START - 1:
                scenario_household_cohort_roster = (
                    _scenario_household_cohort_roster(server))
            cohort_observation = _scenario_household_cohort_observations(
                server, server.turn, scenario_household_cohort_roster)
            if cohort_observation is not None:
                scenario_household_cohort_observations.append(
                    cohort_observation)
            scenario_goods_stock_observations.append(
                _scenario_goods_stock_observation(server, server.turn))
            scenario_actor_observations.append(
                _scenario_actor_observations(server, server.turn))
            hook_state = _intervention_hook_observation(
                server, config, target_tile, server.turn, arm, intervention)
            if hook_state is not None:
                hook_observations.append(hook_state)

    trace = server.run_trace
    trace_path = Path(trace.path)
    trace.publish()
    trace._compact_writer.close()
    scenario_routes = _scenario_route_events(trace_path, scenario_id)
    scenario_mill_orders = _scenario_mill_order_events(
        trace_path, scenario_id,
        getattr(server, "scenario_state", {}).get("domestic_mill_id", -1))
    panel = analyze_trace(trace_path)
    filtered_market_panel = [
        row for row in panel["panel"]
        if 1 <= row["turn"] <= TURN_COUNT and row["good"] in CORE_GOODS
    ]
    market_gates = _market_mechanical_gates(filtered_market_panel)
    trace_gates = _trace_quality_gates(trace_path) if audit_trace else None
    git = _git_info()
    intervention_record = None
    if intervention is not None:
        intervention_record = {
            key: value for key, value in intervention.items()
            if key not in ("tile", "good")
        }
    result = {
        "experiment": experiment_id,
        "experiment_config": EXPERIMENTS[experiment_id],
        "arm": arm,
        "scenario": scenario_id or "default",
        "seed": seed,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "requested_turns": TURN_COUNT,
        "completed_turns": server.turn,
        "shock_turns": [SHOCK_START, SHOCK_END],
        "recovery_starts_turn": RECOVERY_START,
        "target_tile": target_tile.name,
        "target_tile_selection": target_selection,
        "intervention": intervention_record,
        "intervention_removal_event_id": removal_event_id,
        "pre_shock_canonical_state_sha256": pre_shock_state_digest,
        "final_canonical_state_sha256": final_state_digest,
        "trace_path": str(trace_path),
        "trace_event_count": panel["event_count"],
        "trace_market_clearing_missing_count": panel["market_clearing_missing_count"],
        "market_panel": filtered_market_panel,
        "market_mechanical_gates": market_gates,
        "trace_quality_gates": trace_gates,
        "snapshot_time_series": time_series,
        "scenario_actor_observations": scenario_actor_observations,
        "scenario_household_cohort_roster": scenario_household_cohort_roster,
        "scenario_household_cohort_observations": (
            scenario_household_cohort_observations),
        "default_resident_cohort_roster": default_resident_cohort_roster,
        "default_resident_cohort_observations": (
            default_resident_cohort_observations),
        "scenario_goods_stock_observations": scenario_goods_stock_observations,
        "scenario_route_events": scenario_routes,
        "scenario_mill_order_events": scenario_mill_orders,
        "intervention_hook_observations": hook_observations,
        "intervention_hook_passed": (
            all(row["passed"] for row in hook_observations)
            if hook_observations else None),
        **git,
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"arm": arm, "experiment": experiment_id,
                      "turns": server.turn, "trace": str(trace_path),
                      "pre_shock_sha256": pre_shock_state_digest,
                      "report": str(out_path)}, sort_keys=True), flush=True)
    return result


def _row_index(run):
    return {(row["turn"], row["tile"], row["good"]): row
            for row in run["market_panel"]}


def _market_mechanical_gates(panel_rows):
    """Check trace-observed settlement bounds without filling missing values."""
    violations = []
    settlements = 0
    for row in panel_rows:
        market = row.get("market", {})
        for field in ("reference_price_after", "transaction_vwap",
                      "funded_demand_units", "offered_supply_units",
                      "submitted_bids", "offered_asks", "units_sold",
                      "cash_collected", "import_units",
                      "production_units", "producer_inventory_units"):
            value = (market.get(field) if field in market else row.get(field))
            if isinstance(value, (int, float)) and not math.isfinite(value):
                violations.append({"turn": row["turn"], "tile": row["tile"],
                                   "good": row["good"], "check": "finite",
                                   "field": field, "value": value})
        for field in ("funded_demand_units", "offered_supply_units",
                      "submitted_bids", "offered_asks", "units_sold",
                      "cash_collected", "import_units"):
            value = market.get(field)
            if (isinstance(value, (int, float)) and math.isfinite(value)
                    and value < -1e-9):
                violations.append({"turn": row["turn"], "tile": row["tile"],
                                   "good": row["good"],
                                   "check": "nonnegative_" + field,
                                   "value": value})
        for field in ("reference_price_after", "transaction_vwap"):
            value = market.get(field)
            if (isinstance(value, (int, float)) and math.isfinite(value)
                    and value < -1e-9):
                violations.append({"turn": row["turn"], "tile": row["tile"],
                                   "good": row["good"],
                                   "check": "nonnegative_" + field,
                                   "value": value})
        sold = market.get("units_sold")
        demand = market.get("funded_demand_units")
        supply = market.get("offered_supply_units")
        if sold is not None:
            settlements += 1
            if sold < -1e-9:
                violations.append({"turn": row["turn"], "tile": row["tile"],
                                   "good": row["good"], "check": "nonnegative_sales",
                                   "sold": sold})
            if demand is not None and sold > demand + 1e-8:
                violations.append({"turn": row["turn"], "tile": row["tile"],
                                   "good": row["good"], "check": "sales_within_funded_demand",
                                   "sold": sold, "funded_demand": demand})
            if supply is not None and sold > supply + 1e-8:
                violations.append({"turn": row["turn"], "tile": row["tile"],
                                   "good": row["good"], "check": "sales_within_recorded_supply",
                                   "sold": sold, "offered_supply": supply})
            if market.get("no_paid_sale") is True and sold > 1e-9:
                violations.append({"turn": row["turn"], "tile": row["tile"],
                                   "good": row["good"],
                                   "check": "no_paid_sale_matches_zero_sales",
                                   "sold": sold})
        for field in ("production_units", "producer_inventory_units"):
            value = row.get(field)
            if value is not None and value < -1e-9:
                violations.append({"turn": row["turn"], "tile": row["tile"],
                                   "good": row["good"], "check": "nonnegative_" + field,
                                   "value": value})
    return {"passed": not violations, "market_rows": len(panel_rows),
            "settlements_checked": settlements,
            "violations": violations}


def _trace_quality_gates(trace_path):
    from trace_audit import audit
    from trace_coverage import coverage

    structural = audit(trace_path)
    observed = coverage(trace_path)
    treasury = observed["_treasury_reconciliation"]
    closures = observed["_treasury_account_closure"]
    return {
        "structural_and_supported_formula_checks_pass":
            structural["structural_and_supported_formula_checks_pass"],
        "complete_causal_coverage": structural["complete_causal_coverage"],
        "audit_issue_count": len(structural["issues"]),
        "counts": structural["counts"],
        "treasury_reconciliation": {
            **treasury,
            "fully_attributed_turns": treasury["fully_attributed"],
            "unattributed_turns": treasury["turns"] - treasury["fully_attributed"],
            "fully_attributed": treasury["turns"] == treasury["fully_attributed"],
        },
        "treasury_account_closure": {
            **closures,
            "all_verified": (closures["nation_closes"] == closures["verified"]
                             and closures["gaps"] == 0),
        },
    }


def _compare_pair(control, treatment):
    left, right = _row_index(control), _row_index(treatment)
    compared = []
    keys = sorted(left.keys() | right.keys())
    for key in keys:
        control_row = left.get(key)
        treatment_row = right.get(key)
        control_market = (control_row or {}).get("market", {})
        treatment_market = (treatment_row or {}).get("market", {})
        values = {}
        for field in MARKET_FIELDS:
            a, b = control_market.get(field), treatment_market.get(field)
            values[field] = {
                "control": a, "treatment": b,
                "treatment_minus_control": (b - a if isinstance(a, (int, float))
                                               and isinstance(b, (int, float)) else None),
            }
        for field in ("production_units", "producer_inventory_units"):
            a = (control_row or {}).get(field)
            b = (treatment_row or {}).get(field)
            values[field] = {
                "control": a, "treatment": b,
                "treatment_minus_control": (b - a if isinstance(a, (int, float))
                                               and isinstance(b, (int, float)) else None),
            }
        for field in ("shortfall_units", "shortfall_records", "desired_units", "records"):
            a = ((control_row or {}).get("food_intake") or {}).get(field)
            b = ((treatment_row or {}).get("food_intake") or {}).get(field)
            values[f"food_intake.{field}"] = {
                "control": a, "treatment": b,
                "treatment_minus_control": (b - a if isinstance(a, (int, float))
                                               and isinstance(b, (int, float)) else None),
            }
        for field in ("units_consumed", "requested_units", "records",
                      "requested_observed_records"):
            a = ((control_row or {}).get("nonfood_consumption") or {}).get(field)
            b = ((treatment_row or {}).get("nonfood_consumption") or {}).get(field)
            values[f"nonfood_consumption.{field}"] = {
                "control": a, "treatment": b,
                "treatment_minus_control": (b - a if isinstance(a, (int, float))
                                               and isinstance(b, (int, float)) else None),
            }
        compared.append({"turn": key[0], "tile": key[1], "good": key[2],
                         "currency": ((control_row or treatment_row or {}).get("currency")),
                         "values": values})

    control_snapshots = {
        (row["turn"], row["metric_id"], row["tile"], row.get("good")): row
        for row in control["snapshot_time_series"]
    }
    treatment_snapshots = {
        (row["turn"], row["metric_id"], row["tile"], row.get("good")): row
        for row in treatment["snapshot_time_series"]
    }
    snapshot_deltas = []
    for key in sorted(control_snapshots.keys() | treatment_snapshots.keys()):
        a = control_snapshots.get(key)
        b = treatment_snapshots.get(key)
        av = a.get("value") if a else None
        bv = b.get("value") if b else None
        snapshot_deltas.append({
            "turn": key[0], "metric_id": key[1], "tile": key[2],
            "good": key[3], "currency": (a or b).get("currency"),
            "control": av, "treatment": bv,
            "treatment_minus_control": (bv - av if isinstance(av, (int, float))
                                           and isinstance(bv, (int, float)) else None),
        })
    return {"pre_shock_states_match": (
                control.get("pre_shock_canonical_state_sha256")
                == treatment.get("pre_shock_canonical_state_sha256")),
            "pre_shock_control_sha256": control.get("pre_shock_canonical_state_sha256"),
            "pre_shock_treatment_sha256": treatment.get("pre_shock_canonical_state_sha256"),
            "market_response": compared,
            "snapshot_response": snapshot_deltas}


def _format(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _window_summary(pair, good, key, start, end, target_tile):
    rows = [row for row in pair["comparison"]["market_response"]
            if row["tile"] == target_tile and row["good"] == good
            and start <= row["turn"] <= end]
    paired = [row["values"].get(key, {}) for row in rows]
    paired = [value for value in paired
              if isinstance(value.get("control"), (int, float))
              and isinstance(value.get("treatment"), (int, float))]
    deltas = [value["treatment"] - value["control"] for value in paired]
    return {
        "control_total": sum(value["control"] for value in paired) if paired else None,
        "treatment_total": sum(value["treatment"] for value in paired) if paired else None,
        "delta_total": sum(deltas) if paired else None,
        "mean_delta": sum(deltas) / len(deltas) if paired else None,
        "paired_turns": len(paired),
        "expected_turns": end - start + 1,
    }


def _quality_line(label, run):
    market = run.get("market_mechanical_gates") or {}
    trace = run.get("trace_quality_gates") or {}
    treasury = trace.get("treasury_reconciliation") or {}
    closure = trace.get("treasury_account_closure") or {}
    formula = trace.get("structural_and_supported_formula_checks_pass")
    attributed_turns = treasury.get(
        "fully_attributed_turns",
        treasury.get("turns", 0) - treasury.get("unattributed_turns", 0))
    formula_text = "PASS" if formula is True else "FAIL" if formula is False else "not run"
    return (
        f"- `{label}`: settlement bounds **{'PASS' if market.get('passed') else 'FAIL'}** "
        f"({market.get('settlements_checked', 0)}/{market.get('market_rows', 0)} "
        f"rows had clearing summaries); structural/supported-formula checks "
        f"**{formula_text}**; nation-account closes "
        f"**{closure.get('verified', '—')}/{closure.get('nation_closes', '—')}** "
        f"verified; treasury fully attributed "
        f"**{attributed_turns}/{treasury.get('turns', '—')} turns** "
        f"({'complete' if treasury.get('fully_attributed') is True else 'incomplete' if treasury.get('fully_attributed') is False else 'not run'})."
    )


def _quality_payload(run):
    return {
        "source_commit": run.get("source_commit"),
        "tracked_worktree_dirty": run.get("tracked_worktree_dirty"),
        "market_mechanical_gates": run.get("market_mechanical_gates"),
        "trace_quality_gates": run.get("trace_quality_gates"),
        "scenario_actor_observations": run.get("scenario_actor_observations", []),
        "scenario_household_cohort_roster": run.get(
            "scenario_household_cohort_roster", []),
        "scenario_household_cohort_observations": run.get(
            "scenario_household_cohort_observations", []),
        "default_resident_cohort_roster": run.get(
            "default_resident_cohort_roster", []),
        "default_resident_cohort_observations": run.get(
            "default_resident_cohort_observations", []),
        "scenario_goods_stock_observations": run.get(
            "scenario_goods_stock_observations", []),
        "scenario_route_events": run.get("scenario_route_events", []),
        "scenario_mill_order_events": run.get("scenario_mill_order_events", []),
        "intervention_hook_observations": run.get(
            "intervention_hook_observations", []),
        "intervention_hook_passed": run.get("intervention_hook_passed"),
    }


def _display_path(value):
    path = Path(value)
    root = Path(__file__).resolve().parent
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(value)


def _scenario_observation_summary(run):
    turns = [item for item in run.get("scenario_actor_observations", [])
             if SHOCK_START <= int(item.get("turn", -1)) <= SHOCK_END]
    actors = [actor for item in turns for actor in item.get("actors", [])]
    trades = [trade for item in turns
              for trade in item.get("cotton_trade_events", [])]
    routes = [event for event in run.get("scenario_route_events", [])
              if SHOCK_START <= int(event.get("turn", -1)) <= SHOCK_END]
    mill_orders = [event for event in run.get("scenario_mill_order_events", [])
                   if SHOCK_START <= int(event.get("turn", -1)) <= SHOCK_END]
    all_routes = run.get("scenario_route_events", [])
    return {
        "cotton_market_fills": sum(float(row.get("quantity", 0) or 0)
                                   for row in trades),
        "route_departures": sum(float(row.get("quantity", 0) or 0)
                                 for row in routes
                                 if row.get("kind") == "route_shipment_departure"),
        "route_arrivals": sum(float(row.get("quantity", 0) or 0)
                               for row in routes
                               if row.get("kind") == "route_shipment_arrival"),
        "route_departure_events": sum(
            row.get("kind") == "route_shipment_departure" for row in routes),
        "route_arrival_events": sum(
            row.get("kind") == "route_shipment_arrival" for row in routes),
        "run_route_departure_events": sum(
            row.get("kind") == "route_shipment_departure" for row in all_routes),
        "run_route_arrival_events": sum(
            row.get("kind") == "route_shipment_arrival" for row in all_routes),
        "grower_food_intake": sum(float(row.get("food_intake", 0) or 0)
                                   for row in actors if row.get("role") == "grower"),
        "actor_turns_observed": len(actors),
        "mill_submitted_bid_units": sum(
            float(row.get("submitted_quantity", 0) or 0) for row in mill_orders),
        "mill_order_events": len(mill_orders),
        "mill_desired_target_sum": sum(
            float(row.get("desired_target", 0) or 0) for row in mill_orders),
        "mill_unshocked_target_sum": sum(
            float((row.get("unshocked_desired_target")
                   if row.get("unshocked_desired_target") is not None
                   else row.get("desired_target", 0)) or 0)
            for row in mill_orders),
        "mill_override_order_events": sum(
            bool(row.get("target_override_applied")) for row in mill_orders),
    }


def _scenario_actor_rows(run):
    return [actor for snapshot in run.get("scenario_actor_observations", [])
            for actor in snapshot.get("actors", [])]


def _render_report(result):
    source_commits = sorted({
        run.get("source_commit")
        for pair in result["experiments"].values()
        for run in (pair.get("control_result_data", {}),
                    pair.get("treatment_result_data", {}))
        if run.get("source_commit")
    })
    lines = [
        "# Paired 20-turn economic shock screen", "",
        f"Scenario `{result['scenario']}`, seed `{result['seed']}`, simulation "
        f"source commit(s) {', '.join(f'`{item}`' for item in source_commits) or '`unknown`'}. "
        "Turns 1-7 are pre-shock; the shock is active on turns 8-11 and removed "
        "before turn 12. Recovery is observed through turn 20.",
        "One paired seed per intervention is an exploratory screen, not a "
        "robustness or empirical-calibration claim.", "",
    ]
    for experiment_id in SCENARIO_EXPERIMENTS[result["scenario"]]:
        pair = result["experiments"][experiment_id]
        comparison = pair["comparison"]
        control = pair.get("control_result_data", {})
        treatment = pair.get("treatment_result_data", {})
        focus_good = EXPERIMENTS[experiment_id]["good"]
        target_tile = pair.get("target_tile", PREFERRED_TARGET_TILE)
        scenario = result["scenario"]
        if scenario == "supply_rivalry":
            goods = {"cotton", "cloth"}
            market_tiles = {row["tile"] for row in comparison["market_response"]
                            if row["good"] in goods}
        else:
            goods = ({"wood", "furniture"}
                     if experiment_id == "wood_supply_reduction" else {"furniture"})
            market_tiles = {target_tile}
        lines += [
            f"## {EXPERIMENTS[experiment_id]['title']}", "",
            f"Target tile `{target_tile}`. Turn-7 complete canonical states match: "
            f"**{comparison['pre_shock_states_match']}**. "
            f"Control trace: `{_display_path(pair['control_trace'])}`; treatment trace: "
            f"`{_display_path(pair['treatment_trace'])}`.", "",
            ("Treatment minus control in cotton markets at selected turns:" if scenario
             == "supply_rivalry" else
             f"Treatment minus control on `{target_tile}` at selected turns:"), "",
            ("| Turn | Tile | Good | Ref. delta | Paid VWAP delta | Bids | Offers | Imports | Supply | Sold | Output | Inventory |"
             if scenario == "supply_rivalry" else
             "| Turn | Tile | Good | Ref. delta | Paid VWAP delta | Bids | Offers | Imports | Supply | Sold | Output | Inventory | Food shortfall | Nonfood consumed |"),
            ("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
             if scenario == "supply_rivalry" else
             "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"),
        ]
        for row in comparison["market_response"]:
            if (row["tile"] not in market_tiles or row["good"] not in goods
                    or row["turn"] not in {7, 8, 9, 10, 11, 12, 15, 20}):
                continue
            value = row["values"]
            keys = ("reference_price_after", "transaction_vwap", "submitted_bids",
                    "offered_asks", "import_units", "offered_supply_units",
                    "units_sold", "production_units", "producer_inventory_units",
                    "food_intake.shortfall_units", "nonfood_consumption.units_consumed")
            if scenario == "supply_rivalry":
                keys = keys[:9]
            cells = [str(row["turn"]), row["tile"], row["good"]] + [
                _format(value[key]["treatment_minus_control"]) for key in keys]
            lines.append("| " + " | ".join(cells) + " |")
        lines += ["", f"Shock-window totals on turns 8-11 at `{target_tile}`:", "",
                  f"| {target_tile} measure | Control total | Treatment total | Delta | Paired turns |",
                  "|---|---:|---:|---:|---:|"]
        summary_rows = (
            ("units_sold", "Units sold", focus_good),
            ("submitted_bids", "Submitted bids", focus_good),
            ("offered_supply_units", "Recorded offered supply", focus_good),
            ("production_units", "Production", focus_good),
            ("food_intake.shortfall_units", "Food shortfall units", "food"),
            ("nonfood_consumption.units_consumed", "Nonfood units consumed", focus_good),
        )
        if scenario == "supply_rivalry":
            summary_rows = summary_rows[:-1]
        for key, label, good in summary_rows:
            summary = _window_summary(pair, good, key, SHOCK_START, SHOCK_END,
                                      target_tile)
            lines.append(
                f"| {label} | {_format(summary['control_total'])} | "
                f"{_format(summary['treatment_total'])} | {_format(summary['delta_total'])} | "
                f"{summary['paired_turns']}/{summary['expected_turns']} |"
            )
        for key, label in (("reference_price_after", "Mean reference-price delta"),
                           ("transaction_vwap", "Mean paid-VWAP delta")):
            summary = _window_summary(pair, focus_good, key, SHOCK_START, SHOCK_END,
                                      target_tile)
            lines.append(
                f"| {label} | - | - | {_format(summary['mean_delta'])} | "
                f"{summary['paired_turns']}/{summary['expected_turns']} |"
            )
        lines += ["", "Totals use only paired observations; denominators show "
                  "coverage, and missing values remain unavailable.", "",
                  "### Audit gates", "",
                  _quality_line("control", control),
                  _quality_line("treatment", treatment), "",
                  "Structural and supported-formula checks cover only audited "
                  "rules; complete causal coverage is not established. Nation "
                  "account closes and treasury attribution are reported above; "
                  "neither gate establishes complete goods-stock conservation "
                  "or causal coverage. See the plan for remaining limits.", ""]
        if scenario == "supply_rivalry":
            control_summary = _scenario_observation_summary(control)
            treatment_summary = _scenario_observation_summary(treatment)
            lines += [
                "### Named actors and cotton logistics", "",
                "| Shock-window observation | Control | Treatment | Treatment minus control |",
                "|---|---:|---:|---:|",
            ]
            for key, label in (
                    ("cotton_market_fills", "Cotton market fills (units)"),
                    ("mill_submitted_bid_units", "Meridian Mill submitted bids (units)"),
                    ("mill_desired_target_sum", "Meridian Mill desired target on observed orders"),
                    ("mill_unshocked_target_sum", "Unshocked target on observed mill orders"),
                    ("route_departures", "Cotton route departures (units)"),
                    ("route_arrivals", "Cotton route arrivals (units)"),
                    ("grower_food_intake", "Named growers' food intake (units)")):
                left, right = control_summary[key], treatment_summary[key]
                lines.append(f"| {label} | {_format(left)} | {_format(right)} | "
                             f"{_format(right - left)} |")
            lines += [
                "",
                f"Route event coverage: control {control_summary['route_departure_events']} "
                f"departures and {control_summary['route_arrival_events']} arrivals; "
                f"treatment {treatment_summary['route_departure_events']} departures "
                f"and {treatment_summary['route_arrival_events']} arrivals. Mill cotton "
                f"order events observed: control {control_summary['mill_order_events']} "
                f"and treatment {treatment_summary['mill_order_events']}; the target "
                f"override appears on {treatment_summary['mill_override_order_events']} "
                f"treatment order rows. Across all 20 turns, cotton route events were "
                f"{control_summary['run_route_departure_events']} departures / "
                f"{control_summary['run_route_arrival_events']} arrivals in control "
                f"and {treatment_summary['run_route_departure_events']} / "
                f"{treatment_summary['run_route_arrival_events']} in treatment. Named-actor "
                f"turn rows observed during the shock: {control_summary['actor_turns_observed']} "
                f"control and {treatment_summary['actor_turns_observed']} treatment.", "",
                "The table below reports the named growers and mills at the end of "
                "the shock window. Cash and inventories are state observations; they "
                "are not by themselves a complete welfare or goods-conservation measure.", "",
                "| Actor | Turn | Control cash | Treatment cash | Delta | Control food | Treatment food | Control cotton | Treatment cotton | Control cloth | Treatment cloth |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
            control_actors = {(row["actor_id"], row["turn"]): row
                              for row in _scenario_actor_rows(control)}
            treatment_actors = {(row["actor_id"], row["turn"]): row
                                for row in _scenario_actor_rows(treatment)}
            for actor_id, turn in sorted(set(control_actors) | set(treatment_actors)):
                if turn not in {7, 11}:
                    continue
                left = control_actors.get((actor_id, turn), {})
                right = treatment_actors.get((actor_id, turn), {})
                name = right.get("name") or left.get("name") or f"Actor {actor_id}"
                cash_left, cash_right = left.get("cash"), right.get("cash")
                cash_delta = (cash_right - cash_left
                              if isinstance(cash_left, (int, float))
                              and isinstance(cash_right, (int, float)) else None)
                cells = [name, str(turn), _format(cash_left), _format(cash_right),
                         _format(cash_delta), _format(left.get("food_stock")),
                         _format(right.get("food_stock")),
                         _format(left.get("cotton_stock")),
                         _format(right.get("cotton_stock")),
                         _format(left.get("cloth_stock")),
                         _format(right.get("cloth_stock"))]
                lines.append("| " + " | ".join(cells) + " |")
            hook = pair.get("intervention_hook_passed", {})
            lines += ["", f"Scenario-hook integrity: control `not applicable`; "
                      f"treatment `{hook.get('treatment')}`. The treatment hook "
                      "checks that native scenario stepping preserves the cotton "
                      "intervention through turn 11 and restores it before turn 12.", "",
                      "The route events link physical cotton departures to arrivals; "
                      "market fills are reported separately because arrival does not "
                      "guarantee sale to the target mill. Post-shock draws can diverge "
                      "after turn 7, so later arm differences are not draw-aligned.", ""]
        elif experiment_id == "wood_supply_reduction":
            lines += [
                "Read the intervention first against realized wood output, offers "
                "and sales, then against downstream furniture. The posted "
                "furniture reference is capped, so paid VWAP and quantities are "
                "needed to assess price pressure. Turn-7 states match, but later "
                "random streams are not draw-aligned after paths diverge.", "",
            ]
        else:
            lines += [
                "The intervention increases desired furniture stocks for half of "
                "eligible residents. Submitted bids show demand; price, fills, "
                "household consumption, food intake and budgets show whether it "
                "became realized welfare or displaced other spending.", "",
            ]
    lines += [
        "## Reproduction", "", "```sh",
        f"venv/bin/python economic_shock_experiment.py --seed {result['seed']} \\",
        f"  --scenario {result['scenario']} --out-dir "
        f"{_display_path(result['out_dir'])} --reuse-existing --audit",
        "```", "",
        "The JSON retains full turn panels, state snapshots, intervention IDs, "
        "pre-shock digests, audit gates and trace paths. Compressed traces are "
        "generated under `tmp/traces/` and are not checked into Git.", "",
    ]
    return "\n".join(lines)


def _run_parent(seed, out_dir, *, scenario="default", reuse_existing=False,
                audit_trace=False):
    if scenario not in SCENARIO_EXPERIMENTS:
        raise ValueError(f"unsupported scenario {scenario}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = str(seed)
    child_results = {}
    script = Path(__file__).resolve()
    for experiment_id in SCENARIO_EXPERIMENTS[scenario]:
        child_results[experiment_id] = {}
        for arm in ("control", "treatment"):
            child_path = out_dir / f"{experiment_id}-{arm}.json"
            if reuse_existing:
                if not child_path.exists():
                    raise FileNotFoundError(
                        f"cannot reuse missing child result {child_path}; run without --reuse-existing")
                child = json.loads(child_path.read_text())
                if (child.get("experiment") != experiment_id
                        or child.get("arm") != arm
                        or child.get("seed") != seed):
                    raise ValueError(
                        f"saved child result identity does not match requested "
                        f"{experiment_id}/{arm}/seed={seed}: {child_path}")
                trace_path = Path(child["trace_path"])
                if not trace_path.exists():
                    raise FileNotFoundError(f"reused compact trace is missing: {trace_path}")
                panel = analyze_trace(trace_path)
                child["market_panel"] = [
                    row for row in panel["panel"]
                    if 1 <= row["turn"] <= TURN_COUNT and row["good"] in CORE_GOODS
                ]
                child["trace_event_count"] = panel["event_count"]
                child["trace_market_clearing_missing_count"] = panel[
                    "market_clearing_missing_count"]
                child["market_mechanical_gates"] = _market_mechanical_gates(
                    child["market_panel"])
                if audit_trace:
                    child["trace_quality_gates"] = _trace_quality_gates(trace_path)
                elif "trace_quality_gates" not in child:
                    child["trace_quality_gates"] = None
                child_path.write_text(json.dumps(child, indent=2, sort_keys=True) + "\n")
                child_results[experiment_id][arm] = child
            else:
                command = [sys.executable, str(script), "--child",
                           "--experiment", experiment_id, "--arm", arm,
                           "--seed", str(seed), "--out", str(child_path)]
                if audit_trace:
                    command.append("--audit")
                subprocess.run(command, check=True, env=env)
                child_results[experiment_id][arm] = json.loads(child_path.read_text())

    experiments = {}
    for experiment_id, arms in child_results.items():
        control, treatment = arms["control"], arms["treatment"]
        if control["target_tile"] != treatment["target_tile"]:
            raise RuntimeError(
                f"paired arms selected different target tiles for {experiment_id}: "
                f"{control['target_tile']} != {treatment['target_tile']}")
        if control.get("target_tile_selection") != treatment.get("target_tile_selection"):
            raise RuntimeError(
                f"paired arms selected different actors for {experiment_id}")
        comparison = _compare_pair(control, treatment)
        if not comparison["pre_shock_states_match"]:
            raise RuntimeError(
                f"control/treatment starting states diverged before the shock: "
                f"{experiment_id}, seed {seed}")
        if (scenario == "supply_rivalry"
                and treatment.get("intervention_hook_passed") is not True):
            raise RuntimeError(
                f"supply-rivalry scenario overwrote or failed to restore the "
                f"{experiment_id} treatment hook")
        experiments[experiment_id] = {
            "target_tile": control["target_tile"],
            "target_selection": control.get("target_tile_selection"),
            "control_trace": control["trace_path"],
            "treatment_trace": treatment["trace_path"],
            "control_result": str(out_dir / f"{experiment_id}-control.json"),
            "treatment_result": str(out_dir / f"{experiment_id}-treatment.json"),
            "comparison": comparison,
            "control_result_data": _quality_payload(control),
            "treatment_result_data": _quality_payload(treatment),
            "intervention_hook_passed": {
                "control": control.get("intervention_hook_passed"),
                "treatment": treatment.get("intervention_hook_passed"),
            },
        }
    git = _git_info()
    result = {"scenario": scenario, "seed": seed,
              "out_dir": str(out_dir), "experiments": experiments,
              "analysis_source_commit": git["source_commit"],
              "analysis_worktree_dirty": git["tracked_worktree_dirty"],
              "reuse_existing_traces": reuse_existing,
              "deep_trace_audit_requested": audit_trace}
    result_path = out_dir / "paired-results.json"
    report_path = out_dir / "paired-results.md"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report_path.write_text(_render_report(result))
    print(json.dumps({"results": str(result_path), "report": str(report_path),
                      "pre_shock_match": {
                          name: pair["comparison"]["pre_shock_states_match"]
                          for name, pair in experiments.items()}}, sort_keys=True),
          flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--scenario", choices=tuple(SCENARIO_EXPERIMENTS),
                        default="default")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--experiment", choices=tuple(EXPERIMENTS))
    parser.add_argument("--arm", choices=("control", "treatment"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--audit", action="store_true",
                        help="run structural/formula and treasury trace audits")
    parser.add_argument("--reuse-existing", action="store_true",
                        help="reanalyze saved child JSON and compact traces without rerunning simulation")
    args = parser.parse_args()
    seed = (args.seed if args.seed is not None else
            812 if args.scenario == "supply_rivalry" else 4242)
    if args.child:
        if not args.experiment or not args.arm or not args.out:
            parser.error("child mode requires --experiment, --arm and --out")
        _run_child(args.experiment, args.arm, seed, args.out,
                   audit_trace=args.audit)
        return
    if args.out_dir is None:
        parser.error("--out-dir is required")
    _run_parent(seed, args.out_dir, scenario=args.scenario,
                reuse_existing=args.reuse_existing,
                audit_trace=args.audit)


if __name__ == "__main__":
    main()
