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
TRANSFORMATION_OUTPUTS = {
    # These operators add stock outside the regular region production pass.
    # Their execution result records the physical yield, but the ordinary
    # tile_production_total is emitted before the elite planning phase.
    "corvee_cotton_plantation": "cotton",
    "corvee_sugar_plantation": "sugar",
}
INTERNAL_TURNOVER_KINDS = {
    "paid_market_sale", "government_food_purchase", "charity_food_purchase",
    "government_food_aid", "charity_food_aid", "household_food_transfer",
    "route_shipment_loaded", "route_shipment_departure",
    "route_shipment_progress", "route_shipment_arrival",
}


def _stock_totals(snapshot, audited_goods=AUDITED_GOODS):
    totals = defaultdict(float)
    for row in snapshot.get("stocks", ()):
        good = row.get("good")
        if good in audited_goods:
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


def audit_run(run, events, *, tolerance=1e-6, audited_goods=None):
    """Return interval balances and internal turnover counts for one arm."""
    audited_goods = tuple(audited_goods or run.get("audited_goods")
                          or AUDITED_GOODS)
    snapshots = {}
    granary_stocks = {}
    issues = []
    expected_region_count = 1
    expected_active_regions_by_turn = {}
    stock_observations = (run.get("scenario_goods_stock_observations")
                          or run.get("default_goods_stock_observations") or ())
    for snapshot in stock_observations:
        turn = int(snapshot["turn"])
        if turn in snapshots:
            issues.append({"kind": "duplicate_stock_snapshot", "turn": turn})
        snapshots[turn] = _stock_totals(snapshot, audited_goods)
        granary_stocks[turn] = _granary_food_total(snapshot)
        coverage = snapshot.get("coverage") or {}
        expected_active_regions_by_turn[turn] = coverage.get(
            "economic_region_count")
        expected_region_count = int(coverage.get(
            "economic_region_count", coverage.get("region_count", 1)))

    components = defaultdict(lambda: defaultdict(lambda: {
        "production": 0.0, "production_aggregate": 0.0,
        "production_aggregate_event_count": 0,
        "operator_production": 0.0,
        "production_input_use": 0.0,
        "household_nonfood_use": 0.0, "civilian_food_use": 0.0,
        "military_food_use": 0.0, "food_inflow": 0.0,
        "fertilizer_stock_change": 0.0,
    }))
    food_consumption_aggregate_regions = defaultdict(set)
    production_aggregate_regions = defaultdict(set)
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

        if kind == "tile_production_total" and good in audited_goods:
            components[turn][good]["production_aggregate"] += float(
                row.get("value_after") or 0.0)
            components[turn][good]["production_aggregate_event_count"] += 1
            region = subject.get("tile") or subject.get("id")
            if region is not None:
                production_aggregate_regions[turn].add(region)

        elif kind == "elite_operator_execution":
            operator_id = inputs.get("operator_id")
            output_good = TRANSFORMATION_OUTPUTS.get(operator_id)
            execution = inputs.get("execution_result") or {}
            if output_good in audited_goods and execution.get("success"):
                quantity = execution.get("yield")
                if quantity is None:
                    quantity = execution.get("yield_received", 0.0)
                components[turn][output_good]["operator_production"] += float(
                    quantity or 0.0)

        elif kind in PRODUCTION_KINDS:
            if good in audited_goods:
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
                elif input_good in audited_goods:
                    components[turn][input_good]["production_input_use"] += input_amount

        elif kind in FOOD_INFLOW_KINDS and good == "food" \
                and "food" in audited_goods:
            components[turn][good]["food_inflow"] += float(
                row.get("value_after") or 0.0)

        elif (row.get("metric_id") == "ecology.fertilizer_stock"
              and "fertilizer" in audited_goods):
            before = row.get("value_before")
            after = row.get("value_after")
            if before is None or after is None:
                issues.append({
                    "kind": "fertilizer_stock_change_requires_before_after",
                    "turn": turn,
                    "event_id": row.get("event_id"),
                    "before": before,
                    "after": after,
                })
            else:
                components[turn]["fertilizer"][
                    "fertilizer_stock_change"] += float(after) - float(before)

        elif (kind == "civilian_food_consumption_total" and good == "food"
              and "food" in audited_goods):
            region = subject.get("tile") or subject.get("id")
            if region in food_consumption_aggregate_regions[turn]:
                issues.append({"kind": "duplicate_food_consumption_aggregate",
                               "turn": turn, "region": region})
            food_consumption_aggregate_regions[turn].add(region)
            amount = inputs.get("eaten_food_units", row.get("value_after", 0.0))
            components[turn][good]["civilian_food_use"] += float(amount or 0.0)

        elif (kind == "army_ration_consumption" and good == "food"
              and "food" in audited_goods):
            amount = inputs.get("food_consumed", 0.0)
            components[turn][good]["military_food_use"] += float(amount or 0.0)

        elif (kind == "household_nonfood_consumption"
              and good in audited_goods):
            amount = float(inputs.get("units_consumed", 0.0) or 0.0)
            if amount == 0.0:
                amount = max(0.0, -float(row.get("delta") or 0.0))
            components[turn][good]["household_nonfood_use"] += amount

        is_internal_turnover = (
            kind in INTERNAL_TURNOVER_KINDS
            or row.get("record_class") == "transfer"
        )
        if is_internal_turnover and good in audited_goods:
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
                    and not inputs.get("source_region")
                    and not inputs.get("seller_account_tile")):
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
        for good in audited_goods:
            opening = snapshots[turn - 1].get(good, 0.0)
            closing = snapshots[turn].get(good, 0.0)
            flow = components[turn][good]
            ordinary_production = (flow["production_aggregate"]
                                   if flow["production_aggregate_event_count"]
                                   else flow["production"])
            operator_production = flow["operator_production"]
            production = ordinary_production + operator_production
            fertilizer_stock_change = (
                flow["fertilizer_stock_change"]
                if good == "fertilizer" else 0.0)
            expected_delta = (production
                              - flow["production_input_use"]
                              - flow["household_nonfood_use"]
                              + flow["food_inflow"]
                              - flow["civilian_food_use"]
                              - flow["military_food_use"]
                              + fertilizer_stock_change)
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
                "production": round(production, 9),
                "production_source": (
                    ("tile_production_total" if
                     flow["production_aggregate_event_count"] else
                     "producer_outcomes") +
                    ("+elite_operator_execution" if operator_production else "")),
                "operator_production": round(operator_production, 9),
                "production_input_use": round(flow["production_input_use"], 9),
                "household_nonfood_use": round(flow["household_nonfood_use"], 9),
                "food_inflow": round(flow["food_inflow"], 9),
                "civilian_food_use": round(flow["civilian_food_use"], 9),
                "military_food_use": round(flow["military_food_use"], 9),
                "fertilizer_stock_change": round(fertilizer_stock_change, 9),
                "granary_stock_delta": round(granary_delta, 9),
                "instrumented_net_flow": round(expected_delta, 9),
                "residual": round(residual, 9),
                "balanced": abs(residual) <= tolerance,
            })

    for turn in range(2, int(run.get("completed_turns", 0)) + 1):
        if turn not in snapshots or turn - 1 not in snapshots:
            issues.append({"kind": "missing_consecutive_stock_snapshot", "turn": turn})
        elif "food" in audited_goods:
            expected = expected_active_regions_by_turn.get(turn)
            if expected is None:
                # Older default censuses stored the full map tile count. The
                # aggregate production totals identify the regions that ran
                # the active local economy in each turn.
                expected = (len(production_aggregate_regions[turn])
                            or expected_region_count)
            observed = len(food_consumption_aggregate_regions[turn])
            if observed == expected:
                continue
            issues.append({
                "kind": "incomplete_food_consumption_aggregates",
                "turn": turn,
                "expected_regions": expected,
                "observed_regions": observed,
            })

    summaries = {}
    for good in audited_goods:
        rows = [row for row in intervals if row["good"] == good]
        residuals = [abs(float(row["residual"])) for row in rows]
        summaries[good] = {
            "interval_count": len(rows),
            "balanced_interval_count": sum(row["balanced"] for row in rows),
            "max_absolute_residual": max(residuals, default=None),
            "absolute_residual_total": round(sum(residuals), 9),
            "production_units": round(sum(row["production"] for row in rows), 9),
            "operator_production_units": round(sum(
                row["operator_production"] for row in rows), 9),
            "production_input_units": round(sum(
                row["production_input_use"] for row in rows), 9),
            "household_nonfood_consumption_units": round(sum(
                row["household_nonfood_use"] for row in rows), 9),
            "civilian_food_consumption_units": round(sum(
                row["civilian_food_use"] for row in rows), 9),
            "military_food_consumption_units": round(sum(
                row["military_food_use"] for row in rows), 9),
            "fertilizer_stock_change_units": round(sum(
                row["fertilizer_stock_change"] for row in rows), 9),
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
        "audited_goods": list(audited_goods),
        "passed": passed,
        "issues": issues,
        "summary_by_good": summaries,
        "intervals": intervals,
    }


def audit_run_file(path, *, audited_goods=None):
    path = Path(path)
    run = json.loads(path.read_text())
    trace_path = Path(run["trace_path"])
    events = (json.loads(payload) for payload in iter_payloads(trace_path))
    result = audit_run(run, events, audited_goods=audited_goods)
    result["run_json"] = str(path)
    result["trace_path"] = str(trace_path)
    return result


def discover_runs(root, seeds, *, scenario="supply_rivalry"):
    root = Path(root)
    intervention_arms = (tuple(
        f"{experiment}-{arm}"
        for experiment in ("wood_supply_reduction", "furniture_demand_increase")
        for arm in ("control", "treatment")) if scenario == "default" else (
            "rivalry_cotton_supply_reduction-control",
            "rivalry_cotton_supply_reduction-treatment",
            "rivalry_mill_cotton_demand_increase-control",
            "rivalry_mill_cotton_demand_increase-treatment",
        ))
    paths = []
    for seed in seeds:
        for arm in intervention_arms:
            path = root / f"seed-{seed}" / f"{arm}.json"
            if not path.is_file():
                raise FileNotFoundError(path)
            paths.append(path)
    return paths


def render_markdown(results):
    goods = tuple(results[0].get("audited_goods", AUDITED_GOODS))
    detailed_goods = goods == AUDITED_GOODS
    all_physical_goods = len(goods) >= 10
    title = "All-physical-goods" if all_physical_goods else "Selected-goods"
    lines = [
        f"# {title} aggregate stock-flow audit",
        "",
        "This bounded audit compares consecutive whole-world stock censuses with",
        "traced production, recipe input use, food inflows and consumption.",
        "Marketplace, aid, other internal transfers and route events are counted",
        "as turnover, not net flow: both sides and route cargo are inside the",
        "census boundary. This does not prove every possible stock writer is",
        "instrumented. Food includes public stores, regional granaries and one",
        "per-region civilian meal total each turn; army rations are separate.",
        "",
    ]
    if detailed_goods:
        lines.extend([
            "| Seed | Shock | Arm | Cotton | Cloth | Food | Wood | Issues |",
            "|---:|---|---|---:|---:|---:|---:|---:|",
        ])
    else:
        lines.extend([
            "| Seed | Experiment | Arm | Balanced intervals | Issues |",
            "|---:|---|---|---:|---:|",
        ])
    for result in sorted(results, key=lambda row: (
            int(row["seed"]), row["experiment"], row["arm"])):
        for_good = result["summary_by_good"]
        if detailed_goods:
            if result.get("scenario") == "default":
                shock = ("wood supply" if "wood_supply" in result["experiment"]
                         else "furniture demand")
            else:
                shock = ("cotton supply" if "cotton_supply" in result["experiment"]
                         else "mill cotton demand")
            cells = [f"{for_good[good]['balanced_interval_count']}/"
                     f"{for_good[good]['interval_count']} (max "
                     f"{for_good[good]['max_absolute_residual']})"
                     for good in goods]
            lines.append(
                f"| {result['seed']} | {shock} | {result['arm']} | "
                f"{' | '.join(cells)} | {len(result['issues'])} |"
            )
        else:
            balanced = sum(item["balanced_interval_count"]
                           for item in for_good.values())
            intervals = sum(item["interval_count"]
                            for item in for_good.values())
            lines.append(
                f"| {result['seed']} | {result['experiment']} | "
                f"{result['arm']} | {balanced}/{intervals} | "
                f"{len(result['issues'])} |"
            )
    all_intervals = [interval for result in results
                     for interval in result["intervals"]]
    closed_runs = sum(bool(result.get("passed")) for result in results)
    structural_issues = sum(len(result.get("issues", ())) for result in results)
    aggregate = {}
    for good in goods:
        rows = [row for row in all_intervals if row["good"] == good]
        aggregate[good] = (
            sum(row["balanced"] for row in rows), len(rows),
            max((abs(row["residual"]) for row in rows), default=0.0))
    lines.extend([""])
    if detailed_goods:
        food_rows = [row for row in all_intervals if row["good"] == "food"]
        food_nonzero = [row for row in food_rows
                        if abs(row["residual"]) > 1e-6]
        granary_signed_change = sum(row["granary_stock_delta"]
                                    for row in food_rows)
        granary_turnover = sum(
            result["summary_by_good"]["food"]["internal_turnover"].get(
                "granary_food_stock_transfer", {}).get("reported_quantity", 0.0)
            for result in results)
        granary_transfer_count = sum(
            result["summary_by_good"]["food"]["internal_turnover"].get(
                "granary_food_stock_transfer", {}).get("event_count", 0)
            for result in results)
        lines.extend([
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
    else:
        lines.extend([
            "| Good | Balanced intervals | Total intervals | Max absolute residual |",
            "|---|---:|---:|---:|",
        ])
        for good in goods:
            balanced, total, maximum = aggregate[good]
            lines.append(f"| {good} | {balanced} | {total} | {maximum:.6g} |")
        lines.extend([
            "",
            f"Complete stock-flow closure: {closed_runs}/{len(results)} runs. "
            f"Structural or coverage issues: {structural_issues}. A run can "
            "have no structural issues and still fail because one or more "
            "good-stock intervals do not balance.",
        ])
        if "cotton" in goods and "sugar" in goods:
            cotton_output = sum(
                result["summary_by_good"]["cotton"].get(
                    "operator_production_units", 0.0) for result in results)
            sugar_output = sum(
                result["summary_by_good"]["sugar"].get(
                    "operator_production_units", 0.0) for result in results)
            lines.extend([
                "",
                ("The audit includes late corvée output from recorded elite "
                 "operator executions: "
                 f"{cotton_output:.6g} cotton and {sugar_output:.6g} sugar "
                 "units across the sample. These outputs occur after the "
                 "ordinary tile production total and otherwise appear as "
                 "unexplained stock increases."),
            ])
        fertilizer_deltas = [
            abs(interval.get("fertilizer_stock_change", 0.0))
            for interval in all_intervals
            if interval.get("good") == "fertilizer"
        ]
        if ("fertilizer" in goods
                and any(delta > 1e-6 for delta in fertilizer_deltas)):
            fertilizer_note = (
                " Traced before/after fertilizer-reserve changes are included "
                "in this sample's balance."
            )
        elif "fertilizer" in goods:
            fertilizer_note = (
                " This trace set has no nonzero source-linked fertilizer "
                "reserve changes, so fertilizer inflow/use attribution may "
                "be incomplete."
            )
        else:
            fertilizer_note = ""
        lines.extend([
            "",
            f"This {'all-physical-goods' if all_physical_goods else 'selected-goods'} "
            "view is a diagnostic screen. A nonzero "
            "residual identifies a stock-flow gap; zero residuals can still "
            "hide offsetting unsupported flows." + fertilizer_note,
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
    parser.add_argument("--scenario", choices=("supply_rivalry", "default"),
                        default="supply_rivalry")
    parser.add_argument("--all-goods", action="store_true",
                        help="audit all physical Goods plus fertilizer reserves")
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args(argv)
    audited_goods = AUDITED_GOODS
    if args.all_goods:
        from goods import Goods
        audited_goods = tuple(
            [good.name for good in Goods if good not in (Goods.gov, Goods.none)]
            + ["fertilizer"])
    results = [audit_run_file(path, audited_goods=audited_goods)
               for path in discover_runs(args.root, args.seeds,
                                          scenario=args.scenario)]
    report = {
        "scenario": args.scenario,
        "audit": ("whole-world physical-goods stock-flow diagnostic v1"
                  if args.all_goods else
                  "whole-world selected-goods aggregate stock-flow v2"),
        "audited_goods": list(audited_goods),
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
