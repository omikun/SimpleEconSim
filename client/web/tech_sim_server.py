#!/usr/bin/env python3
"""
tech_sim_server.py — Standalone Web & REST Server for the Emergent Tech Tree & Leapfrog Simulator.

Provides both:
  1. An interactive browser/mobile UI on port 8082 (default) for testing multi-avenue discovery,
     factor-price emergence, operation and funded engineering, +1 tier espionage ceilings
     with local refinement, and incumbent guild legislative blockades.
  2. Live synchronization with `macro/innovation.py` (`TECH_CATALOG`) plus REST API endpoints:
       • GET  /api/health   — Server status and catalog sync metadata
       • GET  /api/catalog  — Full multi-avenue specs + live `macro/innovation.py` TECH_CATALOG
       • POST /api/simulate — Headless Python turn-by-turn simulation runner for CLI/remote APIs
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import sitecustomize  # noqa: F401 — ensures domain folders (macro/, core/, etc.) are on sys.path

from macro.innovation import TECH_CATALOG, TechDomain

SERVER_START_TIME = time.time()

# ---------------------------------------------------------------------------
# Multi-Avenue & Refinement Spec Definitions (Synced with macro/innovation.py)
# ---------------------------------------------------------------------------

COMPLEXITY_DEFAULTS = {
    1: {"class_name": "Class I: Low Complexity", "max_steal_tier": 3, "max_steal_xp": 85, "gap_label": "Steal up to Tier 3 (85 XP) — Source - 0.5 Tier"},
    2: {"class_name": "Class II: Medium Complexity", "max_steal_tier": 3, "max_steal_xp": 65, "gap_label": "Steal up to Tier 3 (65 XP) — Source - 1 Tier"},
    3: {"class_name": "Class III: High Complexity", "max_steal_tier": 2, "max_steal_xp": 50, "gap_label": "Steal up to Tier 2 (50 XP) — Source - 1.5 Tiers"},
    4: {"class_name": "Class IV: Extreme Complexity", "max_steal_tier": 2, "max_steal_xp": 30, "gap_label": "Steal up to Tier 2 (30 XP) — Source - 2 Full Tiers"},
}

FLAGSHIP_TECH_SPECS = {
    "gunpowder_blasting": {
        "tech_id": "gunpowder_blasting",
        "name": "Gunpowder & Energetic Chemistry",
        "era": 1,
        "complexity_class": 1,
        "max_steal_tier": 3,
        "max_steal_xp": 85,
        "steal_gap_text": "Class I (Era I): Max Steal = Tier 3 (85 XP) — Low Tacit Friction",
        "prereq_name": "Bloomery Iron & High-Temp Kilns (Tier 1)",
        "incumbent_guild": "Feudal Knight & Crossbow Guilds",
        "law_name": "Chivalric Arms Monopoly Edict",
        "law_desc": "Aristocratic cavalry and bowyer guilds ban gunpowder workshops from urban arsenals, throttling Refinement XP to 25%.",
        "avenues": [
            {"id": "alchemy", "name": "Daoist Elixir & Kiln Alchemy (Song Path)", "crisis": "Court Longevity & Mineral Calcination Patronage", "prototype": "Fire-Lance & Alchemical Bomb"},
            {"id": "siege", "name": "Frontier Siege Warfare (European/Ottoman Path)", "crisis": "Stone Castle Fortification Stalemate", "prototype": "Crude Cast-Bronze Mortar"},
            {"id": "mining", "name": "Hard-Rock Mining & Canal Blasting (Alpine Path)", "crisis": "Granite Mountain Pass & Silver Vein Bottleneck", "prototype": "Black-Powder Blasting Charge"},
        ],
        "downstream": [
            {"name": "Siege Bombards & Blasting Charges", "reqTier": 1, "reqXP": 1, "desc": "Stationary siege/mining charges; tolerates impure powder."},
            {"name": "Corned Powder & Alpine Mountain Pass Roads", "reqTier": 2, "reqXP": 25, "desc": "Wet-graining refinement for predictable chamber & blasting pressure."},
            {"name": "Standardized Field Artillery & Star Forts", "reqTier": 3, "reqXP": 60, "desc": "Requires precision bronze/iron casting & moisture-resistant corning."},
            {"name": "Nitroglycerin & High-Velocity Ballistics", "reqTier": 4, "reqXP": 90, "desc": "High-energy chemical synthesis for modern tunnels & rifled ordnance."},
        ],
    },
    "steam_engines": {
        "tech_id": "steam_engines",
        "name": "The Steam Engine (Watt & High-Pressure)",
        "era": 3,
        "complexity_class": 2,
        "max_steal_tier": 3,
        "max_steal_xp": 65,
        "steal_gap_text": "Class II (Era II–III): Max Steal = Tier 3 (65 XP) — Source Minus 1 Tier",
        "prereq_name": "Coal Coking & Precision Cylinder Boring (Tier 2)",
        "incumbent_guild": "Waterwheel Millers & Hand-Loom Guilds",
        "law_name": "Guild Charter Urban Steam Ban",
        "law_desc": "Traditional craft guilds ban coal-burning engines inside incorporated guild towns, throttling Refinement XP to 25%.",
        "avenues": [
            {"id": "pit", "name": "Deep Pit Mine Drainage (British Newcomen Path)", "crisis": "Flooded Deep Coal/Iron Mine Shafts", "prototype": "Atmospheric Pithead Pump"},
            {"id": "bellows", "name": "Blast Furnace Bellows (Song/Ironworks Path)", "crisis": "Frozen / Low-Flow Rivers Halt Iron Smelting", "prototype": "Steam-Blast Furnace Pump"},
            {"id": "polder", "name": "Civic Polder & Drydock Pumping (Dutch/Venetian Path)", "crisis": "Coastal Flooding & Naval Drydock Sluicing", "prototype": "Hydraulic Sluice Station"},
            {"id": "brine", "name": "Brine & Sugar Pressure Boilers (Sichuan/Caribbean Path)", "crisis": "Evaporation Fuel Crisis in Salt/Sugar Vats", "prototype": "Closed-Coil Pressure Boiler"},
            {"id": "river", "name": "Upstream River Barge Hauling (Mississippi/Yangzi Path)", "crisis": "Strong Downstream Current Blocks Heavy Freight", "prototype": "Shore-Winch & Paddle Tug"},
        ],
        "downstream": [
            {"name": "Pithead Mine Pump & Blast Bellows", "reqTier": 1, "reqXP": 1, "desc": "1% thermal efficiency; only viable sitting directly on cheap fuel."},
            {"name": "Rotary Steam Textile Mills & River Steamboats", "reqTier": 2, "reqXP": 25, "desc": "Separate condenser (12% eff.); river buoyancy floats heavy boiler."},
            {"name": "Railroads & High-Pressure Locomotives", "reqTier": 3, "reqXP": 60, "desc": "High-pressure compact boiler (25% eff.) + Bessemer Steel Rails."},
            {"name": "Compound Steam Turbines & Dreadnoughts", "reqTier": 4, "reqXP": 90, "desc": "Continuous rotary turbine (40%+ eff.) for ocean fleets & power grids."},
        ],
    },
    "petroleum_refining": {
        "tech_id": "petroleum_refining",
        "name": "Internal Combustion & Petrochemicals",
        "era": 4,
        "complexity_class": 3,
        "max_steal_tier": 2,
        "max_steal_xp": 50,
        "steal_gap_text": "Class III (Era III–IV): Max Steal = Tier 2 (50 XP) — Source Minus 1.5 Tiers",
        "prereq_name": "Bessemer Structural Steel & High-Grade Alloys (Tier 2)",
        "incumbent_guild": "Coal-Steam Railway & Turnpike Barons",
        "law_name": "The Locomotive 'Red Flag' Act of 1865",
        "law_desc": "Entrenched Steam Rail & Horse-Coach barons mandate a 4 mph speed limit behind a red flag bearer, crippling urban auto testing!",
        "avenues": [
            {"id": "kerosene", "name": "Kerosene Lighting Byproduct (Pennsylvania/Baku Path)", "crisis": "Whale-Oil Scarcity & Volatile Gasoline Surplus", "prototype": "Stationary Petrol/Gas Engine"},
            {"id": "tractor", "name": "Continental Steppe Farm Mechanization", "crisis": "Heavy Steam Tractors Sink in Soft Farmland Mud", "prototype": "Lightweight Farm Tractor"},
            {"id": "towngas", "name": "Municipal Town-Gas Workshop Engine (Otto/Diesel Path)", "crisis": "Small Workshops Cannot Afford Steam Boilermen", "prototype": "Four-Stroke Town-Gas Engine"},
        ],
        "downstream": [
            {"name": "Stationary Workshop Pump & Generator", "reqTier": 1, "reqXP": 1, "desc": "Heavy single-cylinder engine tethered to fuel depot."},
            {"name": "Motor Cars, Freight Trucks & Early Tanks", "reqTier": 2, "reqXP": 25, "desc": "Carburetor & high-RPM power-to-weight for road chassis."},
            {"name": "Long-Range Aviation & Diesel Submarines", "reqTier": 3, "reqXP": 60, "desc": "Requires lightweight alloys & high-compression fuel injection."},
            {"name": "Haber-Bosch Feedstocks & Combined-Cycle Turbines", "reqTier": 4, "reqXP": 90, "desc": "Petrochemical synthesis & supersonic propulsion."},
        ],
    },
    "microelectronics": {
        "tech_id": "microelectronics",
        "name": "Semiconductors & Microchips",
        "era": 4,
        "complexity_class": 4,
        "max_steal_tier": 2,
        "max_steal_xp": 30,
        "steal_gap_text": "Class IV (Era IV): Max Steal = Tier 2 (30 XP) — Source Minus 2 Full Tiers",
        "prereq_name": "Dynamo Electrification & EUV Precision Optics (Tier 3)",
        "incumbent_guild": "Vacuum-Tube & Electromechanical Telecom Cartel",
        "law_name": "Telecom Monopoly Procurement Mandate",
        "law_desc": "Legacy vacuum-tube defense contractors and state telecom monopolies lock R&D grants into legacy analog relays.",
        "avenues": [
            {"id": "aerospace", "name": "Aerospace & Missile Guidance Miniaturization", "crisis": "Vacuum Tubes Too Heavy for Rocket Nosecones", "prototype": "Planar Silicon Transistor Lab"},
            {"id": "consumer", "name": "Precision Optics & Consumer Export Hub (East Asia)", "crisis": "Resource-Poor State Needs High-Margin Exports", "prototype": "Solid-State Radio & Memory Fab"},
            {"id": "robotics", "name": "Demographic Aging & Factory Robotics", "crisis": "Shrinking Workforce & Sky-High Factory Wages", "prototype": "Numerical Control (NC) Logic Fab"},
        ],
        "downstream": [
            {"name": "Solid-State Radios & Discrete Transistors", "reqTier": 1, "reqXP": 1, "desc": "10-micron discrete logic; low wafer yield."},
            {"name": "Personal Computers & Legacy Auto Chips", "reqTier": 2, "reqXP": 25, "desc": "90nm–28nm CMOS lithography; highest tier reachable by espionage alone."},
            {"name": "Smartphones, Cloud Mainframes & Guided Avionics", "reqTier": 3, "reqXP": 60, "desc": "7nm FinFET; CANNOT be stolen—must be refined domestically after Tier 2."},
            {"name": "Sub-3nm AI Accelerators & Zero-Drag Markets", "reqTier": 4, "reqXP": 90, "desc": "Cutting-edge EUV megafab mastery."},
        ],
    },
}


def build_dynamic_catalog() -> dict:
    """
    Build the complete simulator catalog by combining the 4 flagship deep-dive specs
    with every technology registered in `macro/innovation.py` (`TECH_CATALOG`).
    Any new technology added to `macro/innovation.py` automatically appears here.
    """
    catalog = dict(FLAGSHIP_TECH_SPECS)

    for tech_id, tech in TECH_CATALOG.items():
        if tech_id in catalog:
            # Enrich flagship entry with live TECH_CATALOG fields
            catalog[tech_id]["live_base_xp_required"] = tech.base_xp_required
            catalog[tech_id]["live_domain"] = tech.domain.value
            catalog[tech_id]["live_required_resources"] = [r.value for r in tech.required_resources]
            catalog[tech_id]["live_required_techs"] = list(tech.required_techs)
            catalog[tech_id]["live_unlocked_buildings"] = list(tech.unlocked_buildings)
            continue

        era = getattr(tech, "era", 1)
        c_class = int(getattr(tech, "complexity_class", era))
        comp = COMPLEXITY_DEFAULTS.get(c_class, COMPLEXITY_DEFAULTS[2])
        req_res = [r.value for r in tech.required_resources]
        req_techs = list(tech.required_techs)
        prereq_str = ", ".join(req_techs) if req_techs else f"Domain Practice ({tech.domain.value})"
        res_str = ", ".join(req_res) if req_res else "General Civic Inputs"
        inc_guild = getattr(tech, "incumbent_guild", "") or f"Legacy {tech.domain.value.replace('_', ' ').title()} Guilds"
        prot_law = getattr(tech, "protectionist_law", "") or f"Incumbent {tech.domain.value.replace('_', ' ').title()} Charter Restriction"
        live_avenues = getattr(tech, "discovery_avenues", [])
        if live_avenues:
            avenues_payload = [
                {
                    "id": av.avenue_id,
                    "name": av.name,
                    "crisis": av.crisis_label,
                    "prototype": av.prototype_building,
                }
                for av in live_avenues
            ]
        else:
            avenues_payload = [
                {
                    "id": f"{tech_id}_primary",
                    "name": f"Local {res_str} Hub (Primary Path)",
                    "crisis": f"Acute {tech.domain.value.replace('_', ' ').title()} Scarcity Bottleneck",
                    "prototype": (tech.unlocked_buildings[0] if tech.unlocked_buildings else f"{tech.name} Prototype"),
                }
            ]

        catalog[tech_id] = {
            "tech_id": tech_id,
            "name": tech.name,
            "era": era,
            "complexity_class": c_class,
            "max_steal_tier": comp["max_steal_tier"],
            "max_steal_xp": comp["max_steal_xp"],
            "steal_gap_text": f"{comp['class_name']} (Era {era}): {comp['gap_label']}",
            "prereq_name": f"Prerequisite: {prereq_str}",
            "incumbent_guild": inc_guild,
            "law_name": prot_law,
            "law_desc": f"{inc_guild} enforce '{prot_law}' to restrict {tech.name} deployment (0.25x XP).",
            "live_base_xp_required": tech.base_xp_required,
            "live_domain": tech.domain.value,
            "live_required_resources": req_res,
            "live_required_techs": req_techs,
            "live_unlocked_buildings": list(tech.unlocked_buildings),
            "avenues": avenues_payload,
            "downstream": [
                {"name": f"Tier 1: Crude {tech.name} Prototype", "reqTier": 1, "reqXP": 1, "desc": f"Initial deployment unlocked at {res_str} sites."},
                {"name": f"Tier 2: Standardized {tech.name}", "reqTier": 2, "reqXP": 25, "desc": tech.description},
                {"name": f"Tier 3: High-Efficiency {tech.name} Network", "reqTier": 3, "reqXP": 60, "desc": "Empire-wide scaling with reduced input friction."},
                {"name": f"Tier 4: Mastered {tech.name} Ecosystem", "reqTier": 4, "reqXP": 90, "desc": "Maximum yield and downstream synergy unlocked."},
            ],
        }

    from goods import Goods
    for tech_id, tech in TECH_CATALOG.items():
        catalog[tech_id]['productivity_effects'] = [
            {'good': Goods(good).name, 'frontier_multiplier': value}
            for good, value in tech.production_modifiers.items()]
        catalog[tech_id]['source_urls'] = list(getattr(tech, 'source_urls', ()))
    return catalog


def simulate_trajectory(params: dict) -> dict:
    """
    Headless Python simulation of the Emergent Tech Tree & Leapfrog model.
    Callable via `POST /api/simulate` or directly from Python scripts/tests.
    """
    catalog = build_dynamic_catalog()
    tech_key = params.get("tech_id", "steam_engines")
    if tech_key not in catalog:
        tech_key = "steam_engines"
    tech = catalog[tech_key]

    from engineering import refinement_rates, tier_for_xp, build_cost_factor
    turns = max(1, min(200, int(params.get("turns", 20))))
    mode = str(params.get("subsidy_mode", "commercial"))
    budget = max(0.0, float(params.get("engineering_budget", {"commercial": 0, "standard": 25, "crash": 100}.get(mode, 0))))
    objective = str(params.get("engineering_objective", "performance" if mode == "crash" else "balanced"))
    if objective not in ("performance", "economy", "balanced"):
        raise ValueError("Invalid engineering objective")
    xp = max(0.0, min(100.0, float(params.get("refinement_xp", 0))))
    discovery = max(0.0, min(100.0, float(params.get("discovery_progress", 0))))
    if discovery >= 100:
        xp = max(1.0, xp)
    maturity = {int(g): max(0.0, min(100.0, float(v)))
                for g, v in params.get("maturity_by_generation", {}).items()}
    generation = max(1, tier_for_xp(xp))
    previous = max((g for g in maturity if g < generation), default=None)
    maturity.setdefault(generation, maturity[previous] * 0.35 ** (generation - previous)
                         if previous else float(params.get("commercial_maturity", 0)))
    installed_generation = max(1, int(params.get("installed_generation", generation)))
    treasury = max(0.0, float(params.get("treasury", 5000)))
    private_cash = max(0.0, float(params.get("private_cash", 500)))
    stock = max(0, int(params.get("experiment_stock", 1000)))
    capacity = max(0, min(100, int(params.get("workshop_capacity", 3))))
    workers = max(0, min(100, int(params.get("engineering_workers", 3))))
    unit_cost = max(0.01, float(params.get("experiment_unit_cost", 5)))
    installed = max(0.0, float(params.get("operating_installations", 0)))
    utilization = min(1.5, max(0.0, float(params.get("utilization", 1))))
    has_input = bool(params.get("has_input", True))
    has_prereq = bool(params.get("has_prereq", True))
    blocked = bool(params.get("guild_law_active", False))
    target = float(params.get("program_capability_target", next((v for v in (1, 25, 60, 90, 100) if xp < v), 100)))
    cost_target = float(params.get("program_maturity_target", min(100, maturity[generation] + 20)))
    funded_generation = int(params.get("program_generation", generation))
    active = bool(params.get("program_active", True)) and budget > 0
    repeat = bool(params.get("repeat_program", False))
    crisis_mult = 2.5 if params.get("crisis_active", True) else 0.6
    prox = float(params.get("prox_mult", 4))
    wages = float(params.get("wage_ratio", 3))
    net = float(params.get("net_mult", 1.8))
    organic = max(0.5, net + prox * crisis_mult * (wages * prox / 4) * float(params.get("supply_mult", 2)) * net * float(params.get("inst_mult", 1.5)) * 0.45)
    if not has_input:
        organic = 0.0
    if blocked:
        organic *= 0.45
    history, first_rates = [], None
    last_spend = 0.0
    for step_index in range(1, turns + 1):
        cap_done = xp >= target
        cost_done = maturity.get(funded_generation, 0) >= cost_target
        already_done = cap_done if objective == 'performance' else cost_done if objective == 'economy' else cap_done and cost_done
        if already_done and not repeat:
            active = False
        slots = min(capacity, workers, stock) if has_input else 0
        effort = min(slots, int(min(budget, treasury) // unit_cost)) if active else 0
        private_budget = max(0.0, float(params.get("private_budget", 0))) if installed * utilization else 0
        private_effort = min(slots - effort, int(min(private_budget, private_cash) // unit_cost))
        last_spend = round(effort * unit_cost, 2)
        treasury -= last_spend
        private_cash -= private_effort * unit_cost
        stock -= effort + private_effort
        rates = refinement_rates(installations=installed if has_input else 0,
            utilization=utilization, readiness=1 if has_input else 0,
            capability=xp, public_effort=effort, private_effort=private_effort,
            objective=objective, blockaded=blocked)
        if first_rates is None:
            first_rates = dict(rates)
        if xp <= 0 and discovery < 100:
            discovery = min(100, discovery + organic + 3 * effort * (0.25 if blocked else 1))
            if discovery >= 100:
                xp = 1.0
        else:
            cap = 100 if has_prereq else max(xp, 59)
            xp = max(xp, min(cap, xp + rates["capability"]))
            operating = refinement_rates(installations=installed if has_input else 0,
                utilization=utilization, capability=xp, blockaded=blocked)["maturity"]
            public_maturity = refinement_rates(public_effort=effort, objective=objective,
                capability=xp, blockaded=blocked)["maturity"]
            private_maturity = refinement_rates(private_effort=private_effort,
                capability=xp, blockaded=blocked)["maturity"]
            for design, amount in ((installed_generation, operating),
                                   (funded_generation, public_maturity), (generation, private_maturity)):
                maturity[design] = min(100, maturity.get(design, 0) + amount)
        next_generation = max(1, tier_for_xp(xp))
        if next_generation != generation:
            maturity.setdefault(next_generation, maturity.get(generation, 0) * 0.35 ** (next_generation - generation))
            generation = next_generation
        reached_cap = xp >= target
        reached_cost = maturity.get(funded_generation, 0) >= cost_target
        reached = reached_cap if objective == "performance" else reached_cost if objective == "economy" else reached_cap and reached_cost
        if active and reached and not repeat:
            active = False
        history.append({"step": step_index, "tier": tier_for_xp(xp),
            "discovery_progress": round(discovery, 4), "refinement_xp": round(xp, 4),
            "commercial_maturity": round(maturity.get(generation, 0), 4),
            "treasury": round(treasury, 2), "public_spent": last_spend,
            "private_spent": private_effort * unit_cost, "delivered_effort": effort,
            "experiment_stock": stock, "program_active": active})
    return {"status": "ok", "tech_id": tech_key, "tech_name": tech["name"],
        "emergence_rate_per_turn": round(organic, 4),
        "refinement_rate_per_turn": first_rates["capability"],
        "maturity_rate_per_turn": first_rates["maturity"],
        "final_tier": tier_for_xp(xp), "final_discovery_progress": discovery,
        "final_refinement_xp": xp, "final_commercial_maturity": maturity.get(generation, 0),
        "build_cost_factor": build_cost_factor(maturity.get(generation, 0)),
        "maturity_by_generation": maturity, "treasury": round(treasury, 2),
        "private_cash": private_cash, "experiment_stock": stock, "program_active": active,
        "program_capability_target": target, "program_maturity_target": cost_target,
        "program_generation": funded_generation, "installed_generation": installed_generation, "expected_spend": history[0]["public_spent"],
        "history": history}


# ---------------------------------------------------------------------------
# Self-Contained Responsive HTML/CSS/JS Frontend (Zero External CDN Required)
# ---------------------------------------------------------------------------

SIMULATOR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Call of Capital — Tech Tree & Leapfrog Simulator</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card: #131c2e;
      --content: #0f1624;
      --border: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #ef4444;
      --indigo: #6366f1;
      --sky: #0ea5e9;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      padding: 20px 16px;
      line-height: 1.45;
    }
    .container { max-width: 1360px; margin: 0 auto; display: flex; flex-direction: column; gap: 18px; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      box-shadow: 0 8px 20px rgba(0,0,0,0.25);
    }
    .subcard {
      background: var(--content);
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 12px;
    }
    .header-bar {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }
    .badge {
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }
    .badge-primary { background: var(--primary); color: #fff; }
    .badge-emerald { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(16,185,129,0.35); }
    .badge-rose { background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.35); }
    .badge-amber { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.35); }
    .stats-row { display: flex; flex-wrap: wrap; gap: 10px; }
    .stat-pill {
      background: var(--content);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 14px;
      text-align: center;
      min-width: 90px;
    }
    .stat-pill .label { font-size: 12px; color: var(--muted); }
    .stat-pill .val { font-size: 16px; font-weight: 800; margin-top: 2px; }
    .grid-2 { display: grid; grid-template-columns: 1fr; gap: 18px; }
    .grid-3 { display: grid; grid-template-columns: 1fr; gap: 18px; }
    .grid-4 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
    @media (min-width: 980px) {
      .grid-2 { grid-template-columns: 1fr 1fr; }
      .grid-3 { grid-template-columns: 1fr 1fr 1fr; }
      .grid-4 { grid-template-columns: repeat(4, 1fr); }
    }
    h1 { font-size: 21px; font-weight: 800; margin-top: 4px; }
    h2 { font-size: 16px; font-weight: 700; }
    h3 { font-size: 15px; font-weight: 700; }
    .muted { color: var(--muted); font-size: 12px; }
    button, select {
      font-family: inherit;
      font-size: 12px;
      color: var(--text);
      background: var(--content);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 9px 12px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    button:hover { border-color: var(--primary); }
    button.active-choice {
      border-color: var(--primary);
      background: rgba(59, 130, 246, 0.16);
      box-shadow: inset 0 0 0 1px var(--primary);
    }
    .btn-action {
      background: var(--primary);
      border-color: var(--primary);
      color: #fff;
      font-weight: 700;
      text-align: center;
      justify-content: center;
    }
    .btn-action:hover { background: var(--primary-hover); }
    .btn-indigo {
      background: var(--indigo);
      border-color: var(--indigo);
      color: #fff;
      font-weight: 700;
      width: 100%;
    }
    .progress-track {
      position: relative;
      width: 100%;
      height: 14px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 999px;
      overflow: hidden;
      margin: 6px 0;
    }
    .progress-fill-sky { height: 100%; background: var(--sky); transition: width 0.25s ease; }
    .progress-fill-emerald { height: 100%; background: var(--emerald); transition: width 0.25s ease; }
    .tick {
      position: absolute;
      top: 0;
      bottom: 0;
      width: 2px;
      background: rgba(255,255,255,0.45);
    }
    input[type="range"] { width: 100%; accent-color: var(--primary); margin: 4px 0; }
    .flex-between { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .space-y > * + * { margin-top: 10px; }
    .log-box {
      max-height: 175px;
      overflow-y: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }
    .unlocked-item {
      border-color: rgba(16, 185, 129, 0.55);
      background: rgba(16, 185, 129, 0.1);
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Top Header -->
    <div class="card header-bar">
      <div>
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
          <span class="badge badge-primary">STANDALONE TECH SIMULATOR</span>
          <span class="badge badge-emerald" id="sync-badge">Synced with macro/innovation.py</span>
          <a href="http://localhost:8000" id="manager-link" style="color:var(--sky); font-size:12px; text-decoration:none; font-weight:600;">⚙️ Open Server Control Center (:8000)</a>
        </div>
        <h1>Emergent Multi-Avenue Discovery, Refinement &amp; Guild Leapfrog Simulator</h1>
        <p class="muted">Test multi-avenue catalysts, operation, technical capability and commercial maturity, +1 tier espionage ceilings with local refinement, and incumbent guild legislation.</p>
      </div>

      <div class="stats-row">
        <div class="stat-pill">
          <div class="label">Turn</div>
          <div class="val" id="stat-turn">1</div>
        </div>
        <div class="stat-pill">
          <div class="label">Treasury</div>
          <div class="val" id="stat-gold" style="color:var(--amber);">1,200g</div>
        </div>
        <div class="stat-pill">
          <div class="label">Pol. Capital</div>
          <div class="val" id="stat-pol" style="color:var(--sky);">100</div>
        </div>
        <div class="stat-pill">
          <div class="label">Stability</div>
          <div class="val" id="stat-stab" style="color:var(--emerald);">85%</div>
        </div>
      </div>
    </div>

    <!-- Row 1: Empire Archetype & Target Technology -->
    <div class="grid-2">
      <div class="card space-y">
        <div class="flex-between">
          <h2>1. Empire Archetype Preset</h2>
          <span class="muted">Sets factor prices, treasury &amp; guild clout</span>
        </div>
        <div class="grid-3">
          <button onclick="applyEmpirePreset('britain')" id="btn-preset-britain" style="text-align:left;">
            <div style="font-weight:700;">Maritime Pioneer</div>
            <div class="muted" style="margin-top:3px;">High wages, cheap fuel, ghost acres. High incumbent guilds in later eras.</div>
          </button>
          <button onclick="applyEmpirePreset('china')" id="btn-preset-china" style="text-align:left;">
            <div style="font-weight:700;">Agrarian Hegemon</div>
            <div class="muted" style="margin-top:3px;">Cheap labor, rich treasury, civil exams. Needs State Subsidies or Canals.</div>
          </button>
          <button onclick="applyEmpirePreset('challenger')" id="btn-preset-challenger" style="text-align:left;">
            <div style="font-weight:700;">Latecomer Challenger</div>
            <div class="muted" style="margin-top:3px;">Zero old guild blockades! Ideal for stealing Tier 1–2 &amp; leapfrogging.</div>
          </button>
        </div>
      </div>

      <div class="card space-y">
        <div class="flex-between">
          <h2>2. Target Technology (Flagship &amp; Live Game Catalog)</h2>
          <span class="badge badge-amber" id="complexity-badge">Class II</span>
        </div>
        <div class="grid-4">
          <button onclick="selectTech('gunpowder_blasting')" id="btn-tech-gunpowder_blasting" style="text-align:left;">
            <div class="muted">Era I (Class I)</div>
            <div style="font-weight:700;">Gunpowder</div>
            <div style="font-size:12px; color:var(--emerald);">Steal Cap: 85%</div>
          </button>
          <button onclick="selectTech('steam_engines')" id="btn-tech-steam_engines" style="text-align:left;">
            <div class="muted">Era II–III (Class II)</div>
            <div style="font-weight:700;">Steam Power</div>
            <div style="font-size:12px; color:var(--amber);">Steal Cap: 65%</div>
          </button>
          <button onclick="selectTech('petroleum_refining')" id="btn-tech-petroleum_refining" style="text-align:left;">
            <div class="muted">Era III–IV (Class III)</div>
            <div style="font-weight:700;">Combustion</div>
            <div style="font-size:12px; color:#fb923c;">Steal Cap: 50%</div>
          </button>
          <button onclick="selectTech('microelectronics')" id="btn-tech-microelectronics" style="text-align:left;">
            <div class="muted">Era IV (Class IV)</div>
            <div style="font-weight:700;">Microchips</div>
            <div style="font-size:12px; color:var(--rose);">Steal Cap: 30%</div>
          </button>
        </div>
        <div class="flex-between" style="padding-top:4px;">
          <span class="muted">Or inspect any tech from <code>macro/innovation.py</code> (<code>TECH_CATALOG</code>):</span>
          <select id="catalog-dropdown" onchange="selectTech(this.value)" style="min-width:240px;"></select>
        </div>
      </div>
    </div>

    <!-- Main 3-Column Dashboard -->
    <div class="grid-3">
      <!-- Column 1: Multi-Avenue Catalysts & Factor Sliders -->
      <div class="space-y">
        <div class="card space-y">
          <div class="flex-between">
            <h3>3. Discovery Avenue (Local Catalyst)</h3>
            <span class="muted">Multi-pathway emergence</span>
          </div>
          <p class="muted">Select which local physical bottleneck &amp; resource adjacency drives your prototype:</p>
          <div id="avenue-list" class="space-y"></div>

          <div style="border-top:1px solid var(--border); padding-top:10px;" class="space-y">
            <div>
              <div class="flex-between" style="font-size:12px;">
                <span>Resource Proximity (G_prox)</span>
                <strong id="label-prox">Same Hub / Waterway (4.0x)</strong>
              </div>
              <input id="slider-prox" type="range" min="1" max="3" step="1" value="3" oninput="updateUI()" />
              <div class="flex-between muted">
                <span>Landlocked (0.2x)</span>
                <span>Road (1.0x)</span>
                <span>Water/Hub (4.0x)</span>
              </div>
            </div>

            <label class="subcard flex-between" style="cursor:pointer;">
              <div>
                <div style="font-size:12px; font-weight:700;" id="crisis-title">Active Local Crisis</div>
                <div class="muted" id="crisis-desc">+2.5x Catalyst Surge</div>
              </div>
              <input id="toggle-crisis" type="checkbox" checked onchange="updateUI()" style="width:16px; height:16px;" />
            </label>
          </div>
        </div>

        <div class="card space-y">
          <h3>4. Factor Prices &amp; Institutions</h3>
          <div>
            <div class="flex-between" style="font-size:12px;">
              <span>Wage-to-Fuel Ratio (E_ratio — 30% wt)</span>
              <strong id="label-wage">3.0x</strong>
            </div>
            <input id="slider-wage" type="range" min="0.2" max="4.0" step="0.2" value="3.0" oninput="updateUI()" />
          </div>
          <div>
            <div class="flex-between" style="font-size:12px;">
              <span>"Ghost Acres" / Input Throughput (S_supply)</span>
              <strong id="label-supply">2.0x</strong>
            </div>
            <input id="slider-supply" type="range" min="0.5" max="3.0" step="0.25" value="2.0" oninput="updateUI()" />
          </div>
          <div>
            <div class="flex-between" style="font-size:12px;">
              <span>Scholar-Artisan Network (M_net)</span>
              <strong id="label-net">1.8x</strong>
            </div>
            <input id="slider-net" type="range" min="0.5" max="2.5" step="0.25" value="1.8" oninput="updateUI()" />
          </div>
          <div>
            <div class="flex-between" style="font-size:12px;">
              <span>Patents &amp; Geopolitical Rivalry (M_inst × M_geo)</span>
              <strong id="label-inst">1.5x</strong>
            </div>
            <input id="slider-inst" type="range" min="0.4" max="2.0" step="0.2" value="1.5" oninput="updateUI()" />
          </div>
        </div>
      </div>

      <!-- Column 2: Emergence, Refinement Tiers & Subsidies -->
      <div class="space-y">
        <div class="card space-y">
          <div class="flex-between">
            <div>
              <div class="muted">Current Technology Status</div>
              <h3 id="current-tier-title">Tier 0: Theoretical Concept</h3>
            </div>
            <span class="badge badge-primary" id="current-tier-badge">TIER 0 / 4</span>
          </div>

          <!-- Discovery Progress -->
          <div class="subcard space-y">
            <div class="flex-between" style="font-size:12px;">
              <strong>Phase 1: Prototype Discovery</strong>
              <strong id="discovery-pct">0 / 100</strong>
            </div>
            <div class="progress-track">
              <div id="discovery-bar" class="progress-fill-sky" style="width:0%"></div>
            </div>
            <div class="flex-between muted">
              <span>Background Scholarly Drift</span>
              <strong id="discovery-rate-label" style="color:var(--sky);">+12.0 / turn</strong>
            </div>
          </div>

          <!-- Refinement XP Bar -->
          <div class="subcard space-y">
            <div class="flex-between" style="font-size:12px;">
              <strong>Phase 2: Domestic Refinement XP</strong>
              <strong id="refinement-xp-label">0 / 100 XP</strong>
            </div>
            <div class="progress-track" style="height:16px;">
              <div id="refinement-bar" class="progress-fill-emerald" style="width:0%"></div>
              <div class="tick" style="left:25%;" title="Tier 2 (25 XP)"></div>
              <div class="tick" style="left:60%;" title="Tier 3 (60 XP)"></div>
              <div class="tick" style="left:90%;" title="Tier 4 (90 XP)"></div>
            </div>
            <div class="flex-between muted">
              <span>T1 (1)</span>
              <span>T2 (25)</span>
              <span>T3 (60)</span>
              <span>T4 (90)</span>
            </div>
            <div id="refinement-rate-note" style="font-size:12px; color:var(--emerald); font-weight:600;"></div>
          </div>

          <!-- State Subsidy vs Commercial Mode -->
          <div class="space-y" style="border-top:1px solid var(--border); padding-top:10px;">
            <div class="flex-between" style="font-size:12px;">
              <strong>Engineering program</strong>
              <span class="muted" id="subsidy-cost-badge">+15g Tax/t</span>
            </div>
            <button onclick="setSubsidyMode('commercial')" id="btn-sub-commercial" style="width:100%; text-align:left;" class="flex-between">
              <div>
                <div style="font-weight:700;">No public program</div>
                <div class="muted">Operation generates learning; idle equipment generates none.</div>
              </div>
              <strong style="color:var(--emerald);">0g</strong>
            </button>
            <button onclick="setSubsidyMode('standard')" id="btn-sub-standard" style="width:100%; text-align:left;" class="flex-between">
              <div>
                <div style="font-weight:700;">Workshop program · budget ceiling 25g/turn</div>
                <div class="muted">Pays for delivered workshop labor and experiment supplies.</div>
              </div>
              <strong style="color:var(--amber);">-25g/t</strong>
            </button>
            <button onclick="setSubsidyMode('crash')" id="btn-sub-crash" style="width:100%; text-align:left;" class="flex-between">
              <div>
                <div style="font-weight:700;">National program · budget ceiling 100g/turn</div>
                <div class="muted">Staffing and supplies constrain how much can actually be spent.</div>
              </div>
              <strong style="color:var(--rose);">-100g/t</strong>
            </button>
          </div>

          <div class="subcard space-y">
            <label>Engineering objective<select id="eng-objective" onchange="setSubsidyMode(state.subsidyMode)"><option value="performance">Develop capability</option><option value="economy">Make designs economical</option><option value="balanced">Improve both</option></select></label>
            <label>Operating installations<input id="eng-installations" type="number" min="0" max="1000" value="0" onchange="updateUI()"></label>
            <label>Utilization (%)<input id="eng-utilization" type="number" min="0" max="150" value="100" onchange="updateUI()"></label>
            <label>Available skilled engineers<input id="eng-workers" type="number" min="0" max="100" value="3" onchange="updateUI()"></label>
            <div id="eng-maturity" class="muted"></div>
            <div class="muted">Three workshop shifts maximum per turn. Each shift consumes one experiment bundle and costs 5g in this controlled scenario. Turn advancement uses the live Python engineering rules.</div>
          </div>

          <!-- Step Turn Controls -->
          <div class="grid-3" style="padding-top:4px;">
            <button class="btn-action" onclick="stepTurns(1)">+1 Turn</button>
            <button class="btn-action" style="background:var(--indigo); border-color:var(--indigo);" onclick="stepTurns(5)">+5 Turns</button>
            <button onclick="resetTechProgress()">Reset Tech</button>
          </div>
        </div>

        <!-- Downstream Applications -->
        <div class="card space-y">
          <h3>Downstream Applications (Efficiency Gated)</h3>
          <p class="muted">Unlocks require crossing Refinement XP thresholds &amp; sibling dependencies:</p>
          <div id="downstream-list" class="space-y"></div>
        </div>
      </div>

      <!-- Column 3: Espionage Ceiling & Incumbent Guild Legislation -->
      <div class="space-y">
        <div class="card space-y">
          <div class="flex-between">
            <h3>5. Tech Espionage (+1 Tier Steal)</h3>
            <span class="badge badge-primary">Leader: Tier 4 (100 XP)</span>
          </div>
          <p class="muted">
            Stealing advances you by <strong>+1 Tier per mission</strong> up to the Era's <strong>Theft Ceiling</strong>. Once stolen, refine it locally all the way to Tier 4!
          </p>

          <div class="subcard space-y" style="font-size:12px;">
            <strong>Required Conditions to Steal &amp; Operate:</strong>
            <label class="flex-between" style="cursor:pointer;">
              <span>1. Physical Input Resource Access</span>
              <input id="chk-input-res" type="checkbox" checked onchange="updateUI()" />
            </label>
            <label class="flex-between" style="cursor:pointer;">
              <span id="prereq-tech-label">2. Prerequisite Sibling Tech</span>
              <input id="chk-prereq-tech" type="checkbox" checked onchange="updateUI()" />
            </label>
            <div class="flex-between" style="border-top:1px solid var(--border); padding-top:6px;">
              <span>Era Complexity Theft Cap:</span>
              <strong id="espionage-cap-display" style="color:var(--amber);">Max Stolen = Tier 3</strong>
            </div>
          </div>

          <button class="btn-indigo" onclick="attemptEspionage()">🕵️ Launch Spy Mission: Steal +1 Tier (Cost: 150g)</button>
          <div id="espionage-status" class="muted"></div>
        </div>

        <!-- Entrenched Guilds & Legislation -->
        <div class="card space-y">
          <div class="flex-between">
            <h3>6. Incumbent Guilds &amp; Legislation</h3>
            <span class="badge badge-rose" id="guild-clout-badge">Guild Clout: 65%</span>
          </div>

          <div class="subcard space-y">
            <div class="flex-between">
              <strong style="font-size:12px;" id="guild-name">Incumbent Guild</strong>
              <span class="badge badge-rose" id="law-status-pill">BLOCKADE ACTIVE</span>
            </div>
            <div style="font-size:13px; font-weight:700; color:#f87171;" id="law-title">Protectionist Law</div>
            <p class="muted" id="law-desc"></p>
          </div>

          <div class="space-y">
            <div style="font-size:12px; font-weight:700;">Legislative &amp; Strategic Countermeasures:</div>
            <button onclick="resolveGuild('repeal')" style="width:100%; text-align:left;" class="flex-between">
              <div>
                <div style="font-weight:700;">Force Parliamentary Repeal</div>
                <div class="muted">Repeals law immediately; triggers Guild Strike (-15% Stability)</div>
              </div>
              <strong style="color:var(--sky);">-40 Pol</strong>
            </button>
            <button onclick="resolveGuild('buyout')" style="width:100%; text-align:left;" class="flex-between">
              <div>
                <div style="font-weight:700;">Eminent Domain Asset Buyout</div>
                <div class="muted">Compensate legacy barons to retire stranded assets peacefully</div>
              </div>
              <strong style="color:var(--amber);">-400g</strong>
            </button>
            <button onclick="resolveGuild('frontier')" style="width:100%; text-align:left;" class="flex-between">
              <div>
                <div style="font-weight:700;">Greenfield / Colonial Bypass</div>
                <div class="muted">Build prototypes in frontier towns outside guild jurisdiction (0.75x Artisan Net)</div>
              </div>
              <strong style="color:var(--emerald);">Free</strong>
            </button>
          </div>
        </div>

        <!-- Event Log -->
        <div class="card space-y">
          <div class="flex-between">
            <strong class="muted" style="text-transform:uppercase;">Simulation Chronicle</strong>
            <button onclick="clearLog()" style="padding:3px 8px;">Clear</button>
          </div>
          <div id="event-log" class="log-box space-y"></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    /*__INITIAL_CATALOG__*/
    const TECH_DATA = (typeof SERVER_CATALOG !== "undefined") ? SERVER_CATALOG : {};

    // Point Server Control Center link to current host on port 8000 for seamless remote/LAN navigation
    const mgrLink = document.getElementById("manager-link");
    if (mgrLink && window.location.hostname) {
      mgrLink.href = `${window.location.protocol}//${window.location.hostname}:8000`;
    }

    let state = {
      turn: 1,
      gold: 1200,
      pol: 100,
      stab: 85,
      preset: "britain",
      techKey: "steam_engines",
      avenueIndex: 0,
      discoveryProgress: 0,
      refinementXP: 0,
      subsidyMode: "commercial",
      guildClout: 35,
      guildLawActive: false,
      frontierBypass: false
    };

    function populateCatalogDropdown() {
      const sel = document.getElementById("catalog-dropdown");
      sel.innerHTML = "";
      const entries = Object.values(TECH_DATA).sort((a, b) => (a.era - b.era) || a.name.localeCompare(b.name));
      entries.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item.tech_id;
        opt.textContent = `[Era ${item.era}] ${item.name}`;
        sel.appendChild(opt);
      });
      sel.value = state.techKey;
      document.getElementById("sync-badge").textContent = `Synced: ${entries.length} Techs from macro/innovation.py`;
    }

    function getTierFromXP(xp, discovered) {
      if (!discovered && xp <= 0) return 0;
      if (xp < 25) return 1;
      if (xp < 60) return 2;
      if (xp < 90) return 3;
      return 4;
    }

    function applyEmpirePreset(preset) {
      state.preset = preset;
      state.frontierBypass = false;
      if (preset === "britain") {
        document.getElementById("slider-prox").value = 3;
        document.getElementById("toggle-crisis").checked = true;
        document.getElementById("slider-wage").value = 3.2;
        document.getElementById("slider-supply").value = 2.5;
        document.getElementById("slider-net").value = 2.0;
        document.getElementById("slider-inst").value = 1.6;
        state.gold = 1200; state.pol = 90; state.stab = 85;
        state.subsidyMode = "commercial";
        const era = TECH_DATA[state.techKey]?.era || 3;
        state.guildClout = era >= 4 ? 80 : 25;
        state.guildLawActive = state.guildClout >= 50;
        logEvent("Preset: Maritime Pioneer (High Wages, Cheap Adjacent Fuel, High Guild Clout in Era IV).");
      } else if (preset === "china") {
        document.getElementById("slider-prox").value = 1;
        document.getElementById("toggle-crisis").checked = false;
        document.getElementById("slider-wage").value = 0.4;
        document.getElementById("slider-supply").value = 1.0;
        document.getElementById("slider-net").value = 0.75;
        document.getElementById("slider-inst").value = 0.6;
        state.gold = 3000; state.pol = 140; state.stab = 95;
        state.subsidyMode = "standard";
        state.guildClout = 70;
        state.guildLawActive = true;
        logEvent("Preset: Agrarian Hegemon (Cheap Labor, Distant Fuel, Rich Treasury for State Subsidies).");
      } else if (preset === "challenger") {
        document.getElementById("slider-prox").value = 2;
        document.getElementById("toggle-crisis").checked = true;
        document.getElementById("slider-wage").value = 1.8;
        document.getElementById("slider-supply").value = 1.5;
        document.getElementById("slider-net").value = 1.75;
        document.getElementById("slider-inst").value = 1.8;
        state.gold = 1500; state.pol = 110; state.stab = 85;
        state.subsidyMode = "crash";
        state.guildClout = 10;
        state.guildLawActive = false;
        logEvent("Preset: Latecomer Challenger (0% Entrenched Guild Blockades — primed to steal Tier 1–2 & leapfrog!).");
      }
      updateUI();
    }

    function selectTech(techKey) {
      if (!TECH_DATA[techKey]) return;
      state.techKey = techKey;
      state.avenueIndex = 0;
      state.discoveryProgress = 0;
      state.refinementXP = 0;
      state.maturityByGeneration = {};
      state.installedGeneration = 1;
      state.experimentStock = 1000;
      state.programActive = true;
      state.programTarget = null;
      state.maturityTarget = null;
      state.programGeneration = null;
      state.frontierBypass = false;
      document.getElementById("catalog-dropdown").value = techKey;

      const era = TECH_DATA[techKey].era || 2;
      if (state.preset === "britain") {
        state.guildClout = era >= 4 ? 80 : 25;
        state.guildLawActive = state.guildClout >= 50;
      } else if (state.preset === "china") {
        state.guildClout = 70;
        state.guildLawActive = true;
      } else {
        state.guildClout = 10;
        state.guildLawActive = false;
      }

      renderAvenues();
      updateUI();
      logEvent(`Selected technology: ${TECH_DATA[techKey].name} (Era ${era}).`);
    }

    function renderAvenues() {
      const tech = TECH_DATA[state.techKey];
      const container = document.getElementById("avenue-list");
      container.innerHTML = "";
      tech.avenues.forEach((av, idx) => {
        const btn = document.createElement("button");
        btn.style.width = "100%";
        btn.style.textAlign = "left";
        if (idx === state.avenueIndex) btn.classList.add("active-choice");
        btn.onclick = () => { state.avenueIndex = idx; renderAvenues(); updateUI(); };
        btn.innerHTML = `
          <div class="flex-between">
            <strong>${av.name}</strong>
            <span class="badge" style="background:var(--card); border:1px solid var(--border);">${av.prototype}</span>
          </div>
          <div class="muted" style="margin-top:3px;">Catalyst: ${av.crisis}</div>
        `;
        container.appendChild(btn);
      });
    }

    function setSubsidyMode(mode) {
      state.subsidyMode = mode;
      state.programActive = true;
      state.programTarget = null;
      state.maturityTarget = null;
      state.programGeneration = null;
      updateUI();
    }

    let engineeringPreview = null;
    let previewRequest = 0;
    let stepping = false;

    function engineeringParams(turns = 1) {
      const proxStep = Number(document.getElementById("slider-prox").value);
      return {
        tech_id: state.techKey, turns, subsidy_mode: state.subsidyMode,
        engineering_objective: document.getElementById("eng-objective").value,
        operating_installations: Number(document.getElementById("eng-installations").value),
        utilization: Number(document.getElementById("eng-utilization").value) / 100,
        engineering_workers: Number(document.getElementById("eng-workers").value),
        workshop_capacity: 3, experiment_stock: state.experimentStock ?? 1000,
        treasury: state.gold, discovery_progress: state.discoveryProgress,
        refinement_xp: state.refinementXP, maturity_by_generation: state.maturityByGeneration || {},
        program_active: state.programActive ?? true, installed_generation: state.installedGeneration || 1,
        ...(state.programTarget == null ? {} : {program_capability_target: state.programTarget}),
        ...(state.maturityTarget == null ? {} : {program_maturity_target: state.maturityTarget}),
        ...(state.programGeneration == null ? {} : {program_generation: state.programGeneration}),
        prox_mult: proxStep === 3 ? 4 : proxStep === 2 ? 1 : 0.2,
        crisis_active: document.getElementById("toggle-crisis").checked,
        wage_ratio: Number(document.getElementById("slider-wage").value),
        supply_mult: Number(document.getElementById("slider-supply").value),
        net_mult: Number(document.getElementById("slider-net").value) * (state.frontierBypass ? 0.75 : 1),
        inst_mult: Number(document.getElementById("slider-inst").value),
        has_prereq: document.getElementById("chk-prereq-tech").checked,
        has_input: document.getElementById("chk-input-res").checked,
        guild_law_active: state.guildLawActive
      };
    }

    function calculateRates() {
      const p = engineeringParams();
      return {proxMult:p.prox_mult, crisisActive:p.crisis_active, wageRatio:p.wage_ratio,
        supplyMult:p.supply_mult, netMult:p.net_mult, instMult:p.inst_mult,
        hasPrereq:p.has_prereq, hasInput:p.has_input,
        emergenceRate:engineeringPreview?.emergence_rate_per_turn || 0,
        refinementRate:engineeringPreview?.refinement_rate_per_turn || 0};
    }

    async function simulate(params) {
      const response = await fetch('/api/simulate', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:JSON.stringify(params)});
      if (!response.ok) throw new Error('Simulation request failed');
      const result = await response.json();
      if (result.status !== 'ok') throw new Error(result.error || 'Simulation failed');
      return result;
    }

    async function stepTurns(n) {
      if (stepping) return;
      stepping = true;
      try {
        const params = engineeringParams(n);
        const key = state.techKey;
        const result = await simulate(params);
        if (key !== state.techKey) return;
        state.turn += n;
        state.discoveryProgress = result.final_discovery_progress;
        state.refinementXP = result.final_refinement_xp;
        state.gold = result.treasury;
        state.maturityByGeneration = result.maturity_by_generation;
        state.experimentStock = result.experiment_stock;
        state.programActive = result.program_active;
        state.programTarget = result.program_capability_target;
        state.maturityTarget = result.program_maturity_target;
        state.programGeneration = result.program_generation;
        state.installedGeneration = result.installed_generation;
        state.pol = Math.min(200, state.pol + 2 * n);
        const spent = result.history.reduce((sum, r) => sum + r.public_spent, 0);
        logEvent(`Turn ${state.turn}: capability ${state.refinementXP.toFixed(1)}, commercial maturity ${result.final_commercial_maturity.toFixed(1)}%. Engineering spent ${spent.toFixed(0)}g; ${state.experimentStock} experiment bundles remain.`);
        if (!result.program_active && params.program_active && params.subsidy_mode !== 'commercial') logEvent('Program milestone reached. Public spending stopped; operation continues. Select a funding level to commission the next milestone.');
        engineeringPreview = result;
        updateUI();
      } catch (error) { logEvent(error.message); }
      finally { stepping = false; }
    }

    function attemptEspionage() {
      const tech = TECH_DATA[state.techKey];
      const hasInput = document.getElementById("chk-input-res").checked;
      const hasPrereq = document.getElementById("chk-prereq-tech").checked;
      const statusEl = document.getElementById("espionage-status");

      if (!hasInput) {
        statusEl.innerHTML = `<span style="color:var(--rose); font-weight:700;">Blocked:</span> Missing physical input resources.`;
        logEvent("Espionage blocked: Missing physical input resources.");
        return;
      }
      if (state.gold < 150) {
        statusEl.innerHTML = `<span style="color:var(--rose); font-weight:700;">Insufficient Gold:</span> Requires 150g.`;
        return;
      }

      const currentTier = getTierFromXP(state.refinementXP, state.discoveryProgress >= 100);
      if (currentTier >= tech.max_steal_tier || state.refinementXP >= tech.max_steal_xp) {
        statusEl.innerHTML = `<span style="color:var(--amber); font-weight:700;">Espionage Ceiling Reached (Tier ${tech.max_steal_tier} / ${tech.max_steal_xp} XP):</span> Stealing cannot go higher, but you can refine your Tier ${currentTier} buildings locally to Tier 4!`;
        logEvent(`Espionage Ceiling reached for ${tech.name} (Tier ${tech.max_steal_tier}). Refine locally to reach Tier 4!`);
        return;
      }

      const targetTier = currentTier + 1;
      if (targetTier >= 3 && !hasPrereq) {
        statusEl.innerHTML = `<span style="color:var(--rose); font-weight:700;">Dependency Lock:</span> Must possess [${tech.prereq_name}] before stealing Tier ${targetTier}!`;
        logEvent(`Espionage blocked: Missing prerequisite [${tech.prereq_name}].`);
        return;
      }

      state.gold -= 150;
      state.discoveryProgress = 100;
      const tierFloorXP = { 1: 5, 2: 28, 3: 62 };
      const gainedXP = Math.min(tech.max_steal_xp, tierFloorXP[targetTier] || 28);
      state.refinementXP = Math.min(tech.max_steal_xp, Math.max(state.refinementXP + 15, gainedXP));

      const newTier = getTierFromXP(state.refinementXP, true);
      statusEl.innerHTML = `<span style="color:var(--emerald); font-weight:700;">Spy Heist (+1 Tier):</span> Advanced to Tier ${newTier} (${Math.floor(state.refinementXP)} XP). Now refine domestically!`;
      logEvent(`Turn ${state.turn}: Stolen blueprints (+1 Tier) -> ${tech.name} is now Tier ${newTier} (${Math.floor(state.refinementXP)} XP).`);
      updateUI();
    }

    function resolveGuild(action) {
      if (!state.guildLawActive) return;
      const tech = TECH_DATA[state.techKey];
      if (action === "repeal") {
        if (state.pol < 40) { logEvent("Requires 40 Political Capital to force Parliamentary Repeal."); return; }
        state.pol -= 40;
        state.stab = Math.max(10, state.stab - 15);
        state.guildLawActive = false;
        logEvent(`Turn ${state.turn}: Repealed [${tech.law_name}] in Parliament (-15% Stability)! Refinement uncapped.`);
      } else if (action === "buyout") {
        if (state.gold < 400) { logEvent("Requires 400g Treasury to buy out entrenched guild assets."); return; }
        state.gold -= 400;
        state.guildLawActive = false;
        state.guildClout = 10;
        logEvent(`Turn ${state.turn}: Bought out ${tech.incumbent_guild} for 400g! Blockade lifted.`);
      } else if (action === "frontier") {
        state.guildLawActive = false;
        state.frontierBypass = true;
        logEvent(`Turn ${state.turn}: Relocated prototypes to Greenfield Frontier outside guild jurisdiction.`);
      }
      updateUI();
    }

    function resetTechProgress() {
      state.discoveryProgress = 0;
      state.refinementXP = 0;
      state.maturityByGeneration = {};
      state.installedGeneration = 1;
      state.experimentStock = 1000;
      state.programActive = true;
      state.programTarget = null;
      state.maturityTarget = null;
      state.programGeneration = null;
      state.turn = 1;
      logEvent("Reset technology progress to Turn 1 (Tier 0).");
      updateUI();
    }

    function logEvent(msg) {
      const log = document.getElementById("event-log");
      const div = document.createElement("div");
      div.className = "subcard";
      div.style.padding = "6px 10px";
      div.textContent = msg;
      log.prepend(div);
    }

    function clearLog() {
      document.getElementById("event-log").innerHTML = "";
    }

    function updateUI() {
      renderUI();
      const request = ++previewRequest;
      simulate(engineeringParams()).then(result => {
        if (request !== previewRequest) return;
        engineeringPreview = result;
        renderUI();
      }).catch(error => logEvent(error.message));
    }

    function renderUI() {
      const tech = TECH_DATA[state.techKey];
      const rates = calculateRates();

      document.getElementById("stat-turn").textContent = state.turn;
      document.getElementById("stat-gold").textContent = `${state.gold.toLocaleString()}g`;
      document.getElementById("stat-pol").textContent = state.pol;
      document.getElementById("stat-stab").textContent = `${state.stab}%`;

      ["britain", "china", "challenger"].forEach(p => {
        const btn = document.getElementById(`btn-preset-${p}`);
        btn.classList.toggle("active-choice", state.preset === p);
      });
      ["gunpowder_blasting", "steam_engines", "petroleum_refining", "microelectronics"].forEach(t => {
        const btn = document.getElementById(`btn-tech-${t}`);
        if (btn) btn.classList.toggle("active-choice", state.techKey === t);
      });

      document.getElementById("complexity-badge").textContent = tech.steal_gap_text;

      const proxStep = parseInt(document.getElementById("slider-prox").value, 10);
      document.getElementById("label-prox").textContent = proxStep === 3 ? "Same Hub / Waterway (4.0x)" : proxStep === 2 ? "Road (1.0x)" : "Landlocked (0.2x)";

      const av = tech.avenues[state.avenueIndex] || tech.avenues[0];
      document.getElementById("crisis-title").textContent = `Crisis: ${av.crisis}`;
      document.getElementById("crisis-desc").textContent = rates.crisisActive ? "ACTIVE (+2.5x Catalyst Surge)" : "Inactive (0.6x)";
      document.getElementById("label-wage").textContent = `${rates.wageRatio.toFixed(1)}x`;
      document.getElementById("label-supply").textContent = `${rates.supplyMult.toFixed(2)}x`;
      document.getElementById("label-net").textContent = `${rates.netMult.toFixed(2)}x ${state.frontierBypass ? "(Frontier)" : ""}`;
      document.getElementById("label-inst").textContent = `${rates.instMult.toFixed(1)}x`;

      const isDiscovered = state.discoveryProgress >= 100 || state.refinementXP > 0;
      const currentTier = getTierFromXP(state.refinementXP, isDiscovered);
      const tierNames = [
        "Tier 0: Theoretical Concept",
        `Tier 1: ${av.prototype} (Crude Prototype)`,
        "Tier 2: Commercial Industrial Standard",
        "Tier 3: High-Efficiency / Mobile Precision",
        "Tier 4: Frontier Mastery"
      ];
      document.getElementById("current-tier-title").textContent = tierNames[currentTier];
      document.getElementById("current-tier-badge").textContent = `TIER ${currentTier} / 4`;

      const discPct = isDiscovered ? 100 : Math.floor(state.discoveryProgress);
      document.getElementById("discovery-pct").textContent = `${discPct} / 100`;
      document.getElementById("discovery-bar").style.width = `${discPct}%`;
      document.getElementById("discovery-rate-label").textContent = isDiscovered ? "Prototype Operational" : `+${rates.emergenceRate.toFixed(1)} / turn`;

      const refXP = Math.floor(state.refinementXP);
      document.getElementById("refinement-xp-label").textContent = `${refXP} / 100 XP`;
      document.getElementById("refinement-bar").style.width = `${refXP}%`;

      const refNote = document.getElementById("refinement-rate-note");
      if (!isDiscovered) refNote.textContent = "Develop or acquire a working prototype. Funded experiments can help.";
      else if (!rates.hasInput) refNote.textContent = "HALTED: Missing Physical Input Resources (+0.0 XP/turn).";
      else if (!rates.hasPrereq && state.refinementXP >= 59) refNote.textContent = `CAPPED AT 59 XP: Requires [${tech.prereq_name}] for Tier 3!`;
      else refNote.textContent = `Operation & delivered engineering: +${rates.refinementRate.toFixed(1)} XP / turn ${state.guildLawActive ? "(Throttled to 25% by Guild Law!)" : ""}`;

      ["commercial", "standard", "crash"].forEach(m => {
        document.getElementById(`btn-sub-${m}`).classList.toggle("active-choice", state.subsidyMode === m);
      });
      document.getElementById("subsidy-cost-badge").textContent =
        `Expected spending ${Number(engineeringPreview?.expected_spend || 0).toFixed(0)}g/t`;
      document.getElementById("eng-maturity").textContent = `Commercial maturity: ${Number(state.maturityByGeneration?.[Math.max(1, currentTier)] || 0).toFixed(1)}% · ${state.experimentStock ?? 1000} experiment bundles · Program ${state.programActive === false ? 'completed' : state.subsidyMode === 'commercial' ? 'inactive' : 'active'}`;

      const downContainer = document.getElementById("downstream-list");
      downContainer.innerHTML = "";
      tech.downstream.forEach(item => {
        const unlocked = currentTier >= item.reqTier && state.refinementXP >= item.reqXP && (item.reqTier < 3 || rates.hasPrereq);
        const div = document.createElement("div");
        div.className = `subcard flex-between ${unlocked ? "unlocked-item" : ""}`;
        div.innerHTML = `
          <div>
            <div style="font-size:12px; font-weight:700;">${unlocked ? "🟢 UNLOCKED:" : "🔒"} ${item.name}</div>
            <div class="muted" style="margin-top:2px;">${item.desc}</div>
          </div>
          <span class="badge" style="background:var(--card); border:1px solid var(--border); white-space:nowrap;">Tier ${item.reqTier} (${item.reqXP} XP)</span>
        `;
        downContainer.appendChild(div);
      });

      document.getElementById("prereq-tech-label").textContent = `2. ${tech.prereq_name}`;
      document.getElementById("espionage-cap-display").textContent = `Max Stolen = Tier ${tech.max_steal_tier} (${tech.max_steal_xp} XP)`;

      document.getElementById("guild-clout-badge").textContent = `Guild Clout: ${state.guildClout}%`;
      document.getElementById("guild-name").textContent = `Incumbent: ${tech.incumbent_guild}`;
      document.getElementById("law-title").textContent = tech.law_name;
      document.getElementById("law-desc").textContent = state.guildLawActive
        ? tech.law_desc
        : "Protectionist legislation repealed or bypassed! Prototypes operate at 100% domestic Refinement speed.";

      const pill = document.getElementById("law-status-pill");
      pill.className = state.guildLawActive ? "badge badge-rose" : "badge badge-emerald";
      pill.textContent = state.guildLawActive ? "BLOCKADE ACTIVE (0.25x XP)" : "UNBLOCKED (100% SPEED)";
    }

    populateCatalogDropdown();
    renderAvenues();
    applyEmpirePreset("britain");
  </script>
</body>
</html>
"""


class TechSimHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, payload: dict, status_code: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            catalog = build_dynamic_catalog()
            injection = f"const SERVER_CATALOG = {json.dumps(catalog)};"
            html = SIMULATOR_HTML.replace("/*__INITIAL_CATALOG__*/", injection)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/health":
            catalog = build_dynamic_catalog()
            self._send_json({
                "status": "ok",
                "service": "techsim",
                "uptime_sec": int(time.time() - SERVER_START_TIME),
                "catalog_count": len(catalog),
                "live_innovation_tech_count": len(TECH_CATALOG),
                "domains": [d.value for d in TechDomain],
            })
            return

        if path == "/api/catalog":
            catalog = build_dynamic_catalog()
            self._send_json({
                "status": "ok",
                "count": len(catalog),
                "catalog": catalog,
            })
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/simulate":
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                params = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception as exc:
                self._send_json({"status": "error", "message": str(exc)}, status_code=400)
                return
            try:
                res = simulate_trajectory(params)
            except (ValueError, TypeError, OverflowError) as exc:
                self._send_json({'status': 'error', 'message': str(exc)}, status_code=400)
                return
            self._send_json(res)
            return

        self.send_response(404)
        self.end_headers()


def _detect_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Call of Capital — Emergent Tech Tree & Leapfrog Simulator Server")
    parser.add_argument("--port", type=int, default=8082, help="Port to listen on (default: 8082)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    args = parser.parse_args(argv)

    lan_ip = _detect_lan_ip()
    local_url = f"http://localhost:{args.port}"
    lan_url = f"http://{lan_ip}:{args.port}"

    server = HTTPServer((args.host, args.port), TechSimHTTPRequestHandler)
    print("\n" + "=" * 66)
    print("  🔬 CALL OF CAPITAL — TECH TREE & LEAPFROG SIMULATOR ONLINE")
    print("=" * 66)
    print(f"  👉 Local Browser : {local_url}")
    print(f"  👉 LAN / Mobile  : {lan_url}")
    print(f"  👉 REST Catalog  : {local_url}/api/catalog")
    print(f"  👉 REST Simulate : POST {local_url}/api/simulate")
    print("=" * 66 + "\n")

    try:
        from sim_server.qr_code import print_qr_code
        print_qr_code(lan_url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Tech Simulator Server...")
        server.server_close()


if __name__ == "__main__":
    main()
