"""
economy/true_cost_ledger.py — True Cost & Externalities-to-Profit Tracing Engine.

Connects nominal accounting profits to their internal costs (c, v, rent, tax, interest)
and externalized ecological, public health, and sociological liabilities across all four
economic classes (capitalist firms, landlords, merchants, financiers).

Converts physical damages into monetized liabilities using data-driven shadow pricing
loaded from externalities_shadow_prices.json.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


# Default fallback path for configuration
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "externalities_shadow_prices.json"
)


@dataclass
class EnterpriseExternalities:
    """Monetized externalized damage liabilities incurred during turn t."""
    soil_depletion_cost: float = 0.0
    air_pollution_cost: float = 0.0
    water_effluent_cost: float = 0.0
    soil_toxicity_cost: float = 0.0
    labor_health_wear_cost: float = 0.0
    alienation_despair_cost: float = 0.0
    peasant_displacement_cost: float = 0.0
    epidemic_vector_cost: float = 0.0
    debt_peonage_cost: float = 0.0

    @property
    def total_externalized_cost(self) -> float:
        return (
            self.soil_depletion_cost +
            self.air_pollution_cost +
            self.water_effluent_cost +
            self.soil_toxicity_cost +
            self.labor_health_wear_cost +
            self.alienation_despair_cost +
            self.peasant_displacement_cost +
            self.epidemic_vector_cost +
            self.debt_peonage_cost
        )


@dataclass
class EnterpriseFinancials:
    """Internal accounting flows for an enterprise/landlord/merchant/bank in turn t."""
    gross_revenue: float = 0.0
    constant_capital_cost: float = 0.0   # Raw inputs, machinery depreciation, safety
    variable_capital_cost: float = 0.0   # Living wages and scrip
    land_rent_paid: float = 0.0          # Ground rent to landlords
    taxes_paid: float = 0.0              # State taxes and excises
    finance_interest_paid: float = 0.0   # Loan interest and bill discounts
    nominal_profit: float = 0.0          # Accounting net profit
    dividend_paid_to_owner: float = 0.0  # Profit share transferred to elite owner


@dataclass
class TrueCostAuditRecord:
    """Unified True Cost & Profit Trace for an enterprise in turn t."""
    entity_id: int
    entity_name: str
    entity_class: str       # 'firm', 'landlord', 'merchant', 'bank'
    region_name: str
    turn: int
    financials: EnterpriseFinancials
    externalities: EnterpriseExternalities
    true_net_profit: float
    externalization_ratio: float
    parasitic_status: str    # 'ECO_RESTORATIVE', 'SUBSIDIZED_BY_NATURE', 'EXTRACTIVE_PARASITE'
    pigouvian_tax_gap: float


class ShadowPriceManager:
    """Manages loading, caching, and resolution of shadow price conversion coefficients."""

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._config_cache: Optional[Dict[str, Any]] = None
        self._mtime: float = 0.0

    def load_config(self) -> Dict[str, Any]:
        """Load JSON configuration with caching and automatic reload on change."""
        if not os.path.exists(self.config_path):
            return self._default_fallback_config()

        try:
            cur_mtime = os.path.getmtime(self.config_path)
            if self._config_cache is None or cur_mtime > self._mtime:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config_cache = json.load(f)
                self._mtime = cur_mtime
            return self._config_cache
        except Exception:
            if self._config_cache is not None:
                return self._config_cache
            return self._default_fallback_config()

    def _default_fallback_config(self) -> Dict[str, Any]:
        return {
            "default_profile": "victorian_industrial",
            "profiles": {
                "victorian_industrial": {
                    "coefficients": {
                        "soil_depletion_cost": 15.0,
                        "air_pollution_cost": 8.0,
                        "water_effluent_cost": 10.0,
                        "soil_toxicity_cost": 12.0,
                        "labor_health_wear_cost": 20.0,
                        "alienation_despair_cost": 5.0,
                        "peasant_displacement_cost": 25.0,
                        "epidemic_vector_cost": 40.0,
                        "debt_peonage_cost": 1.5,
                    }
                }
            },
            "scenario_mappings": {}
        }

    def get_coefficients(self, scenario_id: Optional[str] = None,
                         age: Optional[str] = None,
                         inline_overrides: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Resolve shadow price coefficients using the 4-tier hierarchy:
        1. Inline scenario overrides
        2. Scenario mapping key in config
        3. Age profile in config
        4. Default profile fallback
        """
        config = self.load_config()
        profiles = config.get("profiles", {})
        default_prof = config.get("default_profile", "victorian_industrial")

        # Start with default profile coefficients
        base_coeffs = dict(profiles.get(default_prof, {}).get("coefficients", {}))

        # Check age profile
        if age and age in profiles:
            base_coeffs.update(profiles[age].get("coefficients", {}))

        # Check scenario mapping
        scenario_mappings = config.get("scenario_mappings", {})
        if scenario_id and scenario_id in scenario_mappings:
            mapped_prof = scenario_mappings[scenario_id]
            if mapped_prof in profiles:
                base_coeffs.update(profiles[mapped_prof].get("coefficients", {}))
        elif scenario_id and scenario_id in profiles:
            base_coeffs.update(profiles[scenario_id].get("coefficients", {}))

        # Check inline overrides
        if inline_overrides:
            base_coeffs.update(inline_overrides)

        return base_coeffs

    def monetize_damages(self, physical_damages: Dict[str, float],
                         scenario_id: Optional[str] = None,
                         age: Optional[str] = None,
                         inline_overrides: Optional[Dict[str, float]] = None) -> EnterpriseExternalities:
        """Convert a dictionary of physical damage units into monetized liabilities."""
        coeffs = self.get_coefficients(scenario_id=scenario_id, age=age, inline_overrides=inline_overrides)

        return EnterpriseExternalities(
            soil_depletion_cost=physical_damages.get("soil_fertility_loss", 0.0) * coeffs.get("soil_depletion_cost", 15.0),
            air_pollution_cost=physical_damages.get("air_smog_emitted", 0.0) * coeffs.get("air_pollution_cost", 8.0),
            water_effluent_cost=physical_damages.get("water_effluent_discharged", 0.0) * coeffs.get("water_effluent_cost", 10.0),
            soil_toxicity_cost=physical_damages.get("soil_toxins_generated", 0.0) * coeffs.get("soil_toxicity_cost", 12.0),
            labor_health_wear_cost=physical_damages.get("labor_health_wear", 0.0) * coeffs.get("labor_health_wear_cost", 20.0),
            alienation_despair_cost=physical_damages.get("alienation_despair", 0.0) * coeffs.get("alienation_despair_cost", 5.0),
            peasant_displacement_cost=physical_damages.get("peasant_evictions", 0.0) * coeffs.get("peasant_displacement_cost", 25.0),
            epidemic_vector_cost=physical_damages.get("epidemic_infections_seeded", 0.0) * coeffs.get("epidemic_vector_cost", 40.0),
            debt_peonage_cost=physical_damages.get("scrip_debt_issued", 0.0) * coeffs.get("debt_peonage_cost", 1.5),
        )


# Global singleton manager
_shadow_price_mgr = ShadowPriceManager()


def get_shadow_price_manager() -> ShadowPriceManager:
    return _shadow_price_mgr


class TrueCostLedger:
    """Per-turn and historical registry of enterprise True Cost & Externalities traces."""

    def __init__(self):
        # turn -> entity_id -> TrueCostAuditRecord
        self._records: Dict[int, Dict[int, TrueCostAuditRecord]] = {}
        # entity_id -> latest TrueCostAuditRecord
        self._latest_records: Dict[int, TrueCostAuditRecord] = {}
        # Working turn buffers for currently executing turn
        # entity_id -> { 'financials': EnterpriseFinancials, 'physical': dict, 'entity_meta': dict }
        self._active_buffers: Dict[int, Dict[str, Any]] = {}

    def reset(self):
        self._records.clear()
        self._latest_records.clear()
        self._active_buffers.clear()

    def _get_buffer(self, entity_id: int, entity_name: str, entity_class: str, region_name: str) -> Dict[str, Any]:
        if entity_id not in self._active_buffers:
            self._active_buffers[entity_id] = {
                "entity_id": entity_id,
                "entity_name": entity_name,
                "entity_class": entity_class,
                "region_name": region_name,
                "financials": EnterpriseFinancials(),
                "physical": {},
            }
        return self._active_buffers[entity_id]

    def record_production(self, firm: Any, region: Any, turn: int,
                           c_cost: float, v_cost: float,
                           physical_damages: Dict[str, float]):
        """Record production-stage inputs, wages, and physical externalities for a firm."""
        buf = self._get_buffer(firm.id, getattr(firm, "name", lambda: f"firm_{firm.id}")(),
                               "firm", getattr(region, "name", "unknown"))
        fin: EnterpriseFinancials = buf["financials"]
        fin.constant_capital_cost += c_cost
        fin.variable_capital_cost += v_cost

        phys: Dict[str, float] = buf["physical"]
        for k, v in physical_damages.items():
            phys[k] = phys.get(k, 0.0) + v

    def record_sales(self, firm: Any, region: Any, turn: int, revenue: float):
        """Record market commodity sales revenue."""
        buf = self._get_buffer(firm.id, getattr(firm, "name", lambda: f"firm_{firm.id}")(),
                               "firm", getattr(region, "name", "unknown"))
        fin: EnterpriseFinancials = buf["financials"]
        fin.gross_revenue += revenue

    def record_finance_deductions(self, firm: Any, region: Any, turn: int,
                                  rent_paid: float = 0.0,
                                  taxes_paid: float = 0.0,
                                  finance_paid: float = 0.0,
                                  dividend_paid: float = 0.0):
        """Record firm finance and overhead outlays."""
        buf = self._get_buffer(firm.id, getattr(firm, "name", lambda: f"firm_{firm.id}")(),
                               "firm", getattr(region, "name", "unknown"))
        fin: EnterpriseFinancials = buf["financials"]
        fin.land_rent_paid += rent_paid
        fin.taxes_paid += taxes_paid
        fin.finance_interest_paid += finance_paid
        fin.dividend_paid_to_owner += dividend_paid

    def record_landlord(self, lord: Any, region: Any, turn: int,
                         gross_rent: float, collection_cost: float,
                         evicted_count: float = 0.0,
                         commons_degrade: float = 0.0,
                         conquest_casualties: float = 0.0):
        """Record landlord ground rent revenues and peasant displacement liabilities."""
        buf = self._get_buffer(lord.id, getattr(lord, "name", lambda: f"lord_{lord.id}")(),
                               "landlord", getattr(region, "name", "unknown"))
        fin: EnterpriseFinancials = buf["financials"]
        fin.gross_revenue += gross_rent
        fin.constant_capital_cost += collection_cost

        phys: Dict[str, float] = buf["physical"]
        phys["peasant_evictions"] = phys.get("peasant_evictions", 0.0) + evicted_count
        phys["soil_fertility_loss"] = phys.get("soil_fertility_loss", 0.0) + commons_degrade

    def record_merchant(self, trader: Any, region: Any, turn: int,
                         gross_arbitrage: float, tolls_and_transport: float,
                         infected_seeds: float = 0.0, famine_risk: float = 0.0):
        """Record merchant inter-regional arbitrage profit and transport/epidemic liabilities."""
        buf = self._get_buffer(trader.id, getattr(trader, "name", lambda: f"trader_{trader.id}")(),
                               "merchant", getattr(region, "name", "unknown"))
        fin: EnterpriseFinancials = buf["financials"]
        fin.gross_revenue += gross_arbitrage
        fin.constant_capital_cost += tolls_and_transport

        phys: Dict[str, float] = buf["physical"]
        phys["epidemic_infections_seeded"] = phys.get("epidemic_infections_seeded", 0.0) + infected_seeds
        phys["alienation_despair"] = phys.get("alienation_despair", 0.0) + famine_risk

    def record_bank(self, bank: Any, region: Any, turn: int,
                     interest_and_discounts: float, funding_costs: float,
                     scrip_debt_issued: float = 0.0, frozen_turns: float = 0.0):
        """Record financial capital returns and debt peonage/contagion liabilities."""
        bank_id = getattr(bank, "id", 999999)
        buf = self._get_buffer(bank_id, getattr(bank, "name", "Regional Bank"),
                               "bank", getattr(region, "name", "unknown"))
        fin: EnterpriseFinancials = buf["financials"]
        fin.gross_revenue += interest_and_discounts
        fin.constant_capital_cost += funding_costs

        phys: Dict[str, float] = buf["physical"]
        phys["scrip_debt_issued"] = phys.get("scrip_debt_issued", 0.0) + scrip_debt_issued
        phys["alienation_despair"] = phys.get("alienation_despair", 0.0) + (frozen_turns * 2.0)

    def seal_turn(self, turn: int, scenario_id: Optional[str] = None, age: Optional[str] = None,
                  inline_overrides: Optional[Dict[str, float]] = None):
        """Seal active turn buffers, convert physical damages to monetary liabilities,
        compute True Net Social Profit, and archive into records.
        """
        turn_records = {}

        for entity_id, buf in self._active_buffers.items():
            fin: EnterpriseFinancials = buf["financials"]
            phys: Dict[str, float] = buf["physical"]

            # Compute nominal profit:
            # gross_revenue - (c + v + rent + tax + interest)
            total_internal_costs = (
                fin.constant_capital_cost +
                fin.variable_capital_cost +
                fin.land_rent_paid +
                fin.taxes_paid +
                fin.finance_interest_paid
            )
            fin.nominal_profit = fin.gross_revenue - total_internal_costs

            # Monetize externalities via shadow pricing
            ext: EnterpriseExternalities = _shadow_price_mgr.monetize_damages(
                phys, scenario_id=scenario_id, age=age, inline_overrides=inline_overrides
            )

            # True Net Social Profit
            true_profit = fin.nominal_profit - ext.total_externalized_cost

            # Externalization ratio
            base_profit = max(1.0, fin.nominal_profit)
            ext_ratio = ext.total_externalized_cost / base_profit

            # Parasitic status evaluation
            if true_profit > 0 and ext.total_externalized_cost <= 0.001:
                status = "ECO_RESTORATIVE"
            elif true_profit >= 0:
                status = "SUBSIDIZED_BY_NATURE"
            else:
                status = "EXTRACTIVE_PARASITE"

            # Pigouvian tax gap: unpaid damages not covered by existing taxes paid
            pigouvian_gap = max(0.0, ext.total_externalized_cost - fin.taxes_paid)

            record = TrueCostAuditRecord(
                entity_id=entity_id,
                entity_name=buf["entity_name"],
                entity_class=buf["entity_class"],
                region_name=buf["region_name"],
                turn=turn,
                financials=fin,
                externalities=ext,
                true_net_profit=round(true_profit, 2),
                externalization_ratio=round(ext_ratio, 3),
                parasitic_status=status,
                pigouvian_tax_gap=round(pigouvian_gap, 2)
            )

            turn_records[entity_id] = record
            self._latest_records[entity_id] = record

        self._records[turn] = turn_records
        self._active_buffers.clear()

    def get_record(self, entity_id: int, turn: Optional[int] = None) -> Optional[TrueCostAuditRecord]:
        """Get record for entity at specific turn or latest."""
        if turn is not None:
            return self._records.get(turn, {}).get(entity_id)
        return self._latest_records.get(entity_id)

    def get_tile_records(self, region_name: str, turn: Optional[int] = None) -> List[TrueCostAuditRecord]:
        """Get all enterprise records on a tile for a given turn."""
        if turn is not None:
            records = self._records.get(turn, {}).values()
        else:
            records = self._latest_records.values()
        return [r for r in records if r.region_name == region_name]

    def get_tile_aggregate(self, region_name: str, turn: Optional[int] = None) -> Dict[str, Any]:
        """Compute aggregate nominal vs true net profit for all entities on a tile."""
        recs = self.get_tile_records(region_name, turn)
        if not recs:
            return {
                "nominal_profit": 0.0,
                "total_externalized_cost": 0.0,
                "true_net_profit": 0.0,
                "avg_externalization_ratio": 0.0,
                "parasitic_count": 0,
                "restorative_count": 0,
            }

        tot_nom = sum(r.financials.nominal_profit for r in recs)
        tot_ext = sum(r.externalities.total_externalized_cost for r in recs)
        tot_true = sum(r.true_net_profit for r in recs)
        parasitic = sum(1 for r in recs if r.parasitic_status == "EXTRACTIVE_PARASITE")
        restorative = sum(1 for r in recs if r.parasitic_status == "ECO_RESTORATIVE")

        return {
            "nominal_profit": round(tot_nom, 2),
            "total_externalized_cost": round(tot_ext, 2),
            "true_net_profit": round(tot_true, 2),
            "avg_externalization_ratio": round(tot_ext / max(1.0, tot_nom), 3),
            "parasitic_count": parasitic,
            "restorative_count": restorative,
        }

    def get_national_corporate_externalities(self, nation_name: Optional[str] = None, world: Optional[dict] = None) -> Dict[str, Any]:
        """Aggregate total externalized costs and nominal profits across all corporations
        belonging to the country throughout the game or scenario.
        """
        all_corp_records: List[TrueCostAuditRecord] = []
        valid_regions = None
        if world and nation_name:
            tiles = world.get('tiles', [])
            valid_regions = {
                t.name for t in tiles
                if getattr(getattr(t, 'owner_nation', None), 'name', None) == nation_name
            }

        for turn_dict in self._records.values():
            for rec in turn_dict.values():
                if rec.entity_class == 'firm':
                    if valid_regions is not None and rec.region_name not in valid_regions:
                        continue
                    all_corp_records.append(rec)

        if not all_corp_records:
            for rec in self._latest_records.values():
                if rec.entity_class == 'firm':
                    if valid_regions is not None and rec.region_name not in valid_regions:
                        continue
                    all_corp_records.append(rec)

        total_nom = sum(r.financials.nominal_profit for r in all_corp_records)
        total_ext = sum(r.externalities.total_externalized_cost for r in all_corp_records)
        true_net = sum(r.true_net_profit for r in all_corp_records)
        ext_ratio = total_ext / max(1.0, total_nom) if total_nom > 0 else (1.0 if total_ext > 0 else 0.0)

        air_cost = sum(r.externalities.air_pollution_cost for r in all_corp_records)
        water_cost = sum(r.externalities.water_effluent_cost for r in all_corp_records)
        soil_cost = sum(r.externalities.soil_depletion_cost for r in all_corp_records)
        tox_cost = sum(r.externalities.soil_toxicity_cost for r in all_corp_records)
        health_cost = sum(r.externalities.labor_health_wear_cost for r in all_corp_records)
        alien_cost = sum(r.externalities.alienation_despair_cost for r in all_corp_records)
        peonage_cost = sum(r.externalities.debt_peonage_cost for r in all_corp_records)

        victims_breakdown = {
            "Factory Proletariat & Wage Laborers": {
                "cost": round(health_cost + alien_cost, 2),
                "share": round((health_cost + alien_cost) / max(1.0, total_ext) * 100, 1),
                "impact": "Exhaustion from >8h shifts, particulate inhalation & machine-pacing health wear"
            },
            "Urban Pop & Riparian Communities": {
                "cost": round(air_cost + water_cost, 2),
                "share": round((air_cost + water_cost) / max(1.0, total_ext) * 100, 1),
                "impact": "Smog respiratory disease & untreated industrial water effluent advection"
            },
            "Agricultural Commoners & Soil Ecosystem": {
                "cost": round(soil_cost + tox_cost, 2),
                "share": round((soil_cost + tox_cost) / max(1.0, total_ext) * 100, 1),
                "impact": "Metabolic soil fertility depletion, agrochemical toxicity & crop nutrient dilution"
            },
            "Company Store Debt Peons": {
                "cost": round(peonage_cost, 2),
                "share": round(peonage_cost / max(1.0, total_ext) * 100, 1),
                "impact": "Truck System Tommy Shop debt peonage, marked-up food credit & scrip bondage"
            }
        }

        by_entity: Dict[int, Dict[str, Any]] = {}
        for r in all_corp_records:
            if r.entity_id not in by_entity:
                by_entity[r.entity_id] = {
                    "id": r.entity_id,
                    "name": r.entity_name,
                    "region": r.region_name,
                    "nominal_profit": 0.0,
                    "externalized_cost": 0.0,
                    "true_net_profit": 0.0,
                }
            by_entity[r.entity_id]["nominal_profit"] += r.financials.nominal_profit
            by_entity[r.entity_id]["externalized_cost"] += r.externalities.total_externalized_cost
            by_entity[r.entity_id]["true_net_profit"] += r.true_net_profit

        corps_summary_list = sorted(by_entity.values(), key=lambda x: x["externalized_cost"], reverse=True)

        return {
            "total_corporate_nominal_profit": round(total_nom, 2),
            "total_corporate_externalized_cost": round(total_ext, 2),
            "corporate_true_net_profit": round(true_net, 2),
            "corporate_externalization_ratio": round(ext_ratio, 3),
            "parasitic_status": "EXTRACTIVE_PARASITE" if true_net < 0 else ("SUBSIDIZED_BY_NATURE" if total_ext > 0 else "ECO_RESTORATIVE"),
            "damage_breakdown": {
                "air_smog_cost": round(air_cost, 2),
                "water_effluent_cost": round(water_cost, 2),
                "soil_depletion_cost": round(soil_cost, 2),
                "soil_toxicity_cost": round(tox_cost, 2),
                "labor_health_wear_cost": round(health_cost, 2),
                "alienation_despair_cost": round(alien_cost, 2),
                "debt_peonage_cost": round(peonage_cost, 2),
            },
            "victims_breakdown": victims_breakdown,
            "corps_list": corps_summary_list,
        }


# Global singleton instance
_true_cost_ledger = TrueCostLedger()


def get_true_cost_ledger() -> TrueCostLedger:
    return _true_cost_ledger


@dataclass
class DecisionVictimImpact:
    victim_group: str
    burden_cost: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "victim_group": self.victim_group,
            "burden_cost": self.burden_cost,
            "description": self.description,
        }


@dataclass
class DecisionAuditEntry:
    turn: int
    action_id: str
    title: str
    category: str
    externalized_cost: float
    damage_breakdown: Dict[str, float]
    victims: List[DecisionVictimImpact]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "action_id": self.action_id,
            "title": self.title,
            "category": self.category,
            "externalized_cost": self.externalized_cost,
            "damage_breakdown": self.damage_breakdown,
            "victims": [v.to_dict() for v in self.victims],
            "rationale": self.rationale,
        }


DECISION_EXTERNALITY_CATALOG: Dict[str, Dict[str, Any]] = {
    'incorporate_steam_mill': {
        'title': 'Incorporate Steam Textile Mill',
        'category': 'industry',
        'cost': 85.0,
        'breakdown': {'air_smog': 48.0, 'labor_health_wear': 37.0},
        'victims': [
            DecisionVictimImpact('Factory Proletariat', 37.0, '14-hour shift exhaustion, machinery speed-up & respiratory damage'),
            DecisionVictimImpact('Urban Population', 48.0, 'Atmospheric coal smog & sulfur soot inhalation'),
        ],
        'rationale': 'Concentrates high-output textile manufacturing while shifting coal smog and workforce physical wear onto urban society.'
    },
    'charter_enclosure_decree': {
        'title': 'Enact Parliamentary Enclosure Act',
        'category': 'agriculture',
        'cost': 95.0,
        'breakdown': {'peasant_displacement': 75.0, 'commons_degradation': 20.0},
        'victims': [
            DecisionVictimImpact('Customary Peasantry & Smallholders', 75.0, 'Abolition of customary usufruct rights, eviction into wage dependency or parish workhouses'),
            DecisionVictimImpact('Common Land Ecosystem', 20.0, 'Loss of customary fallow rotation and pastoral sheep monoculture soil compaction'),
        ],
        'rationale': 'Expropriates customary peasant plots to create commercial pasture, creating an artificial wage labor supply.'
    },
    'launch_frontier_expedition': {
        'title': 'Charter Armed Frontier Expropriation (War Capitalism)',
        'category': 'imperialism',
        'cost': 120.0,
        'breakdown': {'frontier_violence': 80.0, 'indigenous_dispossession': 40.0},
        'victims': [
            DecisionVictimImpact('Frontier Indigenous Populations', 120.0, 'Armed mercenary conquest, violent territorial displacement & casualty losses'),
        ],
        'rationale': 'Deploys armed expeditionary violence to dispossess indigenous inhabitants and seize raw material enclaves.'
    },
    'procure_plantation_gangs': {
        'title': 'Procure Unfree Captive Labor & Mandate Gangs',
        'category': 'imperialism',
        'cost': 150.0,
        'breakdown': {'unfree_labor_bondage': 90.0, 'mortal_attrition': 60.0},
        'victims': [
            DecisionVictimImpact('Captive Enslaved Hands', 150.0, 'Chattel commodification, unfree plantation gang labor & mortal physical attrition'),
        ],
        'rationale': 'Maximizes primary commodity extraction (cotton/sugar) with zero wages by externalizing the mortal cost of human bondage.'
    },
    'enforce_wage_suppression_decree': {
        'title': 'Enforce Statute of Laborers Wage Cap',
        'category': 'state_power',
        'cost': 65.0,
        'breakdown': {'wage_theft': 45.0, 'worker_despair': 20.0},
        'victims': [
            DecisionVictimImpact('Wage-Earning Proletariat', 65.0, 'Statutory suppression of wages during labor shortages and criminalization of worker combinations'),
        ],
        'rationale': 'Weaponizes state law to cap wages below market equilibrium to preserve employer profit margins.'
    },
    'issue_merchant_bills': {
        'title': 'Issue Negotiable Bills of Exchange',
        'category': 'finance',
        'cost': 35.0,
        'breakdown': {'credit_risk': 35.0},
        'victims': [
            DecisionVictimImpact('Downstream Artisan Creditors & Smallholders', 35.0, 'Systemic liquidity risk from over-leveraged bills and insolvency contagion'),
        ],
        'rationale': 'Expands private credit money without metal backing, externalizing systemic default risks onto secondary holders.'
    },
    'expand_armed_garrison': {
        'title': 'Reinforce Armed Overseas Garrison',
        'category': 'military',
        'cost': 45.0,
        'breakdown': {'military_occupation': 45.0},
        'victims': [
            DecisionVictimImpact('Frontier Colonial Inhabitants', 45.0, 'Martial law surveillance, checkpoint intimidation & pacification costs'),
        ],
        'rationale': 'Maintains coercive state presence to enforce colonial primary commodity extraction.'
    },
    'charter_coercive_plantation_supply': {
        'title': 'Mandate Overseas Frontier Plantation Extraction',
        'category': 'imperialism',
        'cost': 110.0,
        'breakdown': {'coerced_extraction': 110.0},
        'victims': [
            DecisionVictimImpact('Overseas Plantation Hands', 110.0, 'Coerced quota deliveries without fair open-market remuneration'),
        ],
        'rationale': 'Forces frontier enclaves to supply metropolitan mills, externalizing supply risk onto unfree laborers.'
    },
    'pay_caisse_instalment': {
        'title': 'Pay Caisse de la Dette Bond Instalment',
        'category': 'finance',
        'cost': 130.0,
        'breakdown': {'relief_diversion': 130.0},
        'victims': [
            DecisionVictimImpact('Egyptian Fellahin & Famine Victims', 130.0, 'Severe calorie deficits due to public revenue diversion away from famine relief to European creditors'),
        ],
        'rationale': 'Prioritizes foreign bondholder debt service at the direct cost of domestic hunger and public nutrition.'
    },
    'withhold_relief_grain': {
        'title': 'Withhold Relief Grain in State Warehouses',
        'category': 'agriculture',
        'cost': 90.0,
        'breakdown': {'starvation_burden': 90.0},
        'victims': [
            DecisionVictimImpact('Impoverished Rural Households', 90.0, 'Preventable starvation and malnutrition from hoarded grain reserves'),
        ],
        'rationale': 'Protects speculative warehouse prices and fiscal reserves while externalizing famine onto starving cultivators.'
    },
    'impose_grain_requisition': {
        'title': 'Requisition Peasant Grain for Metropolitan Stores',
        'category': 'coercion',
        'cost': 85.0,
        'breakdown': {'peasant_expropriation': 85.0},
        'victims': [
            DecisionVictimImpact('Peasant Cultivators', 85.0, 'Expropriation of household subsistence reserves and rural impoverishment'),
        ],
        'rationale': 'Secures urban grain supply by forcibly seizing peasant harvest stocks.'
    },
    'reduce_fellahin_tax': {
        'title': 'Reduce Fellahin Land Tax',
        'category': 'relief',
        'cost': 0.0,
        'breakdown': {},
        'victims': [
            DecisionVictimImpact('Beneficiaries: Rural Fellahin & Cultivators', 0.0, 'Restorative tax relief alleviating rural poverty and malnutrition'),
        ],
        'rationale': 'Socially restorative decision that reduces tax burden and restores peasant subsistence.'
    },
    'release_relief_grain': {
        'title': 'Distribute Public Relief Grain',
        'category': 'relief',
        'cost': 0.0,
        'breakdown': {},
        'victims': [
            DecisionVictimImpact('Beneficiaries: Starving Households', 0.0, 'Direct food relief preventing starvation deaths and restoring nutrition'),
        ],
        'rationale': 'Direct public welfare intervention preventing mortality from private grain hoarding.'
    },
}


class DecisionExternalitiesTracker:
    """Tracks player decisions, their externalized damage costs, and specific victim groups."""

    def __init__(self):
        self._entries: List[DecisionAuditEntry] = []

    def reset(self):
        self._entries.clear()

    def record_decision(self, action_id: str, title: Optional[str] = None, turn: int = 0,
                        category: Optional[str] = None, cost_override: Optional[float] = None,
                        victims_override: Optional[List[DecisionVictimImpact]] = None,
                        rationale_override: Optional[str] = None) -> DecisionAuditEntry:
        """Record a player sovereign or scenario decision."""
        catalog_info = DECISION_EXTERNALITY_CATALOG.get(action_id, {})

        final_title = title or catalog_info.get('title', action_id.replace('_', ' ').title())
        final_category = category or catalog_info.get('category', 'governance')
        final_cost = cost_override if cost_override is not None else catalog_info.get('cost', 25.0)
        final_breakdown = catalog_info.get('breakdown', {'governance_strain': final_cost})
        final_victims = victims_override or catalog_info.get('victims', [
            DecisionVictimImpact('General Public', final_cost, 'Public burden from policy enforcement')
        ])
        final_rationale = rationale_override or catalog_info.get('rationale', 'Policy decision externalizing administrative and social burdens.')

        entry = DecisionAuditEntry(
            turn=turn,
            action_id=action_id,
            title=final_title,
            category=final_category,
            externalized_cost=round(final_cost, 2),
            damage_breakdown=final_breakdown,
            victims=final_victims,
            rationale=final_rationale
        )
        self._entries.append(entry)
        return entry

    def get_all_entries(self) -> List[DecisionAuditEntry]:
        return list(self._entries)

    def get_all_entries_dict(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries]

    def get_total_externalized_cost(self) -> float:
        return sum(e.externalized_cost for e in self._entries)

    def get_victims_summary(self) -> Dict[str, Dict[str, Any]]:
        """Aggregate total externalized burden and details per victim group across all decisions."""
        summary: Dict[str, Dict[str, Any]] = {}
        for entry in self._entries:
            for vic in entry.victims:
                if vic.victim_group not in summary:
                    summary[vic.victim_group] = {
                        "total_cost": 0.0,
                        "decisions": [],
                        "descriptions": []
                    }
                summary[vic.victim_group]["total_cost"] += vic.burden_cost
                if entry.title not in summary[vic.victim_group]["decisions"]:
                    summary[vic.victim_group]["decisions"].append(entry.title)
                if vic.description not in summary[vic.victim_group]["descriptions"]:
                    summary[vic.victim_group]["descriptions"].append(vic.description)

        for k in summary:
            summary[k]["total_cost"] = round(summary[k]["total_cost"], 2)
        return summary


# Global singleton instance for decision tracking
_decision_tracker = DecisionExternalitiesTracker()


def get_decision_tracker() -> DecisionExternalitiesTracker:
    return _decision_tracker

