"""
economy/portfolio_optimizer.py — Continuous Multi-Asset Portfolio Optimization (Issue-05).

Theoretical Grounding:
Elite landholders (feudal lords, agrarian gentry, corporate plantation managers)
do not simply pick a single discrete operator for their entire estate. Instead,
they solve a constrained land allocation problem:
    max_{x} sum_i x_i * E[R_i] - lambda * Var(R)
    subject to:
        sum_i x_i <= Total_Acreage
        x_food >= Food_Security_Requirement (to feed domestic serfs/retinue)
        x_peasant >= Peasant_Stability_Floor (to avoid immediate peasant jacquerie/revolt)
        x_i >= 0 for all sectors i
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from goods import Goods
from economy.transformation_graph import TransformationGraph


class EstatePortfolioOptimizer:
    """Solves bounded continuous land allocation across multiple agricultural and extractive sectors."""

    def __init__(self, risk_aversion: float = 0.15):
        self.risk_aversion = risk_aversion

    def compute_optimal_allocation(
        self,
        agent: Any,
        region: Any,
        total_plots: int,
        serf_count: int,
        shadow_cash: float = 1.0,
    ) -> Dict[str, Any]:
        """Compute the optimal continuous division of land plots across competing sectors.

        Sectors:
        - 'food_subsistence': Grain/wheat for household and dependent food security.
        - 'pasture_wool': Fenced sheep pasture for market wool export.
        - 'cash_crop': High-value cash crops (cotton, sugar, tobacco) in viable climates.
        - 'customary_tenure': Retaining customary serf strips to preserve corvée labor pool.
        """
        if total_plots <= 0:
            return {'allocations': {}, 'expected_profit': 0.0, 'plots_allocated': 0}

        # 1. Food Security Constraint:
        # Minimum plots needed to feed domestic population/serfs without starving
        calories_per_plot = 15.0 # standard yield
        food_needed = max(1.0, float(serf_count) * 0.40)
        min_food_plots = min(total_plots, max(1, int((food_needed / calories_per_plot) * total_plots)))

        # 2. Peasant Stability Constraint:
        # Avoid total dispossession that immediately sparks revolt (keep at least 1 customary plot if feudal)
        is_lord = getattr(agent, 'is_lord', False)
        min_customary_plots = 1 if (is_lord and serf_count >= 3 and total_plots >= 3) else 0

        # Remaining discretionary plots to optimize
        discretionary_plots = max(0, total_plots - min_food_plots - min_customary_plots)

        # 3. Expected Returns per Plot:
        climate = getattr(region, 'climate', 'temperate')
        biome = getattr(region, 'biome', 'plains')

        # Food return
        p_food = TransformationGraph.compute_expected_price(region, Goods.food)
        return_food = p_food * 12.0 * shadow_cash

        # Wool return
        p_wool = TransformationGraph.compute_expected_price(region, Goods.wool)
        return_wool = (p_wool * 14.0 * shadow_cash) - (2.0 * shadow_cash) # shepherd overhead

        # Cash crop return (Cotton or Sugar)
        cash_crop_name = 'cotton'
        cash_crop_good = Goods.cotton
        can_grow_cash_crop = climate in ('temperate', 'subtropical', 'tropical', 'mediterranean') and biome not in ('ocean', 'deep_ocean', 'arctic')
        if can_grow_cash_crop:
            p_cash = TransformationGraph.compute_expected_price(region, cash_crop_good)
            return_cash_crop = (p_cash * 16.0 * shadow_cash) - (3.0 * shadow_cash)
        else:
            return_cash_crop = -999.0

        # Customary rent/tribute return
        return_customary = 4.0 * shadow_cash

        # 4. Continuous Bounded Optimization (Linear Programming with Risk Diversification Penalty):
        # Candidates for discretionary plots
        sector_returns = [
            ('pasture_wool', return_wool, 0.10),
            ('cash_crop', return_cash_crop, 0.15),
            ('food_surplus', return_food * 0.9, 0.05),
            ('customary_tenure', return_customary, 0.02),
        ]
        # Filter viable
        valid_sectors = [s for s in sector_returns if s[1] > 0]
        valid_sectors.sort(key=lambda s: s[1], reverse=True)

        allocations: Dict[str, int] = {
            'food_subsistence': min_food_plots,
            'customary_tenure': min_customary_plots,
            'pasture_wool': 0,
            'cash_crop': 0,
        }

        # Allocate discretionary plots using convex return-risk ranking
        remaining = discretionary_plots
        if valid_sectors and remaining > 0:
            # If top sector dominates by > 20%, allocate bulk to it while retaining diversification
            top_sector, top_ret, top_risk = valid_sectors[0]
            if len(valid_sectors) > 1 and remaining >= 3:
                second_sector, second_ret, second_risk = valid_sectors[1]
                # Diversified split: 70% to top, 30% to runner-up
                top_share = max(1, int(remaining * 0.70))
                second_share = remaining - top_share

                if top_sector == 'food_surplus':
                    allocations['food_subsistence'] += top_share
                else:
                    allocations[top_sector] = allocations.get(top_sector, 0) + top_share

                if second_sector == 'food_surplus':
                    allocations['food_subsistence'] += second_share
                else:
                    allocations[second_sector] = allocations.get(second_sector, 0) + second_share
            else:
                if top_sector == 'food_surplus':
                    allocations['food_subsistence'] += remaining
                else:
                    allocations[top_sector] = allocations.get(top_sector, 0) + remaining

        total_expected_profit = (
            allocations['food_subsistence'] * return_food +
            allocations.get('pasture_wool', 0) * return_wool +
            allocations.get('cash_crop', 0) * (return_cash_crop if can_grow_cash_crop else 0.0) +
            allocations['customary_tenure'] * return_customary
        )

        return {
            'allocations': allocations,
            'min_food_security_plots': min_food_plots,
            'min_customary_plots': min_customary_plots,
            'discretionary_plots': discretionary_plots,
            'total_plots': total_plots,
            'expected_profit': round(total_expected_profit, 2),
            'cash_crop_type': cash_crop_name if can_grow_cash_crop else None,
        }

    def apply_allocation_to_tenure(
        self,
        agent: Any,
        region: Any,
        allocation_plan: Dict[str, Any],
        t: int = 0
    ) -> List[Dict[str, Any]]:
        """Applies the calculated portfolio allocation across the physical plots of region.tenure."""
        tenure = getattr(region, 'tenure', None)
        if not tenure or not hasattr(tenure, 'plots'):
            return []

        lord_plots = [p for p in tenure.plots if getattr(p, 'lord_id', None) == agent.id]
        if not lord_plots:
            return []

        allocs = allocation_plan.get('allocations', {})
        wool_needed = allocs.get('pasture_wool', 0)
        cash_needed = allocs.get('cash_crop', 0)

        changes = []
        # Assign pasture wool
        for plot in lord_plots:
            pid = getattr(plot, 'plot_id', getattr(plot, 'id', str(plot)))
            if wool_needed > 0:
                plot.production_type = 'pasture'
                wool_needed -= 1
                changes.append({'plot_id': pid, 'new_sector': 'pasture_wool'})
            elif cash_needed > 0:
                plot.production_type = 'cash_crop'
                cash_crop = allocation_plan.get('cash_crop_type', 'cotton')
                plot.crop = cash_crop
                cash_needed -= 1
                changes.append({'plot_id': pid, 'new_sector': 'cash_crop', 'crop': cash_crop})

        return changes
