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


def main():
    parser = argparse.ArgumentParser(description="REGNUM Simulation Server CLI")
    parser.add_argument('--seed', type=int, default=4242, help="Master simulation seed")
    parser.add_argument('--terrain-seed', type=int, default=None, help="Terrain seed")
    parser.add_argument('--nation-seed', type=int, default=None, help="Nation seed")
    parser.add_argument('--turns', type=int, default=20, help="Number of turns to advance")
    parser.add_argument('--bench', action='store_true', help="Run in maximum speed benchmark mode")
    args = parser.parse_args()

    print("==================================================")
    print(" REGNUM Authoritative Simulation Server CLI       ")
    print(f" Master Seed: {args.seed}")
    print("==================================================")

    server = SimServer(seed=args.seed, terrain_seed=args.terrain_seed, nation_seed=args.nation_seed)
    print(f"[Server] Initialized world with {len(server.tiles)} tiles, {len(server.nations)} nations.")

    def on_server_event(ev_type, data):
        if ev_type == "TICKER_MESSAGE":
            print(f"  [{data.get('t')}] ({data.get('kind')}) {data.get('text')}")

    server.subscribe(on_server_event)

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
