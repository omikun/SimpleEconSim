"""
worldview_tooltips.py — Comprehensive Mouse-Over Tooltip System for Left Panel Mechanisms.

Renders detailed floating explanation cards for every button and mechanism on the left-hand panel:
- What each mechanism does (rules, formulas, transfers).
- What it achieves (short & long-term economic, demographic, and political effects).
- Monetary and resource costs / prerequisites.
- Breakdown of relevant live stats (tax rates, treasury, protest, hunger, casualties, etc.).
"""

from __future__ import annotations
import pygame
from worldview_camera import WIDTH, HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon

# Dimensions
CARD_MAX_W = 440
PADDING_X = 16
PADDING_Y = 14


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Wrap text into multiple lines so that none exceed max_width."""
    if not text:
        return []
    lines = []
    for raw_paragraph in text.split('\n'):
        words = raw_paragraph.split(' ')
        current_line = []
        for word in words:
            if not word:
                continue
            test_line = ' '.join(current_line + [word])
            if font.size(test_line)[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []
        if current_line:
            lines.append(' '.join(current_line))
    return lines


def _build_button_tooltip_raw(btn_id: str, world: dict, region=None, nation=None, province=None) -> dict | None:
    """Generate detailed mechanism description, achievement context, and live stat breakdown."""
    pinned = region or world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    owner = nation or (getattr(pinned, 'owner_nation', None) if pinned else None)
    if owner is None and world.get('nations'):
        owner = world['nations'][0]

    prov = province or (getattr(pinned, 'province', None) if pinned else None)
    gov = getattr(pinned, 'gov', None) if pinned else None

    # Live stats helpers
    tile_cash = (gov.agent.cash if gov and hasattr(gov, 'agent') else 0.0) if gov else 0.0
    tax_rate = gov.tax_rate if gov else 0.15
    protest_e = pinned.protest_energy_log[-1] if (pinned and pinned.protest_energy_log) else 0.0
    hungry = sum(1 for a in pinned.agents if not a.is_corporation and not a.is_government and a.hungry_steps > 0) if pinned else 0
    pop_count = len(pinned.agents) if pinned else 0
    prov_cash = (prov.gov.agent.cash if prov and getattr(prov, 'gov', None) and hasattr(prov.gov, 'agent') else 0.0) if prov else 0.0
    tr = owner.treasury() if owner else {'total': 0.0, 'sovereign_cash': 0.0}
    nat_cash = tr.get('sovereign_cash', 0.0)
    tot_cash = tr.get('total', 0.0)

    # -------------------------------------------------------------------------
    # CITY / TILE SCOPE POLICIES
    # -------------------------------------------------------------------------
    if btn_id == 'city_tax_cut':
        return {
            'title': "Municipal Tax Cut [-2%]",
            'badge': "DISPOSABLE CASH",
            'badge_col': (120, 240, 150),
            'category': "City Fiscal Decree",
            'cost': "Revenue Trade-off: Lowers ongoing income tax yield",
            'desc': [
                "Reduces municipal income tax by 2.0% (down to 2.0% floor).",
                "Leaves more liquid cash in citizen pockets, directly boosting",
                "purchasing power for food and consumer wares. Subdues civil",
                "discontent and protest energy.",
                "Trade-off: Less public treasury intake for emergency relief."
            ],
            'stats': [
                ("Current Tax Rate", f"{tax_rate*100:.1f}% -> {max(2.0, (tax_rate-0.02)*100):.1f}%", ACCENT),
                ("Municipal Treasury", f"${tile_cash:,.0f}", (120, 240, 150)),
                ("Protest Energy", f"{protest_e:.2f}", (240, 150, 70) if protest_e > 0.3 else GREEN),
                ("City Population", f"{pop_count} Citizens", TEXT),
            ]
        }

    if btn_id == 'city_tax_raise':
        return {
            'title': "Municipal Tax Hike [+2%]",
            'badge': "TREASURY YIELD",
            'badge_col': (245, 180, 50),
            'category': "City Fiscal Decree",
            'cost': "Unrest Risk: Increases cost of living pressure",
            'desc': [
                "Raises statutory municipal income tax by 2.0% (capped at 60%).",
                "Supplies city treasury with vital revenues to fund grain reserves,",
                "public civic construction, and constabulary patrols.",
                "Trade-off: Squeezes worker living margins and elevates civic unrest."
            ],
            'stats': [
                ("Current Tax Rate", f"{tax_rate*100:.1f}% -> {min(60.0, (tax_rate+0.02)*100):.1f}%", ACCENT),
                ("Municipal Treasury", f"${tile_cash:,.0f}", (120, 240, 150)),
                ("Protest Energy", f"{protest_e:.2f}", (240, 150, 70) if protest_e > 0.3 else GREEN),
                ("Hungry Citizens", f"{hungry}", RED if hungry > 0 else GREEN),
            ]
        }

    if btn_id in ('city_toggle_ubi', 'city_ubi'):
        ubi_on = getattr(gov, 'ubi_enabled', getattr(gov, 'ubi_active', False)) if gov else False
        cost_p_t = pop_count * 5.0
        return {
            'title': f"Universal Basic Income: {'Active' if ubi_on else 'Inactive'}",
            'badge': "ANTI-POVERTY" if not ubi_on else "ACTIVE MANDATE",
            'badge_col': GREEN if not ubi_on else ACCENT,
            'category': "Municipal Welfare Safety Net",
            'cost': f"Cost: ${cost_p_t:,.0f}/turn ($5/citizen from city treasury)" if not ubi_on else "Click to repeal UBI",
            'desc': [
                "Disburses a guaranteed $5 cash stipend each turn to all residents.",
                "Eradicates extreme poverty, ensures citizens can buy market grain,",
                "and stabilizes domestic consumer goods circulation.",
                "Requires robust municipal treasury reserves to sustain."
            ],
            'stats': [
                ("UBI Status", "ENABLED" if ubi_on else "DISABLED", GREEN if ubi_on else DIM),
                ("Eligible Population", f"{pop_count} Citizens", TEXT),
                ("Est. Cost Per Turn", f"${cost_p_t:,.0f}/t", (245, 180, 50)),
                ("Treasury Reserves", f"${tile_cash:,.0f}", (120, 240, 150)),
            ]
        }

    if btn_id in ('city_emergency_food', 'city_food_relief'):
        return {
            'title': "Emergency Grain Relief ($50)",
            'badge': "FAMINE RESCUE",
            'badge_col': GREEN,
            'category': "Municipal Emergency Aid",
            'cost': "Cost: $50 from municipal treasury or city bank",
            'desc': [
                "Purchases and distributes 30 food rations to starving citizens.",
                "Immediately resets hunger counters to zero, halts malnutrition",
                "attrition, and quells imminent bread riots.",
                "Targeted strictly at citizens with positive hungry steps."
            ],
            'stats': [
                ("Hungry Citizens", f"{hungry} Starving", RED if hungry > 0 else GREEN),
                ("Rations Distributed", "30 Food Units", (120, 240, 150)),
                ("Treasury Cash", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= 50 else RED),
            ]
        }

    if btn_id == 'city_farm_subsidy':
        fert = pinned.terrain.get('food', 1.0) if (pinned and hasattr(pinned, 'terrain')) else 1.0
        return {
            'title': "Agricultural Development Subsidy ($100)",
            'badge': "FOOD PRODUCTION",
            'badge_col': (130, 210, 140),
            'category': "Municipal Economic Development",
            'cost': "Cost: $100 from municipal treasury",
            'desc': [
                "Disburses grants directly into local farm estates and grain growers.",
                "Expands agricultural hiring, lowers baseline market food prices,",
                "and generates grain surpluses to insulate city from shortages.",
                "Permanent positive boost to agricultural productivity."
            ],
            'stats': [
                ("Farmland Fertility", f"{fert:.2f}x Baseline", (120, 240, 150)),
                ("Treasury Cash", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= 100 else RED),
            ]
        }

    if btn_id in ('city_safety_patrol', 'city_police_curfew'):
        return {
            'title': "Constabulary Patrol & Curfew ($60)",
            'badge': "PUBLIC ORDER",
            'badge_col': (240, 100, 100),
            'category': "Civil Security & Law Enforcement",
            'cost': "Cost: $60 police operational upkeep",
            'desc': [
                "Mobilizes night patrols and enforces curfew across city districts.",
                "Instantly suppresses active riots and slashes popular protest",
                "energy by 0.35 points across the municipality.",
                "Trade-off: Builds long-term state resentment if unrest is not resolved."
            ],
            'stats': [
                ("Current Protest Energy", f"{protest_e:.2f}", RED if protest_e > 0.4 else (240, 180, 50)),
                ("Treasury Cash", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= 60 else RED),
            ]
        }

    if btn_id == 'city_recruit_garrison':
        garrison = sum(u.soldiers for u in getattr(pinned, 'military_units', [])) if pinned else 0
        return {
            'title': "Recruit 5 Garrison Soldiers ($50)",
            'badge': "MILITARY DEFENSE",
            'badge_col': (100, 180, 240),
            'category': "Military Recruitment",
            'cost': "Cost: $50 uniform & equipment levy",
            'desc': [
                "Musters 5 adult citizens into permanent garrison company.",
                "Fortifies city against external invasion, deters rebellions,",
                "and absorbs idle labor into state payroll.",
                "Soldiers require continuous supply maintenance and grain upkeep."
            ],
            'stats': [
                ("Active Garrison", f"{garrison} Soldiers", ACCENT),
                ("Treasury Cash", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= 50 else RED),
            ]
        }

    if btn_id == 'city_enclose_plot':
        tenure = getattr(pinned, 'tenure', None) if pinned else None
        feudal_pct = tenure.feudal_fraction * 100 if tenure else 0
        fee = 50.0
        return {
            'title': "Enclose Common Land (Crown Charter)",
            'badge': "FEUDAL PRIVATIZATION",
            'badge_col': (230, 140, 70),
            'category': "Agrarian Land Tenure Reform",
            'cost': f"Charter Fee: Lord pays ~${fee:.0f} to crown treasury",
            'desc': [
                "Abolishes customary serf foraging rights on parcel, privatizing",
                "land into enclosed commercial estates under landlord tenure.",
                "Pleases the Gentry faction and yields crown charter fee revenues.",
                "Severe trade-off: Dispossesses commoners, turning serfs into tenants",
                "or landless laborers and triggering long-term protest."
            ],
            'stats': [
                ("Feudal Commons Remaining", f"{feudal_pct:.0f}%", (130, 210, 140)),
                ("Charter Fee Payout", f"+${fee:.0f} to Gov", GREEN),
            ]
        }

    # -------------------------------------------------------------------------
    # PROVINCE SCOPE POLICIES
    # -------------------------------------------------------------------------
    if btn_id == 'prov_pave_highway':
        return {
            'title': "Pave Regional Highway Corridor ($120)",
            'badge': "LOGISTICS ACCEL",
            'badge_col': (100, 200, 240),
            'category': "Provincial Infrastructure",
            'cost': "Cost: $120 from provincial treasury",
            'desc': [
                "Paves macadamized highway connectors between province cities.",
                "Permanently lowers logistics transport delay and route friction",
                "by 30%, speeding trade arbitrage and commodity delivery.",
                "Bridges price disparities across provincial markets."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150) if prov_cash >= 120 else RED),
                ("Territory Count", f"{len(getattr(prov, 'tiles', []))} Cities", TEXT),
            ]
        }

    if btn_id == 'prov_healthcare':
        return {
            'title': "Regional Health & Sanitation ($150)",
            'badge': "EPIDEMIC SHIELD",
            'badge_col': (240, 120, 140),
            'category': "Provincial Public Health",
            'cost': "Cost: $150 from provincial treasury",
            'desc': [
                "Establishes sanatoriums, clean wells, and quarantine posts.",
                "Reduces industrial health attrition from toxic factory shifts",
                "and cuts demographic mortality across all member territories.",
                "Protects workforce life expectancy and reproductive health."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150) if prov_cash >= 150 else RED),
            ]
        }

    if btn_id == 'prov_equalization':
        return {
            'title': "Provincial Fiscal Equalization ($200)",
            'badge': "BANK RECAPITALIZE",
            'badge_col': (245, 215, 110),
            'category': "Provincial Fiscal Transfers",
            'cost': "Cost: $200 grant from provincial treasury",
            'desc': [
                "Transfers capital grant to the poorest city bank in the province.",
                "Prevents insolvency and local credit freezes, restoring private",
                "lending and commercial business investments in struggling towns.",
                "Maintains balanced regional development across the province."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150) if prov_cash >= 200 else RED),
            ]
        }

    if btn_id == 'prov_harmonize_taxes':
        return {
            'title': "Harmonize Provincial Taxes",
            'badge': "FISCAL UNIFICATION",
            'badge_col': ACCENT,
            'category': "Provincial Governance",
            'cost': "Cost: Free (Regulatory Alignment)",
            'desc': [
                "Calculates the average tax rate across all member cities and",
                "enforces it uniformly throughout the province.",
                "Eliminates internal tax havens and harmful fiscal arbitrage",
                "between neighboring municipal jurisdictions."
            ],
            'stats': [
                ("Member Territories", f"{len(getattr(prov, 'tiles', []))}", TEXT),
            ]
        }

    if btn_id == 'prov_standardize_routes':
        return {
            'title': "Standardize Transport Routes",
            'badge': "TRADE INTEGRATION",
            'badge_col': (130, 210, 140),
            'category': "Provincial Logistics",
            'cost': "Cost: Free (Administrative Accord)",
            'desc': [
                "Harmonizes regional toll charges, wagon axle weights, and river",
                "navigation rules to streamline inter-city freight traffic."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150)),
            ]
        }

    # -------------------------------------------------------------------------
    # NATION SCOPE POLICIES
    # -------------------------------------------------------------------------
    if btn_id.startswith('nat_tax_'):
        rate = int(btn_id.split('_')[-1])
        return {
            'title': f"National Statutory Tax Directive ({rate}%)",
            'badge': "SOVEREIGN MANDATE",
            'badge_col': ACCENT,
            'category': "National Fiscal Policy",
            'cost': "Mandatory statutory tax rate for all provinces",
            'desc': [
                f"Decrees statutory {rate}% income tax across all nation's cities.",
                "Overrides disparate local rates to centralize state revenues",
                "for national defense, scientific grants, and sovereign projects."
            ],
            'stats': [
                ("New Statutory Baseline", f"{rate}%", ACCENT),
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150)),
            ]
        }

    if btn_id.startswith('nat_tariff_'):
        rate = int(btn_id.split('_')[-1])
        return {
            'title': f"Customs Tariff Directive ({rate}%)",
            'badge': "PROTECTIONISM" if rate > 0 else "FREE TRADE",
            'badge_col': (100, 190, 240) if rate == 0 else (245, 180, 50),
            'category': "International Trade Policy",
            'cost': "Applies customs surcharges on all foreign imported goods",
            'desc': [
                f"Sets national import tariff to {rate}%.",
                "Protects domestic manufacturers and farms from foreign dumping" if rate > 0 else "Maximizes consumer goods inflow and lowers commodity living costs.",
                "Customs fees flow directly into the sovereign treasury."
            ],
            'stats': [
                ("Tariff Level", f"{rate}% Import Duty", ACCENT),
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150)),
            ]
        }

    if btn_id == 'nat_enact_ubi':
        return {
            'title': "Empire-wide Universal Basic Income",
            'badge': "NATIONAL WELFARE",
            'badge_col': GREEN,
            'category': "Sovereign Social Accord",
            'cost': "Mandates UBI across all provinces and constituent cities",
            'desc': [
                "Orders every municipal government to establish guaranteed UBI.",
                "Eradicates famine and destitute poverty nationwide, boosting",
                "aggregate consumer demand across all domestic markets."
            ],
            'stats': [
                ("Sovereign Treasury", f"${tot_cash:,.0f} Total", (120, 240, 150)),
            ]
        }

    if btn_id == 'nat_toggle_imm':
        return {
            'title': "Border & Immigration Directive",
            'badge': "POPULATION FLOW",
            'badge_col': (160, 210, 255),
            'category': "Border Control",
            'cost': "Toggles border access for foreign migrant labor",
            'desc': [
                "Open borders welcome foreign immigrants into underpopulated cities",
                "to staff industrial factories, mills, and frontier homesteads.",
                "Closed borders protect domestic wages and minimize cultural strain."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150)),
            ]
        }

    if btn_id == 'nat_science_prize':
        return {
            'title': "Royal Innovation Prize Bounty ($300)",
            'badge': "TECH BREAKTHROUGH",
            'badge_col': (180, 140, 240),
            'category': "National Science & Research",
            'cost': "Cost: $300 prize bounty from sovereign treasury",
            'desc': [
                "Funds national research grants and rewards technological discovery.",
                "Spurs breakthroughs in steam mechanization, corporate finance,",
                "and agronomy, accelerating domestic productivity growth."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 300 else RED),
            ]
        }

    if btn_id == 'nat_mobilize_army':
        return {
            'title': "Mobilize Standing Army ($250)",
            'badge': "EXPEDITIONARY FORCE",
            'badge_col': (235, 90, 90),
            'category': "Sovereign Defense Command",
            'cost': "Cost: $250 mobilization & armaments levy",
            'desc': [
                "Levies and equips an elite national army division under direct",
                "sovereign command, capable of maneuvering across the hex world.",
                "Deters foreign military aggression and secures sovereign borders."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 250 else RED),
            ]
        }

    if btn_id == 'nat_sovereign_grant':
        return {
            'title': "Sovereign Development Grant ($250)",
            'badge': "NATIONAL COHESION",
            'badge_col': (245, 215, 110),
            'category': "Sovereign Fiscal Equalization",
            'cost': "Cost: $250 grant from sovereign treasury",
            'desc': [
                "Disburses crown wealth to impoverished provincial treasuries.",
                "Bolsters national creditworthiness, enhances sovereign bond",
                "ratings on the ISRB market, and reduces regional inequality."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 250 else RED),
            ]
        }

    if btn_id == 'nat_ten_hour_act':
        has_ten = getattr(owner, 'ten_hour_act', False) if owner else False
        return {
            'title': "The Ten-Hour Act (Statutory Workday Cap)",
            'badge': "PRO-LABOR MANDATE" if not has_ten else "LAW ENFORCED",
            'badge_col': GREEN if not has_ten else ACCENT,
            'category': "National Labor Legislation",
            'cost': "Political Risk: Alienates capitalists & prompts electoral backlash",
            'desc': [
                "Legally caps factory and mill shifts to a maximum of 10.0 hours/day.",
                "Corporations cannot voluntarily reduce shift hours under competition;",
                "only statutory law forces shift reductions.",
                "Dramatically reduces health attrition and quells strike uprisings.",
                "Trade-off: Squeezes surplus value (s/v), enraging capitalists who pool",
                "PAC warchests to finance opposition candidates and oust the regime."
            ],
            'stats': [
                ("Workday Cap", "10.0h" if has_ten else "16.0h -> 10.0h", GREEN),
                ("Current Status", "ENACTED" if has_ten else "PENDING DECREE", ACCENT if not has_ten else GREEN),
            ]
        }

    if btn_id == 'nat_safety_mandate':
        has_safe = getattr(owner, 'factory_safety_act', False) if owner else False
        return {
            'title': "Factory Safety Standards Mandate",
            'badge': "WORKPLACE GUARDS" if not has_safe else "LAW ENFORCED",
            'badge_col': GREEN if not has_safe else ACCENT,
            'category': "National Workplace Safety Law",
            'cost': "Industrial Burden: Requires machinery guards and safety investment",
            'desc': [
                "Mandates protective gear, machinery shields, and fire exits.",
                "Reduces disabling factory casualties, mangled limbs, and workplace",
                "mortality by over 70%. Halts Luddite machine sabotage.",
                "Improves long-term worker longevity and biological productivity."
            ],
            'stats': [
                ("Safety Regulation", "MANDATED" if has_safe else "UNREGULATED", GREEN if has_safe else RED),
            ]
        }

    if btn_id == 'nat_subsidize_entertainment':
        return {
            'title': "Subsidize Mass Spectacle & Amusements ($50)",
            'badge': "POPULAR PACIFIER",
            'badge_col': (70, 195, 235),
            'category': "Social Control & Pacification",
            'cost': "Cost: $50 public spectacle subsidy from treasury",
            'desc': [
                "Subsidizes commercial music halls, theater, saloons, and public games.",
                "Mass entertainment acts as an isolation pacifier: dampens worker",
                "rebellion energy, lowers class consciousness, and prevents strike organizing.",
                "Safeguards industrial peace and protects capitalists from uprisings."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 50 else RED),
            ]
        }

    # -------------------------------------------------------------------------
    # FRONTIER WILDERNESS POLICIES
    # -------------------------------------------------------------------------
    if btn_id == 'frontier_expedition':
        return {
            'title': "Sponsor Frontier Pioneer Expedition",
            'badge': "TERRITORIAL EXPANSION",
            'badge_col': GREEN,
            'category': "Wilderness Colonization",
            'cost': "Cost: Outfits 5 homesteaders with tools and grain rations",
            'desc': [
                "Dispatches 5 brave pioneer families to homestead the uncolonized tile.",
                "Settlers clear brush, build log cabins, and gather wilderness food.",
                "When your nation's settlers reach 50%+ of frontier population,",
                "the territory can be formally claimed as a new national province."
            ],
            'stats': [
                ("Tile Name", getattr(pinned, 'display_name', getattr(pinned, 'city_name', pinned.name)) if pinned else "Frontier", TEXT),
            ]
        }

    if btn_id == 'frontier_pioneer_grant':
        return {
            'title': "Pioneer Emergency Food Relief",
            'badge': "SURVIVAL AID",
            'badge_col': (130, 210, 140),
            'category': "Colonial Welfare",
            'cost': "Delivers emergency food rations to struggling pioneers",
            'desc': [
                "Prevents pioneer starvation during brutal winter frost or drought.",
                "Preserves settlement population until agriculture is established."
            ],
            'stats': [
                ("Tile Status", "Wilderness Frontier", DIM),
            ]
        }

    # -------------------------------------------------------------------------
    # INFRASTRUCTURE BUILDING RECIPES
    # -------------------------------------------------------------------------
    clean_bkey = btn_id[6:] if btn_id.startswith('build_') else btn_id
    from buildings import BUILDING_RECIPES
    if clean_bkey in BUILDING_RECIPES:
        recipe = BUILDING_RECIPES[clean_bkey]
        tier_names = {'tile': 'Municipal (City)', 'province': 'Provincial', 'nation': 'National Sovereign'}
        tier_str = tier_names.get(recipe.tier, recipe.tier.capitalize())
        mat_str = ", ".join(f"{v} {k.value}" for k, v in recipe.required_goods.items()) if recipe.required_goods else "None"
        bonus_str = ", ".join(f"+{int((v-1.0)*100)}% {k.value}" for k, v in recipe.production_bonuses.items()) if recipe.production_bonuses else "Structural modifier"

        is_built = any(b.name == clean_bkey for b in getattr(pinned, 'buildings', [])) if pinned else False
        active_proj = next((p for p in getattr(pinned, 'construction_projects', []) if p.recipe.name == clean_bkey and p.status == 'in_progress'), None)
        if active_proj is None and owner:
            active_proj = next((p for p in getattr(owner, 'construction_projects', []) if p.recipe.name == clean_bkey and p.status == 'in_progress' and p.region == pinned), None)

        if is_built:
            status_txt = "ALREADY INSTALLED (Active Modifier)"
        elif active_proj is not None:
            pct = active_proj.turns_elapsed / max(1, active_proj.total_turns)
            status_txt = f"UNDER CONSTRUCTION ({active_proj.turns_elapsed}/{active_proj.total_turns} Turns - {int(pct*100)}%)"
        else:
            status_txt = f"Ready to Construct ({recipe.base_turns} Turns)"

        recipe_icons = {
            'farm': 'grain',
            'granary': 'granary',
            'sawmill': 'timber',
            'workshop': 'manufacturing',
            'paved_road': 'civil_engineering',
            'river_bridge': 'civil_engineering',
            'sanatorium': 'municipal',
            'mountain_pass': 'mountain',
            'central_mint': 'finance',
            'military_citadel': 'military',
        }

        return {
            'title': f"Construct {recipe.display_name}",
            'badge': f"{recipe.tier.upper()} TIER",
            'badge_col': (120, 200, 240) if recipe.tier == 'tile' else ((245, 205, 90) if recipe.tier == 'province' else (240, 120, 120)),
            'category': f"{tier_str} Capital Project",
            'cost': f"Requirements: ${recipe.cost:,.0f} & {recipe.base_turns} turns (Materials: {mat_str})",
            'desc': [
                recipe.description,
                f"Production Benefit: {bonus_str}.",
                "Hires local or state contractor corporations to fabricate structural assets.",
                "Weather and labor friction may cause small completion variations."
            ],
            'stats': [
                ("Project Status", status_txt, GREEN if is_built else ((245, 205, 90) if active_proj else ACCENT)),
                ("Base Capital Cost", f"${recipe.cost:,.0f}", (120, 240, 150)),
                ("Construction Duration", f"{recipe.base_turns} turns", TEXT),
            ],
            'icon': recipe_icons.get(clean_bkey, 'hammer'),
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # TIER HEADER OVERVIEWS
    # -------------------------------------------------------------------------
    if btn_id == 'tier_municipal':
        return {
            'title': "Municipal Infrastructure Tier",
            'badge': "LOCAL TILE",
            'badge_col': (120, 200, 240),
            'category': "City Level Public Works",
            'cost': "Funding Source: Local municipal treasury & tile bank reserves",
            'desc': [
                "Local municipal infrastructure projects directly improve city output,",
                "food security, and resource harvesting within this specific territory.",
                "Contracted through local corporations and funded by city taxes."
            ],
            'stats': [
                ("Available Tile Treasury", f"${tile_cash:,.0f}", (120, 240, 150)),
                ("City Population", f"{pop_count} Citizens", TEXT),
            ],
            'icon': 'municipal',
            'btn_id': btn_id
        }

    if btn_id == 'tier_province':
        return {
            'title': "Provincial Public Works Tier",
            'badge': "PROVINCIAL",
            'badge_col': (245, 205, 90),
            'category': "Province Level Public Works",
            'cost': "Funding Source: Pooled provincial municipal treasuries",
            'desc': [
                "Province-wide public works improve logistics, health, and transport",
                "corridors across all constituent cities in the province.",
                "Reduces regional trade delays and healthcare mortality."
            ],
            'stats': [
                ("Provincial Pooled Treasury", f"${prov_cash:,.0f}", (120, 240, 150)),
                ("Constituent Territories", f"{len(getattr(prov, 'tiles', []))} Cities" if prov else "1 City", TEXT),
            ],
            'icon': 'province',
            'btn_id': btn_id
        }

    if btn_id in ('tier_nation', 'tier_crown'):
        return {
            'title': "National Strategic Projects Tier",
            'badge': "SOVEREIGN",
            'badge_col': (240, 120, 120),
            'category': "Empire Level Strategic Works",
            'cost': "Funding Source: National sovereign treasury reserves",
            'desc': [
                "Grand strategic undertakings that transform national capabilities:",
                "alpine mountain passes, central mint monetary stabilization,",
                "and imperial military citadels for empire defense."
            ],
            'stats': [
                ("Sovereign Treasury Cash", f"${nat_cash:,.0f}", (120, 240, 150)),
                ("National Total Wealth", f"${tot_cash:,.0f}", ACCENT),
            ],
            'icon': 'crown',
            'btn_id': btn_id
        }

    if btn_id in ('tier_equalization', 'tier_scale'):
        return {
            'title': "Fiscal Equalization System",
            'badge': "HORIZONTAL EQUALIZATION",
            'badge_col': (245, 215, 110),
            'category': "Fiscal Federalism & Wealth Transfers",
            'cost': "Manual grant: $250 transfer from sovereign treasury to territory",
            'desc': [
                "Transfers capital grants from rich federal reserves directly into",
                "struggling local bank reserves and municipal treasuries.",
                "Prevents bankruptcies, relieves regional debt crises, and preserves",
                "national cohesion across developing frontier provinces."
            ],
            'stats': [
                ("Sovereign Treasury Cash", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 250 else RED),
                ("Target Tile Treasury", f"${tile_cash:,.0f}", (120, 240, 150)),
            ],
            'icon': 'scale',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # LEFT DOCK SWITCHER TABS
    # -------------------------------------------------------------------------
    dock_key = btn_id[5:] if btn_id.startswith('dock_') else btn_id
    dock_catalog = {
        'build': ("Build & Public Infrastructure (B)", "CONSTRUCTION", ACCENT, "Multi-tier civic construction menu for irrigation, mills, roads, and monuments.", "hammer"),
        'governance': ("Governance & Policy Decrees (G)", "PUBLIC ORDER", (245, 215, 110), "Interactive policy drawer for city tax cuts, famine relief, provincial equalizations, and national labor laws.", "policies"),
        'diplomacy': ("Diplomacy & Foreign Relations (D)", "STATECRAFT", (140, 190, 240), "Manage treaties, borders, alliances, trade embargoes, and sovereign claims.", "crown"),
        'debt': ("Sovereign Bonds & Central Banking (S)", "CREDIT & FISCAL", (130, 220, 150), "Issue sovereign debt securities, manage ISRB yield spreads, and regulate national central banking.", "bank"),
        'science': ("Science & Industrial Innovation (T)", "TECHNOLOGY", (190, 140, 245), "Track and reward breakthrough technologies across mechanization, agrarian tools, and corporate finance.", "rare_minerals"),
        'military': ("Military & Garrison Command (M)", "WARFARE", (240, 100, 100), "Review standing garrisons, field armies, expeditionary divisions, and recruitment levies.", "military")
    }
    if dock_key in dock_catalog:
        title, badge, b_col, desc, ico_name = dock_catalog[dock_key]
        return {
            'title': title,
            'badge': badge,
            'badge_col': b_col,
            'category': "Left Navigation Dock",
            'cost': "Hotkey: Click or press shortcut key to toggle drawer",
            'desc': [
                desc,
                "Click again or press the shortcut key to close the drawer and view the hex world."
            ],
            'stats': [
                ("Selected Tile", getattr(pinned, 'display_name', getattr(pinned, 'city_name', pinned.name)) if pinned else "None", TEXT),
            ],
            'icon': ico_name,
            'btn_id': btn_id
        }

    return None


def _infer_icon_for_btn(btn_id: str, tooltip: dict) -> str:
    """Infer procedural vector icon key for any button or mechanism."""
    if 'icon' in tooltip:
        return tooltip['icon']
    b = btn_id.lower()
    if b.startswith('build_'):
        rkey = b[6:]
        return {
            'farm': 'grain',
            'granary': 'granary',
            'sawmill': 'timber',
            'workshop': 'manufacturing',
            'paved_road': 'civil_engineering',
            'river_bridge': 'civil_engineering',
            'sanatorium': 'municipal',
            'mountain_pass': 'mountain',
            'central_mint': 'finance',
            'military_citadel': 'military',
        }.get(rkey, 'hammer')
    if 'tier_municipal' in b or 'municipal' in b:
        return 'municipal'
    if 'tier_province' in b or 'province' in b:
        return 'province'
    if 'tier_crown' in b or 'tier_nation' in b or 'crown' in b:
        return 'crown'
    if 'tier_equalization' in b or 'equalization' in b or 'grant' in b:
        return 'scale'
    if 'tax' in b or 'treasury' in b:
        return 'treasury'
    if 'tariff' in b or 'ex' in b:
        return 'ex'
    if 'ubi' in b:
        return 'pop'
    if 'food' in b or 'famine' in b or 'grain' in b:
        return 'grain'
    if 'farm' in b or 'crop' in b:
        return 'grain'
    if 'patrol' in b or 'curfew' in b or 'police' in b:
        return 'military'
    if 'garrison' in b or 'army' in b or 'mobilize' in b or 'war' in b:
        return 'military'
    if 'road' in b or 'route' in b or 'bridge' in b or 'highway' in b or 'transport' in b:
        return 'civil_engineering'
    if 'health' in b or 'sanatorium' in b or 'hospital' in b:
        return 'municipal'
    if 'frontier' in b or 'pioneer' in b or 'settler' in b:
        return 'pasture'
    if 'science' in b or 'innovation' in b or 'prize' in b or 'tech' in b:
        return 'rare_minerals'
    if 'ten_hour' in b or 'labor' in b or 'safety' in b:
        return 'policies'
    if 'entertainment' in b or 'spectacle' in b or 'theater' in b:
        return 'pop'
    if 'dock_build' in b or b == 'build':
        return 'hammer'
    if 'dock_gov' in b or b == 'governance':
        return 'policies'
    if 'dock_diplomacy' in b or b == 'diplomacy':
        return 'crown'
    if 'dock_debt' in b or b == 'debt':
        return 'bank'
    if 'dock_science' in b or b == 'science':
        return 'rare_minerals'
    if 'dock_military' in b or b == 'military':
        return 'military'
    return 'policies'


def get_button_tooltip_data(btn_id: str, world: dict, region=None, nation=None, province=None) -> dict | None:
    """Generate detailed mechanism description, achievement context, and live stat breakdown."""
    data = _build_button_tooltip_raw(btn_id, world, region=region, nation=nation, province=province)
    if data:
        data.setdefault('btn_id', btn_id)
        data['icon'] = _infer_icon_for_btn(btn_id, data)
    return data


def draw_left_panel_tooltip(surface, world: dict, font_small, mouse_pos=None):
    """Render sleek, dynamically-sized floating tooltip card for the currently hovered left-panel button."""
    tooltip = world.get('_hovered_left_tooltip')
    if not tooltip or not mouse_pos:
        return

    mx, my = mouse_pos
    title = tooltip.get('title', 'Mechanism')
    badge_txt = tooltip.get('badge', '')
    badge_col = tooltip.get('badge_col', ACCENT)
    category = tooltip.get('category', 'Decree')
    cost_str = tooltip.get('cost', '')
    desc_lines = tooltip.get('desc', [])
    stats = tooltip.get('stats', [])
    rect = tooltip.get('btn_rect', (mx, my, 20, 20))
    btn_id = tooltip.get('btn_id', '')
    icon_kind = tooltip.get('icon') or _infer_icon_for_btn(btn_id, tooltip)

    line_h = max(20, font_small.get_height() + 3)
    card_w = CARD_MAX_W
    usable_w = card_w - (PADDING_X * 2)

    # 1. Header Measurements
    icon_box_size = 40
    hx = PADDING_X + icon_box_size + 10

    badge_w = 0
    if badge_txt:
        b_surf = font_small.render(badge_txt, True, badge_col)
        badge_w = b_surf.get_width() + 14

    title_avail_w = usable_w - (icon_box_size + 10) - (badge_w + 8 if badge_w else 0)
    title_lines = wrap_text(title, font_small, title_avail_w)
    if not title_lines:
        title_lines = [title]

    header_h = max(icon_box_size, len(title_lines) * line_h + font_small.get_height() + 4)

    # 2. Cost Measurements
    cost_lines = wrap_text(cost_str, font_small, usable_w - 24) if cost_str else []
    cost_box_h = (len(cost_lines) * line_h + 10) if cost_lines else 0

    # 3. Description Lines
    wrapped_desc = []
    for raw_line in desc_lines:
        wrapped_desc.extend(wrap_text(raw_line, font_small, usable_w))

    # 4. Compute Card Height dynamically
    card_h = PADDING_Y + header_h + 8  # header + gap
    card_h += 1  # divider
    card_h += 8  # gap after divider
    if cost_lines:
        card_h += cost_box_h + 8  # cost box + gap
    card_h += len(wrapped_desc) * line_h + 4  # desc lines + gap
    if stats:
        card_h += 6  # gap
        card_h += 1  # stats divider
        card_h += 6  # gap
        card_h += line_h + 4  # stats section header
        card_h += len(stats) * (line_h + 5)  # stats rows
    card_h += PADDING_Y + 4

    # 5. Position to the right of the button, clamped to screen
    card_x = rect[0] + rect[2] + 12
    if card_x + card_w > WIDTH - 12:
        card_x = max(12, rect[0] - card_w - 12)

    card_y = max(TOP_BAR_H + 8, min(HEIGHT - TICKER_H - card_h - 10, rect[1] - 8))
    if card_y + card_h > HEIGHT - TICKER_H - 10:
        card_y = max(TOP_BAR_H + 8, HEIGHT - TICKER_H - card_h - 10)

    # 6. Render Card Background Surface
    card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
    card_surf.fill((16, 18, 28, 250))
    pygame.draw.rect(card_surf, (65, 78, 112), (0, 0, card_w, card_h), 1, border_radius=8)

    # 7. Render Header
    icon_box_rect = (PADDING_X, PADDING_Y, icon_box_size, icon_box_size)
    pygame.draw.rect(card_surf, (28, 34, 48), icon_box_rect, border_radius=6)
    pygame.draw.rect(card_surf, (68, 84, 122), icon_box_rect, 1, border_radius=6)
    ico_surf = get_icon(icon_kind, size=28)
    card_surf.blit(ico_surf, (PADDING_X + 6, PADDING_Y + 6))

    if badge_txt:
        bx = card_w - PADDING_X - badge_w
        by = PADDING_Y
        bh = max(20, font_small.get_height() + 3)
        pygame.draw.rect(card_surf, (35, 42, 60), (bx, by, badge_w, bh), border_radius=4)
        pygame.draw.rect(card_surf, badge_col, (bx, by, badge_w, bh), 1, border_radius=4)
        card_surf.blit(b_surf, (bx + 7, by + 1))

    ty = PADDING_Y
    for tl in title_lines:
        t_surf = font_small.render(tl, True, (255, 255, 255))
        card_surf.blit(t_surf, (hx, ty))
        ty += line_h

    cat_surf = font_small.render(category, True, (150, 165, 195))
    card_surf.blit(cat_surf, (hx, ty))

    div_y = PADDING_Y + header_h + 8
    pygame.draw.line(card_surf, (48, 56, 80), (PADDING_X, div_y), (card_w - PADDING_X, div_y), 1)

    cur_y = div_y + 8

    # 8. Render Cost Box
    if cost_lines:
        c_box_rect = (PADDING_X, cur_y, usable_w, cost_box_h)
        pygame.draw.rect(card_surf, (36, 32, 24), c_box_rect, border_radius=5)
        pygame.draw.rect(card_surf, (115, 95, 48), c_box_rect, 1, border_radius=5)

        cy = cur_y + 5
        for cl in cost_lines:
            c_surf = font_small.render(cl, True, (250, 215, 110))
            card_surf.blit(c_surf, (PADDING_X + 10, cy))
            cy += line_h

        cur_y += cost_box_h + 8

    # 9. Render Description Lines
    for dl in wrapped_desc:
        d_surf = font_small.render(dl, True, (215, 225, 240))
        card_surf.blit(d_surf, (PADDING_X, cur_y))
        cur_y += line_h

    # 10. Render Live Stats Breakdown
    if stats:
        cur_y += 6
        pygame.draw.line(card_surf, (44, 52, 75), (PADDING_X, cur_y), (card_w - PADDING_X, cur_y), 1)
        cur_y += 6

        stat_hdr = font_small.render("LIVE IMPACT & STATE BREAKDOWN:", True, (145, 165, 200))
        card_surf.blit(stat_hdr, (PADDING_X, cur_y))
        cur_y += line_h + 4

        for idx, (s_lbl, s_val, s_col) in enumerate(stats):
            row_rect = (PADDING_X, cur_y, usable_w, line_h + 3)
            row_bg = (24, 28, 42) if (idx % 2 == 0) else (18, 22, 34)
            pygame.draw.rect(card_surf, row_bg, row_rect, border_radius=3)

            lbl_surf = font_small.render(s_lbl, True, (190, 200, 215))
            val_surf = font_small.render(s_val, True, s_col)
            card_surf.blit(lbl_surf, (PADDING_X + 8, cur_y + 1))
            card_surf.blit(val_surf, (card_w - PADDING_X - val_surf.get_width() - 8, cur_y + 1))
            cur_y += line_h + 5

    surface.blit(card_surf, (card_x, card_y))
