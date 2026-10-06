"""Generic scenario framework and template interpreter for Call of Capital / SimpleEconSim.

Provides declarative scenario orchestration, modular simulation dynamics,
and deterministic script execution from JSON specifications.
"""

from __future__ import annotations

from scenarios.schema import ScenarioSpec, load_scenario_spec
from scenarios.interpreter import ScenarioInterpreter

__all__ = [
    'ScenarioSpec',
    'load_scenario_spec',
    'ScenarioInterpreter',
]
