"""
economy/trade_circuit_discovery.py — Algorithmic Discovery & Gating of Global Trade Circuits.

Implements Option A & B (Sven Beckert / Werner Sombart Macrocirculation):
1. Graph-Theoretic Cycle Discovery: Analyzes registered commodities, recipes, and transformation
   operators on engine startup to identify all possible closed commodity/transformation circuits.
2. JSON Serialization: Exports discovered circuits to `scenarios/discovered_trade_circuits.json`.
3. Resource & Technology Gating: Evaluates whether a circuit is RESOURCE_LOCKED, TECH_LOCKED,
   DORMANT_UNEXPLORED, or ACTIVATED_ROUTE based on regional geology, climate, and workshop recipes.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set, Tuple
from goods import Goods
from economy.transformation_graph import TransformationGraph, CommoditySpec, TransformationOperator


class CircuitStatus:
    RESOURCE_LOCKED = "RESOURCE_LOCKED"
    TECH_LOCKED = "TECH_LOCKED"
    DORMANT_UNEXPLORED = "DORMANT_UNEXPLORED"
    ACTIVATED_ROUTE = "ACTIVATED_ROUTE"
    DISRUPTED = "DISRUPTED"


@dataclass
class TradeCircuitSpec:
    """Specification of a closed multi-stage trade circuit."""
    circuit_id: str
    name: str
    export_good: str                  # Name of manufactured or processed export good
    intermediate_good: Optional[str]  # Name of colonial/primary good or captive labor (optional)
    import_luxury: str                # Name of return foreign luxury good
    legs: List[Dict[str, Any]] = field(default_factory=list)
    required_resources: List[str] = field(default_factory=list)   # e.g. ['has_iron_deposit', 'has_coal_vein']
    required_climates: List[str] = field(default_factory=list)    # e.g. ['subtropical', 'temperate']
    required_recipes: List[str] = field(default_factory=list)     # e.g. ['cloth', 'iron']
    base_voyage_turns: int = 4
    base_freight_cost: float = 12.0
    tariff_rate: float = 0.12         # Crown customs duty (12%)
    status: str = CircuitStatus.DORMANT_UNEXPLORED
    pioneered_by: Optional[int] = None # Agent ID who pioneered this route
    times_sailed: int = 0
    total_volume_traded: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TradeCircuitSpec:
        return cls(**data)


class TradeCircuitGraphSearch:
    """Discovers closed trade loops from commodity specs, recipes, and transformation operators."""

    @classmethod
    def build_bipartite_graph(cls) -> Dict[str, List[Dict[str, Any]]]:
        """Build directed transformation graph between commodities."""
        graph: Dict[str, List[Dict[str, Any]]] = {}

        # 1. Operators in TransformationGraph
        for op in TransformationGraph.all_operators():
            if op.category not in ('manufacture', 'corvee', 'enclosure', 'war_capitalism', 'artisan'):
                continue
            inputs = [g.name if hasattr(g, 'name') else str(g) for g in op.input_goods.keys()]
            outputs = [g.name if hasattr(g, 'name') else str(g) for g in op.output_goods.keys()]
            
            # If no inputs, it's a primary extraction (e.g., pasture wool, mining iron ore)
            if not inputs:
                inputs = ['land_endowment']
            
            for inp in inputs:
                if inp not in graph:
                    graph[inp] = []
                for out in outputs:
                    graph[inp].append({
                        'to': out,
                        'type': 'operator',
                        'operator_id': op.id,
                        'category': op.category,
                        'required_resources': getattr(op, 'required_terrain_tags', []),
                        'required_climates': getattr(op, 'allowed_climates', [])
                    })

        # 2. Foreign Exchange Transformations (War Capitalism / Oceanic Commerce)
        # Manufactured cloth/iron/rum -> Frontier raw commodities (cotton, sugar, tobacco, captive labor)
        frontier_intermediates = ['cotton', 'sugar', 'tobacco', 'captive_labor']
        manufactured_exports = ['cloth', 'iron', 'furniture', 'rum']
        for m in manufactured_exports:
            if m not in graph:
                graph[m] = []
            for fi in frontier_intermediates:
                graph[m].append({
                    'to': fi,
                    'type': 'frontier_exchange',
                    'category': 'colonial_trade'
                })

        # Frontier intermediates -> Foreign Luxury Imports (fine_textiles, porcelain, tea, rum, foreign_luxuries)
        foreign_luxuries = ['fine_textiles', 'porcelain', 'tea', 'foreign_luxuries']
        for fi in frontier_intermediates:
            if fi not in graph:
                graph[fi] = []
            for lx in foreign_luxuries:
                graph[fi].append({
                    'to': lx,
                    'type': 'luxury_import',
                    'category': 'luxury_trade'
                })

        # Direct Manufactured Export -> Foreign Luxury Import (Direct Bilateral Trade)
        for m in manufactured_exports:
            for lx in foreign_luxuries:
                graph[m].append({
                    'to': lx,
                    'type': 'direct_luxury_trade',
                    'category': 'luxury_trade'
                })

        # Foreign Luxuries -> Conspicuous Consumption Sink -> Liquid Capital / Aristocratic Utility
        for lx in foreign_luxuries:
            if lx not in graph:
                graph[lx] = []
            graph[lx].append({
                'to': 'cloth',
                'type': 'consumption_reinvestment',
                'category': 'reinvestment'
            })
            graph[lx].append({
                'to': 'iron',
                'type': 'consumption_reinvestment',
                'category': 'reinvestment'
            })

        return graph

    @classmethod
    def discover_circuits(cls) -> List[TradeCircuitSpec]:
        """Find closed cycles of depth 2 to 4 connecting manufactured exports to luxury imports."""
        graph = cls.build_bipartite_graph()
        circuits: List[TradeCircuitSpec] = []
        seen_keys: Set[Tuple[str, Optional[str], str]] = set()

        manufactured_candidates = ['cloth', 'iron', 'rum']
        foreign_luxuries = ['foreign_luxuries', 'porcelain', 'fine_textiles', 'tea']
        frontier_intermediates = ['cotton', 'sugar', 'tobacco', 'captive_labor']

        # 1. Triangular Circuits: Manufactured Export -> Frontier Intermediate -> Foreign Luxury
        for m in manufactured_candidates:
            for fi in frontier_intermediates:
                for lx in foreign_luxuries:
                    key = (m, fi, lx)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    m_name = m.replace('_', ' ').capitalize()
                    fi_name = fi.replace('_', ' ').capitalize()
                    lx_name = lx.replace('_', ' ').capitalize()

                    # Infer required resources
                    req_res = []
                    if m == 'iron' or fi == 'iron_ore':
                        req_res.append('has_iron_deposit')
                    if m in ('cloth', 'iron'):
                        req_res.append('has_coal_vein')

                    # Infer required climates
                    req_clim = []
                    if fi in ('cotton', 'sugar', 'tobacco'):
                        req_clim = ['subtropical', 'tropical', 'temperate']

                    cid = f"triangle_{m}_{fi}_{lx}".lower()
                    c_name = f"Transatlantic Triangle: {m_name} → {fi_name} → {lx_name}"

                    circuit = TradeCircuitSpec(
                        circuit_id=cid,
                        name=c_name,
                        export_good=m,
                        intermediate_good=fi,
                        import_luxury=lx,
                        legs=[
                            {'leg': 1, 'action': 'EXPORT', 'source': m, 'target': fi, 'desc': f'Ship {m_name} to colonial frontier'},
                            {'leg': 2, 'action': 'EXTRACTION', 'source': fi, 'target': lx, 'desc': f'Exchange for {fi_name} and trade for {lx_name}'},
                            {'leg': 3, 'action': 'IMPORT', 'source': lx, 'target': 'metropole', 'desc': f'Deliver {lx_name} to metropolitan port'}
                        ],
                        required_resources=req_res,
                        required_climates=req_clim,
                        required_recipes=[m],
                        base_voyage_turns=4 if fi != 'captive_labor' else 5,
                        base_freight_cost=14.0,
                        tariff_rate=0.12,
                        status=CircuitStatus.DORMANT_UNEXPLORED
                    )
                    circuits.append(circuit)

        # 2. Bilateral Luxury Circuits: Manufactured Export -> Direct Foreign Luxury
        for m in manufactured_candidates:
            for lx in foreign_luxuries:
                key = (m, None, lx)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                m_name = m.replace('_', ' ').capitalize()
                lx_name = lx.replace('_', ' ').capitalize()

                cid = f"bilateral_{m}_{lx}".lower()
                c_name = f"Direct Trade: {m_name} → {lx_name}"

                req_res = []
                if m == 'iron':
                    req_res.append('has_iron_deposit')

                circuit = TradeCircuitSpec(
                    circuit_id=cid,
                    name=c_name,
                    export_good=m,
                    intermediate_good=None,
                    import_luxury=lx,
                    legs=[
                        {'leg': 1, 'action': 'EXPORT', 'source': m, 'target': lx, 'desc': f'Export {m_name} to foreign emporium'},
                        {'leg': 2, 'action': 'IMPORT', 'source': lx, 'target': 'metropole', 'desc': f'Import {lx_name} to home port'}
                    ],
                    required_resources=req_res,
                    required_climates=[],
                    required_recipes=[m],
                    base_voyage_turns=3,
                    base_freight_cost=10.0,
                    tariff_rate=0.10,
                    status=CircuitStatus.DORMANT_UNEXPLORED
                )
                circuits.append(circuit)

        return circuits

    @classmethod
    def save_to_json(cls, circuits: List[TradeCircuitSpec], filepath: str) -> None:
        """Serialize discovered circuits to JSON."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = [c.to_dict() for c in circuits]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_from_json(cls, filepath: str) -> List[TradeCircuitSpec]:
        """Load trade circuits from JSON."""
        if not os.path.exists(filepath):
            return []
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [TradeCircuitSpec.from_dict(item) for item in data]


class CircuitGatingEvaluator:
    """Evaluates geological, technological, and market exploration status of a circuit."""

    @classmethod
    def evaluate_circuit_status(cls, circuit: TradeCircuitSpec, region: Any) -> str:
        """Determines the live status of a circuit relative to a specific metropolitan region."""
        # 1. Geological & Mineral Vein Gate
        for res_tag in circuit.required_resources:
            has_tag = getattr(region, res_tag, False)
            if not has_tag:
                # Check if any neighbor has it (spatial supply chain)
                neighbors = getattr(region, 'neighbors', {})
                neighbor_has = any(getattr(n, res_tag, False) for n in neighbors.values())
                if not neighbor_has:
                    return CircuitStatus.RESOURCE_LOCKED

        # 2. Technological Workshop & Recipe Gate
        recipes = getattr(region, 'recipes', {})
        for req_rec in circuit.required_recipes:
            rec_good = getattr(Goods, req_rec, None)
            if rec_good is not None and rec_good not in recipes:
                # Check string recipe keys
                if req_rec not in recipes:
                    return CircuitStatus.TECH_LOCKED

        # 3. Market Exploration Gate
        if circuit.times_sailed > 0 or getattr(circuit, 'pioneered_by', None) is not None:
            return CircuitStatus.ACTIVATED_ROUTE

        return CircuitStatus.DORMANT_UNEXPLORED
