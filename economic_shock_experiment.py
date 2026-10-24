"""Run paired, trace-audited 20-turn economy shock screens.

Each control/treatment arm runs in a fresh process. The default screen uses the
same seed and compares complete canonical state (including RNG) after turn 7.

Example::

    venv/bin/python economic_shock_experiment.py --out-dir tmp/economic-shocks/seed-4242
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
TARGET_TILE = "c50"
CORE_GOODS = ("food", "wood", "furniture")
MARKET_FIELDS = (
    "reference_price_after", "transaction_vwap", "demand_ratio",
    "funded_demand_units", "offered_supply_units", "submitted_bids",
    "offered_asks", "units_sold", "cash_collected",
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


def _apply_shock(server, experiment_id):
    from goods import Goods

    config = EXPERIMENTS[experiment_id]
    tile = next((item for item in server.tiles if item.name == TARGET_TILE), None)
    if tile is None:
        raise RuntimeError(f"target tile {TARGET_TILE!r} is absent from this seed")
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


def _snapshot_rows(server, turn):
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
            if tile_name != TARGET_TILE:
                continue
        else:
            continue
        tile = next((item for item in server.tiles if item.name == tile_name), None)
        rows.append({"turn": turn, "metric_id": metric_id, "tile": tile_name,
                     "good": good, "unit": unit,
                     "currency": getattr(tile, "home_currency", None),
                     "value": value})
    return rows


def _run_child(experiment_id, arm, seed, out_path):
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
    for next_turn in range(1, TURN_COUNT + 1):
        if next_turn == SHOCK_START and arm == "treatment":
            intervention = _apply_shock(server, experiment_id)
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
        time_series.extend(_snapshot_rows(server, server.turn))

    trace = server.run_trace
    trace_path = Path(trace.path)
    trace.publish()
    trace._compact_writer.close()
    panel = analyze_trace(trace_path)
    filtered_market_panel = [
        row for row in panel["panel"]
        if 1 <= row["turn"] <= TURN_COUNT and row["good"] in CORE_GOODS
    ]
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
        "target_tile": TARGET_TILE,
        "intervention": intervention_record,
        "intervention_removal_event_id": removal_event_id,
        "pre_shock_canonical_state_sha256": pre_shock_state_digest,
        "final_canonical_state_sha256": final_state_digest,
        "trace_path": str(trace_path),
        "trace_event_count": panel["event_count"],
        "trace_market_clearing_missing_count": panel["market_clearing_missing_count"],
        "market_panel": filtered_market_panel,
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
        compared.append({"turn": key[0], "tile": key[1], "good": key[2],
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


def _render_report(result):
    lines = [
        "# Paired 20-turn economic shock screen",
        "",
        f"Scenario `{result['scenario']}`, seed `{result['seed']}`, source "
        f"commit `{result['source_commit']}`. Turns 1–7 are pre-shock; the "
        "shock is active on turns 8–11 and removed before turn 12. Recovery "
        "is observed through turn 20.",
        "The sample is one paired seed per intervention and is exploratory, "
        "not a robustness or empirical-calibration claim.",
        "",
    ]
    for experiment_id, pair in result["experiments"].items():
        lines += [
            f"## {EXPERIMENTS[experiment_id]['title']}", "",
            f"Turn-7 full canonical states match: **{pair['comparison']['pre_shock_states_match']}**. "
            f"Control trace: `{pair['control_trace']}`. Treatment trace: "
            f"`{pair['treatment_trace']}`.",
            "",
            "Treatment minus control on c50:",
            "",
            "| Turn | Good | Ref. price Δ | Paid VWAP Δ | Bids Δ | Offers Δ | Sold Δ | Output Δ | Inventory Δ | Food shortfall Δ |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in pair["comparison"]["market_response"]:
            if row["tile"] != TARGET_TILE or row["good"] not in CORE_GOODS:
                continue
            v = row["values"]
            lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                row["turn"], row["good"],
                _format(v["reference_price_after"]["treatment_minus_control"]),
                _format(v["transaction_vwap"]["treatment_minus_control"]),
                _format(v["submitted_bids"]["treatment_minus_control"]),
                _format(v["offered_asks"]["treatment_minus_control"]),
                _format(v["units_sold"]["treatment_minus_control"]),
                _format(v["production_units"]["treatment_minus_control"]),
                _format(v["producer_inventory_units"]["treatment_minus_control"]),
                _format(v["food_intake.shortfall_units"]["treatment_minus_control"]),
            ))
        lines += [
            "",
            "At turns with missing market/transaction rows, the difference is "
            "shown as unavailable. A positive or negative response is not "
            "judged in isolation: prices, quantities, production, inventories "
            "and household outcomes must move together, with funding and trade "
            "channels checked in the linked traces.",
            "",
        ]
    lines += [
        "## Reproduction",
        "",
        "```sh",
        f"venv/bin/python economic_shock_experiment.py --seed {result['seed']} \\",
        f"  --out-dir {result['out_dir']}",
        "```",
        "",
        "The JSON result contains per-turn market and state series, exact "
        "intervention agent IDs, canonical pre-shock digests, and trace paths. "
        "These trace files are generated under `tmp/traces/` and are not "
        "checked into Git.",
        "",
    ]
    return "\n".join(lines)


def _run_parent(seed, out_dir):
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
            command = [sys.executable, str(script), "--child",
                       "--experiment", experiment_id, "--arm", arm,
                       "--seed", str(seed), "--out", str(child_path)]
            subprocess.run(command, check=True, env=env)
            child_results[experiment_id][arm] = json.loads(child_path.read_text())

    experiments = {}
    for experiment_id, arms in child_results.items():
        control, treatment = arms["control"], arms["treatment"]
        experiments[experiment_id] = {
            "control_trace": control["trace_path"],
            "treatment_trace": treatment["trace_path"],
            "control_result": str(out_dir / f"{experiment_id}-control.json"),
            "treatment_result": str(out_dir / f"{experiment_id}-treatment.json"),
            "comparison": _compare_pair(control, treatment),
        }
    git = _git_info()
    result = {"scenario": "default", "seed": seed,
              "out_dir": str(out_dir), "experiments": experiments,
              **git}
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
    args = parser.parse_args()
    if args.child:
        if not args.experiment or not args.arm or not args.out:
            parser.error("child mode requires --experiment, --arm and --out")
        _run_child(args.experiment, args.arm, args.seed, args.out)
        return
    if args.out_dir is None:
        parser.error("--out-dir is required")
    _run_parent(args.seed, args.out_dir)


if __name__ == "__main__":
    main()
