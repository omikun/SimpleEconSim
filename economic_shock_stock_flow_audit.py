"""Audit selected aggregate goods stocks against traced production and use.

The audit compares consecutive whole-world stock censuses in the
``supply_rivalry`` scenario with explicitly traced production, production
inputs, food inflows and consumption. Marketplace, public-transfer,
household-transfer, and route events are summarized as internal turnover; they
do not change whole-world stocks when both counterparties and route cargo are
inside the census boundary.

This is a bounded aggregate material-balance check, not a proof that every
possible goods writer or stock pool is instrumented. Food and wood are
included as diagnostic circuits; missing flows remain explicit audit failures.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from trace_codec import iter_payloads


AUDITED_GOODS = ("cotton", "cloth", "food", "wood")
PRODUCTION_KINDS = {"firm_production", "independent_production"}
FOOD_INFLOW_KINDS = {"foraged_food_receipt"}
INTERNAL_TURNOVER_KINDS = {
    "paid_market_sale", "government_food_purchase", "charity_food_purchase",
    "government_food_aid", "charity_food_aid", "household_food_transfer",
    "route_shipment_loaded", "route_shipment_departure",
    "route_shipment_progress", "route_shipment_arrival",
}


def _stock_totals(snapshot):
    totals = defaultdict(float)
    for row in snapshot.get("stocks", ()):
        good = row.get("good")
        if good in AUDITED_GOODS:
            quantity = float(row.get("quantity", 0.0))
            if not math.isfinite(quantity):
                raise ValueError(f"non-finite {good} stock in turn {snapshot.get('turn')}")
            totals[good] += quantity
    return dict(totals)


def _granary_food_total(snapshot):
    return sum(float(row.get("quantity", 0.0))
               for row in snapshot.get("stocks", ())
               if row.get("good") == "food"
               and row.get("pool") == "granary_food")


def audit_run(run, events, *, tolerance=1e-6):
    """Return interval balances and internal turnover counts for one arm."""
    snapshots = {}
    granary_stocks = {}
    issues = []
    expected_region_count = 1
    for snapshot in run.get("scenario_goods_stock_observations", ()):
        turn = int(snapshot["turn"])
        if turn in snapshots:
            issues.append({"kind": "duplicate_stock_snapshot", "turn": turn})
        snapshots[turn] = _stock_totals(snapshot)
        granary_stocks[turn] = _granary_food_total(snapshot)
        expected_region_count = int(
            (snapshot.get("coverage") or {}).get("region_count", 1))

    components = defaultdict(lambda: defaultdict(lambda: {
        "production": 0.0, "production_input_use": 0.0,
        "household_nonfood_use": 0.0, "civilian_food_use": 0.0,
        "military_food_use": 0.0, "food_inflow": 0.0,
    }))
    food_consumption_aggregate_regions = defaultdict(set)
    turnover = defaultdict(lambda: defaultdict(lambda: {
        "event_count": 0, "reported_quantity": 0.0,
    }))
    for row in events:
        turn = row.get("turn")
        if turn is None:
            continue
        turn = int(turn)
        kind = row.get("kind")
        subject = row.get("subject") or {}
        inputs = row.get("inputs") or {}
        good = subject.get("good") or inputs.get("good")

        if kind in PRODUCTION_KINDS:
            if good in AUDITED_GOODS:
                amount = float(row.get("value_after") or 0.0)
                components[turn][good]["production"] += amount
            input_amount = float(inputs.get(
                "input_quantity_used", inputs.get("inputs_used", 0.0)) or 0.0)
            if input_amount > tolerance:
                input_good = inputs.get("input_good")
                if input_good is None:
                    issues.append({
                        "kind": "missing_production_input_good",
                        "turn": turn,
                        "event_id": row.get("event_id"),
                        "output_good": good,
                        "input_good": input_good,
                        "input_quantity": input_amount,
                    })
                elif input_good in AUDITED_GOODS:
                    components[turn][input_good]["production_input_use"] += input_amount

        elif kind in FOOD_INFLOW_KINDS and good == "food":
            components[turn][good]["food_inflow"] += float(
                row.get("value_after") or 0.0)

        elif kind == "civilian_food_consumption_total" and good == "food":
            region = subject.get("tile") or subject.get("id")
            if region in food_consumption_aggregate_regions[turn]:
                issues.append({"kind": "duplicate_food_consumption_aggregate",
                               "turn": turn, "region": region})
            food_consumption_aggregate_regions[turn].add(region)
            amount = inputs.get("eaten_food_units", row.get("value_after", 0.0))
            components[turn][good]["civilian_food_use"] += float(amount or 0.0)

        elif kind == "army_ration_consumption" and good == "food":
            amount = inputs.get("food_consumed", 0.0)
            components[turn][good]["military_food_use"] += float(amount or 0.0)

        elif kind == "household_nonfood_consumption" and good in AUDITED_GOODS:
            amount = float(inputs.get("units_consumed", 0.0) or 0.0)
            if amount == 0.0:
                amount = max(0.0, -float(row.get("delta") or 0.0))
            components[turn][good]["household_nonfood_use"] += amount

        is_internal_turnover = (
            kind in INTERNAL_TURNOVER_KINDS
            or row.get("record_class") == "transfer"
        )
        if is_internal_turnover and good in AUDITED_GOODS:
            counter = turnover[good][kind]
            counter["event_count"] += 1
            quantity = None
            if kind == "paid_market_sale":
                quantity = row.get("value_after")
            elif kind == "granary_food_stock_transfer":
                quantity = inputs.get("units")
            elif kind in {"route_shipment_loaded", "route_shipment_departure",
                          "route_shipment_progress", "route_shipment_arrival"}:
                quantity = inputs.get("quantity")
            if quantity is not None:
                counter["reported_quantity"] += abs(float(quantity))
            if (kind == "paid_market_sale" and inputs.get("imported")
                    and not inputs.get("source_region")):
                issues.append({
                    "kind": "imported_market_sale_requires_boundary_review",
                    "turn": turn,
                    "event_id": row.get("event_id"),
                    "good": good,
                    "quantity": row.get("value_after"),
                })

    intervals = []
    for turn in sorted(snapshots):
        if turn - 1 not in snapshots:
            continue
        for good in AUDITED_GOODS:
            opening = snapshots[turn - 1].get(good, 0.0)
            closing = snapshots[turn].get(good, 0.0)
            flow = components[turn][good]
            expected_delta = (flow["production"]
                              - flow["production_input_use"]
                              - flow["household_nonfood_use"]
                              + flow["food_inflow"]
                              - flow["civilian_food_use"]
                              - flow["military_food_use"])
            actual_delta = closing - opening
            residual = actual_delta - expected_delta
            granary_delta = (granary_stocks.get(turn, 0.0)
                             - granary_stocks.get(turn - 1, 0.0)
                             if good == "food" else 0.0)
            intervals.append({
                "turn": turn,
                "good": good,
                "opening_stock": round(opening, 9),
                "closing_stock": round(closing, 9),
                "stock_delta": round(actual_delta, 9),
                "production": round(flow["production"], 9),
                "production_input_use": round(flow["production_input_use"], 9),
                "household_nonfood_use": round(flow["household_nonfood_use"], 9),
                "food_inflow": round(flow["food_inflow"], 9),
                "civilian_food_use": round(flow["civilian_food_use"], 9),
                "military_food_use": round(flow["military_food_use"], 9),
                "granary_stock_delta": round(granary_delta, 9),
                "instrumented_net_flow": round(expected_delta, 9),
                "residual": round(residual, 9),
                "balanced": abs(residual) <= tolerance,
            })

    for turn in range(2, int(run.get("completed_turns", 0)) + 1):
        if turn not in snapshots or turn - 1 not in snapshots:
            issues.append({"kind": "missing_consecutive_stock_snapshot", "turn": turn})
        elif len(food_consumption_aggregate_regions[turn]) != expected_region_count:
            issues.append({
                "kind": "incomplete_food_consumption_aggregates",
                "turn": turn,
                "expected_regions": expected_region_count,
                "observed_regions": len(food_consumption_aggregate_regions[turn]),
            })

    summaries = {}
    for good in AUDITED_GOODS:
        rows = [row for row in intervals if row["good"] == good]
        residuals = [abs(float(row["residual"])) for row in rows]
        summaries[good] = {
            "interval_count": len(rows),
            "balanced_interval_count": sum(row["balanced"] for row in rows),
            "max_absolute_residual": max(residuals, default=None),
            "absolute_residual_total": round(sum(residuals), 9),
            "production_units": round(sum(row["production"] for row in rows), 9),
            "production_input_units": round(sum(
                row["production_input_use"] for row in rows), 9),
            "household_nonfood_consumption_units": round(sum(
                row["household_nonfood_use"] for row in rows), 9),
            "civilian_food_consumption_units": round(sum(
                row["civilian_food_use"] for row in rows), 9),
            "military_food_consumption_units": round(sum(
                row["military_food_use"] for row in rows), 9),
            "foraged_food_units": round(sum(
                row["food_inflow"] for row in rows), 9),
            "granary_stock_change_units": round(sum(
                row["granary_stock_delta"] for row in rows), 9),
            "internal_turnover": dict(turnover[good]),
        }

    passed = (bool(intervals)
              and all(row["balanced"] for row in intervals)
              and not issues)
    return {
        "scenario": run.get("scenario"),
        "seed": run.get("seed"),
        "experiment": run.get("experiment"),
        "arm": run.get("arm"),
        "source_commit": run.get("source_commit"),
        "tracked_worktree_dirty": run.get("tracked_worktree_dirty"),
        "completed_turns": run.get("completed_turns"),
        "audited_goods": list(AUDITED_GOODS),
        "passed": passed,
        "issues": issues,
        "summary_by_good": summaries,
        "intervals": intervals,
    }


def audit_run_file(path):
    path = Path(path)
    run = json.loads(path.read_text())
    trace_path = Path(run["trace_path"])
    events = (json.loads(payload) for payload in iter_payloads(trace_path))
    result = audit_run(run, events)
    result["run_json"] = str(path)
    result["trace_path"] = str(trace_path)
    return result


def discover_runs(root, seeds):
    root = Path(root)
    intervention_arms = (
        "rivalry_cotton_supply_reduction-control",
        "rivalry_cotton_supply_reduction-treatment",
        "rivalry_mill_cotton_demand_increase-control",
        "rivalry_mill_cotton_demand_increase-treatment",
    )
    paths = []
    for seed in seeds:
        for arm in intervention_arms:
            path = root / f"seed-{seed}" / f"{arm}.json"
            if not path.is_file():
                raise FileNotFoundError(path)
            paths.append(path)
    return paths


def render_markdown(results):
    lines = [
        "# Selected-goods aggregate stock-flow audit",
        "",
        "This bounded audit compares consecutive whole-world stock censuses with",
        "traced production, recipe input use, food inflows and consumption.",
        "Marketplace, aid, other internal transfers and route events are counted",
        "as turnover, not net flow: both sides and route cargo are inside the",
        "census boundary. This does not prove every possible stock writer is",
        "instrumented, and does not cover goods beyond cotton, cloth, food and",
        "wood. Food includes regional granary stocks and one",
        "per-region civilian meal total each turn; army rations are separate.",
        "",
        "| Seed | Shock | Arm | Cotton | Cloth | Food | Wood | Issues |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for result in sorted(results, key=lambda row: (
            int(row["seed"]), row["experiment"], row["arm"])):
        shock = ("cotton supply" if "cotton_supply" in result["experiment"]
                 else "mill cotton demand")
        for_good = result["summary_by_good"]
        cells = [f"{for_good[good]['balanced_interval_count']}/"
                 f"{for_good[good]['interval_count']} (max "
                 f"{for_good[good]['max_absolute_residual']})"
                 for good in AUDITED_GOODS]
        lines.append(
            f"| {result['seed']} | {shock} | {result['arm']} | "
            f"{' | '.join(cells)} | "
            f"{len(result['issues'])} |"
        )
    all_intervals = [interval for result in results
                     for interval in result["intervals"]]
    aggregate = {}
    for good in AUDITED_GOODS:
        rows = [row for row in all_intervals if row["good"] == good]
        aggregate[good] = (
            sum(row["balanced"] for row in rows), len(rows),
            max((abs(row["residual"]) for row in rows), default=0.0))
    food_rows = [row for row in all_intervals if row["good"] == "food"]
    food_nonzero = [row for row in food_rows if abs(row["residual"]) > 1e-6]
    granary_signed_change = sum(row["granary_stock_delta"] for row in food_rows)
    granary_turnover = sum(
        result["summary_by_good"]["food"]["internal_turnover"].get(
            "granary_food_stock_transfer", {}).get("reported_quantity", 0.0)
        for result in results)
    granary_transfer_count = sum(
        result["summary_by_good"]["food"]["internal_turnover"].get(
            "granary_food_stock_transfer", {}).get("event_count", 0)
        for result in results)
    lines.extend([
        "",
        (f"Across this sample, cotton closes in {aggregate['cotton'][0]}/"
         f"{aggregate['cotton'][1]} intervals, cloth in "
         f"{aggregate['cloth'][0]}/{aggregate['cloth'][1]}, and wood in "
         f"{aggregate['wood'][0]}/{aggregate['wood'][1]}. Food closes in "
         f"{aggregate['food'][0]}/{aggregate['food'][1]}; its largest absolute "
         f"residual is {aggregate['food'][2]:.6g} units."),
        (f"There are {len(food_nonzero)} nonzero food residuals at the 1e-6 "
         f"tolerance. Summed interval granary-stock changes are "
         f"{granary_signed_change:.6g} units; {granary_transfer_count} traced "
         f"deposit/release transfers report {granary_turnover:.6g} units of "
         "internal turnover. Harvest deposits debit producer inventories and "
         "seasonal releases credit government food inventory, so these moves "
         "remain inside the census boundary."),
    ])
    source_commits = sorted({result.get("source_commit") for result in results})
    lines.extend([
        "",
        f"Simulation source commit(s): {', '.join(f'`{item}`' for item in source_commits)}.",
        "Each run excludes turn 1 because no pre-turn-1 stock census exists.",
        "Per-turn details and trace paths are in the JSON sidecar.",
        "",
        "The residual is closing stock minus prior closing stock and traced net flow. Food includes foraging, civilian meals and army rations; regional granaries are inside the stock boundary, so transfers into or out of them are internal. Zero aggregate residuals support the measured circuit but may hide offsetting unsupported flows; keep complete causal coverage false.",
        "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="root containing seed-N paired run JSON files")
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args(argv)
    results = [audit_run_file(path) for path in discover_runs(args.root, args.seeds)]
    report = {
        "scenario": "supply_rivalry",
        "audit": "whole-world selected-goods aggregate stock-flow v2",
        "tolerance": 1e-6,
        "run_count": len(results),
        "passed_run_count": sum(result["passed"] for result in results),
        "issue_count": sum(len(result["issues"]) for result in results),
        "runs": results,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.out_md.write_text(render_markdown(results))
    print(json.dumps({key: report[key] for key in (
        "run_count", "passed_run_count", "issue_count")}, sort_keys=True))
    return 0 if report["passed_run_count"] == report["run_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
