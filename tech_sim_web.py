#!/usr/bin/env python3
"""
tech_sim_web.py — Standalone Web & CLI Entrypoint for the Emergent Tech Tree & Leapfrog Simulator.

Facade module re-exporting from `client.web.tech_sim_server`.
Can be launched directly from anywhere:
    ./venv/bin/python tech_sim_web.py --port 8082
"""

from client.web.tech_sim_server import *  # noqa: F401,F403

if __name__ == "__main__":
    from client.web.tech_sim_server import main
    main()
