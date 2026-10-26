"""Stream compact simulation traces into turn/tile/good economic panels.

The panel deliberately keeps absent observations as ``None`` and records event
coverage. In particular, a missing clearing or transaction-VWAP event is not a
zero trade or a zero price.

Example::

    python economic_shock_analysis.py run.ctr --json-out panel.json \
        --report-out baseline.md --source-commit <git-sha>
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from trace_codec import iter_payloads

PANEL_EVENT_KINDS = {
    "market_price_update",
    "market_price_decay",
    "market_demand_total",
    "market_supply_total",
    "market_clearing_summary",
    "market_transaction_vwap",
    "tile_production_total",
    "producer_inventory_total",
    "independent_production_zero",
    "firm_production_zero",
    "household_nonfood_consumption",
    "household_food_intake",
}


def _panel_row(panel: dict, turn: int, tile: str, good: str) -> dict:
    key = (turn, tile, good)
    if key not in panel:
        panel[key] = {
            "turn": turn,
            "tile": tile,
            "good": good,
            "currency": None,
            "market": {},
            "production_units": None,
            "producer_inventory_units": None,
            "food_intake": None,
            "nonfood_consumption": None,
            "production_zero_reasons": {},
            "production_zero_example_event_ids": {},
            "example_food_shortfall_event_id": None,
            "event_counts": {},
        }
    return panel[key]


def analyze_trace(path: str | Path) -> dict[str, Any]:
    """Read one compact trace in a single pass and return a compact panel."""
    panel: dict[tuple[int, str, str], dict] = {}
    event_counts: Counter[str] = Counter()
    food_counts: dict[tuple[int, str], Counter] = defaultdict(Counter)
    zero_counts: dict[tuple[int, str, str], Counter] = defaultdict(Counter)
    metadata: dict[str, Any] = {}
    turns: set[int] = set()
    run_ids: set[str] = set()

    for payload in iter_payloads(path):
        row = json.loads(payload)
        kind = row.get("kind")
        if kind is None:
            metadata.update(row)
            continue
        event_counts[kind] += 1
        turn = int(row.get("turn", 0))
        turns.add(turn)
        if row.get("run_id"):
            run_ids.add(row["run_id"])

        subject = row.get("subject") or {}
        inputs = row.get("inputs") or {}
        if kind not in PANEL_EVENT_KINDS:
            continue
        tile = subject.get("tile")
        if tile is None and subject.get("type") == "tile":
            tile = subject.get("id")
        good = subject.get("good") or inputs.get("good")
        if not tile or not good:
            continue

        key = (turn, str(tile), str(good))
        out = _panel_row(panel, *key)
        out["event_counts"][kind] = out["event_counts"].get(kind, 0) + 1
        event_id = row.get("event_id")
        market = out["market"]

        if kind in ("market_price_update", "market_price_decay"):
            market.update({
                "reference_price_before": row.get("value_before"),
                "reference_price_after": row.get("value_after"),
                "demand_ratio": inputs.get("demand_ratio"),
                "local_asks": inputs.get("local_asks"),
                "imported_asks": inputs.get("imported_asks"),
                "submitted_bids": inputs.get("bids"),
                "scarcity_term": inputs.get("scarcity"),
                "inflation_term": inputs.get("inflation_term"),
                "input_cost_floor": inputs.get("input_cost_floor"),
                "price_update_event_id": event_id,
            })
            out["currency"] = inputs.get("currency") or out["currency"]
        elif kind == "market_demand_total":
            market["funded_demand_units"] = row.get("value_after")
            market["demand_event_id"] = event_id
        elif kind == "market_supply_total":
            market["offered_supply_units"] = row.get("value_after")
            market["supply_event_id"] = event_id
        elif kind == "market_clearing_summary":
            market.update({
                "clearing_record_present": True,
                "submitted_bids": inputs.get("submitted_bids"),
                "offered_asks": inputs.get("offered_asks"),
                "units_sold": row.get("value_after"),
                "cash_collected": inputs.get("cash_collected"),
                "import_units": inputs.get("import_units"),
                "no_paid_sale": inputs.get("no_paid_sale"),
                "clearing_event_id": event_id,
            })
        elif kind == "market_transaction_vwap":
            market["transaction_vwap"] = row.get("value_after")
            market["transaction_vwap_event_id"] = event_id
            out["currency"] = inputs.get("currency") or out["currency"]
        elif kind == "tile_production_total":
            out["production_units"] = row.get("value_after")
            out["production_event_id"] = event_id
        elif kind == "producer_inventory_total":
            out["producer_inventory_units"] = row.get("value_after")
            out["producer_inventory_event_id"] = event_id
        elif kind == "household_nonfood_consumption":
            consumption = out["nonfood_consumption"]
            if consumption is None:
                consumption = {"records": 0, "units_consumed": 0,
                               "requested_units": 0,
                               "requested_observed_records": 0}
                out["nonfood_consumption"] = consumption
            consumption["records"] += 1
            consumption["units_consumed"] += int(
                inputs.get("units_consumed", row.get("value_before", 0) -
                           row.get("value_after", 0)) or 0)
            components = inputs.get("consumption_components") or ()
            requested = [component.get("requested_quantity")
                         for component in components
                         if component.get("requested_quantity") is not None]
            if requested:
                consumption["requested_units"] += sum(requested)
                consumption["requested_observed_records"] += 1
        elif kind in ("independent_production_zero", "firm_production_zero"):
            reason = str(inputs.get("reason", "unspecified"))
            zero_counts[(turn, str(tile), str(good))][reason] += 1
            out["production_zero_example_event_ids"].setdefault(reason, event_id)
        elif kind == "household_food_intake" and good == "food":
            food = food_counts[(turn, str(tile))]
            food["records"] += 1
            shortfall = float(inputs.get("food_shortfall_units", 0) or 0)
            food["shortfall_records"] += shortfall > 0
            food["shortfall_units"] += shortfall
            food["desired_units"] += float(inputs.get("desired_food_units", 0) or 0)
            food["eaten_units"] += float(inputs.get("eaten_food_units", 0) or 0)
            food["local_inventory_units_consumed"] += float(
                inputs.get("consumed_from_local_inventory_units", 0) or 0
            )
            food["zero_intake_records"] += int(
                float(inputs.get("eaten_food_units", 0) or 0) == 0
            )
            if shortfall > 0 and out["example_food_shortfall_event_id"] is None:
                out["example_food_shortfall_event_id"] = event_id

    for (turn, tile, good), reasons in zero_counts.items():
        _panel_row(panel, turn, tile, good)["production_zero_reasons"] = dict(reasons)
    for (turn, tile), food in food_counts.items():
        _panel_row(panel, turn, tile, "food")["food_intake"] = dict(food)

    for out in panel.values():
        market = out["market"]
        market["clearing_record_present"] = market.get("clearing_record_present", False)
        market["transaction_vwap_record_present"] = "transaction_vwap" in market
        market["reference_price_record_present"] = "reference_price_after" in market
        market["funded_demand_record_present"] = "funded_demand_units" in market
        market["offered_supply_record_present"] = "offered_supply_units" in market
        out["coverage"] = {
            "market_clearing": market["clearing_record_present"],
            "transaction_vwap": market["transaction_vwap_record_present"],
            "reference_price": market["reference_price_record_present"],
            "funded_demand": market["funded_demand_record_present"],
            "offered_supply": market["offered_supply_record_present"],
            "production": out["production_units"] is not None,
            "producer_inventory": out["producer_inventory_units"] is not None,
            "food_intake": out["food_intake"] is not None,
            "nonfood_consumption": out["nonfood_consumption"] is not None,
        }

    return {
        "source": str(Path(path)),
        "run_id": next(iter(run_ids)) if len(run_ids) == 1 else sorted(run_ids),
        "scenario": metadata.get("scenario"),
        "seed": metadata.get("seed"),
        "trace_schema_version": metadata.get("schema_version"),
        "storage_format": metadata.get("storage_format"),
        "event_count": sum(event_counts.values()),
        "turns_observed": sorted(turns),
        "event_counts": dict(sorted(event_counts.items())),
        "market_clearing_missing_count": sum(
            not row["coverage"]["market_clearing"]
            for row in panel.values()
            if row["market"]["reference_price_record_present"]
        ),
        "market_reference_observation_count": sum(
            row["coverage"]["reference_price"] for row in panel.values()
        ),
        "panel": sorted(panel.values(), key=lambda x: (x["turn"], x["tile"], x["good"])),
    }


def _index(panel: dict) -> dict[tuple[int, str, str], dict]:
    return {(row["turn"], row["tile"], row["good"]): row for row in panel["panel"]}


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return f"{value:.{digits}f}"
    return str(value)


def render_report(panel: dict, *, source_commit: str | None = None) -> str:
    ix = _index(panel)
    t10_food_tiles = ("c10", "c46", "c59")
    lines = [
        "# 20-turn economic baseline trace review",
        "",
        f"Trace run `{panel.get('run_id')}`; scenario `{panel.get('scenario')}`; "
        f"seed `{panel.get('seed')}`; {panel.get('event_count'):,} events over "
        f"turns {min(panel['turns_observed'])}–{max(panel['turns_observed'])}.",
        f"Source commit: `{source_commit or 'not supplied'}`. The trace is an "
        "observational startup run with no controlled shock or counterfactual.",
        "All prices below distinguish actual transaction VWAP from the posted "
        "reference; each market quantity uses the trace's recorded unit basis.",
        "",
        "## Furniture market: c50 (CNY)",
        "",
        "The local wood-to-furniture chain shows tight furniture supply and a "
        "persistent price cap. The counts below are recorded production-zero "
        "reasons; they are not additive lost units. Missing market records stay "
        "blank rather than being interpreted as zero.",
        "",
        "| Turn | Furniture ref. | Paid VWAP | Demand ratio | Bids | Offers | Sold | Furniture output | Missing-wood zeroes | Wood ref. | Wood sold |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    furniture_at_cap = 0
    for turn in range(1, 21):
        furniture = ix.get((turn, "c50", "furniture"), {})
        wood = ix.get((turn, "c50", "wood"), {})
        fm = furniture.get("market", {})
        wm = wood.get("market", {})
        price = fm.get("reference_price_after")
        furniture_at_cap += price is not None and price >= 50
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            turn,
            _fmt(price),
            _fmt(fm.get("transaction_vwap")),
            _fmt(fm.get("demand_ratio")),
            _fmt(fm.get("submitted_bids")),
            _fmt(fm.get("offered_asks")),
            _fmt(fm.get("units_sold")),
            _fmt(furniture.get("production_units")),
            _fmt(furniture.get("production_zero_reasons", {}).get("input_material_unavailable", 0)),
            _fmt(wm.get("reference_price_after")),
            _fmt(wm.get("units_sold")),
        ))
    lines += [
        "",
        f"The c50 furniture reference is at the hard cap on {furniture_at_cap} "
        "of 20 turns. Its actual paid VWAP reaches 61, exceeding the reference "
        "cap. At turn 10, the reference is 50, recorded demand ratio "
        "25, bids 50, offers 2, sales 2 and output 1; 17 zero-output events "
        "cite unavailable wood. The cap applies to the reference, not the paid "
        "VWAP. This supports a local intermediate-input bottleneck hypothesis, "
        "but does not prove that wood scarcity alone explains the price path: "
        "labor, input purchasing and producer entry also need to be separated.",
        "",
        "## Food: local supply versus household intake at turn 10",
        "",
        "| Tile | Currency | Ref. | Paid VWAP | Demand ratio | Bids | Offers | Sold | Production | Intake shortfalls | Shortfall units / desired |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for tile in t10_food_tiles:
        food = ix.get((10, tile, "food"), {})
        market = food.get("market", {})
        intake = food.get("food_intake") or {}
        desired = intake.get("desired_units")
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} / {} records | {} / {} |".format(
            tile,
            food.get("currency") or "—",
            _fmt(market.get("reference_price_after")),
            _fmt(market.get("transaction_vwap")),
            _fmt(market.get("demand_ratio")),
            _fmt(market.get("submitted_bids")),
            _fmt(market.get("offered_asks")),
            _fmt(market.get("units_sold")),
            _fmt(food.get("production_units")),
            _fmt(intake.get("shortfall_records")),
            _fmt(intake.get("records")),
            _fmt(intake.get("shortfall_units")),
            _fmt(desired),
        ))
    lines += [
        "",
        "c10 is the abundant-market comparison: offers substantially exceed "
        "funded bids, and the recorded intake cohort has no shortfall. At c46 "
        "and c59, local offers are below bids and many observed households "
        "still report shortfalls, despite positive local production. Production "
        "is not the same as food offered for sale or accessible to a household; "
        "inventory carryover, meal reserves, trader stocks, allocation and "
        "relief remain relevant. c46 is USD while c10 is JPY, so nominal prices "
        "cannot be compared across those tiles without an exchange-rate basis.",
        "",
        "Representative source events:",
        "",
    ]
    evidence = (
        ("c50 furniture, turn 10", (10, "c50", "furniture"), {
            "price update": ("market", "price_update_event_id"),
            "clearing": ("market", "clearing_event_id"),
            "paid-price VWAP": ("market", "transaction_vwap_event_id"),
            "production total": ("row", "production_event_id"),
            "missing-wood zero": ("zero", "input_material_unavailable"),
        }),
        ("c50 wood, turn 10", (10, "c50", "wood"), {
            "price update": ("market", "price_update_event_id"),
            "clearing": ("market", "clearing_event_id"),
            "production total": ("row", "production_event_id"),
        }),
        ("c46 food, turn 10", (10, "c46", "food"), {
            "price update": ("market", "price_update_event_id"),
            "clearing": ("market", "clearing_event_id"),
            "paid-price VWAP": ("market", "transaction_vwap_event_id"),
            "production total": ("row", "production_event_id"),
            "shortfall intake": ("row", "example_food_shortfall_event_id"),
        }),
    )
    for label, key, fields in evidence:
        row = ix.get(key, {})
        ids = []
        for display, (source, field) in fields.items():
            if source == "market":
                event_id = row.get("market", {}).get(field)
            elif source == "zero":
                event_id = row.get("production_zero_example_event_ids", {}).get(field)
            else:
                event_id = row.get(field)
            if event_id:
                ids.append(f"{display}: `{event_id}`")
        lines.append(f"- **{label}:** " + ("; ".join(ids) or "no linked events"))
    lines += [
        "",
        "## Coverage and limits",
        "",
        f"The analyzer found {panel['market_clearing_missing_count']} of "
        f"{panel['market_reference_observation_count']} market reference-price "
        "observations without a corresponding clearing summary. Its panel "
        "retains coverage flags and missing values. Food "
        "intake records are a trace-observed cohort, not a census denominator "
        "guaranteed to cover every resident or every turn.",
        "The current trace is strong for posted-price formulas, order totals, "
        "sales, production totals, producer inventories and recorded food "
        "intake. It does not by itself provide a complete household-cohort "
        "panel, all wage/profit/credit balances, or complete physical "
        "inventories in transit. Phase 2 must combine trace events with "
        "canonical state snapshots for matched comparisons, and must preserve "
        "coverage and missingness rather than filling gaps with zeros.",
        "",
        "## Reproduction",
        "",
        "```sh",
        "venv/bin/python economic_shock_analysis.py \\",
        "  tmp/trace-fat-analysis/prototype.source.ctr \\",
        "  --source-commit b523f5f939453f9de09f3fbba874ea99ecd76616 \\",
        "  --json-out tmp/economic-shock-baseline-panel.json \\",
        "  --report-out planning/reports/economic_shock_baseline.md",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="compact framed trace path")
    parser.add_argument("--json-out", type=Path, help="write the panel as JSON")
    parser.add_argument("--report-out", type=Path, help="write a Markdown report")
    parser.add_argument("--source-commit", help="simulation source commit SHA")
    args = parser.parse_args()

    panel = analyze_trace(args.trace)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(panel, indent=2, sort_keys=True) + "\n")
    report = render_report(panel, source_commit=args.source_commit)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
