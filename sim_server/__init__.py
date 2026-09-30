"""
sim_server — Authoritative Simulation Server for REGNUM.

Coordinates authoritative world state, multi-layered turn pipelines,
AI sovereign decisions, economic models, and client command processing.
"""

from sim_server.sim_server import SimServer
from sim_server.protocol import CommandType, ServerEvent

__all__ = ['SimServer', 'CommandType', 'ServerEvent', 'RegnumWebServer', 'run_web_server']


def __getattr__(name: str):
    if name in ('RegnumWebServer', 'run_web_server'):
        from sim_server.web_server import RegnumWebServer, run_web_server
        return RegnumWebServer if name == 'RegnumWebServer' else run_web_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
