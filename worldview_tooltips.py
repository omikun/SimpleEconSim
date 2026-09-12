"""worldview_tooltips.py — Comprehensive Tooltip System for Left Panel Mechanisms & Systems."""

from __future__ import annotations
import pygame
from worldview_camera import WIDTH, HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon

# Dimensions
CARD_MAX_W = 480
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
        res = {
            'title': "Municipal Tax Cut [-2%]",
            'badge': "DISPOSABLE CASH",
            'badge_col': (120, 240, 150),
            'category': "City Fiscal Decree",
            'cost': "Revenue Trade-off: Lowers ongoing income tax yield",
            'desc': [
                "Reduces municipal income tax by 2.0% (down to a statutory 2.0% floor). Leaves more disposable cash in citizen pockets, directly boosting local purchasing power for market food and consumer wares.",
                "Subdues civil discontent and lowers popular protest energy. Trade-off: Reduces city treasury revenue available for public grain reserves and civic infrastructure."
            ],
            'stats': [
                ("Current Tax Rate", f"{tax_rate*100:.1f}% -> {max(2.0, (tax_rate-0.02)*100):.1f}%", ACCENT),
                ("Municipal Treasury", f"${tile_cash:,.0f}", (120, 240, 150)),
                ("Protest Energy", f"{protest_e:.2f}", (240, 150, 70) if protest_e > 0.3 else GREEN),
                ("City Population", f"{pop_count} Citizens", TEXT),
            ]
        }
        if tax_rate <= 0.02:
            res['disabled_reason'] = "Statutory Tax Floor Reached: Municipal income tax cannot be lowered below 2.0%."
        return res

    if btn_id == 'city_tax_raise':
        res = {
            'title': "Municipal Tax Hike [+2%]",
            'badge': "TREASURY YIELD",
            'badge_col': (245, 180, 50),
            'category': "City Fiscal Decree",
            'cost': "Unrest Risk: Squeezes citizen living margins",
            'desc': [
                "Raises statutory municipal income tax by 2.0% (capped at 60.0%). Supplies the city treasury with crucial funds needed to maintain emergency food reserves, civic buildings, and police patrols.",
                "Trade-off: Depletes worker disposable income, aggravating poverty and escalating civil protest energy across the municipality."
            ],
            'stats': [
                ("Current Tax Rate", f"{tax_rate*100:.1f}% -> {min(60.0, (tax_rate+0.02)*100):.1f}%", ACCENT),
                ("Municipal Treasury", f"${tile_cash:,.0f}", (120, 240, 150)),
                ("Protest Energy", f"{protest_e:.2f}", (240, 150, 70) if protest_e > 0.3 else GREEN),
                ("Hungry Citizens", f"{hungry}", RED if hungry > 0 else GREEN),
            ]
        }
        if tax_rate >= 0.60:
            res['disabled_reason'] = "Statutory Tax Ceiling Reached: Municipal income tax cannot be raised above 60.0%."
        return res

    if btn_id in ('city_toggle_ubi', 'city_ubi'):
        ubi_on = getattr(gov, 'ubi_enabled', getattr(gov, 'ubi_active', False)) if gov else False
        cost_p_t = pop_count * 5.0
        total_10t = cost_p_t * 10.0
        return {
            'title': f"Universal Basic Income: {'Active' if ubi_on else 'Inactive'}",
            'badge': "ANTI-POVERTY" if not ubi_on else "ACTIVE MANDATE",
            'badge_col': GREEN if not ubi_on else ACCENT,
            'category': "Municipal Welfare Safety Net",
            'cost': f"Cost: ${total_10t:,.0f} for 10-turn period (${cost_p_t:,.0f}/t @ $5/cit)" if not ubi_on else "Click to repeal UBI",
            'desc': [
                "Disburses a guaranteed $5 cash stipend each turn to all registered residents, committed for a 10-turn policy duration.",
                "Eradicates extreme poverty, ensures every worker can afford market food, and stabilizes aggregate consumer demand.",
                "Money Destination: Disbursed directly from municipal treasury reserves into citizen personal cash wallets every turn. Citizens spend this basic income on local market food (grain) and consumer goods, circulating money back to farmers, merchants, and artisan workshops."
            ],
            'stats': [
                ("UBI Status", "ENABLED" if ubi_on else "DISABLED", GREEN if ubi_on else DIM),
                ("Eligible Population", f"{pop_count} Citizens", TEXT),
                ("Est. Cost Per Turn", f"${cost_p_t:,.0f}/t ($5/cit)", (245, 180, 50)),
                ("10-Turn Commitment", f"${total_10t:,.0f} Total", (245, 215, 110)),
                ("Treasury Reserves", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= total_10t else RED),
            ]
        }

    if btn_id in ('city_emergency_food', 'city_food_relief'):
        res = {
            'title': "Emergency Grain Relief ($50)",
            'badge': "FAMINE RESCUE",
            'badge_col': GREEN,
            'category': "Municipal Emergency Aid",
            'cost': "Cost: $50 from municipal treasury or city bank",
            'desc': [
                "Purchases and distributes 30 food rations directly to starving citizens. Instantly resets hunger counters to zero, halts malnutrition attrition, and quells imminent bread riots.",
                "Money Destination: Paid directly to local market grain merchants and warehouse suppliers to purchase 30 food rations, which are immediately distributed to malnourished citizens."
            ],
            'stats': [
                ("Hungry Citizens", f"{hungry} Starving", RED if hungry > 0 else GREEN),
                ("Rations Distributed", "30 Food Units", (120, 240, 150)),
                ("Treasury Cash", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= 50 else RED),
            ]
        }
        if tile_cash < 50.0:
            res['disabled_reason'] = f"Insufficient Municipal Treasury: Requires $50.00 (Current: ${tile_cash:,.0f})."
        return res

    if btn_id == 'city_farm_subsidy':
        fert = pinned.terrain.get('food', 1.0) if (pinned and hasattr(pinned, 'terrain')) else 1.0
        res = {
            'title': "Agricultural Development Subsidy ($100)",
            'badge': "FOOD PRODUCTION",
            'badge_col': (130, 210, 140),
            'category': "Municipal Economic Development",
            'cost': "Cost: $100 from municipal treasury",
            'desc': [
                "Disburses capital development grants directly to agricultural estates and grain growers, expanding farm employment and lowering baseline food prices.",
                "Insulates the municipality against regional crop failures and stabilizes urban grain markets.",
                "Money Destination: Paid as capital grants to local farming enterprises and agrarian landlords to purchase draught oxen, iron plows, fertilizer, and high-yield seed."
            ],
            'stats': [
                ("Farmland Fertility", f"{fert:.2f}x Baseline", (120, 240, 150)),
                ("Treasury Cash", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= 100 else RED),
            ]
        }
        if tile_cash < 100.0:
            res['disabled_reason'] = f"Insufficient Municipal Treasury: Requires $100.00 (Current: ${tile_cash:,.0f})."
        return res

    if btn_id in ('city_safety_patrol', 'city_police_curfew'):
        res = {
            'title': "Constabulary Patrol ($60)" if btn_id == 'city_safety_patrol' else "Police Curfew Decree",
            'badge': "PUBLIC ORDER",
            'badge_col': (240, 100, 100),
            'category': "Civil Security & Law Enforcement",
            'cost': "Cost: $60 police operational upkeep",
            'desc': [
                "Mobilizes armed constabulary patrols and enforces evening curfews across municipal districts. Instantly suppresses riots and reduces popular protest energy by 0.35 points.",
                "Trade-off: Builds long-term state grievance if underlying poverty or working condition demands are left unaddressed.",
                "Money Destination: Paid to municipal police constables and night watchmen as service wages, equipment allowances, and patrol provisions."
            ],
            'stats': [
                ("Current Protest Energy", f"{protest_e:.2f}", RED if protest_e > 0.4 else (240, 180, 50)),
                ("Treasury Cash", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= 60 else RED),
            ]
        }
        if btn_id == 'city_police_curfew':
            u_level = getattr(pinned, 'unrest_level', 0.0) if pinned else 0.0
            from popular_resistance import get_popular_resistance_manager
            r_st = get_popular_resistance_manager().get_state(pinned.name) if pinned else None
            is_active_revolt = r_st and r_st.enclosure_stage not in ('dormant', 'leveling')
            if u_level < 1.50 and protest_e < 0.40 and not is_active_revolt:
                res['disabled_reason'] = f"Civil Order Stable (Unrest {u_level:.2f} < 1.50): Curfew is restricted to active civil unrest, riots, or marching revolts."
        elif tile_cash < 60.0:
            res['disabled_reason'] = f"Insufficient Municipal Treasury: Requires $60.00 (Current: ${tile_cash:,.0f})."
        return res

    if btn_id == 'city_recruit_garrison':
        garrison = sum(u.soldiers for u in getattr(pinned, 'military_units', [])) if pinned else 0
        res = {
            'title': "Recruit 5 Garrison Soldiers ($50)",
            'badge': "MILITARY DEFENSE",
            'badge_col': (100, 180, 240),
            'category': "Military Recruitment",
            'cost': "Cost: $50 uniform & equipment levy",
            'desc': [
                "Musters 5 adult citizens into the permanent city garrison company, fortifying the territory against foreign assault and deterring insurgent uprisings.",
                "Money Destination: $50 is disbursed to local artisan armorers and munitions workshops for uniforms and flintlocks, with a portion paid as cash enlistment bonuses to new recruits."
            ],
            'stats': [
                ("Active Garrison", f"{garrison} Soldiers", ACCENT),
                ("Treasury Cash", f"${tile_cash:,.0f}", (120, 240, 150) if tile_cash >= 50 else RED),
            ]
        }
        if tile_cash < 50.0:
            res['disabled_reason'] = f"Insufficient Municipal Treasury: Requires $50.00 (Current: ${tile_cash:,.0f})."
        return res

    if btn_id == 'city_enclose_plot':
        tenure = getattr(pinned, 'tenure', None) if pinned else None
        feudal_pct = tenure.feudal_fraction * 100 if tenure else 0
        fee = 500.0
        if tenure and getattr(tenure, 'plots', None):
            from enclosure import calculate_charter_fee
            f_plot = next((p for p in tenure.plots if getattr(getattr(p, 'tenure', None), 'name', '') == 'FEUDAL'), None)
            if f_plot:
                fee = calculate_charter_fee(f_plot)
        res = {
            'title': "Enclose Common Land (Crown Charter)",
            'badge': "FEUDAL PRIVATIZATION",
            'badge_col': (230, 140, 70),
            'category': "Agrarian Land Tenure Reform",
            'cost': f"Charter Fee: Landlord pays ~${fee:.0f} to municipal treasury",
            'desc': [
                "Abolishes customary serf foraging rights on parcel, privatizing the commons into enclosed commercial estates under landlord tenure.",
                "Pleases the Gentry faction and yields crown charter revenues. Severe trade-off: Dispossesses commoners, turning serfs into rent-paying tenants or landless wage laborers and triggering long-term protest.",
                f"Money Destination: The private estate wealth of the acquiring aristocratic landlord pays this statutory ${fee:.0f} charter fee directly into the public city/crown treasury to gain legal property title."
            ],
            'stats': [
                ("Feudal Commons Remaining", f"{feudal_pct:.0f}%", (130, 210, 140)),
                ("Statutory Fee Inflow", f"+${fee:.0f} to Gov", GREEN),
            ]
        }
        if feudal_pct <= 0:
            res['disabled_reason'] = "No Feudal Commons Remaining: All agricultural plots are already enclosed into commercial estates."
        return res

    # -------------------------------------------------------------------------
    # PROVINCE SCOPE POLICIES
    # -------------------------------------------------------------------------
    if btn_id == 'prov_pave_highway':
        res = {
            'title': "Pave Regional Highway Corridor ($120)",
            'badge': "LOGISTICS ACCEL",
            'badge_col': (100, 200, 240),
            'category': "Provincial Infrastructure",
            'cost': "Cost: $120 from provincial treasury",
            'desc': [
                "Constructs macadamized highway connectors between provincial cities, permanently reducing logistics transport delays and road friction by 30%.",
                "Speeds commodity delivery and bridges price disparities across provincial consumer markets.",
                "Money Destination: Paid to provincial road civil engineering contractor corps and stone quarry teams to pave highway connectors."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150) if prov_cash >= 120 else RED),
                ("Territory Count", f"{len(getattr(prov, 'tiles', []))} Cities", TEXT),
            ]
        }
        if prov_cash < 120.0:
            res['disabled_reason'] = f"Insufficient Provincial Treasury: Requires $120.00 (Current: ${prov_cash:,.0f})."
        return res

    if btn_id == 'prov_healthcare':
        res = {
            'title': "Regional Health & Sanitation ($150)",
            'badge': "EPIDEMIC SHIELD",
            'badge_col': (240, 120, 140),
            'category': "Provincial Public Health",
            'cost': "Cost: $150 from provincial treasury",
            'desc': [
                "Establishes sanatoriums, clean artesian wells, and quarantine posts across all provincial territories.",
                "Reduces industrial health attrition from toxic factory shifts and cuts demographic mortality, protecting workforce longevity.",
                "Money Destination: Paid to municipal physicians, apothecary druggists, and sanitary well-diggers to install clean water systems and medical dispensaries."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150) if prov_cash >= 150 else RED),
            ]
        }
        if prov_cash < 150.0:
            res['disabled_reason'] = f"Insufficient Provincial Treasury: Requires $150.00 (Current: ${prov_cash:,.0f})."
        return res

    if btn_id == 'prov_equalization':
        res = {
            'title': "Provincial Fiscal Equalization ($200)",
            'badge': "BANK RECAPITALIZE",
            'badge_col': (245, 215, 110),
            'category': "Provincial Fiscal Transfers",
            'cost': "Cost: $200 grant from provincial treasury",
            'desc': [
                "Transfers a capital grant to the poorest municipal bank in the province, preventing insolvency and credit freezes.",
                "Restores private commercial lending and business investments in struggling towns, maintaining balanced regional growth.",
                "Money Destination: Transferred directly from the provincial treasury as a recapitalization grant into the vault of the poorest municipal bank in the province."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150) if prov_cash >= 200 else RED),
            ]
        }
        if prov_cash < 200.0:
            res['disabled_reason'] = f"Insufficient Provincial Treasury: Requires $200.00 (Current: ${prov_cash:,.0f})."
        return res

    if btn_id == 'prov_harmonize_taxes':
        return {
            'title': "Harmonize Provincial Taxes",
            'badge': "FISCAL UNIFICATION",
            'badge_col': ACCENT,
            'category': "Provincial Governance",
            'cost': "Cost: Free (Regulatory Alignment)",
            'desc': [
                "Calculates the weighted average tax rate across all member cities and enforces it uniformly throughout the province.",
                "Eliminates internal tax havens and harmful fiscal arbitrage between neighboring municipal jurisdictions."
            ],
            'stats': [
                ("Member Territories", f"{len(getattr(prov, 'tiles', []))}", TEXT),
            ]
        }

    if btn_id == 'prov_standardize_routes':
        return {
            'title': "Standardize Transport Routes ($100)",
            'badge': "TRADE INTEGRATION",
            'badge_col': (130, 210, 140),
            'category': "Provincial Logistics",
            'cost': "Cost: $100 administrative accord from provincial treasury",
            'desc': [
                "Harmonizes regional toll charges, wagon axle standards, and river navigation rules to streamline inter-city freight traffic."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150)),
            ]
        }

    if btn_id == 'prov_soil_conservation':
        res = {
            'title': "Fund Soil Conservation Program ($150)",
            'badge': "ECOLOGY GRANT",
            'badge_col': (140, 230, 170),
            'category': "Provincial Agriculture & Ecology",
            'cost': "Cost: $150 from provincial treasury",
            'desc': [
                "Enacts contour plowing, windbreak planting, and cover-cropping incentives across provincial agricultural land.",
                "Halts topsoil erosion, restores degraded silt reserves, and boosts long-term soil moisture and fertility.",
                "Money Destination: Disbursed to regional farming syndicates and soil conservators for tree seedlings, terracing stone, and restorative legumes."
            ],
            'stats': [
                ("Provincial Treasury", f"${prov_cash:,.0f}", (120, 240, 150) if prov_cash >= 150 else RED),
            ]
        }
        if prov_cash < 150.0:
            res['disabled_reason'] = f"Insufficient Provincial Treasury: Requires $150.00 (Current: ${prov_cash:,.0f})."
        return res

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
                f"Decrees a statutory {rate}% income tax across all nation's cities.",
                "Overrides disparate local rates to centralize state revenues for national defense, scientific research, and sovereign projects."
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
                "Orders every municipal government to establish guaranteed basic income for all citizens, committed across a 10-turn policy period.",
                "Eradicates famine and destitute poverty nationwide, boosting consumer demand across all domestic markets."
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
                "Open borders welcome foreign immigrants into underpopulated cities to staff industrial factories, mills, and frontier homesteads.",
                "Closed borders protect domestic wages and minimize cultural strain."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150)),
            ]
        }

    if btn_id == 'nat_science_prize':
        res = {
            'title': "Royal Innovation Prize Bounty ($300)",
            'badge': "TECH BREAKTHROUGH",
            'badge_col': (180, 140, 240),
            'category': "National Science & Research",
            'cost': "Cost: $300 prize bounty from sovereign treasury",
            'desc': [
                "Funds national research grants and rewards technological discovery in bottleneck domains, accelerating domestic productivity growth.",
                "Money Destination: Awarded as a royal bounty to academic universities, inventors, and guild researchers who achieve technological breakthroughs."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 300 else RED),
            ]
        }
        if nat_cash < 300.0:
            res['disabled_reason'] = f"Insufficient Sovereign Treasury: Requires $300.00 (Current: ${nat_cash:,.0f})."
        return res

    if btn_id == 'nat_mobilize_army':
        res = {
            'title': "Mobilize Standing Army ($150)",
            'badge': "EXPEDITIONARY FORCE",
            'badge_col': (235, 90, 90),
            'category': "Sovereign Defense Command",
            'cost': "Cost: $150 mobilization & armaments levy",
            'desc': [
                "Levies and equips an elite national army division under direct sovereign command, capable of maneuvering across the hex world.",
                "Money Destination: Paid to military foundries, ordnance contractors, and standing soldier enlistment bounties."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 150 else RED),
            ]
        }
        if nat_cash < 150.0:
            res['disabled_reason'] = f"Insufficient Sovereign Treasury: Requires $150.00 (Current: ${nat_cash:,.0f})."
        return res

    if btn_id == 'nat_sovereign_grant':
        res = {
            'title': "Sovereign Development Grant ($250)",
            'badge': "NATIONAL COHESION",
            'badge_col': (245, 215, 110),
            'category': "Sovereign Fiscal Equalization",
            'cost': "Cost: $250 grant from sovereign treasury",
            'desc': [
                "Disburses crown wealth to impoverished provincial treasuries, bolstering national creditworthiness and reducing regional inequality.",
                "Money Destination: Transferred from national sovereign treasury directly into underdeveloped provincial and municipal city treasuries."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 250 else RED),
            ]
        }
        if nat_cash < 250.0:
            res['disabled_reason'] = f"Insufficient Sovereign Treasury: Requires $250.00 (Current: ${nat_cash:,.0f})."
        return res

    if btn_id == 'nat_ten_hour_act':
        has_ten = getattr(owner, 'ten_hour_act', False) if owner else False
        res = {
            'title': "The Ten-Hour Act (Statutory Workday Cap)",
            'badge': "PRO-LABOR MANDATE" if not has_ten else "LAW ENFORCED",
            'badge_col': GREEN if not has_ten else ACCENT,
            'category': "National Labor Legislation",
            'cost': "Political Risk: Alienates capitalists & prompts electoral backlash",
            'desc': [
                "Legally caps factory and mill shifts to a maximum of 10.0 hours/day. Corporations cannot voluntarily reduce shift hours under competition; only statutory law forces shift reductions.",
                "Dramatically reduces worker health attrition and quells strike uprisings.",
                "Trade-off: Squeezes surplus value, enraging capitalists who pool PAC warchests to finance opposition candidates and oust the regime."
            ],
            'stats': [
                ("Workday Cap", "10.0h" if has_ten else "16.0h -> 10.0h", GREEN),
                ("Current Status", "ENACTED" if has_ten else "PENDING DECREE", ACCENT if not has_ten else GREEN),
            ]
        }
        if has_ten:
            res['disabled_reason'] = "Statute Already Enacted: The Ten-Hour Workday Act has already been codified into sovereign law."
        return res

    if btn_id == 'nat_safety_mandate':
        has_safe = getattr(owner, 'factory_safety_act', False) if owner else False
        res = {
            'title': "Factory Safety Standards Mandate",
            'badge': "WORKPLACE GUARDS" if not has_safe else "LAW ENFORCED",
            'badge_col': GREEN if not has_safe else ACCENT,
            'category': "National Workplace Safety Law",
            'cost': "Industrial Burden: Requires machinery guards and safety investment",
            'desc': [
                "Mandates protective gear, machinery shields, and fire exits in all industrial mills and factories.",
                "Reduces disabling factory casualties, mangled limbs, and workplace mortality by over 70%, putting an end to Luddite machine sabotage."
            ],
            'stats': [
                ("Safety Regulation", "MANDATED" if has_safe else "UNREGULATED", GREEN if has_safe else RED),
            ]
        }
        if has_safe:
            res['disabled_reason'] = "Statute Already Enacted: The Factory Safety Mandate has already been codified into sovereign law."
        return res

    if btn_id == 'nat_truck_act':
        has_truck = getattr(owner, 'truck_act_enacted', False) if owner else False
        res = {
            'title': "Anti-Truck Act (Abolish Company Scrip)",
            'badge': "ABOLISH PEONAGE" if not has_truck else "LAW ENFORCED",
            'badge_col': GREEN if not has_truck else ACCENT,
            'category': "National Labor Legislation",
            'cost': "Bourgeois Backlash: -10 Faction Support | Capital Squeeze",
            'desc': [
                "Prohibits corporations and industrial masters from paying wages in private company scrip or forcing patronage of monopolistic company stores ('Tommy Shops').",
                "Statute legally forces all employee compensation to be disbursed strictly in sovereign legal tender coin/cash.",
                "Instantly discharges and cancels all accumulated company debt peonage balances accrued by workers at company stores.",
                "Historical Precedent: British Truck Acts of 1831 & 1887 and US coal town Anti-Company Store legislation.",
                "Political Effect: Substantially increases Labor and Peasant faction loyalty (+15), while alienating the Bourgeoisie (-10)."
            ],
            'stats': [
                ("Mandatory Currency", "Legal Tender (Cash)" if has_truck else "Scrip Permitted", GREEN if has_truck else (240, 140, 80)),
                ("Tommy Shop Monopoly", "OUTLAWED" if has_truck else "+35% Markup Active", GREEN if has_truck else RED),
                ("Current Status", "ENACTED" if has_truck else "PENDING STATUTE", ACCENT if not has_truck else GREEN),
            ]
        }
        if has_truck:
            res['disabled_reason'] = "Statute Already Enacted: The Anti-Truck Act is already codified into sovereign law; all wages must be paid in legal tender."
        return res

    if btn_id == 'nat_subsidize_entertainment':
        res = {
            'title': "Subsidize Mass Spectacle & Amusements ($50)",
            'badge': "POPULAR PACIFIER",
            'badge_col': (70, 195, 235),
            'category': "Social Control & Pacification",
            'cost': "Cost: $50 public spectacle subsidy from treasury",
            'desc': [
                "Subsidizes commercial music halls, theater, saloons, and public games.",
                "Mass entertainment acts as an isolation pacifier: dampens worker rebellion energy, lowers class consciousness, and prevents strike organizing.",
                "Money Destination: Paid to saloonkeepers, theater troupes, music hall owners, and spectacle impresarios to stage mass public amusements."
            ],
            'stats': [
                ("Sovereign Treasury", f"${nat_cash:,.0f}", (120, 240, 150) if nat_cash >= 50 else RED),
            ]
        }
        if nat_cash < 50.0:
            res['disabled_reason'] = f"Insufficient Sovereign Treasury: Requires $50.00 (Current: ${nat_cash:,.0f})."
        return res

    if btn_id == 'nat_restore_commons':
        res = {
            'title': "Restore Ancestral Commons",
            'badge': "AGRARIAN REFORM",
            'badge_col': (120, 220, 140),
            'category': "Land Tenure & Common Usufruct",
            'cost': "Gentry Opposition: Alienates landlords while calming peasant unrest",
            'desc': [
                "De-encloses 1 privatized plot, restoring customary foraging and gleaning access to customary commons (TenureStatus.COMMONS).",
                "Reverses peasant dispossession, allows hungry landless serfs to forage wild food, and lowers dangerous rural insurrection fever.",
                "Trade-off: Gentry landlords lose cash rent rights on the de-enclosed parcel."
            ],
            'stats': [
                ("Peasant Unrest", f"-0.30 Unrest Drop", GREEN),
                ("Legitimacy Bonus", f"+0.08 Consent Drift", (120, 220, 140)),
            ]
        }
        from land_tenure import TenureStatus
        any_enclosed = False
        if owner and hasattr(owner, 'tiles'):
            for t in owner.tiles:
                tenure = getattr(t, 'tenure', None)
                if tenure and hasattr(tenure, 'plots'):
                    if any(getattr(p, 'tenure', None) == TenureStatus.ENCLOSED for p in tenure.plots):
                        any_enclosed = True
                        break
        if not any_enclosed:
            res['disabled_reason'] = "All Agricultural Plots Already Commons: No enclosed parcels remain within sovereign territory to restore."
        return res

    if btn_id == 'nat_martial_law':
        res = {
            'title': "Declare Martial Law & Bust Unions",
            'badge': "STATE COERCION",
            'badge_col': (240, 80, 80),
            'category': "Counter-Insurgency & Repression",
            'cost': "Repression Memory: -0.10 Legitimacy and accrues long-term public trauma",
            'desc': [
                "Mobilizes state bayonets and gendarmes to dismantle worker barricades and forcibly break regional general strikes.",
                "Restores factory production and clears transport routes immediately.",
                "Warning: Writes severe broken promises and casualty memories, causing future grievances to explode in the next political cycle."
            ],
            'stats': [
                ("Direct Effect", "Clears all barricades & general strikes", (240, 100, 100)),
                ("Legitimacy Hit", "-0.10 Consent Drop", RED),
            ]
        }
        active_units = [u for u in getattr(owner, 'military_units', []) if getattr(u, 'soldiers', 0) > 0] if owner else []
        if not active_units:
            res['disabled_reason'] = "Military Force Required: Nation has no active standing military units to enforce martial law and clear barricades."
        return res

    if btn_id == 'nat_recapitalize_banks':
        from banking_policy import get_banking_system_health
        b_health = get_banking_system_health(owner)
        is_frz = b_health['is_system_frozen']
        recap_cost = b_health['recapitalization_cost']
        res = {
            'title': "Recapitalize Domestic Commercial Banks",
            'badge': "TIER-1 BAILOUT" if is_frz else "BANKS SOLVENT",
            'badge_col': (120, 240, 150) if is_frz else (70, 195, 235),
            'category': "National Banking Resolution",
            'cost': f"Fiscal Transfer: ${recap_cost:,.0f} injected from sovereign treasury into bank capital",
            'desc': [
                "Injects liquid sovereign treasury funds into domestic commercial banks to restore Tier-1 capital reserves.",
                "Immediately terminates the emergency Corralito deposit freeze, restoring citizen withdrawal rights and reopening the commercial lending window for businesses.",
                "Strictly Conserved: Funds move 1-for-1 from sovereign treasury into bank capital reserves.",
                "Historical Precedent: Panic of London (1825), British Bank Charter Act suspensions (1847/1857), and the 2008 Emergency Economic Stabilization Act (TARP)."
            ],
            'stats': [
                ("System Status", "EMERGENCY FREEZE" if is_frz else "SOLVENT (Tier-1 OK)", RED if is_frz else GREEN),
                ("Total Bank Capital", f"${b_health['total_capital']:,.0f}", (120, 240, 150) if b_health['total_capital'] > 0 else RED),
                ("Recapitalization Cost", f"${recap_cost:,.0f}", (245, 180, 50)),
                ("Sovereign Treasury", f"${nat_cash:,.0f}", GREEN if nat_cash >= recap_cost else RED),
            ]
        }
        if not is_frz:
            res['disabled_reason'] = "Banks Already Solvent: All domestic commercial banks maintain healthy Tier-1 capital; bailout unneeded."
        elif nat_cash < recap_cost:
            res['disabled_reason'] = f"Insufficient Sovereign Treasury: Requires ${recap_cost:,.0f} to recapitalize banks (Current: ${nat_cash:,.0f})."
        return res

    if btn_id == 'nat_deposit_haircut':
        from banking_policy import get_banking_system_health
        b_health = get_banking_system_health(owner)
        is_frz = b_health['is_system_frozen']
        res = {
            'title': "Enact Depositor Bail-In Haircut (25%)",
            'badge': "CYPRUS RESOLUTION" if is_frz else "BANKS SOLVENT",
            'badge_col': (245, 180, 50) if is_frz else (70, 195, 235),
            'category': "Emergency Banking Resolution",
            'cost': "Elite Outrage: -25 Bourgeoisie & Lords Loyalty | -0.15 Legitimacy",
            'desc': [
                "Mandates a statutory 25% haircut on private deposit balances exceeding $50.0 across all insolvent banks.",
                "Expropriates private deposit liabilities and converts them directly into Tier-1 bank shareholder equity, restoring solvency without spending public treasury cash.",
                "Immediately ends the Corralito deposit freeze, allowing regular transactions and business borrowing to resume.",
                "Historical Precedent: Cyprus Banking Resolution of March 2013 (Laiki Bank resolution and Bank of Cyprus bail-in).",
                "Severe Backlash: Alienates wealthy depositors, triggering deep elite and capitalist fury (-25 loyalty)."
            ],
            'stats': [
                ("Resolution Mechanism", "Statutory Depositor Bail-In", (245, 180, 50)),
                ("Haircut Rate", "25% on balances > $50.0", RED),
                ("Treasury Fiscal Cost", "$0.00 (Self-Funded)", GREEN),
                ("System Status", "EMERGENCY FREEZE" if is_frz else "SOLVENT", RED if is_frz else GREEN),
            ]
        }
        if not is_frz:
            res['disabled_reason'] = "Banks Already Solvent: No domestic commercial banks are currently insolvent or frozen; bail-in resolution not permitted."
        return res

    # -------------------------------------------------------------------------
    # FRONTIER WILDERNESS POLICIES
    # -------------------------------------------------------------------------
    if btn_id == 'frontier_expedition':
        res = {
            'title': "Sponsor Frontier Pioneer Expedition",
            'badge': "TERRITORIAL EXPANSION",
            'badge_col': GREEN,
            'category': "Wilderness Colonization",
            'cost': "Cost: Outfits 5 homesteaders with tools and grain rations ($100)",
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
        if tile_cash < 100.0 and nat_cash < 100.0:
            res['disabled_reason'] = f"Insufficient Treasury: Requires $100.00 (Available: ${max(tile_cash, nat_cash):,.0f})."
        return res

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

        tier_cash = tile_cash if recipe.tier == 'tile' else (prov_cash if recipe.tier == 'province' else nat_cash)

        recipe_icons = {
            'farm': 'grain',
            'granary': 'granary',
            'sawmill': 'timber',
            'workshop': 'manufacturing',
            'paved_road': 'civil_engineering',
            'river_bridge': 'civil_engineering',
            'sanatorium': 'health',
            'mountain_pass': 'mountain',
            'central_mint': 'finance',
            'military_citadel': 'military',
            'trunk_sewer': 'civil_engineering',
            'smoke_scrubber': 'factory',
            'soil_conservation_reserve': 'farm',
            'municipal_clinic': 'health',
            'water_filtration_plant': 'civil_engineering',
        }

        res = {
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
        if is_built:
            res['disabled_reason'] = "Structure Already Installed: Capital asset is already operating on this territory."
        elif active_proj is not None:
            pct = active_proj.turns_elapsed / max(1, active_proj.total_turns)
            res['disabled_reason'] = f"Under Active Construction: Project is {int(pct*100)}% complete ({active_proj.turns_elapsed}/{active_proj.total_turns} turns)."
        elif tier_cash < recipe.cost:
            res['disabled_reason'] = f"Insufficient {tier_str} Treasury: Requires ${recipe.cost:,.0f} (Available: ${tier_cash:,.0f})."
        return res

    # -------------------------------------------------------------------------
    # BUILD SUBCATEGORY SWITCHERS
    # -------------------------------------------------------------------------
    if btn_id == 'build_subcat_industry':
        return {
            'title': "Build Category: Industry & State Works",
            'badge': "CIVIC & MILITARY",
            'badge_col': ACCENT,
            'category': "Infrastructure Catalog",
            'cost': "Click to inspect industrial, logistical, and state infrastructure",
            'desc': [
                "Blueprints for commodity processing, transport corridors, and sovereign defenses:",
                "farms, granaries, sawmills, artisan workshops, regional highways, river bridges,",
                "alpine mountain passes, central mints, and military citadels."
            ],
            'stats': [
                ("Catalog Focus", "Production, Transport & Defense", ACCENT),
                ("Municipal Treasury", f"${tile_cash:,.0f}", (120, 240, 150)),
            ],
            'icon': 'hammer',
            'btn_id': btn_id
        }

    if btn_id == 'build_subcat_ecology':
        return {
            'title': "Build Category: Ecology & Sanitation",
            'badge': "METABOLIC RIFT & HEALTH",
            'badge_col': (120, 220, 140),
            'category': "Infrastructure Catalog",
            'cost': "Click to inspect environmental remediation and public health works",
            'desc': [
                "Blueprints for metabolic rift repair, pollution abatement, and epidemic healthcare:",
                "brick trunk sewers, industrial wet smoke scrubbers, soil conservation reserves,",
                "municipal clinics, water filtration plants, and regional sanatoriums."
            ],
            'stats': [
                ("Catalog Focus", "Sanitation, Soil Restoration & Clinics", (120, 220, 140)),
                ("Municipal Treasury", f"${tile_cash:,.0f}", (120, 240, 150)),
            ],
            'icon': 'health',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # TIER HEADER OVERVIEWS
    # -------------------------------------------------------------------------
    if btn_id in ('tier_municipal', 'tier_tile', 'tier_city'):
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

    if btn_id in ('tier_province', 'tier_prov'):
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

    if btn_id in ('tier_nation', 'tier_crown', 'tier_national', 'tier_state'):
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

    if btn_id in ('tier_frontier', 'tier_camp', 'tier_wilderness'):
        hs_count = sum(1 for a in (pinned.agents if pinned else []) if getattr(a, 'is_homesteader', False))
        return {
            'title': "Frontier Wilderness Territory",
            'badge': "COLONIAL HOMESTEADING",
            'badge_col': (245, 180, 50),
            'category': "Territorial Expansion",
            'cost': "Frontier settlement scope for unannexed wilderness tiles",
            'desc': [
                "Frontier wilderness tiles are rich in pristine natural resources but lack established municipal institutions.",
                "Sponsor pioneer expeditions and homesteading families to build majority settlement presence (50%+ population).",
                "Once majority is attained, the tile can be formally incorporated into your sovereign national territory."
            ],
            'stats': [
                ("Homesteader Population", f"{hs_count} Settlers", GREEN if hs_count > 0 else DIM),
                ("Incorporation Goal", "50%+ Settler Majority", ACCENT),
            ],
            'icon': 'camp',
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

    # -------------------------------------------------------------------------
    # SCIENCE, DIPLOMACY, DEBT & MILITARY EXTENDED TOOLTIPS
    # -------------------------------------------------------------------------
    from worldview_tooltips_extra import (
        build_science_resource_tooltip,
        build_science_tech_tooltip,
        build_diplomacy_tooltip,
        build_debt_tooltip,
        build_military_tooltip
    )
    if btn_id.startswith('res_'):
        res_tip = build_science_resource_tooltip(btn_id, world, nation=owner)
        if res_tip:
            return res_tip

    if btn_id.startswith('sci_') or btn_id.startswith('tech_'):
        sci_tip = build_science_tech_tooltip(btn_id, world, nation=owner)
        if sci_tip:
            return sci_tip

    if btn_id.startswith('dip_'):
        dip_tip = build_diplomacy_tooltip(btn_id, world, nation=owner)
        if dip_tip:
            return dip_tip

    if btn_id.startswith('debt_'):
        debt_tip = build_debt_tooltip(btn_id, world, nation=owner)
        if debt_tip:
            return debt_tip

    if btn_id.startswith('mil_'):
        mil_tip = build_military_tooltip(btn_id, world, region=pinned, nation=owner)
        if mil_tip:
            return mil_tip

    from worldview_tooltips_ecology import build_ecology_tooltip
    eco_tip = build_ecology_tooltip(btn_id, world, region=pinned, nation=owner, province=prov)
    if eco_tip:
        return eco_tip

    from worldview_tooltips_visualizations import build_visualization_tooltip
    vis_tip = build_visualization_tooltip(btn_id, world, region=pinned, nation=owner, province=prov)
    if vis_tip:
        return vis_tip

    from worldview_tooltips_charts import (
        build_sidebar_chart_tooltip,
        build_citizen_tooltip,
        build_labor_tooltip,
        build_compare_tooltip
    )
    if btn_id.startswith('chart_'):
        tip = build_sidebar_chart_tooltip(btn_id, world, region=pinned, nation=owner)
        if tip:
            return tip

    if btn_id.startswith('citizen_') or btn_id in ('tab_charts', 'tab_citizens'):
        tip = build_citizen_tooltip(btn_id, world, region=pinned, nation=owner)
        if tip:
            return tip

    if btn_id.startswith('labor_'):
        tip = build_labor_tooltip(btn_id, world, region=pinned, nation=owner)
        if tip:
            return tip

    if btn_id.startswith('compare_'):
        tip = build_compare_tooltip(btn_id, world)
        if tip:
            return tip

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
            'trunk_sewer': 'civil_engineering',
            'smoke_scrubber': 'manufacturing',
            'soil_conservation_reserve': 'grain',
            'water_filtration_plant': 'municipal',
        }.get(rkey, 'hammer')
    if b.startswith('res_'):
        return b[4:]
    KEYWORD_ICONS = [
        (('tier_municipal', 'municipal', 'health', 'sanatorium', 'hospital'), 'municipal'),
        (('tier_province', 'province'), 'province'),
        (('tier_crown', 'tier_nation', 'crown', 'dock_diplomacy', 'diplomacy'), 'crown'),
        (('tier_equalization', 'equalization', 'grant'), 'scale'),
        (('tax', 'treasury'), 'treasury'),
        (('tariff', 'ex'), 'ex'),
        (('ubi', 'entertainment', 'spectacle', 'theater', 'pop'), 'pop'),
        (('food', 'famine', 'grain', 'farm', 'crop'), 'grain'),
        (('patrol', 'curfew', 'police', 'garrison', 'army', 'mobilize', 'war', 'military'), 'military'),
        (('road', 'route', 'bridge', 'highway', 'transport'), 'civil_engineering'),
        (('frontier', 'pioneer', 'settler'), 'pasture'),
        (('science', 'innovation', 'prize', 'tech', 'dock_science'), 'rare_minerals'),
        (('ten_hour', 'labor', 'safety', 'dock_gov', 'governance'), 'policies'),
        (('dock_build', 'build'), 'hammer'),
        (('dock_debt', 'debt', 'bank'), 'bank'),
    ]
    for keywords, icon_name in KEYWORD_ICONS:
        if any(k in b for k in keywords):
            return icon_name
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
    if not world.get('_hovered_left_tooltip') and mouse_pos:
        try:
            from ui_targets import resolve_hover_tooltip
            resolve_hover_tooltip(world, mouse_pos)
        except Exception:
            pass
    raw_tip = world.get('_hovered_left_tooltip')
    if not raw_tip or not mouse_pos:
        return

    rect_override, tooltip = None, raw_tip
    if isinstance(raw_tip, (tuple, list)):
        if len(raw_tip) >= 2 and isinstance(raw_tip[1], dict):
            rect_override, tooltip = raw_tip[0], raw_tip[1]
        elif len(raw_tip) >= 1 and isinstance(raw_tip[0], dict):
            tooltip = raw_tip[0]
        else:
            return
    elif not isinstance(raw_tip, dict):
        return

    mx, my = mouse_pos
    title = tooltip.get('title', 'Mechanism')
    badge_txt = tooltip.get('badge', '')
    badge_col = tooltip.get('badge_col', ACCENT)
    category = tooltip.get('category', 'Decree')
    cost_str = tooltip.get('cost', '')
    desc_lines = tooltip.get('desc', [])
    stats = tooltip.get('stats', [])
    rect = rect_override if rect_override else tooltip.get('btn_rect', (mx, my, 20, 20))
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

    # 2. Cost & Disabled Reason Measurements
    disabled_reason = tooltip.get('disabled_reason')
    disabled_lines = wrap_text(f"⚠️ CANNOT ENACT: {disabled_reason}", font_small, usable_w - 24) if disabled_reason else []
    disabled_box_h = (len(disabled_lines) * line_h + 10) if disabled_lines else 0

    cost_lines = wrap_text(cost_str, font_small, usable_w - 24) if cost_str else []
    cost_box_h = (len(cost_lines) * line_h + 10) if cost_lines else 0

    # 3. Description Lines (Grouped by Paragraph with soft wraps)
    wrapped_paras: list[list[str]] = []
    total_desc_lines_count = 0
    for raw_line in desc_lines:
        lines = wrap_text(raw_line, font_small, usable_w)
        if lines:
            wrapped_paras.append(lines)
            total_desc_lines_count += len(lines)

    para_gap = 5

    # 4. Compute Card Height dynamically
    card_h = PADDING_Y + header_h + 8  # header + gap
    card_h += 1  # divider
    card_h += 8  # gap after divider
    if disabled_lines:
        card_h += disabled_box_h + 8  # disabled alert box + gap
    if cost_lines:
        card_h += cost_box_h + 8  # cost box + gap
    card_h += total_desc_lines_count * line_h + max(0, len(wrapped_paras) - 1) * para_gap + 4
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

    # 7.5. Render Disabled Reason Alert Box
    if disabled_lines:
        d_box_rect = (PADDING_X, cur_y, usable_w, disabled_box_h)
        pygame.draw.rect(card_surf, (54, 18, 24), d_box_rect, border_radius=5)
        pygame.draw.rect(card_surf, (225, 75, 75), d_box_rect, 1, border_radius=5)

        dy = cur_y + 5
        for dl in disabled_lines:
            d_surf = font_small.render(dl, True, (255, 185, 185))
            card_surf.blit(d_surf, (PADDING_X + 10, dy))
            dy += line_h

        cur_y += disabled_box_h + 8

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

    # 9. Render Description Lines (Paragraphs with spacing)
    for p_idx, para_lines in enumerate(wrapped_paras):
        for dl in para_lines:
            d_surf = font_small.render(dl, True, (215, 225, 240))
            card_surf.blit(d_surf, (PADDING_X, cur_y))
            cur_y += line_h
        if p_idx < len(wrapped_paras) - 1:
            cur_y += para_gap

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
