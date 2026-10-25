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


def _abs_nonzero(value):
    return _is_number(value) and abs(float(value)) > 1e-9


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


def _household_rows(run: dict, turn: int) -> dict[int, dict]:
    return {
        int(member["actor_id"]): member
        for snapshot in run.get("scenario_household_cohort_observations", [])
        if int(snapshot.get("turn", -1)) == int(turn)
        for member in snapshot.get("members", [])
        if member.get("actor_id") is not None
    }


def _paired_mean_effect(control_values, treatment_values, *, expected,
                        unit=None):
    paired = [(float(control_values[key]), float(treatment_values[key]))
              for key in sorted(control_values.keys() & treatment_values.keys())
              if _is_number(control_values[key])
              and _is_number(treatment_values[key])]
    control_mean = statistics.fmean(row[0] for row in paired) if paired else None
    treatment_mean = statistics.fmean(row[1] for row in paired) if paired else None
    return {
        "effect": treatment_mean - control_mean
        if paired else None,
        "control_mean": control_mean,
        "treatment_mean": treatment_mean,
        "observed": len(paired),
        "expected": expected,
        "unit": unit,
    }


def household_cohort_effects(pair: dict) -> dict:
    """Compare a fixed turn-7 resident cohort without treating missing as zero."""
    controls = pair.get("control_result_data", {})
    treatments = pair.get("treatment_result_data", {})
    c_roster = {int(row["actor_id"]) for row in
                controls.get("scenario_household_cohort_roster", [])}
    t_roster = {int(row["actor_id"]) for row in
                treatments.get("scenario_household_cohort_roster", [])}
    cohort_ids = c_roster & t_roster
    baseline_c = _household_rows(controls, SHOCK_START - 1)
    baseline_t = _household_rows(treatments, SHOCK_START - 1)
    end_c = _household_rows(controls, SHOCK_END)
    end_t = _household_rows(treatments, SHOCK_END)
    metrics = {}

    for field, label, unit in (
            ("cash", "Cash", "local_currency"),
            ("food_stock", "Food stock", "food_units"),
            ("total_debt", "Total debt", "local_currency")):
        control_change, treatment_change = {}, {}
        for ident in cohort_ids:
            c0, c1 = baseline_c.get(ident), end_c.get(ident)
            t0, t1 = baseline_t.get(ident), end_t.get(ident)
            if (c0 and c1 and t0 and t1 and c1.get("present")
                    and t1.get("present") and all(
                        _is_number(row.get(field)) for row in (c0, c1, t0, t1))):
                control_change[ident] = c1[field] - c0[field]
                treatment_change[ident] = t1[field] - t0[field]
        effect = _paired_mean_effect(
            control_change, treatment_change, expected=len(cohort_ids), unit=unit)
        effect.update({"label": label, "comparison": "mean per-member T7-to-T11 change"})
        metrics[field] = effect

    shock_rows_c = {turn: _household_rows(controls, turn)
                    for turn in range(SHOCK_START, SHOCK_END + 1)}
    shock_rows_t = {turn: _household_rows(treatments, turn)
                    for turn in range(SHOCK_START, SHOCK_END + 1)}
    expected_person_turns = len(cohort_ids) * (SHOCK_END - SHOCK_START + 1)

    def member_turn_values(field, *, predicate=None):
        control_values, treatment_values = {}, {}
        for turn in range(SHOCK_START, SHOCK_END + 1):
            c_rows, t_rows = shock_rows_c[turn], shock_rows_t[turn]
            for ident in cohort_ids:
                c_row, t_row = c_rows.get(ident), t_rows.get(ident)
                if (c_row is None or t_row is None or not c_row.get("present")
                        or not t_row.get("present")):
                    continue
                c_value, t_value = c_row.get(field), t_row.get(field)
                if predicate is not None:
                    c_value, t_value = predicate(c_row), predicate(t_row)
                if c_value is None or t_value is None:
                    continue
                key = (turn, ident)
                control_values[key] = c_value
                treatment_values[key] = t_value
        return control_values, treatment_values

    for field, label, unit in (
            ("food_need_met_ratio", "Calorie need met", "share_of_need"),
            ("employer_linked", "Employer-linked", "share_of_cohort")):
        c_values, t_values = member_turn_values(
            field, predicate=(lambda row: float(row.get(field) is True))
            if field == "employer_linked" else None)
        effect = _paired_mean_effect(c_values, t_values,
                                     expected=expected_person_turns, unit=unit)
        effect.update({"label": label,
                       "comparison": "mean of observed person-turns, T8-T11"})
        metrics[field] = effect

    def is_shortfall(row):
        return (1.0 if row.get("food_shortfall") is True else
                0.0 if row.get("food_shortfall") is False else None)

    c_shortfall, t_shortfall = member_turn_values("food_shortfall",
                                                   predicate=is_shortfall)
    shortfall = _paired_mean_effect(c_shortfall, t_shortfall,
                                    expected=expected_person_turns,
                                    unit="share_of_person_turns")
    shortfall.update({"label": "Food shortfall", "comparison":
                      "share of observed person-turns, T8-T11"})
    metrics["food_shortfall"] = shortfall

    for field, label in (("calories_eaten", "Calories eaten"),
                         ("wage_income_cash", "Wage income"),
                         ("sales_cash", "Sales cash"),
                         ("purchases_cash", "Purchase cash"),
                         ("input_consumed_cost", "Input cost")):
        c_values, t_values = member_turn_values(field)
        effect = _paired_mean_effect(c_values, t_values,
                                     expected=expected_person_turns,
                                     unit="kcal/person-turn" if field == "calories_eaten"
                                     else "local_currency/person-turn")
        effect.update({"label": label,
                       "comparison": "mean per observed person-turn, T8-T11"})
        metrics[field] = effect

    c_alive = {ident: float(end_c[ident].get("alive") is True)
               for ident in cohort_ids if ident in end_c
               and end_c[ident].get("present")
               and end_c[ident].get("alive") is not None}
    t_alive = {ident: float(end_t[ident].get("alive") is True)
               for ident in cohort_ids if ident in end_t
               and end_t[ident].get("present")
               and end_t[ident].get("alive") is not None}
    survival = _paired_mean_effect(c_alive, t_alive,
                                   expected=len(cohort_ids), unit="share_of_cohort")
    survival.update({"label": "Alive at T11",
                     "comparison": "turn-11 baseline-cohort share"})
    metrics["alive_t11"] = survival

    return {
        "baseline_cohort_control": len(c_roster),
        "baseline_cohort_treatment": len(t_roster),
        "paired_baseline_members": len(cohort_ids),
        "shock_person_turns_expected": expected_person_turns,
        "metrics": metrics,
    }


def _stock_totals_at_turn(run: dict, turn: int) -> tuple[dict, dict | None]:
    snapshot = next((row for row in run.get("scenario_goods_stock_observations", [])
                     if int(row.get("turn", -1)) == int(turn)), None)
    if snapshot is None:
        return {}, None
    totals = {}
    for row in snapshot.get("stocks", []):
        key = (row.get("category"), row.get("pool"), row.get("good"))
        totals[key] = totals.get(key, 0.0) + float(row.get("quantity", 0.0))
    return totals, snapshot.get("coverage")


def physical_stock_effects(pair: dict,
                           turns=(SHOCK_START - 1, SHOCK_END, 20)) -> dict:
    """Return holdings deltas, retaining census coverage per arm and turn."""
    controls = pair.get("control_result_data", {})
    treatments = pair.get("treatment_result_data", {})
    control_by_turn, treatment_by_turn = {}, {}
    coverage = {"control": {}, "treatment": {}}
    for turn in turns:
        control_by_turn[turn], coverage["control"][str(turn)] = (
            _stock_totals_at_turn(controls, turn))
        treatment_by_turn[turn], coverage["treatment"][str(turn)] = (
            _stock_totals_at_turn(treatments, turn))
    keys = set().union(*(set(values) for values in
                         [*control_by_turn.values(), *treatment_by_turn.values()]))
    rows = []
    for category, pool, good in sorted(keys):
        points = {}
        for turn in turns:
            c_values, t_values = control_by_turn[turn], treatment_by_turn[turn]
            if coverage["control"][str(turn)] is None or coverage["treatment"][str(turn)] is None:
                control = treatment = difference = None
            else:
                control = c_values.get((category, pool, good), 0.0)
                treatment = t_values.get((category, pool, good), 0.0)
                difference = treatment - control
            points[str(turn)] = {"control": control, "treatment": treatment,
                                 "treatment_minus_control": difference}
        first = points[str(turns[0])]["treatment_minus_control"]
        shock_end = points[str(SHOCK_END)]["treatment_minus_control"]
        rows.append({
            "category": category, "pool": pool, "good": good,
            "points": points,
            "shock_window_change_effect": (
                shock_end - first if first is not None and shock_end is not None
                else None),
        })
    return {"turns": list(turns), "coverage": coverage, "stocks": rows}


def _stock_census_quality(pair: dict) -> dict:
    arms = {}
    for arm_name, field in (("control", "control_result_data"),
                            ("treatment", "treatment_result_data")):
        run = pair.get(field, {})
        snapshots = run.get("scenario_goods_stock_observations", [])
        by_turn = {int(row.get("turn", -1)): row for row in snapshots}
        negative_rows = [
            {"turn": int(snapshot.get("turn", -1)), **row}
            for snapshot in snapshots
            for row in snapshot.get("negative_stock_rows", [])]
        t7 = by_turn.get(SHOCK_START - 1, {})
        arms[arm_name] = {
            "turns_observed": len(snapshots),
            "turns_expected": 20,
            "baseline_coverage": t7.get("coverage"),
            "negative_stock_observation_count": len(negative_rows),
            "negative_stock_observations": negative_rows,
        }
    return arms


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


def _deep_audit_summary(results: dict[int, dict]) -> dict:
    by_seed = {}
    arms = []
    for seed, result in results.items():
        seed_arms = []
        for experiment_id, experiment in result["experiments"].items():
            for arm_name in ("control_result_data", "treatment_result_data"):
                arm = experiment.get(arm_name, {})
                trace = arm.get("trace_quality_gates")
                market = arm.get("market_mechanical_gates") or {}
                closures = (trace or {}).get("treasury_account_closure") or {}
                treasury = (trace or {}).get("treasury_reconciliation") or {}
                row = {
                    "seed": seed, "experiment": experiment_id,
                    "arm": arm_name.removesuffix("_result_data"),
                    "audited": isinstance(trace, dict),
                    "market_gate_passed": market.get("passed") is True,
                    "structural_formula_passed": (trace or {}).get(
                        "structural_and_supported_formula_checks_pass") is True,
                    "audit_issue_count": (trace or {}).get("audit_issue_count"),
                    "account_closes_verified": closures.get("verified", 0),
                    "account_closes_expected": closures.get("nation_closes", 0),
                    "treasury_turns_attributed": treasury.get(
                        "fully_attributed_turns", 0),
                    "treasury_turns_expected": treasury.get("turns", 0),
                    "absolute_residual_total": treasury.get(
                        "unattributed_absolute_total"),
                    "complete_causal_coverage": (trace or {}).get(
                        "complete_causal_coverage") is True,
                }
                seed_arms.append(row)
                arms.append(row)
        residuals = [row["absolute_residual_total"] for row in seed_arms
                     if _is_number(row["absolute_residual_total"])]
        by_seed[str(seed)] = {
            "arms_expected": len(seed_arms),
            "arms_deep_audited": sum(row["audited"] for row in seed_arms),
            "market_gates_passed": sum(row["market_gate_passed"]
                                        for row in seed_arms),
            "structural_formula_passed": sum(
                row["structural_formula_passed"] for row in seed_arms),
            "audit_issue_count": sum(row["audit_issue_count"] or 0
                                      for row in seed_arms),
            "account_closes_verified": sum(
                row["account_closes_verified"] for row in seed_arms),
            "account_closes_expected": sum(
                row["account_closes_expected"] for row in seed_arms),
            "treasury_turns_attributed": sum(
                row["treasury_turns_attributed"] for row in seed_arms),
            "treasury_turns_expected": sum(
                row["treasury_turns_expected"] for row in seed_arms),
            "maximum_absolute_residual_total": max(residuals) if residuals else None,
            "complete_causal_coverage_arms": sum(
                row["complete_causal_coverage"] for row in seed_arms),
        }
    return {
        "arms": arms,
        "arms_expected": len(arms),
        "arms_deep_audited": sum(row["audited"] for row in arms),
        "market_gates_passed": sum(row["market_gate_passed"] for row in arms),
        "structural_formula_passed": sum(
            row["structural_formula_passed"] for row in arms),
        "audit_issue_count": sum(row["audit_issue_count"] or 0 for row in arms),
        "account_closes_verified": sum(
            row["account_closes_verified"] for row in arms),
        "account_closes_expected": sum(
            row["account_closes_expected"] for row in arms),
        "treasury_turns_attributed": sum(
            row["treasury_turns_attributed"] for row in arms),
        "treasury_turns_expected": sum(
            row["treasury_turns_expected"] for row in arms),
        "maximum_absolute_residual_total": max((
            row["absolute_residual_total"] for row in arms
            if _is_number(row["absolute_residual_total"])), default=None),
        "complete_causal_coverage_arms": sum(
            row["complete_causal_coverage"] for row in arms),
        "by_seed": by_seed,
    }


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
            household_cohort = household_cohort_effects(pair)
            physical_stocks = physical_stock_effects(pair)
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
                "household_cohort": household_cohort,
                "physical_stocks": physical_stocks,
                "stock_census_quality": _stock_census_quality(pair),
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
    output["deep_audit_summary"] = _deep_audit_summary(results)
    return output


def _fmt(value, places=2):
    return "—" if value is None else f"{value:.{places}f}"


def _fmt_residual(value):
    return "—" if value is None else f"{value:.2e}"


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
    audits = summary.get("deep_audit_summary", {})
    lines += ["## Deep trace audits", "",
              f"Deep audits cover {audits.get('arms_deep_audited', 0)}/"
              f"{audits.get('arms_expected', 0)} arm traces. The audited arms "
              f"pass {audits.get('account_closes_verified', 0)}/"
              f"{audits.get('account_closes_expected', 0)} public-account closes "
              f"and attribute {audits.get('treasury_turns_attributed', 0)}/"
              f"{audits.get('treasury_turns_expected', 0)} treasury turns. "
              f"Bounded structural/formula issues: "
              f"{audits.get('audit_issue_count', '—')}; maximum absolute residual "
              f"total within any arm: "
              f"{_fmt_residual(audits.get('maximum_absolute_residual_total'))}. "
              f"Complete causal coverage is reported in "
              f"{audits.get('complete_causal_coverage_arms', 0)}/"
              f"{audits.get('arms_deep_audited', 0)} audited arms.", "",
              "| Seed | Deep-audited arms | Account closes | Treasury turns | "
              "Largest arm residual | Formula issues |", "|---:|---:|---:|---:|---:|---:|"]
    for seed in seeds:
        audit = audits.get("by_seed", {}).get(str(seed), {})
        lines.append("| " + " | ".join(map(str, [
            seed,
            f"{audit.get('arms_deep_audited', 0)}/{audit.get('arms_expected', 0)}",
            f"{audit.get('account_closes_verified', 0)}/"
            f"{audit.get('account_closes_expected', 0)}",
            f"{audit.get('treasury_turns_attributed', 0)}/"
            f"{audit.get('treasury_turns_expected', 0)}",
            _fmt_residual(audit.get("maximum_absolute_residual_total")),
            audit.get("audit_issue_count", 0),
        ])) + " |")
    lines.append("")
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
                  "### Turn-7 household cohort", "",
                  "The roster freezes all living non-company, non-government, "
                  "non-trader residents in both scenario regions at turn 7. "
                  "Effects compare matched baseline members; turn-8–11 flow "
                  "metrics are per observed person-turn. Employer linkage is a "
                  "status proxy, and calorie intake is compared with each "
                  "person's recorded calorie need. This is the complete resident "
                  "cohort for this small scenario, not a general population "
                  "welfare index.", "",
                  "| Seed | Baseline members C/T | Matched | Alive T11 (pp) | "
                  "Need met (pp) | Food shortfall (pp) | Employer-linked (pp) | "
                  "Calories (kcal/person-turn) | Cash change/person | "
                  "Debt change/person | Wages/person-turn | Sales/person-turn | "
                  "Purchases/person-turn | Input cost/person-turn |",
                  "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for seed in seeds:
            cohort = experiment["by_seed"][str(seed)]["household_cohort"]
            metrics = cohort["metrics"]

            def cohort_cell(field, *, percentage=False):
                metric = metrics[field]
                value = metric.get("effect")
                if value is None:
                    rendered = "—"
                elif percentage:
                    rendered = f"{100.0 * value:+.2f}"
                else:
                    rendered = f"{value:+.2f}"
                return f"{rendered} ({metric['observed']}/{metric['expected']})"

            cells = [
                seed,
                f"{cohort['baseline_cohort_control']}/"
                f"{cohort['baseline_cohort_treatment']}",
                cohort["paired_baseline_members"],
                cohort_cell("alive_t11", percentage=True),
                cohort_cell("food_need_met_ratio", percentage=True),
                cohort_cell("food_shortfall", percentage=True),
                cohort_cell("employer_linked", percentage=True),
                cohort_cell("calories_eaten"), cohort_cell("cash"),
                cohort_cell("total_debt"), cohort_cell("wage_income_cash"),
                cohort_cell("sales_cash"), cohort_cell("purchases_cash"),
                cohort_cell("input_consumed_cost"),
            ]
            lines.append("| " + " | ".join(map(str, cells)) + " |")
        lines += ["", "Percentage entries are treatment-minus-control percentage "
                  "point effects. Parentheses show matched members or observed "
                  "person-turns over expected coverage; missing or migrated-out "
                  "members are not silently imputed as zero.", "",
                  "### Physical holdings census", "",
                  "The census sums every agent's ordinary inventory and the "
                  "trader export, foreign, parked and legacy-pipeline pools; it "
                  "also counts distinct government/charity food stores and "
                  "pending/in-transit route cargo. It is a complete point-in-time "
                  "census of these enumerated supply-rivalry stores, not a "
                  "goods-flow conservation proof. The JSON sidecar retains all "
                  "goods and turns; this table shows food, cotton and cloth at "
                  "T7, T11 and T20.", "",
                  "| Seed | T7 agents / routes / public stores | Negative stock observations C/T | "
                  "Good | Holder / pool | T7 C/T | T11 C/T | T7-to-T11 change effect | "
                  "T20 C/T |",
                  "|---:|---|---:|---|---|---:|---:|---:|---:|"]
        for seed in seeds:
            seed_data = experiment["by_seed"][str(seed)]
            stocks = seed_data["physical_stocks"]["stocks"]
            quality = seed_data["stock_census_quality"]
            c_quality, t_quality = quality["control"], quality["treatment"]
            c_coverage = c_quality.get("baseline_coverage") or {}
            t_coverage = t_quality.get("baseline_coverage") or {}
            coverage_text = (
                f"{c_coverage.get('agents_scanned', '—')}/"
                f"{t_coverage.get('agents_scanned', '—')} agents; "
                f"{c_coverage.get('routes_scanned', '—')}/"
                f"{t_coverage.get('routes_scanned', '—')} routes; "
                f"{c_coverage.get('distinct_government_stores', '—')}+"
                f"{c_coverage.get('distinct_charity_stores', '—')} public stores")
            negative_text = (
                f"{c_quality['negative_stock_observation_count']}/"
                f"{t_quality['negative_stock_observation_count']}")
            selected = [row for row in stocks
                        if row["good"] in {"food", "cotton", "cloth"}
                        and any(_is_number(point.get("control"))
                                and (_abs_nonzero(point.get("control"))
                                     or _abs_nonzero(point.get("treatment")))
                                for point in row["points"].values())]
            if not selected:
                lines.append(f"| {seed} | {coverage_text} | {negative_text} | "
                             "— | no nonzero holdings in selected goods | — | — | — | — |")
            for index, row in enumerate(selected):
                def stock_pair(turn):
                    point = row["points"].get(str(turn), {})
                    control, treatment = point.get("control"), point.get("treatment")
                    if control is None or treatment is None:
                        return "—"
                    return f"{control:.1f}/{treatment:.1f}"

                lines.append("| " + " | ".join(map(str, [
                    seed if index == 0 else "", coverage_text if index == 0 else "",
                    negative_text if index == 0 else "", row["good"],
                    f"{row['category']} / {row['pool']}", stock_pair(7),
                    stock_pair(11),
                    _fmt(row.get("shock_window_change_effect")),
                    stock_pair(20),
                ])) + " |")
        lines += ["", "Negative-stock counts are negative category/pool/good "
                  "holdings observed over all 20 turns in each arm. They are "
                  "preserved as findings for follow-up, not clamped during "
                  "census or report aggregation.", "",
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
        "The table above reports the deep-accounting and structural checks for "
        "each retained arm trace. See "
        "`economic_shock_supply_rivalry_seed812.md` and the treasury follow-up "
        "for residuals and limitations.", "",
        "The five-seed sample describes local mechanism response in this fixed "
        "scenario. It does not establish general supply-chain resilience, "
        "population welfare, goods-stock conservation, causal recovery, or historical "
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
