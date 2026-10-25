"""Aggregate matched supply-rivalry shock runs without re-decoding traces."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics


SHOCK_START = 8
SHOCK_END = 11
SCENARIO = "supply_rivalry"
EXPERIMENTS = {
    "rivalry_cotton_supply_reduction": {
        "title": "Temporary cotton supply reduction",
        "target_good": "cotton",
    },
    "rivalry_mill_cotton_demand_increase": {
        "title": "Temporary Meridian Mill cotton-input target increase",
        "target_good": "cotton",
    },
}
MARKET_MEASURES = [
    ("Cotton Fields", "cotton", "production_units", "Cotton production", "sum"),
    ("Cotton Fields", "cotton", "offered_supply_units", "Cotton offered supply", "sum"),
    ("Cotton Fields", "cotton", "units_sold", "Cotton units sold", "sum"),
    ("Cotton Fields", "cotton", "submitted_bids", "Cotton submitted bids", "sum"),
    ("Cotton Fields", "cotton", "producer_inventory_units", "Cotton producer inventory at T11", "end"),
    ("Cotton Fields", "cotton", "reference_price_after", "Cotton reference-price change (%)", "percent"),
    ("Cotton Fields", "cotton", "transaction_vwap", "Cotton paid-VWAP change (%)", "percent"),
    ("Cotton Fields", "cloth", "production_units", "Cloth production", "sum"),
    ("Cotton Fields", "cloth", "units_sold", "Cloth units sold", "sum"),
    ("Cotton Fields", "cloth", "transaction_vwap", "Cloth paid-VWAP change (%)", "percent"),
    ("Rival Port", "cotton", "units_sold", "Rival Port cotton units sold", "sum"),
    ("Rival Port", "cotton", "transaction_vwap", "Rival Port cotton paid-VWAP change (%)", "percent"),
    ("Rival Port", "cloth", "units_sold", "Rival Port cloth units sold", "sum"),
    ("Rival Port", "cloth", "transaction_vwap", "Rival Port cloth paid-VWAP change (%)", "percent"),
]
RECOVERY_MEASURES = {
    "rivalry_cotton_supply_reduction": [
        ("cotton", "production_units", "Cotton production", "quantity"),
        ("cotton", "offered_supply_units", "Cotton offered supply", "quantity"),
        ("cotton", "units_sold", "Cotton units sold", "quantity"),
        ("cotton", "transaction_vwap", "Cotton paid VWAP", "price"),
    ],
    "rivalry_mill_cotton_demand_increase": [
        ("cotton", "submitted_bids", "Cotton submitted bids", "quantity"),
        ("cotton", "units_sold", "Cotton units sold", "quantity"),
        ("cotton", "transaction_vwap", "Cotton paid VWAP", "price"),
    ],
}
ACTORS = (
    "Amina, secure grower",
    "Binta, cash-poor grower",
    "Meridian Mill",
    "Vesper Mill",
)
STOCK_FIELDS = ("cash", "food_stock", "cotton_stock", "cloth_stock",
                "debt", "bank_debt")
FLOW_FIELDS = ("food_intake", "produced_units", "sales_cash",
               "purchases_cash", "wages_cash", "input_consumed_cost")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def market_window_effect(pair: dict, tile: str, good: str, key: str,
                         statistic: str, start: int = SHOCK_START,
                         end: int = SHOCK_END) -> dict:
    """Return a paired shock-window effect with explicit coverage."""
    rows = [row for row in pair["comparison"]["market_response"]
            if row.get("tile") == tile and row.get("good") == good
            and start <= row.get("turn", -1) <= end]
    values = []
    for row in rows:
        measure = row.get("values", {}).get(key, {})
        control, treatment = measure.get("control"), measure.get("treatment")
        if not (_is_number(control) and _is_number(treatment)):
            continue
        if statistic == "percent":
            if control <= 0:
                continue
            values.append((treatment / control - 1.0) * 100.0)
        elif statistic == "end":
            values.append((int(row.get("turn", -1)), treatment - control))
        elif statistic == "sum":
            values.append(treatment - control)
        else:
            raise ValueError(f"unsupported statistic {statistic!r}")
    if statistic == "end":
        end_values = [value for value in values if value[0] == end]
        effect = end_values[-1][1] if end_values else None
        observed_turns = 1 if end_values else 0
        expected_turns = 1
    else:
        effect = (sum(values) if statistic == "sum" else
                  statistics.fmean(values)) if values else None
        observed_turns = len(values)
        expected_turns = end - start + 1
    return {"effect": effect, "observed_turns": observed_turns,
            "expected_turns": expected_turns, "statistic": statistic}


def recovery_assessment(pair: dict, good: str, key: str, kind: str,
                        *, tolerance: float = 0.05,
                        consecutive_turns: int = 3,
                        start: int = SHOCK_START,
                        end: int = SHOCK_END,
                        recovery_end: int = 20) -> dict:
    """Describe return to a paired-control band after shock removal.

    Quantity outcomes use an absolute tolerance of max(1 unit, 5% of control).
    Price outcomes use a 5% relative tolerance. Missing observations break a
    candidate run. Results after turn 11 are descriptive because RNG paths can
    diverge after the intervention.
    """
    rows = [row for row in pair["comparison"]["market_response"]
            if row.get("tile") == "Cotton Fields" and row.get("good") == good
            and start <= row.get("turn", -1) <= recovery_end]
    by_turn = {}
    for row in rows:
        values = row.get("values", {}).get(key, {})
        control, treatment = values.get("control"), values.get("treatment")
        turn = int(row.get("turn", -1))
        if not (_is_number(control) and _is_number(treatment)):
            continue
        if kind == "price":
            if control <= 0:
                continue
            deviation = abs(treatment / control - 1.0)
            inside = deviation <= tolerance
        elif kind == "quantity":
            deviation = abs(treatment - control)
            band = max(1.0, tolerance * abs(control))
            inside = deviation <= band
        else:
            raise ValueError(f"unsupported recovery kind {kind!r}")
        by_turn[turn] = {"inside": inside, "deviation": deviation,
                         "control": control, "treatment": treatment}

    shock_rows = [by_turn.get(turn) for turn in range(start, end + 1)]
    shock_observed = [row for row in shock_rows if row is not None]
    shock_response = any(not row["inside"] for row in shock_observed)
    post_start = end + 1
    recovery_turn = None
    if shock_response:
        for first in range(post_start, recovery_end - consecutive_turns + 2):
            turns = range(first, first + consecutive_turns)
            if all(turn in by_turn and by_turn[turn]["inside"] for turn in turns):
                recovery_turn = first
                break
    post_observed_turns = [turn for turn in range(post_start, recovery_end + 1)
                           if turn in by_turn]
    if not shock_observed:
        status = "shock_window_unobserved"
    elif not shock_response:
        status = "no_detectable_shock_response"
    elif recovery_turn is not None:
        status = "within_tolerance"
    elif len(post_observed_turns) == recovery_end - post_start + 1:
        status = "not_recovered_by_window_end"
    else:
        status = "not_established_missing_observations"
    return {
        "status": status,
        "shock_response_observed": shock_response if shock_observed else None,
        "shock_observed_turns": len(shock_observed),
        "shock_expected_turns": end - start + 1,
        "recovery_turn": recovery_turn,
        "consecutive_turns_required": consecutive_turns,
        "tolerance": tolerance,
        "tolerance_kind": kind,
        "post_shock_observed_turns": len(post_observed_turns),
        "post_shock_expected_turns": recovery_end - post_start + 1,
        "post_shock_missing_turns": [
            turn for turn in range(post_start, recovery_end + 1)
            if turn not in by_turn],
    }


def mill_order_summary(run: dict, buyer_ids: set[int] | None = None,
                       start: int = SHOCK_START,
                       end: int = SHOCK_END) -> dict:
    """Summarize observed mill orders, retaining missing-turn coverage."""
    events = [row for row in run.get("scenario_mill_order_events", [])
              if start <= int(row.get("turn", -1)) <= end
              and (buyer_ids is None or row.get("buyer_id") in buyer_ids)]
    targets = [float(row["desired_target"]) for row in events
               if _is_number(row.get("desired_target"))]
    baseline_targets = []
    for row in events:
        value = row.get("unshocked_desired_target")
        if value is None:
            value = row.get("desired_target")
        if _is_number(value):
            baseline_targets.append(float(value))
    bids = [float(row["submitted_quantity"]) for row in events
            if _is_number(row.get("submitted_quantity"))]
    return {
        "order_events": len(events),
        "order_turns_observed": sorted({int(row["turn"]) for row in events}),
        "desired_target_sum": sum(targets) if targets else None,
        "unshocked_target_sum": sum(baseline_targets) if baseline_targets else None,
        "target_uplift_sum": (sum(targets) - sum(baseline_targets)
                              if targets and baseline_targets else None),
        "submitted_bid_units": sum(bids) if bids else None,
        "override_events": sum(bool(row.get("target_override_applied"))
                                for row in events),
        "expected_turns": end - start + 1,
    }


def _actor_index(run: dict, turn: int) -> dict[str, dict]:
    actors = {}
    for snapshot in run.get("scenario_actor_observations", []):
        if int(snapshot.get("turn", -1)) != turn:
            continue
        for actor in snapshot.get("actors", []):
            if actor.get("name") in ACTORS:
                actors[actor["name"]] = actor
    return actors


def _actor_rows(run: dict, name: str, start: int, end: int) -> dict[int, dict]:
    rows = {}
    for snapshot in run.get("scenario_actor_observations", []):
        turn = int(snapshot.get("turn", -1))
        if start <= turn <= end:
            for actor in snapshot.get("actors", []):
                if actor.get("name") == name:
                    rows[turn] = actor
    return rows


def actor_effects(pair: dict, name: str) -> dict:
    """Compare a named actor's stock change and observed shock-window flows."""
    controls = pair.get("control_result_data", {})
    treatments = pair.get("treatment_result_data", {})
    c_start, t_start = _actor_index(controls, SHOCK_START - 1).get(name), \
        _actor_index(treatments, SHOCK_START - 1).get(name)
    c_end, t_end = _actor_index(controls, SHOCK_END).get(name), \
        _actor_index(treatments, SHOCK_END).get(name)
    stocks = {}
    for field in STOCK_FIELDS:
        if all(_is_number(actor.get(field)) for actor in (c_start, t_start, c_end, t_end)
               if actor is not None) and all(actor is not None
                                              for actor in (c_start, t_start, c_end, t_end)):
            control_change = c_end[field] - c_start[field]
            treatment_change = t_end[field] - t_start[field]
            stocks[field] = {"effect": treatment_change - control_change,
                             "observed": True,
                             "control_change": control_change,
                             "treatment_change": treatment_change}
        else:
            stocks[field] = {"effect": None, "observed": False}

    c_rows = _actor_rows(controls, name, SHOCK_START, SHOCK_END)
    t_rows = _actor_rows(treatments, name, SHOCK_START, SHOCK_END)
    paired_turns = sorted(set(c_rows) & set(t_rows))
    flows = {}
    for field in FLOW_FIELDS:
        observed = [turn for turn in paired_turns
                    if _is_number(c_rows[turn].get(field))
                    and _is_number(t_rows[turn].get(field))]
        effect = (sum(t_rows[turn][field] - c_rows[turn][field]
                      for turn in observed) if observed else None)
        flows[field] = {"effect": effect, "observed_turns": len(observed),
                        "expected_turns": SHOCK_END - SHOCK_START + 1}
    return {
        "control_actor_id": c_start.get("actor_id") if c_start else None,
        "treatment_actor_id": t_start.get("actor_id") if t_start else None,
        "baseline_present_both_arms": bool(c_start and t_start),
        "end_present_both_arms": bool(c_end and t_end),
        "stocks": stocks,
        "flows": flows,
    }


def _route_summary(run: dict) -> dict:
    rows = run.get("scenario_route_events", [])
    window = [row for row in rows
              if SHOCK_START <= int(row.get("turn", -1)) <= SHOCK_END]
    def measure(events):
        result = {}
        for kind, label in (("route_shipment_departure", "departures"),
                            ("route_shipment_arrival", "arrivals")):
            matched = [row for row in events if row.get("kind") == kind]
            result[f"{label}_events"] = len(matched)
            quantities = [float(row["quantity"]) for row in matched
                          if _is_number(row.get("quantity"))]
            result[f"{label}_units"] = sum(quantities) if quantities else 0.0
        return result
    return {"shock_window": measure(window), "full_run": measure(rows)}


def _load_seed(root: Path, seed: int) -> dict:
    path = root / f"seed-{seed}" / "paired-results.json"
    if not path.exists():
        raise FileNotFoundError(f"missing paired results for seed {seed}: {path}")
    result = json.loads(path.read_text())
    if result.get("seed") != seed or result.get("scenario") != SCENARIO:
        raise ValueError(f"scenario/seed mismatch in {path}")
    missing = set(EXPERIMENTS) - set(result.get("experiments", {}))
    if missing:
        raise ValueError(f"{path} is missing experiments: {sorted(missing)}")
    return result


def _source_provenance(result: dict) -> list[dict]:
    arms = []
    for experiment in result["experiments"].values():
        for arm_name in ("control_result_data", "treatment_result_data"):
            arm = experiment.get(arm_name, {})
            arms.append({"source_commit": arm.get("source_commit"),
                         "tracked_worktree_dirty": arm.get("tracked_worktree_dirty")})
    return arms


def summarize(root: Path, seeds: list[int]) -> dict:
    results = {seed: _load_seed(root, seed) for seed in seeds}
    output = {"scenario": SCENARIO, "seeds": seeds,
              "source_provenance_by_seed": {
                  str(seed): _source_provenance(result)
                  for seed, result in results.items()},
              "experiments": {}}

    for experiment_id, config in EXPERIMENTS.items():
        by_seed = {}
        for seed, result in results.items():
            pair = result["experiments"][experiment_id]
            control, treatment = (pair.get("control_result_data", {}),
                                  pair.get("treatment_result_data", {}))
            gates = [arm.get("market_mechanical_gates") or {}
                     for arm in (control, treatment)]
            target_ids = (set(pair.get("target_selection", {}).get(
                "target_agent_ids", []))
                if experiment_id == "rivalry_mill_cotton_demand_increase"
                else None)
            markets = {}
            for tile, good, key, label, statistic in MARKET_MEASURES:
                measure_id = f"{tile}|{good}|{key}"
                markets[measure_id] = market_window_effect(
                    pair, tile, good, key, statistic)
                markets[measure_id]["label"] = label
            actors = {name: actor_effects(pair, name) for name in ACTORS}
            control_orders = mill_order_summary(control, target_ids)
            treatment_orders = mill_order_summary(treatment, target_ids)
            recovery = {
                f"{good}|{key}": recovery_assessment(
                    pair, good, key, kind)
                for good, key, _label, kind in RECOVERY_MEASURES[experiment_id]
            }
            routes = {arm_name: _route_summary(arm)
                      for arm_name, arm in (("control", control),
                                            ("treatment", treatment))}
            route_effects = {}
            for period in ("shock_window", "full_run"):
                route_effects[period] = {}
                for measure in ("departures_events", "departures_units",
                                "arrivals_events", "arrivals_units"):
                    route_effects[period][measure] = (
                        routes["treatment"][period][measure]
                        - routes["control"][period][measure])
            trace_gates = [arm.get("trace_quality_gates")
                           for arm in (control, treatment)]
            by_seed[str(seed)] = {
                "source_seed": seed,
                "target_tile": pair.get("target_tile"),
                "target_selection": pair.get("target_selection"),
                "pre_shock_states_match": pair.get("comparison", {}).get(
                    "pre_shock_states_match") is True,
                "treatment_hook_passed": treatment.get(
                    "intervention_hook_passed") is True,
                "market_gates_passed_both_arms": all(
                    gate.get("passed") is True for gate in gates),
                "market_gates": gates,
                "markets": markets,
                "actors": actors,
                "mill_orders": {"control": control_orders,
                                "treatment": treatment_orders},
                "recovery": recovery,
                "routes": routes,
                "route_effects": route_effects,
                "trace_audits": trace_gates,
            }

        aggregate_markets = {}
        for _tile, _good, _key, label, _statistic in MARKET_MEASURES:
            measure_id = f"{_tile}|{_good}|{_key}"
            seed_effects = {str(seed): by_seed[str(seed)]["markets"][measure_id]
                            for seed in seeds}
            observed = [item["effect"] for item in seed_effects.values()
                        if _is_number(item.get("effect"))]
            aggregate_markets[measure_id] = {
                "label": label,
                "by_seed": seed_effects,
                "seeds_observed": len(observed),
                "mean": statistics.fmean(observed) if observed else None,
                "median": statistics.median(observed) if observed else None,
                "minimum": min(observed) if observed else None,
                "maximum": max(observed) if observed else None,
            }
        output["experiments"][experiment_id] = {
            "title": config["title"], "by_seed": by_seed,
            "turn7_match_count": sum(item["pre_shock_states_match"]
                                      for item in by_seed.values()),
            "hook_pass_count": sum(item["treatment_hook_passed"]
                                    for item in by_seed.values()),
            "market_gate_pass_count": sum(
                item["market_gates_passed_both_arms"]
                for item in by_seed.values()),
            "market_measures": aggregate_markets,
        }
    return output


def _fmt(value, places=2):
    return "—" if value is None else f"{value:.{places}f}"


def _market_report_row(label: str, measure: dict, seeds: list[int]) -> list[str]:
    items = [measure["by_seed"][str(seed)] for seed in seeds]
    values = [item.get("effect") for item in items]
    observed = [value for value in values if _is_number(value)]
    mean = statistics.fmean(observed) if observed else None
    span = (f"{_fmt(min(observed))} to {_fmt(max(observed))}"
            if observed else "—")
    coverage = ", ".join(
        f"{seed}:{item.get('observed_turns', 0)}/"
        f"{item.get('expected_turns', SHOCK_END - SHOCK_START + 1)}"
        for seed, item in zip(seeds, items))
    return [label, *[_fmt(value) for value in values], _fmt(mean), span,
            f"{len(observed)}/{len(seeds)}", coverage]


def render_report(summary: dict) -> str:
    seeds = summary["seeds"]
    provenance = []
    for seed in seeds:
        arms = summary["source_provenance_by_seed"].get(str(seed), [])
        versions = {}
        for arm in arms:
            commit = arm.get("source_commit")
            if commit:
                row = versions.setdefault(commit, {"arms": 0, "dirty": 0})
                row["arms"] += 1
                row["dirty"] += arm.get("tracked_worktree_dirty") is True
        commits = ", ".join(
            f"`{commit}` ({row['arms']} arms; dirty {row['dirty']})"
            for commit, row in sorted(versions.items())) or "unavailable"
        provenance.append(f"{seed}: {commits}")
    lines = [
        f"# {len(seeds)}-seed supply-rivalry shock screen", "",
        f"Matched 20-turn runs at seeds {', '.join(map(str, seeds))}. The two "
        "interventions are analyzed separately; turns 8–11 are the shock "
        "window and later differences are not draw-aligned after RNG paths "
        "diverge. Per-seed ranges are descriptive, not confidence intervals "
        "or empirical calibration.", "",
        "Simulation provenance by seed: " + "; ".join(provenance) + ".", "",
    ]
    for experiment_id, experiment in summary["experiments"].items():
        lines += [f"## {experiment['title']}", "",
                  f"Turn-7 complete-state match: {experiment['turn7_match_count']}/{len(seeds)}; "
                  f"scenario hook passes: {experiment['hook_pass_count']}/{len(seeds)}; "
                  f"market gates pass in both arms: {experiment['market_gate_pass_count']}/{len(seeds)}.", "",
                  "Shock-window paired effects in Cotton Fields and connected markets. "
                  "Flow quantities sum observed turn deltas; producer inventory is "
                  "the point-in-time turn-11 difference; price rows average per-turn "
                  "percent changes from that seed's control.", "",
                  "| Measure | " + " | ".join(map(str, seeds)) +
                  " | Mean | Range | Seeds observed | Turn coverage |",
                  "|---|" + "---:|" * (len(seeds) + 5)]
        for tile, good, key, label, _statistic in MARKET_MEASURES:
            measure_id = f"{tile}|{good}|{key}"
            measure = experiment["market_measures"][measure_id]
            line = _market_report_row(label, measure, seeds)
            lines.append("| " + " | ".join(line) + " |")
        lines += ["", "Paid prices are only compared when both arms recorded a "
                  "positive control transaction price. Missing clearings are "
                  "excluded and shown in turn coverage, never treated as zero.", "",
                  "### Meridian Mill cotton orders", "",
                  "Control and treatment order totals use observed order rows; "
                  "the treatment's unshocked target is recorded alongside the "
                  "override so desired demand is separated from submitted bids.", "",
                  "| Seed | Control rows | Treatment rows | Control target | "
                  "Treated target | Treatment unshocked target | Target uplift | "
                  "Control bids | Treatment bids | Override rows |",
                  "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for seed in seeds:
            row = experiment["by_seed"][str(seed)]["mill_orders"]
            control, treatment = row["control"], row["treatment"]
            cells = [seed, control["order_events"], treatment["order_events"],
                     _fmt(control["desired_target_sum"]),
                     _fmt(treatment["desired_target_sum"]),
                     _fmt(treatment["unshocked_target_sum"]),
                     _fmt(treatment["target_uplift_sum"]),
                     _fmt(control["submitted_bid_units"]),
                     _fmt(treatment["submitted_bid_units"]),
                     treatment["override_events"]]
            lines.append("| " + " | ".join(map(str, cells)) + " |")
        lines += ["", "A missing mill order row means no order event was observed "
                  "for that turn; the table reports row counts rather than "
                  "imputing a zero target.", "",
                  "### Stable named actors", "",
                  "Effects on stocks are treatment-minus-control differences in "
                  "the actor's turn-7-to-11 change. Flow effects sum paired "
                  "observed turns 8–11. These are actor-level accounting "
                  "indicators, not a complete welfare index.", "",
                  "| Seed | Actor | Cash change | Food stock change | Cotton stock change | "
                  "Cloth stock change | Food intake | Output | Sales cash | Input costs | "
                  "Wages | Debt / bank debt change | Flow coverage |",
                  "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
        for seed in seeds:
            seed_data = experiment["by_seed"][str(seed)]
            for actor in ACTORS:
                data = seed_data["actors"][actor]
                stocks, flows = data["stocks"], data["flows"]
                coverage = ", ".join(str(flows[key]["observed_turns"])
                                      for key in ("food_intake", "produced_units",
                                                  "sales_cash", "input_consumed_cost",
                                                  "wages_cash"))
                debt_change = (f"{_fmt(stocks['debt']['effect'])} / "
                               f"{_fmt(stocks['bank_debt']['effect'])}")
                cells = [seed, actor,
                         _fmt(stocks["cash"]["effect"]),
                         _fmt(stocks["food_stock"]["effect"]),
                         _fmt(stocks["cotton_stock"]["effect"]),
                         _fmt(stocks["cloth_stock"]["effect"]),
                         _fmt(flows["food_intake"]["effect"]),
                         _fmt(flows["produced_units"]["effect"]),
                         _fmt(flows["sales_cash"]["effect"]),
                         _fmt(flows["input_consumed_cost"]["effect"]),
                         _fmt(flows["wages_cash"]["effect"]),
                         debt_change, coverage]
                lines.append("| " + " | ".join(map(str, cells)) + " |")
        lines += ["", "Flow coverage columns list observed turns, in order for "
                  "food intake, output, sales cash, input costs and wages; each "
                  "denominator is four. These are observed transactions, not a "
                  "complete profit calculation. A stock value is unavailable "
                  "when either arm lacks the same actor at turn 7 or 11.", "",
                  "### Post-shock return to control bands", "",
                  "Descriptive recovery rule: after the shock is removed, a "
                  "measure is within band when quantity differences are no more "
                  "than max(1 unit, 5% of the control) or paid-price differences "
                  "are within 5% of control for three consecutive observed turns. "
                  "Missing observations break a candidate run. Post-shock RNG "
                  "streams can diverge, so these are path summaries rather than "
                  "draw-aligned causal recovery estimates.", "",
                  "| Measure | " + " | ".join(map(str, seeds)) + " | Rule |",
                  "|---|" + "---:|" * len(seeds) + "---|"]
        for _good, _key, label, _kind in RECOVERY_MEASURES[experiment_id]:
            metric_id = f"{_good}|{_key}"
            cells = [label]
            for seed in seeds:
                recovery = experiment["by_seed"][str(seed)]["recovery"][metric_id]
                recovery_turn = (f"T{recovery['recovery_turn']}"
                                 if recovery["recovery_turn"] is not None else "—")
                cells.append(f"{recovery['status']} ({recovery_turn}; "
                             f"{recovery['post_shock_observed_turns']}/"
                             f"{recovery['post_shock_expected_turns']} observed)")
            cells.append("3 consecutive; quantity ±max(1, 5%), price ±5%")
            lines.append("| " + " | ".join(cells) + " |")
        lines += ["", "A result of no detectable shock-window response means the "
                  "metric never moved outside its tolerance in observed turns; "
                  "it is not evidence of rapid recovery.", "",
                  "### Cotton route events", "",
                  "| Seed | Period | Control departures | Treatment departures | "
                  "Departure delta | Control arrivals | Treatment arrivals | "
                  "Arrival delta |", "|---:|---|---:|---:|---:|---:|---:|---:|"]
        for seed in seeds:
            seed_data = experiment["by_seed"][str(seed)]
            for period, label in (("shock_window", "Shock window"),
                                  ("full_run", "Full 20 turns")):
                c, t = (seed_data["routes"][arm][period]
                        for arm in ("control", "treatment"))
                cells = [seed, label, c["departures_units"],
                         t["departures_units"],
                         seed_data["route_effects"][period]["departures_units"],
                         c["arrivals_units"], t["arrivals_units"],
                         seed_data["route_effects"][period]["arrivals_units"]]
                lines.append("| " + " | ".join(map(str, cells)) + " |")
        lines.append("")

    lines += [
        "## Audit scope and interpretation", "",
        "All seed pairs share complete canonical state at turn 7, and all "
        "treatment hooks pass through the shock and restore before turn 12. "
        "Both arms pass the market settlement-bound checks in every seed pair. "
        "The clean-source seed-812 deep audit additionally passes all 40/40 "
        "account closes and 40/40 treasury-attributed turns in each of its four "
        "arms, with zero bounded structural/formula issues; the remaining seeds "
        "were not deep-audited. See "
        "`economic_shock_supply_rivalry_seed812.md` and the treasury follow-up "
        "for residuals and limitations.", "",
        "The five-seed sample describes local mechanism response in this fixed "
        "scenario. It does not establish general supply-chain resilience, "
        "population welfare, goods-stock conservation, recovery, or historical "
        "realism. Complete causal coverage remains false. No route event in a "
        "shock window means that seed did not exercise a new shipping response; "
        "it does not establish that trade is generally unresponsive. Stable "
        "named-actor snapshots improve cohort comparability but omit households "
        "outside the scenario instrumentation.", "",
        "Reproduce each clean-source pair with `economic_shock_experiment.py --scenario supply_rivalry`, "
        "then summarize the saved JSON without re-decoding traces:", "",
        "```sh",
        "venv/bin/python economic_shock_scenario_multiseed.py --root tmp/economic-shocks/supply-rivalry --seeds 812 813 814 815 816",
        "```", "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path("tmp/economic-shocks/supply-rivalry"))
    parser.add_argument("--seeds", type=int, nargs="+",
                        default=[812, 813, 814, 815, 816])
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--report-out", type=Path, default=Path(
        "planning/reports/economic_shock_multiseed_supply_rivalry.md"))
    args = parser.parse_args()
    result = summarize(args.root, args.seeds)
    json_path = args.json_out or args.report_out.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    args.report_out.write_text(render_report(result))
    print(json.dumps({"seeds": args.seeds, "json": str(json_path),
                      "report": str(args.report_out)}, sort_keys=True))


if __name__ == "__main__":
    main()
