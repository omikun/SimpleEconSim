"""
economy/conspicuous_consumption.py — Aristocratic Prestige, Conspicuous Consumption, and Status Dynamics.

Theoretical Grounding (Werner Sombart / Thorstein Veblen / Sven Beckert):
1. Conspicuous Consumption: Elites derive social prestige, lineage standing, and political influence
   from consuming high-status non-subsistence foreign luxuries (fine textiles, porcelain, tea, rum).
2. Status Decay & Insatiable Greed: Prestige decays over time unless constantly replenished by new luxury
   inflows. When prestige drops, the elite's marginal utility for money (shadow price of cash) spikes,
   motivating aggressive land enclosure, industrial machinery investment, and colonial trade ventures.
3. Extensible Incentives: Generalizable profile mapping commodities to alternative social outcomes
   (Prestige, Popular Relief / Morale, Piety).
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Any, Tuple
from goods import Goods
from economy.transformation_graph import TransformationGraph, CommoditySpec


class PrestigeTier:
    PROVINCIAL = "Provincial Gentry"        # 0 - 14 prestige
    BURGHER = "Burgher / Merchant"          # 15 - 39 prestige
    LORD_OF_MANOR = "Lord of the Manor"     # 40 - 99 prestige
    MAGNATE = "Magnate / Grand Duke"        # 100+ prestige


class ConspicuousConsumptionManager:
    """Manages luxury consumption schedules, prestige accumulation, and status decay."""

    @classmethod
    def get_status_tier(cls, prestige_score: float) -> str:
        """Map numeric prestige score to aristocratic social title."""
        if prestige_score >= 100.0:
            return PrestigeTier.MAGNATE
        elif prestige_score >= 40.0:
            return PrestigeTier.LORD_OF_MANOR
        elif prestige_score >= 15.0:
            return PrestigeTier.BURGHER
        else:
            return PrestigeTier.PROVINCIAL

    @classmethod
    def consume_luxuries_for_agent(cls, agent: Any, region: Any, t: int) -> Dict[str, Any]:
        """Process turn-based consumption of held luxury goods for an elite agent."""
        is_elite = (getattr(agent, 'is_lord', False) or
                    getattr(agent, 'is_corporation', False) or
                    getattr(agent, 'cash', 0.0) >= 80.0 or
                    getattr(agent, 'prestige_score', 0.0) > 0.0)

        if not is_elite or not getattr(agent, 'alive', True):
            return {'consumed': {}, 'prestige_gain': 0.0, 'current_score': getattr(agent, 'prestige_score', 0.0)}

        if not hasattr(agent, 'prestige_score'):
            agent.prestige_score = 0.0
        if not hasattr(agent, 'luxury_consumption_log'):
            agent.luxury_consumption_log = []

        total_gain = 0.0
        consumed_dict = {}

        # Scan for all goods with prestige_rating > 0
        for g in getattr(region, 'goods', []):
            spec = TransformationGraph.get_commodity_spec(g)
            if spec and spec.prestige_rating > 0.0:
                held = agent.inv_get(g, 0)
                if held > 0:
                    # Consume 1 unit per cycle (conspicuous aristocratic consumption)
                    consume_qty = 1
                    agent.inv_add(g, -consume_qty)
                    consumed_dict[spec.name] = consume_qty

                    # Diminishing marginal utility of prestige
                    saturation = 1.0 / (1.0 + 0.02 * agent.prestige_score)
                    gain = spec.prestige_rating * saturation
                    agent.prestige_score += gain
                    total_gain += gain

        # Apply natural prestige decay (status must be maintained through steady flows)
        if total_gain == 0.0 and agent.prestige_score > 0.0:
            decay = min(agent.prestige_score, 0.40)
            agent.prestige_score = max(0.0, agent.prestige_score - decay)

        agent.prestige_score = round(agent.prestige_score, 2)
        agent.status_tier = cls.get_status_tier(agent.prestige_score)

        return {
            'agent_id': agent.id,
            'consumed': consumed_dict,
            'prestige_gain': round(total_gain, 2),
            'current_score': agent.prestige_score,
            'status_tier': agent.status_tier
        }

    @classmethod
    def step_region_conspicuous_consumption(cls, region: Any, t: int) -> List[Dict[str, Any]]:
        """Run consumption for all elites in the region."""
        reports = []
        for a in getattr(region, 'agents', []):
            if getattr(a, 'alive', True):
                rep = cls.consume_luxuries_for_agent(a, region, t)
                if rep['prestige_gain'] > 0 or rep.get('consumed'):
                    reports.append(rep)
        return reports
