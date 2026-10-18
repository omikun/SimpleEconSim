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

        prestige_before = float(agent.prestige_score)
        status_before = getattr(
            agent, 'status_tier', cls.get_status_tier(prestige_before))
        total_gain = 0.0
        consumed_dict = {}
        consumption_event_ids = []
        prestige_calculations = []
        eligible_luxury_holdings = []

        # Scan for all goods with prestige_rating > 0
        for g in getattr(region, 'goods', []):
            spec = TransformationGraph.get_commodity_spec(g)
            if spec and spec.prestige_rating > 0.0:
                held = agent.inv_get(g, 0)
                eligible_luxury_holdings.append(
                    {'good': g.name, 'held_units': held})
                if held > 0:
                    # Consume 1 unit per cycle (conspicuous aristocratic consumption)
                    consume_qty = 1
                    inventory_before = held
                    prestige_before_good = float(agent.prestige_score)
                    saturation = 1.0 / (1.0 + 0.02 * prestige_before_good)
                    gain = spec.prestige_rating * saturation
                    agent.inv_add(g, -consume_qty)
                    consumed_dict[spec.name] = consume_qty

                    # Diminishing marginal utility of prestige
                    agent.prestige_score += gain
                    total_gain += gain
                    calculation = {
                        'good': g.name,
                        'good_name': spec.name,
                        'inventory_before': inventory_before,
                        'inventory_after': agent.inv_get(g, 0),
                        'units_consumed': consume_qty,
                        'prestige_rating': float(spec.prestige_rating),
                        'prestige_before': prestige_before_good,
                        'saturation_multiplier': saturation,
                        'prestige_gain': gain,
                        'prestige_after': float(agent.prestige_score),
                    }
                    prestige_calculations.append(calculation)
                    event_id = _emit_trace(
                        region, kind='elite_luxury_consumption',
                        record_class='outcome', phase='scenario_economy',
                        subject={'type': 'agent/good', 'id': str(agent.id),
                                 'good': g.name},
                        metric_id='goods.elite_luxury_consumption',
                        unit='units', before=inventory_before,
                        after=calculation['inventory_after'],
                        inputs={'turn': t, 'agent_id': agent.id,
                                'good_name': spec.name,
                                'prestige_rating': float(spec.prestige_rating),
                                'prestige_before': prestige_before_good,
                                'saturation_multiplier': saturation,
                                'prestige_gain': gain,
                                'prestige_after': float(agent.prestige_score)})
                    if event_id is not None:
                        consumption_event_ids.append(event_id)

        # Apply natural prestige decay (status must be maintained through steady flows)
        decay = 0.0
        if total_gain == 0.0 and agent.prestige_score > 0.0:
            decay = min(agent.prestige_score, 0.40)
            agent.prestige_score = max(0.0, agent.prestige_score - decay)

        agent.prestige_score = round(agent.prestige_score, 2)
        agent.status_tier = cls.get_status_tier(agent.prestige_score)

        if consumed_dict or prestige_before > 0.0:
            is_decay = total_gain == 0.0 and decay > 0.0
            _emit_trace(
                region,
                kind='elite_prestige_decay' if is_decay else 'elite_prestige_update',
                record_class='outcome', phase='scenario_economy',
                subject={'type': 'agent', 'id': str(agent.id)},
                metric_id='society.elite_prestige',
                before=prestige_before, after=float(agent.prestige_score),
                unit='prestige_points',
                formula_id=('prestige.no_luxury_decay.v1' if is_decay
                            else 'prestige.luxury_gain.v1'),
                cause_event_ids=consumption_event_ids or None,
                inputs={
                    'turn': t, 'agent_id': agent.id,
                    'outcome': 'decay' if is_decay else 'luxury_gain',
                    'prestige_gain_unrounded': float(total_gain),
                    'decay_applied': float(decay),
                    'decay_cap': 0.40,
                    'rounding_decimals': 2,
                    'prestige_calculations': prestige_calculations,
                    'eligible_luxury_holdings': eligible_luxury_holdings,
                    'status_tier_before': status_before,
                    'status_tier_after': agent.status_tier,
                    'status_tier_formula_id':
                        'prestige.status_tier_thresholds.v1'})

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


def _emit_trace(region: Any, **event: Any) -> Optional[str]:
    """Emit an event only when this scenario region is collecting a run trace."""
    if (getattr(region, '_run_trace', None) is None
            or getattr(region, '_collective_trace_clock', None) is None):
        return None
    from run_trace import emit
    return emit(region, **event)
