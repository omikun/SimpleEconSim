"""
sim_server/server_cli.py — Standalone CLI runner for the simulation server.

Usage:
    python -m sim_server.server_cli [--seed 42] [--turns 50] [--tps 10]
"""

import sys
import os
import time
import argparse

# Ensure project root is on sys.path when invoked directly as a script
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sim_server import SimServer
from sim_server.protocol import CommandType, CommandMessage
from world_config import (GAMEPLAY_FLAG_NAMES, describe_gameplay_flags,
                          resolve_gameplay_flags)


def main():
    parser = argparse.ArgumentParser(description="Call of Capital (CoC) Simulation Server CLI")
    parser.add_argument('--seed', type=int, default=None, help="Master simulation seed (default: Mapgen2 slot one)")
    parser.add_argument('--terrain-seed', type=int, default=None, help="Terrain seed")
    parser.add_argument('--nation-seed', type=int, default=None, help="Nation seed")
    parser.add_argument('--turns', type=int, default=20, help="Number of turns to advance")
    parser.add_argument('--bench', action='store_true', help="Run in maximum speed benchmark mode")
    parser.add_argument('--web', action='store_true', help="Start embedded mobile web server with QR code")
    parser.add_argument('--port', type=int, default=8080, help="Port for web server (default: 8080)")
    parser.add_argument('--host', type=str, default='0.0.0.0', help="Host for web server (default: 0.0.0.0)")
    parser.add_argument('--topology', type=str, default='voronoi', choices=['voronoi', 'hex'],
                        help="World topology: 'voronoi' (irregular polygons) or 'hex' (honeycomb)")
    parser.add_argument('--scenario', choices=['labor-frontier-rivalry', 'supply-rivalry'], default=None)
    parser.add_argument('--disable-mechanism', action='append', default=[],
                        choices=sorted(GAMEPLAY_FLAG_NAMES), metavar='NAME',
                        help='Disable one gameplay mechanism for this run; repeatable')
    parser.add_argument('--profile', default='full', metavar='PROFILE',
                        help='Gameplay profile: full, core, or isolate:MECHANISM')
    from world_config import add_elite_planning_arguments, elite_planning_config_from_args
    add_elite_planning_arguments(parser)
    args = parser.parse_args()
    try:
        elite_settings = elite_planning_config_from_args(args)
    except ValueError as error:
        parser.error(str(error))

    scenario_id = {'labor-frontier-rivalry': 'labor_frontier_rivalry',
                   'supply-rivalry': 'supply_rivalry'}.get(args.scenario)
    try:
        gameplay_flags = resolve_gameplay_flags(
            profile=args.profile, disabled=args.disable_mechanism,
            scenario_id=scenario_id)
    except ValueError as error:
        parser.error(str(error))

    print("==================================================")
    print(" Call of Capital (CoC) Simulation Server CLI      ")
    print(f" Master Seed: {args.seed} | Topology: {args.topology or 'default'}")
    print("==================================================")

    server = SimServer(seed=args.seed, terrain_seed=args.terrain_seed, nation_seed=args.nation_seed,
                       topology=args.topology,
                       gameplay_flags=gameplay_flags,
                       gameplay_profile=args.profile, elite_planning_config=elite_settings,
                       scenario_id=scenario_id)
    print(f"[Gameplay] {describe_gameplay_flags(server.gameplay_profile, server.gameplay_flags)}")
    print(f"[Server] Initialized world with {len(server.tiles)} tiles, {len(server.nations)} nations.")

    def on_server_event(ev_type, data):
        if ev_type == "TICKER_MESSAGE":
            print(f"  [{data.get('t')}] ({data.get('kind')}) {data.get('text')}")

    if args.web:
        from sim_server.web_server import run_web_server
        print(f"[Server] Launching mobile web server on {args.host}:{args.port}...")
        web = run_web_server(sim_server=server, host=args.host, port=args.port, wait_forever=True)
        return

    t0 = time.perf_counter()
    for i in range(args.turns):
        res = server.execute_command(CommandMessage(CommandType.STEP))
        if not args.bench:
            print(f"[Server] Step complete -> Turn {res.get('turn')}")
    t_total = time.perf_counter() - t0

    print("==================================================")
    print(f" Completed {args.turns} turns in {t_total:.3f}s ({args.turns / max(1e-5, t_total):.1f} turns/sec)")
    print(f" Violations recorded: {len(server.violations)}")
    print("==================================================")


if __name__ == '__main__':
    main()
