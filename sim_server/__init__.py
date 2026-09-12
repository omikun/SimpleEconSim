"""
sim_server — Authoritative Simulation Server for REGNUM.

Coordinates authoritative world state, multi-layered turn pipelines,
AI sovereign decisions, economic models, and client command processing.
"""

from sim_server.sim_server import SimServer
from sim_server.protocol import CommandType, ServerEvent

__all__ = ['SimServer', 'CommandType', 'ServerEvent']
