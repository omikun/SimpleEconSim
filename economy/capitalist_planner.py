"""
economy/capitalist_planner.py — Goal-Oriented Action Planner & Investment Engine for Elites.

Theoretical Grounding (Sven Beckert / Werner Sombart):
1. Luxury Catalyst: Traditional elites are stimulated by the presence of prestige goods on the
   market to convert their endowments (feudal land tenure, serf labor, natural resources)
   into liquid money.
2. Capitalist Investment: Capitalists allocate liquid wealth into production sectors yielding
   the highest Return on Capital (ROC), bidding up wages and creating labor vacancies.
3. Cadence Requirement: Elites run planning every 5 turns or immediately when a new item enters
   the market.
"""

from __future__ import annotations
import math
from typing import List, Dict, Any, Optional, Tuple
from goods import Goods
from economy.transformation_graph import TransformationGraph, CommoditySpec, TransformationOperator


class EliteCapitalistPlanner:
    """Decision engine for landed nobility, merchants, and capitalists."""

    def __init__(self):
        self._known_market_goods: Dict[str, set] = {}
        self._last_plan_turn: Dict[int, int] = {}
        self._active_plans: Dict[int, Dict[str, Any]] = {}

    def get_market_luxuries(self, region: Any) -> List[Tuple[Any, float, float, int]]:
        """Identify available luxury goods in region or trade pipelines.
        
        Returns: list of (good, price, prestige_rating, available_qty)
        """
        luxuries = []
        recipes = getattr(region, 'recipes', {})
        for g in getattr(region, 'goods', []):
            spec = TransformationGraph.get_commodity_spec(g)
            if spec and spec.prestige_rating > 0:
                price = float(recipes.get(g, {}).get('price', spec.base_price))
                # Check supply on market or in region agent inventories
                market_qty = sum(a.inv_get(g, 0) for a in getattr(region, 'agents', [])
                                 if getattr(a, 'alive', True) and not getattr(a, 'is_lord', False))
                if market_qty > 0:
                    luxuries.append((g, price, spec.prestige_rating, market_qty))
        return luxuries

    def check_new_market_items(self, region: Any) -> bool:
        """Check if any previously unobserved goods have appeared on the region market."""
        reg_name = getattr(region, 'name', 'default')
        known = self._known_market_goods.get(reg_name, set())
        current = set()
        for a in getattr(region, 'agents', []):
            if getattr(a, 'alive', True):
                for g in getattr(region, 'goods', []):
                    if a.inv_get(g, 0) > 0:
                        current.add(g)

        new_items = current - known
        if new_items:
            self._known_market_goods[reg_name] = current
            return True
        self._known_market_goods[reg_name] = current
        return False

    def calculate_shadow_price_cash(self, agent: Any, region: Any) -> float:
        """Calculate dynamic shadow price of cash (lambda_cash) based on luxury desires."""
        base_lambda = 1.0
        luxuries = self.get_market_luxuries(region)
        if not luxuries:
            return base_lambda

        # Check agent's existing luxury satisfaction
        held_luxury_prestige = 0.0
        for g, _, prestige, _ in luxuries:
            held_luxury_prestige += agent.inv_get(g, 0) * prestige

        # Marginal utility of cash spikes when high-prestige luxuries are available
        best_luxury_ratio = max(prestige / max(1.0, price) for _, price, prestige, _ in luxuries)
        saturation_discount = 1.0 / (1.0 + 0.1 * held_luxury_prestige)
        shadow_price = base_lambda + (best_luxury_ratio * 2.0 * saturation_discount)
        return round(shadow_price, 3)

    def is_elite(self, agent: Any, region: Any) -> bool:
        """Check if agent qualifies as an elite (lord, capitalist, large merchant)."""
        if getattr(agent, 'is_lord', False):
            return True
        if getattr(agent, 'is_corporation', False) or getattr(agent, 'company_owned', None) is not None:
            return True
        if getattr(agent, 'cash', 0.0) >= 150.0:
            return True
        if getattr(agent, 'is_trader', False) and getattr(agent, 'cash', 0.0) >= 50.0:
            return True
        return False

    def should_run_planning(self, agent: Any, region: Any, t: int, market_has_new_items: bool) -> bool:
        """Check user cadence constraint: every 5 turns or when a new item enters market."""
        if not self.is_elite(agent, region):
            return False
        if market_has_new_items:
            return True
        return (t % 5 == 0)

    def evaluate_spatial_trade(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
        """Evaluate inter-regional trade opportunities across neighboring tiles (Sven Beckert macro trade)."""
        neighbors = getattr(region, 'neighbors', {})
        if not neighbors:
            return None

        # 1. Spatial Luxury Import: If local has 0 luxury, but neighbor has luxury for sale
        if agent.cash >= 30.0:
            for n_name, neighbor in neighbors.items():
                # This direct local-cash path has no FX settlement. Foreign
                # purchases must use the priced route/forex trade system.
                if neighbor.home_currency != region.home_currency:
                    continue
                n_luxuries = self.get_market_luxuries(neighbor)
                for good, price, prestige, qty in n_luxuries:
                    total_cost = price + 2.0  # including haulage fee
                    if agent.cash >= total_cost and agent.inv_get(good, 0) == 0:
                        seller = next((a for a in neighbor.agents if a.alive and a.inv_get(good, 0) > 0), None)
                        if seller:
                            agent.cash -= total_cost
                            seller.cash += price
                            seller.inv_add(good, -1)
                            agent.inv_add(good, 1)
                            gov = getattr(region, 'gov', None)
                            if gov and gov.agent:
                                gov.agent.cash += 2.0
                            return {
                                'action_taken': 'SPATIAL_LUXURY_IMPORT',
                                'details': {'good': good.name if hasattr(good, 'name') else str(good),
                                            'neighbor': n_name, 'price': price, 'total_cost': total_cost}
                            }

        # 2. Spatial Raw Material Input Import for Local Manufacturing:
        company = getattr(agent, 'company_owned', None)
        if (company and getattr(company, 'is_corporation', False) and company.alive
                and company in region.agents
                and company.home_currency == region.home_currency):
            recipe = region.recipes.get(company.output, {})
            input_good = recipe.get('input')
            if input_good and company.inv_get(input_good, 0) < recipe.get('numInput', 1) * 2:
                for n_name, neighbor in neighbors.items():
                    if neighbor.home_currency != region.home_currency:
                        continue
                    n_price = float(neighbor.recipes.get(input_good, {}).get('price', 5.0))
                    seller = next((a for a in neighbor.agents if a.alive and a.inv_get(input_good, 0) > 0), None)
                    if seller and company.cash >= n_price * 4:
                        import_qty = min(seller.inv_get(input_good, 0), 4)
                        cost = import_qty * n_price
                        company.cash -= cost
                        seller.cash += cost
                        seller.inv_add(input_good, -import_qty)
                        company.inv_add(input_good, import_qty)
                        return {
                            'action_taken': 'SPATIAL_INPUT_IMPORT',
                            'details': {'good': input_good.name if hasattr(input_good, 'name') else str(input_good),
                                        'neighbor': n_name, 'quantity': import_qty, 'cost': cost}
                        }

        # 3. Spatial Export of Finished Goods to High-Price Neighbor:
        for g in getattr(region, 'goods', []):
            held = agent.inv_get(g, 0)
            if held > 0 and g != Goods.food:
                p_local = float(region.recipes.get(g, {}).get('price', 1.0))
                for n_name, neighbor in neighbors.items():
                    if neighbor.home_currency != region.home_currency:
                        continue
                    p_neighbor = float(neighbor.recipes.get(g, {}).get('price', 1.0))
                    if p_neighbor >= p_local + 2.0:
                        buyer = next((a for a in neighbor.agents if a.alive and a.cash >= p_neighbor), None)
                        if buyer:
                            export_qty = min(held, max(1, int(buyer.cash // p_neighbor)))
                            sale_val = export_qty * p_neighbor
                            buyer.cash -= sale_val
                            agent.cash += sale_val
                            agent.inv_add(g, -export_qty)
                            buyer.inv_add(g, export_qty)
                            return {
                                'action_taken': 'SPATIAL_EXPORT',
                                'details': {'good': g.name if hasattr(g, 'name') else str(g),
                                            'neighbor': n_name, 'quantity': export_qty, 'revenue': sale_val}
                            }

        return None

    def evaluate_class_legislation(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
        """Evaluate institutional state power operators (Statute of Laborers, Vagrancy Enforcement)."""
        statute_op = TransformationGraph.get_operator('petition_statute_of_laborers')
        if statute_op:
            can_run, _ = statute_op.can_agent_execute(agent, region)
            if can_run:
                exec_res = statute_op.on_execute(agent, region, t)
                return {
                    'action_taken': 'PETITION_STATUTE_OF_LABORERS',
                    'details': exec_res
                }

        vagrancy_op = TransformationGraph.get_operator('enforce_vagrancy_decree')
        if vagrancy_op:
            can_run, _ = vagrancy_op.can_agent_execute(agent, region)
            if can_run:
                exec_res = vagrancy_op.on_execute(agent, region, t)
                return {
                    'action_taken': 'PETITION_VAGRANCY_DECREE',
                    'details': exec_res
                }

        return None

    def _elite_candidate_snapshot(self, agent: Any, region: Any, shadow_cash: float) -> List[Dict[str, Any]]:
        """Capture the actionable alternatives and gates used by elite planning."""
        candidates = [{'candidate': 'do_nothing', 'feasible': True,
                       'priority': 'fallback'}]
        cash = float(getattr(agent, 'cash', 0.0))
        for good, price, prestige, quantity in self.get_market_luxuries(region):
            seller = next((person for person in getattr(region, 'agents', [])
                           if person.id != agent.id and getattr(person, 'alive', True)
                           and person.inv_get(good, 0) > 0), None)
            candidates.append({
                'candidate': 'luxury_purchase', 'good': getattr(good, 'name', str(good)),
                'feasible': bool(cash >= 25.0 and cash >= price and seller),
                'reason': ('ready seller and cash available' if seller and cash >= price
                           else 'requires a live seller and enough cash'),
                'seller_id': str(seller.id) if seller else None,
                'price': float(price), 'prestige': float(prestige),
                'available_quantity': int(quantity),
                'prestige_per_cash': float(prestige) / max(1.0, float(price))})

        recipes = getattr(region, 'recipes', {})
        sectors = []
        for good, recipe in recipes.items():
            if good in (Goods.gov, Goods.none, Goods.foreign_luxuries):
                continue
            if recipe.get('is_luxury') and recipe.get('numInput', 0) == 0:
                continue
            output_price = float(recipe.get('price', 1.0))
            input_good = recipe.get('input')
            input_price = float(recipes.get(input_good, {}).get('price', 0.0)) \
                if recipe.get('numInput', 0) > 0 else 0.0
            margin = (output_price * recipe.get('production', 1.0)
                      - input_price * recipe.get('numInput', 0))
            if not math.isfinite(float(margin)):
                continue
            sectors.append({'good': getattr(good, 'name', str(good)),
                             'estimated_margin': float(margin),
                             'output_price': output_price, 'input_price': input_price})
        sectors.sort(key=lambda row: row['estimated_margin'], reverse=True)
        for sector in sectors[:8]:
            candidates.append({'candidate': 'capital_investment',
                               'feasible': cash >= 150.0 and not getattr(agent, 'is_lord', False),
                               'reason': 'cash threshold 150 and non-lord', **sector})

        trade_manager = getattr(region, 'trade_manager', None)
        if trade_manager is not None:
            for circuit in getattr(trade_manager, 'circuits', {}).values():
                try:
                    arbitrage = trade_manager.evaluate_dynamic_arbitrage(circuit, region)
                    can_charter, charter_reason = trade_manager.can_charter_voyage(
                        agent, region, circuit)
                except (AttributeError, KeyError, TypeError, ValueError):
                    continue
                roi = float(arbitrage.get('roi', 0.0))
                if not math.isfinite(roi):
                    continue
                pioneer = getattr(circuit, 'status', '') == 'DORMANT_UNEXPLORED'
                score = roi + (0.2 if pioneer else 0.0)
                candidates.append({'candidate': 'triangular_trade_voyage',
                                   'circuit_id': str(getattr(circuit, 'circuit_id', 'unknown')),
                                   'feasible': bool(arbitrage.get('viable') and can_charter),
                                   'reason': str(charter_reason), 'roi': roi,
                                   'pioneer_bonus': 0.2 if pioneer else 0.0,
                                   'effective_score': score, 'selection_threshold': 0.20})

        for neighbor_name, neighbor in getattr(region, 'neighbors', {}).items():
            for good, price, prestige, quantity in self.get_market_luxuries(neighbor):
                if agent.inv_get(good, 0) > 0:
                    continue
                total_cost = float(price) + 2.0
                seller = next((person for person in getattr(neighbor, 'agents', [])
                               if getattr(person, 'alive', True) and person.inv_get(good, 0) > 0), None)
                candidates.append({'candidate': 'spatial_luxury_import',
                                   'neighbor': str(neighbor_name),
                                   'good': getattr(good, 'name', str(good)),
                                   'feasible': bool(seller and cash >= 30.0 and cash >= total_cost),
                                   'reason': 'requires cash threshold and neighbor seller',
                                   'price': float(price), 'haulage_fee': 2.0,
                                   'available_quantity': int(quantity)})

        for operator_id in ('petition_statute_of_laborers', 'enforce_vagrancy_decree',
                            'maintain_repair_machinery', 'construct_machinery',
                            'mandate_plantation_labor_gang', 'procure_captive_labor',
                            'chartered_frontier_conquest'):
            operator = TransformationGraph.get_operator(operator_id)
            if operator is None:
                continue
            try:
                feasible, reason = operator.can_agent_execute(agent, region)
                net_return = (operator.estimate_net_return(agent, region, shadow_cash)
                              if feasible else None)
                if net_return is not None and not math.isfinite(float(net_return)):
                    net_return = None
            except (AttributeError, KeyError, TypeError, ValueError):
                feasible, reason, net_return = False, 'candidate evaluation unavailable', None
            candidates.append({'candidate': operator_id, 'feasible': bool(feasible),
                               'reason': str(reason), 'estimated_net_return': net_return,
                               'cash': cash, 'shadow_cash_price': float(shadow_cash)})

        if getattr(agent, 'is_lord', False):
            for operator in TransformationGraph.all_operators():
                if operator.category not in ('enclosure', 'corvee', 'artisan', 'war_capitalism'):
                    continue
                try:
                    feasible, reason = operator.can_agent_execute(agent, region)
                    net_return = (operator.estimate_net_return(agent, region, shadow_cash)
                                  if feasible else None)
                    if net_return is not None and not math.isfinite(float(net_return)):
                        net_return = None
                except (AttributeError, KeyError, TypeError, ValueError):
                    feasible, reason, net_return = False, 'candidate evaluation unavailable', None
                candidates.append({'candidate': operator.id, 'category': operator.category,
                                   'feasible': bool(feasible), 'reason': str(reason),
                                   'estimated_net_return': net_return,
                                   'selection_threshold': 5.0})
        return candidates

    def evaluate_triangular_trade_voyage(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
        """Evaluate chartering an oceanic merchant voyage on discovered trade circuits."""
        trade_mgr = getattr(region, 'trade_manager', None)
        if not trade_mgr:
            return None

        best_circuit = None
        best_roi = -999.0
        best_is_pioneer = False

        for c in trade_mgr.circuits.values():
            arb = trade_mgr.evaluate_dynamic_arbitrage(c, region)
            if arb.get('viable'):
                can_run, _ = trade_mgr.can_charter_voyage(agent, region, c)
                if can_run:
                    roi = arb.get('roi', 0.0)
                    is_pioneer = (getattr(c, 'status', '') == 'DORMANT_UNEXPLORED')
                    effective_score = roi + (0.2 if is_pioneer else 0.0)
                    if effective_score > best_roi:
                        best_roi = effective_score
                        best_circuit = c
                        best_is_pioneer = is_pioneer

        if best_circuit and best_roi >= 0.20:
            res = trade_mgr.charter_voyage(agent, region, best_circuit.circuit_id, is_pioneer=best_is_pioneer)
            if res.get('success'):
                return {
                    'action_taken': 'CHARTER_MERCHANT_VOYAGE',
                    'details': res
                }
        return None

    def plan_and_execute_elite(self, agent: Any, region: Any, t: int) -> Dict[str, Any]:
        """Trace the evaluated plan and its observed execution without a second AI pass."""
        from run_trace import emit
        cash_before = float(agent.cash)
        TransformationGraph.step_pending_capacity_decay(region, t)
        shadow_cash = self.calculate_shadow_price_cash(agent, region)
        candidates = self._elite_candidate_snapshot(agent, region, shadow_cash)
        result = self._plan_and_execute_elite(agent, region, t)
        reported_details = result.get('details', {})
        scalar_details = {str(key): value for key, value in reported_details.items()
                          if value is None or isinstance(value, (str, int, float, bool))}
        subject = {'type': 'agent', 'id': agent.id, 'tile': region.name}
        decision_id = emit(region, kind='corporation_ai_decision', record_class='decision',
                           phase='local', subject=subject,
                           inputs={'opening_cash': cash_before, 'candidates': candidates,
                                   'consideration_order': [
                                       'luxury_purchase', 'triangular_trade', 'spatial_trade',
                                       'class_legislation', 'lord_transformation',
                                       'machinery', 'captured_labor', 'capital_investment',
                                       'inventory_liquidation', 'do_nothing'],
                                   'selected': result.get('action_taken') or 'do_nothing',
                                   'shadow_cash_price': shadow_cash,
                                   'neighbors': sorted(getattr(region, 'neighbors', {}).keys())})
        emit(region, kind='corporation_ai_outcome', record_class='outcome',
             phase='local', subject=subject, metric_id='economy.cash',
             unit=getattr(region, 'home_currency', 'local_currency'),
             before=cash_before, after=float(agent.cash),
             decision_id=decision_id,
             inputs={'action': result.get('action_taken') or 'do_nothing',
                     'details': scalar_details,
                     'omitted_detail_keys': sorted(str(key) for key, value in reported_details.items()
                                                   if value is not None and not isinstance(value, (str, int, float, bool)))})
        return result

    def _plan_and_execute_elite(self, agent: Any, region: Any, t: int) -> Dict[str, Any]:
        """Formulate and execute a multi-step conversion or investment plan for an elite agent."""
        self._last_plan_turn[agent.id] = t
        shadow_cash = self.calculate_shadow_price_cash(agent, region)
        luxuries = self.get_market_luxuries(region)
        result = {
            'agent_id': agent.id,
            'is_lord': getattr(agent, 'is_lord', False),
            'shadow_price_cash': shadow_cash,
            'action_taken': None,
            'details': {}
        }

        # ---------------------------------------------------------------------
        # 1. Luxury Purchase Check: If elite has enough cash, buy luxury!
        # ---------------------------------------------------------------------
        if luxuries and agent.cash >= 25.0:
            luxuries.sort(key=lambda item: item[2] / max(1.0, item[1]), reverse=True)
            for good, price, prestige, qty in luxuries:
                if agent.cash >= price:
                    seller = next((a for a in region.agents if a.id != agent.id and a.alive
                                   and a.inv_get(good, 0) > 0), None)
                    if seller:
                        agent.cash -= price
                        seller.cash += price
                        seller.inv_add(good, -1)
                        agent.inv_add(good, 1)
                        result['action_taken'] = 'PURCHASE_LUXURY'
                        result['details'] = {'good': good.name if hasattr(good, 'name') else str(good),
                                             'price': price, 'seller_id': seller.id}
                        return result

        # ---------------------------------------------------------------------
        # 2. Oceanic Triangular Trade Check (Venture Capital & Merchant Voyages)
        # ---------------------------------------------------------------------
        voyage_res = self.evaluate_triangular_trade_voyage(agent, region, t)
        if voyage_res:
            result['action_taken'] = voyage_res['action_taken']
            result['details'] = voyage_res['details']
            return result

        # ---------------------------------------------------------------------
        # 3. Macro & Spatial Trade Check (Inter-Regional Luxury & Input Import)
        # ---------------------------------------------------------------------
        spatial_res = self.evaluate_spatial_trade(agent, region, t)
        if spatial_res:
            result['action_taken'] = spatial_res['action_taken']
            result['details'] = spatial_res['details']
            return result

        # ---------------------------------------------------------------------
        # 4. Class Legislation Check (Statute of Laborers / Vagrancy Decrees)
        # ---------------------------------------------------------------------
        leg_res = self.evaluate_class_legislation(agent, region, t)
        if leg_res:
            result['action_taken'] = leg_res['action_taken']
            result['details'] = leg_res['details']
            return result

        # ---------------------------------------------------------------------
        # 4. Feudal Lord Conversion: Convert Customary Tenures to Liquid Cash Flows
        # ---------------------------------------------------------------------
        if getattr(agent, 'is_lord', False):
            # Lord evaluates conversion paths to generate cash for luxuries:
            # - Enclosure of customary plot to sheep pasture
            # - Corvée cash crops (cotton, sugar, tobacco)
            # - War Capitalism frontier conquest
            all_ops = TransformationGraph.all_operators()
            best_op = None
            best_roc = -999.0

            for op in all_ops:
                can_run, _ = op.can_agent_execute(agent, region)
                if can_run and op.category in ('enclosure', 'corvee', 'artisan', 'war_capitalism'):
                    net_return = op.estimate_net_return(agent, region, shadow_cash)
                    if net_return > best_roc:
                        best_roc = net_return
                        best_op = op

            # If an enclosure, corvée, or war capitalism operator yields positive net return, execute it!
            if best_op and best_roc > 5.0:
                if best_op.on_execute:
                    exec_res = best_op.on_execute(agent, region, t)
                    result['action_taken'] = f'OPERATOR_EXECUTED_{best_op.id.upper()}'
                    result['details'] = {'operator': best_op.name, 'execution_result': exec_res}
                    return result
                else:
                    # Generic operator inventory transformation
                    if best_op.cash_cost > 0:
                        # Generic cash costs are local permit and service
                        # fees. Keep the payment in the monetary system.
                        if getattr(region, 'gov', None) is None:
                            return result
                        agent.cash -= best_op.cash_cost
                        region.gov.agent.cash += best_op.cash_cost
                        from run_trace import emit
                        emit(region, kind='elite_operator_fee',
                             record_class='transfer', phase='labor',
                             subject={'type': 'agent', 'id': agent.id},
                             metric_id='finance.operator_fee',
                             unit=region.home_currency,
                             after=best_op.cash_cost,
                             inputs={'operator': best_op.id,
                                     'recipient_id': region.gov.agent.id})
                    for g, q in best_op.output_goods.items():
                        agent.inv_add(g, int(q))
                    result['action_taken'] = f'OPERATOR_EXECUTED_{best_op.id.upper()}'
                    result['details'] = {'operator': best_op.name, 'yield': best_op.output_goods}
                    return result

        # ---------------------------------------------------------------------
        # 5. Capital Goods Maintenance & Machinery Construction (Issue-06)
        # ---------------------------------------------------------------------
        repair_op = TransformationGraph.get_operator('maintain_repair_machinery')
        if repair_op:
            can_repair, _ = repair_op.can_agent_execute(agent, region)
            if can_repair:
                exec_res = repair_op.on_execute(agent, region, t)
                if exec_res.get('success'):
                    result['action_taken'] = 'REPAIR_MACHINERY'
                    result['details'] = exec_res
                    return result

        construct_op = TransformationGraph.get_operator('construct_machinery')
        if construct_op and agent.cash >= 60.0:
            can_construct, _ = construct_op.can_agent_execute(agent, region)
            if can_construct:
                construct_ret = construct_op.estimate_net_return(agent, region, shadow_cash)
                if construct_ret > 15.0:
                    exec_res = construct_op.on_execute(agent, region, t)
                    if exec_res.get('success'):
                        result['action_taken'] = 'CONSTRUCT_MACHINERY'
                        result['details'] = exec_res
                        return result

        # ---------------------------------------------------------------------
        # 6. Non-Lord War Capitalism: Chartered Colonial Concessions & Plantation Regimes
        # ---------------------------------------------------------------------
        # A. Plantation gang labor extraction if captive labor available
        gang_op = TransformationGraph.get_operator('mandate_plantation_labor_gang')
        if gang_op:
            can_gang, _ = gang_op.can_agent_execute(agent, region)
            if can_gang:
                gang_ret = gang_op.estimate_net_return(agent, region, shadow_cash)
                if gang_ret > 10.0:
                    exec_res = gang_op.on_execute(agent, region, t)
                    if exec_res.get('success'):
                        result['action_taken'] = 'MANDATE_PLANTATION_LABOR_GANG'
                        result['details'] = exec_res
                        return result

        # B. Procure captive labor for existing estates
        procure_op = TransformationGraph.get_operator('procure_captive_labor')
        if procure_op:
            can_procure, _ = procure_op.can_agent_execute(agent, region)
            if can_procure:
                procure_ret = procure_op.estimate_net_return(agent, region, shadow_cash)
                if procure_ret > 15.0:
                    exec_res = procure_op.on_execute(agent, region, t)
                    if exec_res.get('success'):
                        result['action_taken'] = 'PROCURE_CAPTIVE_LABOR'
                        result['details'] = exec_res
                        return result

        # C. Chartered frontier conquest
        war_cap_op = TransformationGraph.get_operator('chartered_frontier_conquest')
        if war_cap_op and agent.cash >= 50.0:
            can_conquer, _ = war_cap_op.can_agent_execute(agent, region)
            if can_conquer:
                conquer_ret = war_cap_op.estimate_net_return(agent, region, shadow_cash)
                if conquer_ret > 20.0:
                    exec_res = war_cap_op.on_execute(agent, region, t)
                    if exec_res.get('success'):
                        result['action_taken'] = 'WAR_CAPITALISM_FRONTIER_CONQUEST'
                        result['details'] = exec_res
                        return result

        # ---------------------------------------------------------------------
        # 3. Capitalist Investment & Wage Bidding
        # ---------------------------------------------------------------------
        if agent.cash >= 150.0 and not getattr(agent, 'is_lord', False):
            # Find the most profitable sector to invest or incorporate
            recipes = getattr(region, 'recipes', {})
            best_sector = None
            best_profit_margin = 0.0

            for g, r in recipes.items():
                if g in (Goods.gov, Goods.none, Goods.foreign_luxuries):
                    continue
                if r.get('is_luxury') and r.get('numInput', 0) == 0:
                    continue
                if r.get('import_only'):
                    continue
                p_out = float(r.get('price', 1.0))
                req_qty = float(r.get('numInput', 0))
                in_good = r.get('input')
                p_in = float(recipes.get(in_good, {}).get('price', 0.0)) if req_qty > 0 else 0.0
                margin = (p_out * r.get('production', 1.0)) - (p_in * req_qty)
                if req_qty > 0 and in_good is not None:
                    local_supply = (
                        sum(p.inv_get(in_good, 0) for p in getattr(region, 'agents', []) if getattr(p, 'alive', True))
                        + sum(1 for p in getattr(region, 'agents', []) if getattr(p, 'alive', True) and getattr(p, 'output', None) == in_good)
                    )
                    if local_supply < req_qty:
                        margin *= 0.05
                if margin > best_profit_margin:
                    best_profit_margin = margin
                    best_sector = g

            # Invest in existing firm or found new corporation
            company = getattr(agent, 'company_owned', None)
            if (company and getattr(company, 'is_corporation', False) and company.alive
                    and company in region.agents
                    and company.home_currency == region.home_currency):
                # Capital injection to expand workforce & machinery
                injection = min(agent.cash * 0.4, 50.0)
                agent.cash -= injection
                company.cash += injection
                # Raise offered wage to attract more workers
                company.wage = round(max(company.wage * 1.10, company.wage + 0.5), 2)
                company.max_employees = min(50, company.max_employees + 5)
                result['action_taken'] = 'CAPITAL_EXPANSION'
                result['details'] = {'company_id': company.id, 'injection': injection, 'new_wage': company.wage}
                return result
            elif (company is None and agent.cash >= 300.0
                  and not getattr(agent, 'employer', None) and best_sector):
                # Incorporate firm in highest-margin sector
                from agent import Agent, seed_traits
                comp = Agent(t)
                comp.is_corporation = True
                seed_traits(comp)
                comp.output = best_sector
                comp.owner = agent
                comp._bank_ref = getattr(region, 'bank', None)
                comp.home_currency = getattr(region, 'home_currency', None)
                comp.region = getattr(region, 'name', '')
                agent.company_owned = comp
                equity = min(agent.cash * 0.5, agent.cash - 60.0)
                agent.cash -= equity
                comp.cash = equity
                # Attractive wage to stimulate profession adoption
                food_p = float(region.recipes.get(Goods.food, {}).get('price', 1.0))
                comp.wage = round(max(2.0, food_p * 2.0), 2)
                comp.max_employees = 15
                region.agents.append(comp)
                result['action_taken'] = 'INCORPORATE_FIRM'
                result['details'] = {'company_id': comp.id, 'sector': best_sector.name, 'wage': comp.wage}
                return result

        # ---------------------------------------------------------------------
        # 4. Market Liquidation: Sell excess non-luxury inventory for cash
        # ---------------------------------------------------------------------
        for g in getattr(region, 'goods', []):
            spec = TransformationGraph.get_commodity_spec(g)
            if spec and spec.prestige_rating == 0.0 and g != Goods.food:
                held = agent.inv_get(g, 0)
                if held > 0:
                    p = float(region.recipes.get(g, {}).get('price', 1.0))
                    buyer = next((a for a in region.agents if a.id != agent.id and a.alive
                                  and a.cash >= p), None)
                    if buyer:
                        sale_qty = min(held, max(1, int(buyer.cash // p)))
                        trade_cash = sale_qty * p
                        buyer.cash -= trade_cash
                        agent.cash += trade_cash
                        agent.inv_add(g, -sale_qty)
                        buyer.inv_add(g, sale_qty)
                        result['action_taken'] = f'LIQUIDATE_{g.name.upper()}'
                        result['details'] = {'good': g.name, 'quantity': sale_qty, 'cash_received': trade_cash}
                        return result

        return result
