"""
agents/resistance/models.py — Data structures for popular revolts, communes, and insurrections.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional

@dataclass
class AssassinationPlot:
    """Active covert plot against a charismatic rebellion leader."""
    target_leader_id: int
    target_leader_name: str
    tile_name: str
    turns_remaining: int
    total_turns: int
    funding_allocated: float
    detection_risk_per_turn: float = 0.12
    status: str = "in_progress"  # 'in_progress' | 'struck_decapitation' | 'struck_martyrdom' | 'blown' | 'aborted'


@dataclass
class RebellionConfig:
    """Configurable knobs for tailoring fermentation duration and criticality thresholds."""
    fermentation_pace: float = 1.0       # Global pace multiplier [0.2 = slow burn, 2.0 = powder keg]
    alpha_broadcast: float = 0.08        # Leader manifesto / soapbox recruitment rate
    beta_contagion: float = 0.12         # Peer-to-peer social diffusion rate
    deterrence_factor: float = 0.05      # Police presence slowdown factor
    f_crit_ratio: float = 0.35           # Fraction of sympathizers needed for Martyrdom (below = Decapitation)
    eruption_ratio: float = 0.70         # Fraction of sympathizers needed for open street action


@dataclass
class ResistanceState:
    """Per-tile popular resistance status."""
    tile_name: str
    revolt_intensity: float = 0.0      # 0.0 to 1.0
    fences_torn: int = 0               # cumulative plots de-enclosed by revolt
    is_general_strike: bool = False    # halts production and transport routes
    strike_turns_active: int = 0
    has_barricades: bool = False       # barricades erected by worker militias
    barricade_hp: float = 0.0          # structural integrity of street barricades (requires military to breach)
    armory_raided: bool = False        # state armory weapons seized
    militia_strength: int = 0          # armed citizen insurgents

    # ---- Multi-turn Stepped Anti-Enclosure Escalation ----
    enclosure_stage: str = "dormant"   # 'dormant' | 'organizing' | 'announced' | 'marching' | 'protest' | 'leveling'
    target_plot_id: Optional[str] = None
    target_plot_fraction: float = 0.0
    revolt_participants: List[int] = field(default_factory=list)  # Agent IDs actively mobilizing
    stage_turn: int = 0                # turn index of current stage
    martyrdom_multiplier: float = 1.0  # multiplier to future turnout from police killings
    terror_cooldown: int = 0           # chilling effect: turns where terror prevents organizing
    sympathizer_food_donated: int = 0  # food provided to marchers
    police_employed: int = 0           # employed police officers on payroll

    # ---- Charismatic Agitators & Fermentation Dynamics ----
    leader_id: Optional[int] = None
    leader_name: str = ""
    leader_charisma: float = 0.0
    followers: List[int] = field(default_factory=list)
    fermentation_turns: int = 0
    martyrs: List[str] = field(default_factory=list)
    active_plot: Optional[AssassinationPlot] = None


