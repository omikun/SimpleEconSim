"""Summarize matched economic shock screens across independent seeds.

This consumes the compact JSON summaries emitted by
``economic_shock_experiment.py``. It does not rerun or decode traces.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

from economic_shock_experiment import _compare_pair

SHOCK_START = 8
SHOCK_END = 11


EXPERIMENTS = {
    "wood_supply_reduction": {
        "title": "Temporary local wood supply reduction",
        "measures": [
            ("wood", "production_units", "Wood production", "sum"),
            ("wood", "offered_supply_units", "Wood offered supply", "sum"),
            ("wood", "units_sold", "Wood units sold", "sum"),
            ("wood", "submitted_bids", "Wood submitted bids", "sum"),
            ("wood", "transaction_vwap", "Wood paid VWAP change (%)", "mean_percent"),
            ("furniture", "units_sold", "Furniture units sold", "sum"),
            ("furniture", "transaction_vwap", "Furniture paid VWAP change (%)", "mean_percent"),
            ("food", "food_intake.shortfall_units", "Food shortfall units", "sum"),
            ("wood", "nonfood_consumption.units_consumed", "Wood consumed", "sum"),
        ],
    },
    "furniture_demand_increase": {
        "title": "Temporary local furniture inventory-target increase",
        "measures": [
            ("furniture", "submitted_bids", "Furniture submitted bids", "sum"),
            ("furniture", "offered_supply_units", "Furniture offered supply", "sum"),
            ("furniture", "units_sold", "Furniture units sold", "sum"),
            ("furniture", "production_units", "Furniture production", "sum"),
            ("furniture", "transaction_vwap", "Furniture paid VWAP change (%)", "mean_percent"),
            ("food", "food_intake.shortfall_units", "Food shortfall units", "sum"),
            ("furniture", "nonfood_consumption.units_consumed", "Furniture consumed", "sum"),
        ],
    },
}


def paired_effect(pair: dict, good: str, key: str, statistic: str,
                  *, start: int = 8, end: int = 11,
                  target_tile: str | None = None) -> dict:
    """Compute treatment-minus-control effect without filling missing rows."""
    target_tile = target_tile or pair.get("target_tile", "c50")
    rows = [row for row in pair["comparison"]["market_response"]
            if row["tile"] == target_tile and row["good"] == good
            and start <= row["turn"] <= end]
    observed = []
    for row in rows:
        value = row["values"].get(key, {})
        if statistic == "mean_percent":
            control, treatment = value.get("control"), value.get("treatment")
            if not isinstance(control, (int, float)) or not isinstance(treatment, (int, float)):
                continue
            if control > 0:
                observed.append((treatment / control - 1.0) * 100.0)
        else:
            delta = value.get("treatment_minus_control")
            if isinstance(delta, (int, float)):
                observed.append(delta)
    if not observed:
        value = None
    elif statistic == "sum":
        value = sum(observed)
    elif statistic == "mean":
        value = statistics.fmean(observed)
    elif statistic == "mean_percent":
        value = statistics.fmean(observed)
    else:
        raise ValueError(f"unsupported statistic {statistic!r}")
    return {"effect": value, "observed_turns": len(observed),
            "expected_turns": end - start + 1, "statistic": statistic}


def _resident_cohort_window_summary(cohort: dict | None) -> dict:
    if not cohort:
        return {"available": False, "observed_turns": 0}
    observations = cohort.get("observations", ())
    baseline_count = len(cohort.get("roster", ()))
    rows = [row for row in observations if SHOCK_START <= int(row.get("turn", -1))
            <= SHOCK_END]
    if baseline_count <= 0 or not rows:
        return {"available": False, "baseline_member_count": baseline_count,
                "observed_turns": len(rows)}

    def mean_alive_share():
        values = [float(row.get("alive_member_count", 0)) / baseline_count
                  for row in rows]
        return statistics.fmean(values) if values else None

    need_observations = sum(int(row.get("need_observed_member_count", 0))
                            for row in rows)
    need_met = sum(int(row.get("need_met_member_count", 0)) for row in rows)
    calories = sum(float(row.get("calories_eaten_total_kcal", 0.0))
                   for row in rows)
    shortfall = sum(float(row.get("calorie_shortfall_total_kcal", 0.0))
                    for row in rows)
    living_person_turns = sum(int(row.get("alive_member_count", 0)) for row in rows)
    linked = sum(int(row.get("employer_linked_member_count", 0)) for row in rows)
    account_totals = {}
    for field in ("wages_cash", "sales_cash", "purchases_cash",
                  "input_consumed_cost"):
        account_totals[field] = sum(float(
            (row.get("account_flow_totals") or {}).get(field, 0.0) or 0.0)
            for row in rows)
    account_coverage = {}
    for field in account_totals:
        account_coverage[field] = sum(int(
            (row.get("account_flow_coverage") or {}).get(field, 0))
            for row in rows)
    turn11 = next((row for row in observations
                   if int(row.get("turn", -1)) == SHOCK_END), None)

    return {
        "available": True,
        "baseline_member_count": baseline_count,
        "observed_turns": len(rows),
        "expected_turns": SHOCK_END - SHOCK_START + 1,
        "present_person_turns": sum(int(row.get("present_member_count", 0))
                                     for row in rows),
        "expected_person_turns": baseline_count * (SHOCK_END - SHOCK_START + 1),
        "need_observed_person_turns": need_observations,
        "mean_alive_share_of_baseline": mean_alive_share(),
        "need_met_share": need_met / need_observations
        if need_observations else None,
        "calories_eaten_per_need_person_turn": calories / need_observations
        if need_observations else None,
        "calorie_shortfall_per_need_person_turn": shortfall / need_observations
        if need_observations else None,
        "employer_linked_share_of_living_person_turns": linked / living_person_turns
        if living_person_turns else None,
        "cash_change_total_per_baseline_member_at_t11": (
            float(turn11.get("cash_change_total_from_turn7", 0.0)) / baseline_count
            if turn11 else None),
        "debt_change_total_per_covered_member_at_t11": (
            float(turn11.get("debt_change_total_from_turn7", 0.0))
            / int(turn11.get("debt_change_member_coverage", 0))
            if turn11 and int(turn11.get("debt_change_member_coverage", 0)) else None),
        "account_flow_per_covered_person_turn": {
            field: account_totals[field] / account_coverage[field]
            if account_coverage[field] else None
            for field in account_totals
        },
        "account_flow_coverage": account_coverage,
        "turn11_alive_share_of_baseline": (
            float(turn11.get("alive_member_count", 0)) / baseline_count
            if turn11 else None),
        "turn11_present_member_count": (
            int(turn11.get("present_member_count", 0)) if turn11 else None),
    }


def resident_cohort_effect(pair: dict) -> dict:
    """Compare the fixed default-game turn-7 cohort without imputing missing people."""
    cohort = pair.get("default_resident_cohort") or {}
    control = cohort.get("control")
    treatment = cohort.get("treatment")
    if not control or not treatment:
        return {"available": False, "reason": "cohort_not_recorded"}
    control_roster = control.get("roster", ())
    treatment_roster = treatment.get("roster", ())
    control_ids = [row.get("actor_id") for row in control_roster]
    treatment_ids = [row.get("actor_id") for row in treatment_roster]
    matched = control_ids == treatment_ids and bool(control_ids)
    control_summary = _resident_cohort_window_summary(control)
    treatment_summary = _resident_cohort_window_summary(treatment)
    metrics = (
        "mean_alive_share_of_baseline", "need_met_share",
        "calories_eaten_per_need_person_turn",
        "calorie_shortfall_per_need_person_turn",
        "employer_linked_share_of_living_person_turns",
        "cash_change_total_per_baseline_member_at_t11",
        "debt_change_total_per_covered_member_at_t11",
        "turn11_alive_share_of_baseline",
    )
    effects = {}
    for metric in metrics:
        left = control_summary.get(metric)
        right = treatment_summary.get(metric)
        effects[metric] = (right - left if matched
                           and isinstance(left, (int, float))
                           and isinstance(right, (int, float)) else None)
    for field in ("wages_cash", "sales_cash", "purchases_cash",
                  "input_consumed_cost"):
        left = control_summary.get("account_flow_per_covered_person_turn", {}).get(field)
        right = treatment_summary.get("account_flow_per_covered_person_turn", {}).get(field)
        effects[f"{field}_per_covered_person_turn"] = (
            right - left if matched and isinstance(left, (int, float))
            and isinstance(right, (int, float)) else None)
    return {
        "available": control_summary.get("available") is True
        and treatment_summary.get("available") is True,
        "roster_matched": matched,
        "baseline_member_count_control": len(control_roster),
        "baseline_member_count_treatment": len(treatment_roster),
        "control": control_summary,
        "treatment": treatment_summary,
        "treatment_minus_control": effects,
    }


def _load_seed(root: Path, seed: int) -> dict:
    path = root / f"seed-{seed}" / "paired-results.json"
    if not path.exists():
        raise FileNotFoundError(f"missing paired results for seed {seed}: {path}")
    result = json.loads(path.read_text())
    if result.get("seed") != seed:
        raise ValueError(f"seed mismatch in {path}: expected {seed}, found {result.get('seed')}")
    for pair in result["experiments"].values():
        children = {}
        for arm, path_key in (("control", "control_result"),
                              ("treatment", "treatment_result")):
            arm_path = Path(pair[path_key])
            if not arm_path.exists():
                arm_path = path.parent / arm_path.name
            children[arm] = json.loads(arm_path.read_text())
        if children["control"].get("target_tile") != children["treatment"].get("target_tile"):
            raise ValueError(f"paired arms use different targets in {path}")
        pair["target_tile"] = children["control"]["target_tile"]
        pair["comparison"] = _compare_pair(children["control"], children["treatment"])
        pair["default_resident_cohort"] = {
            arm: {
                "roster": children[arm].get("default_resident_cohort_roster", []),
                "observations": children[arm].get(
                    "default_resident_cohort_observations", []),
            }
            for arm in ("control", "treatment")
        }
    return result


def summarize(root: Path, seeds: list[int]) -> dict:
    runs = {seed: _load_seed(root, seed) for seed in seeds}
    source_provenance = {}
    for seed, result in runs.items():
        arms = []
        for pair in result["experiments"].values():
            for path_key in ("control_result", "treatment_result"):
                path = Path(pair[path_key])
                if not path.exists():
                    path = root / f"seed-{seed}" / path.name
                child = json.loads(path.read_text()) if path.exists() else {}
                arms.append({
                    "source_commit": child.get("source_commit"),
                    "tracked_worktree_dirty": child.get("tracked_worktree_dirty"),
                })
        source_provenance[str(seed)] = arms
    output = {"seeds": seeds, "source_provenance_by_seed": source_provenance,
              "experiments": {}}
    for experiment_id, config in EXPERIMENTS.items():
        per_seed = {}
        for seed, result in runs.items():
            pair = result["experiments"][experiment_id]
            arm_data = (pair.get("control_result_data", {}),
                        pair.get("treatment_result_data", {}))
            market_gates = [arm.get("market_mechanical_gates") or {}
                            for arm in arm_data]
            per_seed[seed] = {
                "target_tile": pair["target_tile"],
                "target_currency": next((row.get("currency")
                    for row in pair["comparison"]["market_response"]
                    if row["tile"] == pair["target_tile"]
                    and row["good"] == config["measures"][0][0]
                    and SHOCK_START <= row["turn"] <= SHOCK_END
                    and row.get("currency")), None),
                "pre_shock_states_match": pair["comparison"]["pre_shock_states_match"],
                "market_gates_pass": all(gate.get("passed") is True
                                          for gate in market_gates),
                "market_rows": [gate.get("market_rows") for gate in market_gates],
                "measures": {
                    f"{good}:{key}": paired_effect(
                        pair, good, key, statistic,
                        target_tile=pair["target_tile"])
                    for good, key, _label, statistic in config["measures"]
                },
                "resident_cohort": resident_cohort_effect(pair),
            }
        measures = {}
        for good, key, label, statistic in config["measures"]:
            measure_id = f"{good}:{key}"
            seed_values = {
                str(seed): per_seed[seed]["measures"][measure_id]
                for seed in seeds
            }
            observed = [item["effect"] for item in seed_values.values()
                        if isinstance(item["effect"], (int, float))]
            measures[measure_id] = {
                "good": good, "label": label, "statistic": statistic,
                "by_seed": seed_values,
                "seeds_observed": len(observed),
                "mean": statistics.fmean(observed) if observed else None,
                "median": statistics.median(observed) if observed else None,
                "minimum": min(observed) if observed else None,
                "maximum": max(observed) if observed else None,
            }
        output["experiments"][experiment_id] = {
            "title": config["title"], "by_seed": per_seed,
            "turn7_match_count": sum(
                item["pre_shock_states_match"] for item in per_seed.values()),
            "market_gate_pass_count": sum(
                item["market_gates_pass"] for item in per_seed.values()),
            "measures": measures,
        }
    return output


def _fmt(value):
    return "—" if value is None else f"{value:.3f}"


def _fmt_percent(value):
    return "—" if value is None else f"{100 * value:.1f}%"


def _fmt_signed(value, digits=2):
    return "—" if value is None else f"{value:+.{digits}f}"


def render_report(summary: dict) -> str:
    seeds = summary["seeds"]
    provenance = []
    for seed in seeds:
        arms = summary["source_provenance_by_seed"].get(str(seed), [])
        by_commit = {}
        for arm in arms:
            commit = arm.get("source_commit")
            if commit:
                counts = by_commit.setdefault(commit, {"arms": 0, "dirty": 0})
                counts["arms"] += 1
                counts["dirty"] += arm.get("tracked_worktree_dirty") is True
        revisions = [f"`{commit}` (dirty arms: {counts['dirty']}/{counts['arms']})"
                     for commit, counts in sorted(by_commit.items())]
        provenance.append(f"{seed} " + (", ".join(revisions) or "revision unavailable"))
    lines = [
        f"# {len(seeds)}-seed default-game shock screen", "",
        f"Paired 20-turn screens at seeds {', '.join(map(str, seeds))}; "
        "turns 8–11 are the shock window. Per-seed differences are matched "
        "treatment minus control; displayed ranges are descriptive, not "
        "confidence intervals or empirical calibration.", "",
        "Each seed uses an independent world initialization. Within each seed, "
        "the control and treatment must match at turn 7. Later RNG streams can "
        "diverge after the intervention, so recovery-path differences are not "
        "draw-aligned.", "",
        "Simulation source provenance by seed: " + "; ".join(provenance) + ".", "",
    ]
    for experiment_id, experiment in summary["experiments"].items():
        target_tiles = ", ".join(
            f"{seed}:{experiment['by_seed'][seed]['target_tile']} "
            f"({experiment['by_seed'][seed]['target_currency'] or 'currency unavailable'})"
            for seed in seeds)
        lines += [f"## {experiment['title']}", "",
                  f"Selected active target tiles by seed: {target_tiles}.",
                  f"Turn-7 states match: {experiment['turn7_match_count']}/{len(seeds)}; "
                  f"market mechanical gates pass: {experiment['market_gate_pass_count']}/{len(seeds)} "
                  "seed pairs in both arms.", "",
                  "| Measure | " + " | ".join(map(str, seeds)) +
                  " | Mean | Median | Range | Seeds observed | Seed coverage |",
                  "|---|" + "---:|" * (len(seeds) + 5)]
        for _good, _key, label, _statistic in EXPERIMENTS[experiment_id]["measures"]:
            measure = experiment["measures"][f"{_good}:{_key}"]
            by_seed = measure["by_seed"]
            cells = [_fmt(by_seed[str(seed)]["effect"]) for seed in seeds]
            minimum, maximum = measure["minimum"], measure["maximum"]
            span = "—" if minimum is None else f"{_fmt(minimum)} to {_fmt(maximum)}"
            coverage = ", ".join(
                f"{seed}:{by_seed[str(seed)]['observed_turns']}/"
                f"{by_seed[str(seed)]['expected_turns']}"
                for seed in seeds)
            lines.append("| " + " | ".join([
                label, *cells, _fmt(measure["mean"]), _fmt(measure["median"]),
                span, str(measure["seeds_observed"]), coverage,
            ]) + " |")
        lines += ["", "A seed-level sum is cumulative over observed shock-window "
                  "turns for quantities and consumption; price rows show mean "
                  "per-turn percent changes from that seed's control so currencies "
                  "remain comparable. Coverage cells prevent a "
                  "missing record from being silently counted as zero.", ""]
    lines += [
        "## Fixed default-game resident cohort", "",
        "Each default-game arm freezes the same eligible resident IDs after "
        "turn 7 and records compact aggregate observations through turn 20. "
        "The table covers turns 8–11. Need-met rates use present, living "
        "roster members with positive measured calorie need; missing people "
        "are not assigned zero intake. Cash change is cumulative from turn 7 "
        "per baseline roster member. Wage flow is divided by resident-turns "
        "with an account record. Differences are treatment minus control; "
        "need-met differences are percentage points.", "",
        "| Experiment | Seed | Baseline N C/T | Roster matched | T11 present C/T | "
        "T11 alive C/T | Need met C/T (Δ pp) | kcal/need-person-turn C/T (Δ) | "
        "Cash Δ/member C/T (Δ) | Wages/covered-person-turn C/T (Δ) | "
        "Need coverage C/T |",
        "|---|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for experiment_id, experiment in summary["experiments"].items():
        for seed in seeds:
            cohort = experiment["by_seed"][seed].get("resident_cohort", {})
            control = cohort.get("control", {})
            treatment = cohort.get("treatment", {})
            effects = cohort.get("treatment_minus_control", {})
            baseline = (f"{cohort.get('baseline_member_count_control', 0)}/"
                        f"{cohort.get('baseline_member_count_treatment', 0)}")
            matched = "yes" if cohort.get("roster_matched") else "no"

            def present_share(row):
                count = row.get("turn11_present_member_count")
                total = row.get("baseline_member_count")
                return count / total if count is not None and total else None

            wages = [
                row.get("account_flow_per_covered_person_turn", {}).get("wages_cash")
                for row in (control, treatment)
            ]
            wages_effect = effects.get("wages_cash_per_covered_person_turn")
            coverage = [
                f"{row.get('need_observed_person_turns', 0)}/"
                f"{row.get('expected_person_turns', 0)}"
                for row in (control, treatment)
            ]
            lines.append("| " + " | ".join([
                experiment["title"], str(seed), baseline, matched,
                f"{_fmt_percent(present_share(control))}/"
                f"{_fmt_percent(present_share(treatment))}",
                f"{_fmt_percent(control.get('turn11_alive_share_of_baseline'))}/"
                f"{_fmt_percent(treatment.get('turn11_alive_share_of_baseline'))}",
                f"{_fmt_percent(control.get('need_met_share'))}/"
                f"{_fmt_percent(treatment.get('need_met_share'))} "
                f"({_fmt_signed(100 * effects['need_met_share'], 1) if effects.get('need_met_share') is not None else '—'} pp)",
                f"{_fmt(control.get('calories_eaten_per_need_person_turn'))}/"
                f"{_fmt(treatment.get('calories_eaten_per_need_person_turn'))} "
                f"({_fmt_signed(effects.get('calories_eaten_per_need_person_turn'))})",
                f"{_fmt(control.get('cash_change_total_per_baseline_member_at_t11'))}/"
                f"{_fmt(treatment.get('cash_change_total_per_baseline_member_at_t11'))} "
                f"({_fmt_signed(effects.get('cash_change_total_per_baseline_member_at_t11'))})",
                f"{_fmt(wages[0])}/{_fmt(wages[1])} ({_fmt_signed(wages_effect)})",
                f"{coverage[0]}/{coverage[1]}",
            ]) + " |")
    lines += [
        "", "An absent roster member can have migrated or otherwise left the "
        "observed actor set; absence is not treated as death. Alive coverage "
        "and presence coverage are shown separately. This is a fixed-cohort "
        "shock-window comparison, not an estimate of long-run recovery or a "
        "historically calibrated welfare effect.", "",
    ]
    lines += [
        "## Limits", "",
        "Five seeds are a diagnostic sample, not a precise uncertainty estimate. "
        "Deep structural/formula and treasury audits were run on the seed-4242 "
        "traces; the other seed pairs carry the market mechanical gates only. "
        "Full goods-stock conservation, broader welfare accounting, prospective "
        "recovery evidence, and primary-source calibration remain open in the "
        "analysis plan.", "",
        "Reproduce the paired runs with `economic_shock_experiment.py` for each "
        "seed, then summarize their saved JSON without re-decoding traces:", "",
        "```sh",
        "venv/bin/python economic_shock_multiseed.py --root tmp/economic-shocks "
        "--seeds 4242 4243 4244 4245 4246",
        "```", "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("tmp/economic-shocks"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[4242, 4243, 4244, 4245, 4246])
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--report-out", type=Path,
                        default=Path("planning/reports/economic_shock_multiseed_default.md"))
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
