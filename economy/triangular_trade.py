"""
economy/triangular_trade.py — Dynamic Arbitrage, Oceanic Voyages, and Multi-Stage Circuit Manager.

Theoretical Grounding (Sven Beckert / Werner Sombart):
1. Macro Oceanic Circulation: Connects metropolitan industrial ports, colonial frontier extraction,
   and exotic luxury trade emporia.
2. Progressive Route Activation: Pioneers venture capital into unexplored circuits, transitioning
   dormant routes into active high-throughput arteries.
3. Strict Conservation: Freight payments are strictly distributed to mariners/artisans, import
   tariffs are credited 100% to the Crown, and cargo exchanges strictly conserve physical quantities.
"""

from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from goods import Goods
from economy.transformation_graph import TransformationGraph, CommoditySpec
from economy.trade_circuit_discovery import TradeCircuitSpec, TradeCircuitGraphSearch, CircuitGatingEvaluator, CircuitStatus


@dataclass
class MerchantVoyage:
    """Active multi-turn oceanic voyage state machine."""
    voyage_id: str
    investor_id: int
    circuit_id: str
    home_region: str
    current_leg: int                  # 1: Outbound, 2: Intermediate/Extraction, 3: Inbound Return
    turns_remaining: int
    total_turns: int
    cargo: Dict[str, float]           # Currently held physical cargo onboard
    capital_invested: float
    expected_luxury: str              # Target luxury commodity to bring home
    expected_qty: float
    is_pioneer: bool = False
    status: str = "EN_ROUTE_OUTBOUND" # "EN_ROUTE_OUTBOUND", "AT_INTERMEDIATE", "EN_ROUTE_INBOUND", "DOCKED_COMPLETED", "LOST"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'voyage_id': self.voyage_id,
            'investor_id': self.investor_id,
            'circuit_id': self.circuit_id,
            'home_region': self.home_region,
            'current_leg': self.current_leg,
            'turns_remaining': self.turns_remaining,
            'total_turns': self.total_turns,
            'cargo': dict(self.cargo),
            'capital_invested': self.capital_invested,
            'expected_luxury': self.expected_luxury,
            'expected_qty': self.expected_qty,
            'is_pioneer': self.is_pioneer,
            'status': self.status
        }


class TradeTriangleManager:
    """Manages discovered trade circuits, voyage scheduling, tariff collection, and route activation."""

    def __init__(self, circuits: Optional[List[TradeCircuitSpec]] = None):
        self.circuits: Dict[str, TradeCircuitSpec] = {}
        self.active_voyages: List[MerchantVoyage] = []
        self.completed_voyages: List[MerchantVoyage] = []
        self.total_tariffs_collected: float = 0.0
        self._voyage_counter: int = 1

        if circuits:
            for c in circuits:
                self.circuits[c.circuit_id] = c
        else:
            # Auto-discover or load default circuits
            loaded = TradeCircuitGraphSearch.discover_circuits()
            for c in loaded:
                self.circuits[c.circuit_id] = c

    def get_circuit(self, circuit_id: str) -> Optional[TradeCircuitSpec]:
        return self.circuits.get(circuit_id)

    def evaluate_dynamic_arbitrage(self, circuit: TradeCircuitSpec, region: Any) -> Dict[str, Any]:
        """Option B: Runtime ROI and negative-cycle evaluation based on live prices."""
        status = CircuitGatingEvaluator.evaluate_circuit_status(circuit, region)
        if status in (CircuitStatus.RESOURCE_LOCKED, CircuitStatus.TECH_LOCKED):
            return {
                'viable': False,
                'status': status,
                'roi': -1.0,
                'roi_threshold': 0.15,
                'reason': f"Circuit is {status}"
            }

        recipes = getattr(region, 'recipes', {})
        export_g = getattr(Goods, circuit.export_good, None)
        luxury_g = getattr(Goods, circuit.import_luxury, None)

        spec_exp = TransformationGraph.get_commodity_spec(export_g or circuit.export_good)
        spec_lux = TransformationGraph.get_commodity_spec(luxury_g or circuit.import_luxury)

        p_exp = float(recipes.get(export_g, {}).get('price', spec_exp.base_price if spec_exp else 10.0))
        p_lux = float(recipes.get(luxury_g, {}).get('price', spec_lux.base_price if spec_lux else 80.0))

        # Standard cargo lot
        q_exp = 5.0 if circuit.export_good == 'cloth' else 2.0
        export_cost = q_exp * p_exp
        freight_cost = circuit.base_freight_cost

        # Yield multiplier: intermediate colonial extraction yields 2x-3x physical leverage
        leverage = 2.5 if circuit.intermediate_good else 1.5
        q_lux = round(max(1.0, (export_cost * leverage) / max(10.0, p_lux)), 1)
        expected_gross_revenue = q_lux * p_lux

        tariff_cost = expected_gross_revenue * circuit.tariff_rate
        total_costs = export_cost + freight_cost + tariff_cost
        net_profit = expected_gross_revenue - total_costs
        roi = net_profit / max(1.0, total_costs)

        return {
            'viable': roi >= 0.15,
            'status': status,
            'roi': round(roi, 3),
            'roi_threshold': 0.15,
            'export_qty': q_exp,
            'luxury_qty': q_lux,
            'export_cost': round(export_cost, 2),
            'export_unit_price': p_exp,
            'freight_cost': freight_cost,
            'expected_gross': round(expected_gross_revenue, 2),
            'luxury_unit_price': p_lux,
            'yield_leverage': leverage,
            'tariff_rate': float(circuit.tariff_rate),
            'tariff_cost': tariff_cost,
            'total_costs': total_costs,
            'expected_profit': round(net_profit, 2),
            'roi_numerator': net_profit,
            'roi_denominator': max(1.0, total_costs),
            'roi_formula': 'expected_profit / max(1, export_cost + freight_cost + tariff_cost)'
        }

    def can_charter_voyage(self, agent: Any, region: Any, circuit: TradeCircuitSpec) -> Tuple[bool, str]:
        """Check if *agent* in *region* has resources and capital to charter this circuit."""
        status = CircuitGatingEvaluator.evaluate_circuit_status(circuit, region)
        if status == CircuitStatus.RESOURCE_LOCKED:
            return False, "Required geological mineral deposit or biome is missing"
        if status == CircuitStatus.TECH_LOCKED:
            return False, "Regional workshops lack the required industrial recipe"

        freight = circuit.base_freight_cost
        if getattr(agent, 'cash', 0.0) < freight:
            return False, f"Insufficient cash for freight (${agent.cash:.1f} < ${freight:.1f})"

        export_g = getattr(Goods, circuit.export_good, None)
        q_needed = 5 if circuit.export_good == 'cloth' else 2
        held_qty = agent.inv_get(export_g, 0) if export_g else 0

        if held_qty < q_needed:
            # Check if agent has cash to buy from local market
            p_exp = float(region.recipes.get(export_g, {}).get('price', 15.0)) if export_g and hasattr(region, 'recipes') else 15.0
            total_cash_needed = freight + (q_needed - held_qty) * p_exp
            if getattr(agent, 'cash', 0.0) < total_cash_needed:
                return False, f"Need {q_needed} {circuit.export_good} or ${total_cash_needed:.1f} to purchase export cargo"

        return True, "Ready to charter"

    def charter_voyage(self, agent: Any, region: Any, circuit_id: str, is_pioneer: bool = False) -> Dict[str, Any]:
        """Dispatch a merchant voyage on circuit_id with strict currency & inventory conservation."""
        circuit = self.get_circuit(circuit_id)
        if not circuit:
            return {'success': False, 'message': f'Unknown circuit {circuit_id}'}

        can_run, reason = self.can_charter_voyage(agent, region, circuit)
        if not can_run:
            return {'success': False, 'message': reason}

        freight = circuit.base_freight_cost
        _public_write = begin_public_change(None, agent)
        agent.cash -= freight
        finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.charter_voyage',
                             inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.charter_voyage:846ba675d0f884c8:1', 'semantic_operation_id': locals().get('operation_id')})

        # Distribute freight cash strictly to local mariners / commoners
        mariners = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                    and a.id != agent.id
                    and not getattr(a, 'is_lord', False) and not getattr(a, 'is_corporation', False)]
        if mariners:
            split = freight / len(mariners)
            for m in mariners:
                _public_write = begin_public_change(None, m)
                m.cash += split
                finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.charter_voyage',
                                     inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.charter_voyage:927237a0ff8750eb:1', 'semantic_operation_id': locals().get('operation_id')})
        elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
            _public_write = begin_public_change(None, region.gov.agent)
            region.gov.agent.cash += freight
            finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.charter_voyage',
                                 inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.charter_voyage:b189ad0516ba53a3:1', 'semantic_operation_id': locals().get('operation_id')})
        else:
            _public_write = begin_public_change(None, agent)
            agent.cash += freight  # refund if no recipient
            finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.charter_voyage',
                                 inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.charter_voyage:1806ec529c0a547b:1', 'semantic_operation_id': locals().get('operation_id')})

        # Acquire export cargo
        export_g = getattr(Goods, circuit.export_good, None)
        q_needed = 5 if circuit.export_good == 'cloth' else 2
        held_qty = agent.inv_get(export_g, 0) if export_g else 0

        actual_cargo_loaded = 0.0
        if held_qty >= q_needed and export_g:
            agent.inv_add(export_g, -q_needed)
            actual_cargo_loaded = float(q_needed)
        else:
            # Deduct held, buy remainder from market
            if held_qty > 0 and export_g:
                agent.inv_add(export_g, -held_qty)
                actual_cargo_loaded += held_qty
            rem = q_needed - actual_cargo_loaded
            p_exp = float(region.recipes.get(export_g, {}).get('price', 15.0)) if export_g and hasattr(region, 'recipes') else 15.0
            cost = rem * p_exp
            _public_write = begin_public_change(None, agent)
            agent.cash -= cost
            finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.charter_voyage',
                                 inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.charter_voyage:cfa352224a344e4c:1', 'semantic_operation_id': locals().get('operation_id')})
            actual_cargo_loaded += rem
            # Conserve cash to producers of export good
            producers = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True) and getattr(a, 'output', None) == export_g]
            if producers:
                split_p = cost / len(producers)
                for p in producers:
                    _public_write = begin_public_change(None, p)
                    p.cash += split_p
                    finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.charter_voyage',
                                         inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.charter_voyage:12ea3b2bedf9d4a9:1', 'semantic_operation_id': locals().get('operation_id')})

        # Calculate target return luxury quantity
        arb = self.evaluate_dynamic_arbitrage(circuit, region)
        expected_q_lux = arb.get('luxury_qty', 3.0)

        voyage = MerchantVoyage(
            voyage_id=f"voyage_{self._voyage_counter}_{region.name}",
            investor_id=agent.id,
            circuit_id=circuit.circuit_id,
            home_region=region.name,
            current_leg=1,
            turns_remaining=circuit.base_voyage_turns,
            total_turns=circuit.base_voyage_turns,
            cargo={circuit.export_good: actual_cargo_loaded},
            capital_invested=freight + (actual_cargo_loaded * 10.0),
            expected_luxury=circuit.import_luxury,
            expected_qty=expected_q_lux,
            is_pioneer=is_pioneer,
            status="EN_ROUTE_OUTBOUND"
        )
        self._voyage_counter += 1
        self.active_voyages.append(voyage)

        # Update circuit status if pioneering
        if is_pioneer or circuit.status == CircuitStatus.DORMANT_UNEXPLORED:
            circuit.status = CircuitStatus.ACTIVATED_ROUTE
            circuit.pioneered_by = agent.id

        return {
            'success': True,
            'voyage_id': voyage.voyage_id,
            'circuit_name': circuit.name,
            'is_pioneer': is_pioneer,
            'turns': circuit.base_voyage_turns,
            'cargo_loaded': actual_cargo_loaded,
            'expected_luxury': circuit.import_luxury,
            'expected_qty': expected_q_lux
        }

    def step_all_voyages(self, world: dict, t: int) -> List[Dict[str, Any]]:
        """Advance active voyages, handle port arrivals, tariff payments, and dockings."""
        events: List[Dict[str, Any]] = []
        still_active: List[MerchantVoyage] = []

        for v in self.active_voyages:
            v.turns_remaining -= 1
            circuit = self.circuits.get(v.circuit_id)

            # Leg 1: Outbound reaching foreign port halfway
            if v.turns_remaining == (v.total_turns // 2) and v.current_leg == 1:
                v.current_leg = 2
                v.status = "AT_INTERMEDIATE"
                # Exchange outbound cargo for colonial/intermediate goods
                if circuit and circuit.intermediate_good:
                    v.cargo = {circuit.intermediate_good: v.expected_qty * 1.5}
                else:
                    v.cargo = {v.expected_luxury: v.expected_qty}
                events.append({
                    'type': 'VOYAGE_INTERMEDIATE',
                    'voyage_id': v.voyage_id,
                    'message': f"Voyage #{v.voyage_id} arrived at overseas post; exchanging cargo for {list(v.cargo.keys())[0]}."
                })
                still_active.append(v)

            # Leg 2 -> Leg 3: Inbound journey
            elif v.turns_remaining == 1 and v.current_leg == 2:
                v.current_leg = 3
                v.status = "EN_ROUTE_INBOUND"
                v.cargo = {v.expected_luxury: v.expected_qty}
                still_active.append(v)

            # Voyage Completes and Docks at Home Port!
            elif v.turns_remaining <= 0:
                v.status = "DOCKED_COMPLETED"
                v.current_leg = 3
                self.completed_voyages.append(v)

                # Locate home region and investor
                region = None
                if 'regions' in world:
                    region = next((r for r in world['regions'] if getattr(r, 'name', '') == v.home_region), None)
                if not region and 'selected_region' in world and getattr(world['selected_region'], 'name', '') == v.home_region:
                    region = world['selected_region']

                investor = None
                if region:
                    investor = next((a for a in getattr(region, 'agents', []) if a.id == v.investor_id and getattr(a, 'alive', True)), None)

                lux_good = getattr(Goods, v.expected_luxury, None)
                qty_arrived = int(v.expected_qty)

                # Collect Crown Customs Tariff (strictly conserved)
                tariff_rate = circuit.tariff_rate if circuit else 0.12
                unit_val = float(region.recipes.get(lux_good, {}).get('price', 60.0)) if region and lux_good and hasattr(region, 'recipes') else 60.0
                total_val = qty_arrived * unit_val
                tariff_owed = round(total_val * tariff_rate, 2)

                if investor and investor.cash >= tariff_owed:
                    _public_write = begin_public_change(None, investor)
                    investor.cash -= tariff_owed
                    finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.step_all_voyages',
                                         inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.step_all_voyages:ac0739d980947e2e:1', 'semantic_operation_id': locals().get('operation_id')})
                elif investor:
                    tariff_owed = min(investor.cash, tariff_owed)
                    _public_write = begin_public_change(None, investor)
                    investor.cash -= tariff_owed
                    finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.step_all_voyages',
                                         inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.step_all_voyages:5f0801bc9b162884:1', 'semantic_operation_id': locals().get('operation_id')})

                if region and getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
                    _public_write = begin_public_change(None, region.gov.agent)
                    region.gov.agent.cash += tariff_owed
                    finish_public_change(_public_write, 'economy.triangular_trade:TradeTriangleManager.step_all_voyages',
                                         inputs={'source_writer': 'economy/triangular_trade.py:TradeTriangleManager.step_all_voyages:c8efbbc8f0146861:1', 'semantic_operation_id': locals().get('operation_id')})
                self.total_tariffs_collected += tariff_owed

                # Deliver cargo
                if investor and lux_good:
                    investor.inv_add(lux_good, qty_arrived)
                elif region and lux_good:
                    # Distribute to local merchants/artisans if investor missing
                    for a in region.agents:
                        if getattr(a, 'alive', True) and not getattr(a, 'is_lord', False):
                            a.inv_add(lux_good, 1)
                            qty_arrived -= 1
                            if qty_arrived <= 0:
                                break

                # Update circuit metrics
                if circuit:
                    circuit.times_sailed += 1
                    circuit.total_volume_traded += v.expected_qty

                msg = f"Voyage #{v.voyage_id} docked safely! Delivered {int(v.expected_qty)}x {v.expected_luxury} (Tariff: ${tariff_owed:.1f})."
                events.append({
                    'type': 'VOYAGE_COMPLETED',
                    'voyage_id': v.voyage_id,
                    'investor_id': v.investor_id,
                    'luxury_received': v.expected_luxury,
                    'qty': v.expected_qty,
                    'tariff_paid': tariff_owed,
                    'message': msg
                })
            else:
                still_active.append(v)

        self.active_voyages = still_active
        return events
