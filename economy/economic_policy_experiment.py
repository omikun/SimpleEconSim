"""Compare existing sovereign autonomy and bounded supply-response changes.

Run with ``venv/bin/python -m economy.economic_policy_experiment --out-dir ...``.
Each arm starts in a fresh process with the same random/hash seeds. Compact
traces stay compressed; only selected market/intake panels are exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys

ARMS = {
    "rivals_only": (False, False, False),
    "all_ai": (True, False, False),
    "artisan_inputs": (True, True, False),
    "national_relief": (True, False, True),
    "combined": (True, True, True),
}

SOURCE_FILES = (
    'core/sim_engine.py', 'meso/province.py', 'meso/food_logistics.py',
    'meso/region_logistics.py', 'micro/region_market.py', 'micro/food_security.py',
    'macro/ai_nation.py', 'sim_server/sim_server.py', 'economy/economic_policy_experiment.py',
)


def _initial_digest(server):
    """Compare the common economy and RNG before installing policy treatments."""
    from economic_shock_experiment import _canonical_digest

    ais = [nation.ai for nation in server.nations]
    try:
        for nation in server.nations:
            nation.ai = None
        return _canonical_digest(server)
    finally:
        for nation, ai in zip(server.nations, ais):
            nation.ai = ai


def run_arm(arm, seed, turns, out_dir):
    import numpy as np
    from sim_server.sim_server import SimServer
    from dataclasses import replace
    from economic_shock_experiment import _git_info, _goods_stock_observation
    from economic_shock_analysis import analyze_trace
    from economic_shock_stock_flow_audit import audit_run
    from trace_codec import iter_payloads
    from run_trace import verify
    from world_config import FULL_GAMEPLAY_FLAGS

    provenance = _git_info()
    source_diff_hash = hashlib.sha256(subprocess.check_output(["git", "diff"])).hexdigest()
    source_files = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    for path in SOURCE_FILES}
    random.seed(seed)
    np.random.seed(seed)
    autoplay, artisans, national = ARMS[arm]
    gameplay_flags = replace(
        FULL_GAMEPLAY_FLAGS,
        independent_input_requests=artisans,
        national_food_logistics=national)
    server = SimServer(seed=seed, terrain_seed=seed, nation_seed=seed,
                       topology="voronoi", autoplay_nations=False)
    initial_digest = _initial_digest(server)
    server.gameplay_flags = gameplay_flags
    server.gameplay_profile = 'custom'
    for participant in (*server.tiles, *server.nations):
        participant._gameplay_flags = gameplay_flags
    server.autoplay_nations = autoplay
    server._configure_nation_ai()
    stocks = [_goods_stock_observation(server, 0, aggregate_world=True)]
    nation_turns = []
    initial_ownership = {tile.name: tile.owner_nation.name
                         for tile in server.tiles if tile.owner_nation}
    for turn in range(1, turns + 1):
        server.step()
        if server.turn != turn:
            raise RuntimeError(f"stopped before turn {turn}")
        stocks.append(_goods_stock_observation(server, turn, aggregate_world=True))
        for nation in server.nations:
            residents = [a for tile in nation.tiles for a in tile.agents
                         if a.alive and not a.is_corporation and not a.is_government
                         and not getattr(a, "military_unit_id", None)]
            nation_turns.append({
                "turn": turn, "nation": nation.name,
                "residents": len(residents),
                "underfed": sum(a.calorie_deficit_kcal > 0 for a in residents),
                "calorie_need": sum(a.calorie_need_kcal for a in residents),
                "calories_eaten": sum(a.last_calories_eaten for a in residents),
                "deaths": sum(tile.deaths_this_turn for tile in nation.tiles),
                "treasury": nation.treasury(),
            })
        print(f"{arm}: turn {turn}/{turns}", flush=True)
    trace = server.run_trace
    trace.publish()
    trace._compact_writer.close()
    trace_path = Path(trace.path)
    verification = verify(trace_path)
    panel = analyze_trace(trace_path)
    from collections import Counter
    events = Counter()
    quantities = Counter()
    policy_evidence = []
    role_evidence = []

    def stream():
        for payload in iter_payloads(trace_path):
            event = json.loads(payload)
            subject, inputs = event.get("subject", {}), event.get("inputs", {})
            kind = event.get("kind")
            tile = subject.get("tile") or subject.get("id")
            events[(str(tile), kind)] += 1
            if kind == "government_food_aid":
                quantities[(str(tile), kind)] += inputs.get("units_delivered", 0)
            if kind in ("provincial_food_dispatch", "provincial_food_arrival"):
                quantities[(str(tile), kind)] += event.get("value_after", 0)
                policy_evidence.append(event)
            if kind == "food_security_assessment" and event.get("turn") == 10:
                policy_evidence.append(event)
            if (kind == "market_seller_order_submitted" and inputs.get("seller_output") == "gov"
                    and subject.get("good") == "food" and event.get("turn") == 10):
                role_evidence.append({"subject": subject, "inputs": inputs,
                                      "event_id": event.get("event_id")})
            yield event

    result = {
        "experiment": "economic_policy_response", "scenario": "default",
        "arm": arm, "seed": seed, "requested_turns": turns,
        "completed_turns": server.turn, "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "initial_economy_and_rng_sha256": initial_digest,
        "policy": {"autoplay_nations": autoplay, "artisan_inputs": artisans,
                   "national_relief": national},
        "trace_path": str(trace_path), "trace_verification": verification,
        "initial_tile_nations": initial_ownership,
        "default_goods_stock_observations": stocks, "nation_turns": nation_turns,
        "market_panel": panel["panel"],
        **provenance,
        "worktree_diff_sha256": source_diff_hash,
        "source_files_sha256": source_files,
    }
    result["stock_flow_audit"] = audit_run(result, stream(), audited_goods=("food", "wood", "furniture"))
    result["event_counts"] = [{"subject": s, "kind": k, "count": v}
                              for (s, k), v in sorted(events.items(), key=lambda x: str(x[0]))]
    result["quantities"] = [{"tile": s, "kind": k, "units": v}
                            for (s, k), v in sorted(quantities.items())]
    result["policy_evidence"] = policy_evidence
    result["estate_sale_evidence"] = role_evidence
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{arm}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"{arm}: saved {path}", flush=True)
    return result


def render_report(runs):
    lines = ["# Twenty-turn economic policy comparison", "",
             "Fresh processes use the same world, terrain, nation and hash seeds. "
             "All arms must match the initial economy/RNG digest before policy assignment. "
             "This is a current-source comparison, not an exact replay of the old trace. "
             "Paths diverge after intervention, including their random draws.", "",
             "The all-AI arm isolates sovereign autonomy against rivals-only. "
             "Artisan-input and national-relief arms each change one mechanism against all-AI. "
             "The combined arm tests their interaction.", "",
             "| Arm | Nation | Resident-turns | Underfed resident-turns | Deaths |",
             "|---|---|---:|---:|---:|"]
    for run in runs:
        for nation in sorted({r["nation"] for r in run["nation_turns"]}):
            rows = [r for r in run["nation_turns"] if r["nation"] == nation]
            lines.append(f"| {run['arm']} | {nation} | {sum(r['residents'] for r in rows)} | "
                         f"{sum(r['underfed'] for r in rows)} | {sum(r['deaths'] for r in rows)} |")
    lines += ["", "Resident-turns use each turn's current population; these are not fixed-cohort welfare estimates.", "",
              "| Arm | Tile | Food shortfall units | Food intake records | Wood input failures in furniture |",
              "|---|---|---:|---:|---:|"]
    for run in runs:
        for tile in ("c10", "c46", "c59", "c50"):
            rows = [r for r in run["market_panel"] if r["tile"] == tile]
            food = [r["food_intake"] for r in rows if r.get("food_intake")]
            failures = sum(r["production_zero_reasons"].get("input_material_unavailable", 0)
                           for r in rows if r["good"] == "furniture")
            lines.append(f"| {run['arm']} | {tile} | {sum(f['shortfall_units'] for f in food):g} | "
                         f"{sum(f['records'] for f in food)} | {failures} |")
    lines += ["", "| Arm | Trace checkpoints | Food balanced intervals | Wood balanced intervals | Furniture balanced intervals |",
              "|---|---:|---:|---:|---:|"]
    for run in runs:
        summaries = run["stock_flow_audit"]["summary_by_good"]
        values = [f"{summaries[g]['balanced_interval_count']}/{summaries[g]['interval_count']}"
                  for g in ("food", "wood", "furniture")]
        lines.append(f"| {run['arm']} | {run['trace_verification']['checkpoints']} | " + " | ".join(values) + " |")
    lines += ["", "Nonzero stock residuals remain accounting/coverage limitations; trace verification alone does not prove physical conservation. "
              "The JSON files retain complete interval audits, compact trace paths, policy decisions and selected city panels. "
              "One seed and twenty turns do not establish general resilience.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=4242)
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    parser.add_argument("--child", choices=ARMS)
    args = parser.parse_args(argv)
    if args.turns < 1:
        parser.error("--turns must be positive")
    if args.child:
        run_arm(args.child, args.seed, args.turns, args.out_dir)
        return
    env = dict(os.environ, PYTHONHASHSEED=str(args.seed), SDL_VIDEODRIVER="dummy",
               MPLCONFIGDIR=str(Path("tmp/matplotlib-policy").resolve()))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for arm in args.arms:
        with (args.out_dir / f"{arm}.log").open("w") as log:
            subprocess.run([sys.executable, "-m", "economy.economic_policy_experiment",
                            "--child", arm, "--seed", str(args.seed), "--turns", str(args.turns),
                            "--out-dir", str(args.out_dir)], env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        runs.append(json.loads((args.out_dir / f"{arm}.json").read_text()))
        print(f"completed {arm}", flush=True)
    if len({r["initial_economy_and_rng_sha256"] for r in runs}) != 1:
        raise RuntimeError("policy arms do not share an identical initial economy and RNG")
    if len({(r['source_commit'], r['worktree_diff_sha256']) for r in runs}) != 1:
        raise RuntimeError("source changed between policy arms; rerun on a stable worktree")
    if len({json.dumps(r['source_files_sha256'], sort_keys=True) for r in runs}) != 1:
        raise RuntimeError("implementation files changed between policy arms")
    (args.out_dir / "report.md").write_text(render_report(runs))


if __name__ == "__main__":
    main()
