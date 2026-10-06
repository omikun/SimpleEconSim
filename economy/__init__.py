"""
economy package — Sven Beckert Capitalist Propagation Engine.

Provides:
- TransformationGraph: Generalized commodity and operator registry with zero-hardcoding extensibility.
- EliteCapitalistPlanner: Decision engine for elites (5-turn / market novelty cadence, dynamic shadow cash pricing, luxury conversion, capital investment).
- LaborMobilityScheduler: Time-sliced n-group scheduler for commoners (< 1s per group), dispossession response, and wage-induced career attraction.
"""

from economy.transformation_graph import (
    TransformationGraph,
    CommoditySpec,
    TransformationOperator,
    initialize_default_transformation_ontology,
    apply_machinery_depreciation,
)
from economy.capitalist_planner import EliteCapitalistPlanner
from economy.labor_mobility import LaborMobilityScheduler
from economy.portfolio_optimizer import EstatePortfolioOptimizer
from economy.finance_bills import BillOfExchange, CreditMarketManager
from economy.commodity_visuals import get_commodity_visual, get_fast_commodity_slot
from economy.map_generator import (
    generate_capitalism_map,
    apply_geological_and_economic_distribution,
    setup_capitalism_institutions,
)
from economy.trade_circuit_discovery import (
    TradeCircuitSpec,
    CircuitStatus,
    TradeCircuitGraphSearch,
    CircuitGatingEvaluator,
)
from economy.triangular_trade import (
    MerchantVoyage,
    TradeTriangleManager,
)
from economy.conspicuous_consumption import (
    PrestigeTier,
    ConspicuousConsumptionManager,
)
from economy.true_cost_ledger import (
    EnterpriseExternalities,
    EnterpriseFinancials,
    TrueCostAuditRecord,
    ShadowPriceManager,
    TrueCostLedger,
    get_shadow_price_manager,
    get_true_cost_ledger,
    DecisionVictimImpact,
    DecisionAuditEntry,
    DecisionExternalitiesTracker,
    get_decision_tracker,
)
from economy.luddite_resistance import (
    LudditeState,
    LudditeMovementManager,
)
from economy.geopolitical_rivalry import (
    StrategicPosture,
    RivalNationState,
    GeopoliticalRivalryManager,
)

__all__ = [
    'TransformationGraph',
    'CommoditySpec',
    'TransformationOperator',
    'initialize_default_transformation_ontology',
    'apply_machinery_depreciation',
    'EliteCapitalistPlanner',
    'LaborMobilityScheduler',
    'EstatePortfolioOptimizer',
    'BillOfExchange',
    'CreditMarketManager',
    'get_commodity_visual',
    'get_fast_commodity_slot',
    'generate_capitalism_map',
    'apply_geological_and_economic_distribution',
    'setup_capitalism_institutions',
    'TradeCircuitSpec',
    'CircuitStatus',
    'TradeCircuitGraphSearch',
    'CircuitGatingEvaluator',
    'MerchantVoyage',
    'TradeTriangleManager',
    'PrestigeTier',
    'ConspicuousConsumptionManager',
    'EnterpriseExternalities',
    'EnterpriseFinancials',
    'TrueCostAuditRecord',
    'ShadowPriceManager',
    'TrueCostLedger',
    'get_shadow_price_manager',
    'get_true_cost_ledger',
    'DecisionVictimImpact',
    'DecisionAuditEntry',
    'DecisionExternalitiesTracker',
    'get_decision_tracker',
    'LudditeState',
    'LudditeMovementManager',
    'StrategicPosture',
    'RivalNationState',
    'GeopoliticalRivalryManager',
]
