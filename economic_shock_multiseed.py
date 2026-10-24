"""Summarize matched economic shock screens across independent seeds.

This consumes the compact JSON summaries emitted by
``economic_shock_experiment.py``. It does not rerun or decode traces.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics


EXPERIMENTS = {
    "wood_supply_reduction": {
        "title": "Temporary c50 wood supply reduction",
        "measures": [
            ("wood", "production_units", "Wood production", "sum"),
            ("wood", "offered_supply_units", "Wood offered supply", "sum"),
            ("wood", "units_sold", "Wood units sold", "sum"),
            ("wood", "submitted_bids", "Wood submitted bids", "sum"),
            ("wood", "transaction_vwap", "Wood paid VWAP", "mean"),
            ("furniture", "units_sold", "Furniture units sold", "sum"),
            ("furniture", "transaction_vwap", "Furniture paid VWAP", "mean"),
            ("food", "food_intake.shortfall_units", "Food shortfall units", "sum"),
            ("wood", "nonfood_consumption.units_consumed", "Wood consumed", "sum"),
        ],
    },
    "furniture_demand_increase": {
        "title": "Temporary c50 furniture inventory-target increase",
        "measures": [
            ("furniture", "submitted_bids", "Furniture submitted bids", "sum"),
            ("furniture", "offered_supply_units", "Furniture offered supply", "sum"),
            ("furniture", "units_sold", "Furniture units sold", "sum"),
            ("furniture", "production_units", "Furniture production", "sum"),
            ("furniture", "transaction_vwap", "Furniture paid VWAP", "mean"),
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
    deltas = [row["values"].get(key, {}).get("treatment_minus_control")
              for row in rows]
    observed = [value for value in deltas
                if isinstance(value, (int, float))]
    if not observed:
        value = None
    elif statistic == "sum":
        value = sum(observed)
    elif statistic == "mean":
        value = statistics.fmean(observed)
    else:
        raise ValueError(f"unsupported statistic {statistic!r}")
    return {"effect": value, "observed_turns": len(observed),
            "expected_turns": end - start + 1, "statistic": statistic}


def _load_seed(root: Path, seed: int) -> dict:
    path = root / f"seed-{seed}" / "paired-results.json"
    if not path.exists():
        raise FileNotFoundError(f"missing paired results for seed {seed}: {path}")
    result = json.loads(path.read_text())
    if result.get("seed") != seed:
        raise ValueError(f"seed mismatch in {path}: expected {seed}, found {result.get('seed')}")
    for pair in result["experiments"].values():
        if "target_tile" not in pair:
            arm_path = Path(pair["control_result"])
            if not arm_path.exists():
                arm_path = path.parent / arm_path.name
            child = json.loads(arm_path.read_text())
            pair["target_tile"] = child["target_tile"]
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
            f"{seed}:{experiment['by_seed'][seed]['target_tile']}" for seed in seeds)
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
                  "turns for quantities and consumption; price rows show the "
                  "mean per-turn paired delta. The coverage cells prevent a "
                  "missing record from being silently counted as zero.", ""]
    lines += [
        "## Limits", "",
        "Five seeds are a diagnostic sample, not a precise uncertainty estimate. "
        "Deep structural/formula and treasury audits were run on the seed-4242 "
        "traces; the other seed pairs carry the market mechanical gates only. "
        "Treasury residual attribution, full goods-stock conservation, stable "
        "household cohorts, a supply-rivalry cross-scenario sample, and primary-"
        "source calibration remain open in the analysis plan.", "",
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
