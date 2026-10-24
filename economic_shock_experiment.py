"""Run paired, trace-audited 20-turn economy shock screens.

Each control/treatment arm runs in a fresh process. The default screen uses the
same seed and compares complete canonical state (including RNG) after turn 7.

Example::

    venv/bin/python economic_shock_experiment.py --out-dir tmp/economic-shocks/seed-4242
    venv/bin/python economic_shock_experiment.py --seed 4242 \
        --out-dir tmp/economic-shocks/seed-4242 --reuse-existing --audit
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

from economic_shock_analysis import analyze_trace


TURN_COUNT = 20
SHOCK_START = 8
SHOCK_END = 11
RECOVERY_START = 12
PREFERRED_TARGET_TILE = "c50"
CORE_GOODS = ("food", "wood", "furniture")
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


def _apply_shock(server, experiment_id, tile):
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

    cohort = _eligible_demand_cohort(tile)
    affected = [agent for index, agent in enumerate(cohort) if index % 2 == 0]
    base_target = _default_target(tile, config["good"])
    overrides = dict(getattr(tile, "_analysis_demand_target_overrides", {}) or {})
    overrides[good] = {int(agent.id): config["factor"] for agent in affected}
    tile._analysis_demand_target_overrides = overrides
    event_id = _emit_intervention(
        server, tile, kind="economic_shock_applied", turn=SHOCK_START,
        metric_id="analysis.household_inventory_target_multiplier", unit="ratio",
        before=1.0, after=config["factor"],
        formula_id="analysis.household_inventory_target_multiplier.v1",
        inputs={"experiment": experiment_id, "good": config["good"],
                "intervention_target": "household desired inventory target",
                "base_target_units_at_start": base_target,
                "treated_target_units_at_start": max(
                    0, int(math.ceil(base_target * config["factor"]))),
                "eligible_household_count": len(cohort),
                "affected_agent_ids": [int(agent.id) for agent in affected],
                "assignment": "every other eligible resident by stable agent ID",
                "rounding": "ceil(base target multiplied by 1.5)",
                "shock_turns_inclusive": [SHOCK_START, SHOCK_END],
                "direct_transfer_or_money_creation": False})
    return {"tile": tile, "good": good, "event_id": event_id,
            "before": 1.0, "after": config["factor"],
            "base_target_units_at_start": base_target,
            "eligible_agent_ids": [int(agent.id) for agent in cohort],
            "affected_agent_ids": [int(agent.id) for agent in affected]}


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
    else:
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
    return _emit_intervention(
        server, tile, kind="economic_shock_removed", turn=RECOVERY_START,
        metric_id=metric_id, unit="ratio", before=config["factor"], after=1.0,
        formula_id=formula_id, inputs=inputs)


def _snapshot_rows(server, turn, target_tile):
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
            if tile_name != target_tile:
                continue
        else:
            continue
        tile = next((item for item in server.tiles if item.name == tile_name), None)
        rows.append({"turn": turn, "metric_id": metric_id, "tile": tile_name,
                     "good": good, "unit": unit,
                     "currency": getattr(tile, "home_currency", None),
                     "value": value})
    return rows


def _run_child(experiment_id, arm, seed, out_path, audit_trace=False):
    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    from sim_server.sim_server import SimServer

    Path("tmp/traces").mkdir(parents=True, exist_ok=True)
    server = SimServer(seed=seed, terrain_seed=seed, nation_seed=seed,
                       topology="voronoi", scenario_id=None,
                       autoplay_nations=False, trace_enabled=True)
    if server.run_trace is None:
        raise RuntimeError("the experiment runner requires an enabled trace")

    intervention = None
    removal_event_id = None
    pre_shock_state_digest = None
    final_state_digest = None
    time_series = []
    target_tile, target_selection = _select_target_tile(server, experiment_id)
    for next_turn in range(1, TURN_COUNT + 1):
        if next_turn == SHOCK_START and arm == "treatment":
            intervention = _apply_shock(server, experiment_id, target_tile)
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
        time_series.extend(_snapshot_rows(server, server.turn, target_tile.name))

    trace = server.run_trace
    trace_path = Path(trace.path)
    trace.publish()
    trace._compact_writer.close()
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
        "scenario": "default",
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
        "market_mechanical_gates": run.get("market_mechanical_gates"),
        "trace_quality_gates": run.get("trace_quality_gates"),
    }


def _display_path(value):
    path = Path(value)
    root = Path(__file__).resolve().parent
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(value)


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
    for experiment_id in EXPERIMENTS:
        pair = result["experiments"][experiment_id]
        comparison = pair["comparison"]
        control = pair.get("control_result_data", {})
        treatment = pair.get("treatment_result_data", {})
        focus_good = EXPERIMENTS[experiment_id]["good"]
        target_tile = pair.get("target_tile", PREFERRED_TARGET_TILE)
        goods = {"wood", "furniture"} if experiment_id == "wood_supply_reduction" else {"furniture"}
        lines += [
            f"## {EXPERIMENTS[experiment_id]['title']}", "",
            f"Target tile `{target_tile}`. Turn-7 complete canonical states match: "
            f"**{comparison['pre_shock_states_match']}**. "
            f"Control trace: `{_display_path(pair['control_trace'])}`; treatment trace: "
            f"`{_display_path(pair['treatment_trace'])}`.", "",
            f"Treatment minus control on `{target_tile}` at selected turns:", "",
            "| Turn | Good | Ref. delta | Paid VWAP delta | Bids | Offers | Imports | Supply | Sold | Output | Inventory | Food shortfall | Nonfood consumed |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in comparison["market_response"]:
            if (row["tile"] != target_tile or row["good"] not in goods
                    or row["turn"] not in {7, 8, 9, 10, 11, 12, 15, 20}):
                continue
            value = row["values"]
            keys = ("reference_price_after", "transaction_vwap", "submitted_bids",
                    "offered_asks", "import_units", "offered_supply_units",
                    "units_sold", "production_units", "producer_inventory_units",
                    "food_intake.shortfall_units", "nonfood_consumption.units_consumed")
            cells = [str(row["turn"]), row["good"]] + [
                _format(value[key]["treatment_minus_control"]) for key in keys]
            lines.append("| " + " | ".join(cells) + " |")
        lines += ["", "Shock-window totals on turns 8-11:", "",
                  f"| {target_tile} measure | Control total | Treatment total | Delta | Paired turns |",
                  "|---|---:|---:|---:|---:|"]
        for key, label, good in (
            ("units_sold", "Units sold", focus_good),
            ("submitted_bids", "Submitted bids", focus_good),
            ("offered_supply_units", "Recorded offered supply", focus_good),
            ("production_units", "Production", focus_good),
            ("food_intake.shortfall_units", "Food shortfall units", "food"),
            ("nonfood_consumption.units_consumed", "Nonfood units consumed", focus_good),
        ):
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
                  "account closes pass, but treasury reconciliation retains "
                  "unattributed turn residuals. See the plan for counts and "
                  "follow-up work.", ""]
        if experiment_id == "wood_supply_reduction":
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
        f"  --out-dir {_display_path(result['out_dir'])} --reuse-existing --audit",
        "```", "",
        "The JSON retains full turn panels, state snapshots, intervention IDs, "
        "pre-shock digests, audit gates and trace paths. Compressed traces are "
        "generated under `tmp/traces/` and are not checked into Git.", "",
    ]
    return "\n".join(lines)


def _run_parent(seed, out_dir, *, reuse_existing=False, audit_trace=False):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = str(seed)
    child_results = {}
    script = Path(__file__).resolve()
    for experiment_id in EXPERIMENTS:
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
        experiments[experiment_id] = {
            "target_tile": control["target_tile"],
            "control_trace": control["trace_path"],
            "treatment_trace": treatment["trace_path"],
            "control_result": str(out_dir / f"{experiment_id}-control.json"),
            "treatment_result": str(out_dir / f"{experiment_id}-treatment.json"),
            "comparison": _compare_pair(control, treatment),
            "control_result_data": _quality_payload(control),
            "treatment_result_data": _quality_payload(treatment),
        }
    git = _git_info()
    result = {"scenario": "default", "seed": seed,
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
    parser.add_argument("--seed", type=int, default=4242)
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
    if args.child:
        if not args.experiment or not args.arm or not args.out:
            parser.error("child mode requires --experiment, --arm and --out")
        _run_child(args.experiment, args.arm, args.seed, args.out,
                   audit_trace=args.audit)
        return
    if args.out_dir is None:
        parser.error("--out-dir is required")
    _run_parent(args.seed, args.out_dir,
                reuse_existing=args.reuse_existing,
                audit_trace=args.audit)


if __name__ == "__main__":
    main()
