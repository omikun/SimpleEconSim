"""
worldview_tooltips_extra.py — Extended Tooltip Providers for Science, Diplomacy, Debt & Military Panels.

Provides detailed mechanism explanations, economic/political achievements, costs, live statistics,
and explicit Money Destinations for:
- Strategic natural resources (arable silt, timber, iron, coal, pasture, petroleum, rare minerals)
- Science eras and technology innovation cards (with bottleneck pressure and domain XP)
- Sovereign bond debt, ISRB credit rating lobbying, audit attacks, board seats, and duration tabs
- Bilateral diplomacy decrees (Trade Pacts, Non-Aggression Pacts, Defensive Alliances, War/Peace, Foreign Aid)
- Military mobilization and standing division recruitment
"""

from __future__ import annotations
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from tile_resources import TileResource, RESOURCE_META, get_nation_resources
from innovation import get_innovation_system, TECH_CATALOG, TechDomain
from diplomacy import get_diplomacy, TreatyType
from sovereign_bonds import get_bond_market


# =============================================================================
# 1. SCIENCE & STRATEGIC NATURAL RESOURCES
# =============================================================================

def build_science_resource_tooltip(btn_id: str, world: dict, nation=None) -> dict | None:
    """Tooltip for strategic natural resource ribbon in the science drawer."""
    res_key = btn_id[4:] if btn_id.startswith('res_') else btn_id
    try:
        r_enum = TileResource(res_key)
    except ValueError:
        return None

    r_meta = RESOURCE_META.get(r_enum)
    if not r_meta:
        return None

    accessible = get_nation_resources(nation, world=world) if nation else set()
    has_res = r_enum in accessible

    # Territory occurrences
    t_count = 0
    if nation and hasattr(nation, 'tiles'):
        t_count = sum(1 for t in nation.tiles if r_enum in getattr(t, 'resources', []))

    role_details = {
        TileResource.ARABLE_SILT: (
            "Alluvial river silt and nutrient-rich soil. Multiplies baseline farm crop yields and "
            "insulates urban centers from winter famine. Required to research advanced four-field crop rotation."
        ),
        TileResource.TIMBER: (
            "Old-growth hardwood forests. Supplies timber for buildings, river gristmills, charcoal "
            "metallurgy, and caravel shipping fleets. Required for watermill automation and deep navigation."
        ),
        TileResource.IRON_ORE: (
            "Mountain hematite and magnetite veins. Foundational input for cast iron implements, artisan tools, "
            "heavy weaponry, and railroad construction. Required for bloomery smelting and siege artillery."
        ),
        TileResource.COAL_SEAM: (
            "Sub-surface bituminous and anthracite deposits. Generates intense thermal energy for coking blast "
            "furnaces and high-pressure steam boilers. Required for the Industrial Revolution and Watt steam engines."
        ),
        TileResource.PASTURE_FLAX: (
            "High grasslands and fertile flax basins. Produces raw wool fleece and flax fibers for domestic "
            "textile mills, sailcloth, and consumer clothing. Required for mechanical flying shuttles."
        ),
        TileResource.CRUDE_PETROLEUM: (
            "Subsurface sedimentary hydrocarbon basins. Refined into petroleum, kerosene, lubricants, and synthetic "
            "petrochemicals. Essential for internal combustion engines and modern transport mechanization."
        ),
        TileResource.RARE_MINERALS: (
            "Highland quartz, copper lodes, and conductive silica. Essential raw components for electrical wiring, "
            "galvanic batteries, telegraphy networks, and modern scientific laboratory instrumentation."
        ),
    }

    desc_text = role_details.get(r_enum, r_meta.description)

    return {
        'title': f"{r_meta.name} ({r_meta.icon})",
        'badge': "SOVEREIGN ENDOWMENT" if has_res else "NOT ACCESSIBLE",
        'badge_col': GREEN if has_res else (240, 120, 120),
        'category': "Strategic Natural Resource Endowment",
        'cost': "Domestic Availability: Accessible within sovereign borders" if has_res else "Trade Access Required: Import via bilateral trade pacts",
        'desc': [
            desc_text,
            "Access to domestic deposits eliminates international supply dependency and unlocks advanced technologies within the innovation tree."
        ],
        'stats': [
            ("Domestic Deposit Count", f"{t_count} Tile(s) in Empire", GREEN if t_count > 0 else DIM),
            ("Innovation Tree Status", "UNLOCKED" if has_res else "BLOCKED (Missing Resource)", GREEN if has_res else RED),
            ("Sovereign Nation", getattr(nation, 'name', 'National'), ACCENT),
        ],
        'icon': r_enum.value,
        'btn_id': btn_id
    }


def build_science_tech_tooltip(btn_id: str, world: dict, nation=None) -> dict | None:
    """Tooltip for tech cards, era tabs, and prize pledge buttons."""
    # Era tabs
    if btn_id.startswith('sci_era_'):
        era_num = int(btn_id.split('_')[-1])
        era_titles = {
            1: ("Era I: Medieval & Agrarian Feudalism", "Customary manorial agriculture, watermills, and feudal commons."),
            2: ("Era II: Renaissance & Mercantile Expansion", "Standardized craft guilds, double-entry banking, and gunpowder rock blasting."),
            3: ("Era III: Steam & Industrial Revolution", "Coal coking blast furnaces, Watt steam engines, and structural Bessemer steel."),
            4: ("Era IV: Electrification & Modern Corporate Era", "Petroleum refining, electric grids, and multinational corporate charters.")
        }
        etitle, edesc = era_titles.get(era_num, (f"Era {era_num}", "Technological advancement era."))
        return {
            'title': etitle,
            'badge': f"ERA {era_num}",
            'badge_col': ACCENT,
            'category': "Technological Evolution Era",
            'cost': "Click tab to switch technological era view",
            'desc': [
                edesc,
                "Technologies within each era reflect progressive economic specialization and industrial transformations."
            ],
            'stats': [
                ("Selected Era", f"Era {era_num}", ACCENT),
            ],
            'icon': 'rare_minerals',
            'btn_id': btn_id
        }

    # Prize pledge or Tech card
    clean_id = btn_id
    is_pledge = False
    if clean_id.startswith('sci_pledge_'):
        clean_id = clean_id[11:]
        is_pledge = True
    elif clean_id.startswith('tech_'):
        clean_id = clean_id[5:]

    tech = TECH_CATALOG.get(clean_id)
    if not tech:
        return None

    inno = get_innovation_system()
    nat_name = nation.name if nation else ""
    discovered = inno.get_discovered_techs(nat_name)
    diffusing = inno.diffusion_progress.get(nat_name, {})
    accessible_res = get_nation_resources(nation, world=world) if nation else set()

    is_disc = clean_id in discovered
    diff_pct = diffusing.get(clean_id, 0.0)
    has_bounty = any(b.nation_name == nat_name and b.tech_id == clean_id for b in inno.active_bounties)

    missing_techs = [t_req for t_req in tech.required_techs if t_req not in discovered]
    missing_res = [r_req for r_req in tech.required_resources if r_req not in accessible_res]

    pressure = tech.bottleneck_evaluator(nation, nation.tiles) if (tech.bottleneck_evaluator and nation) else 1.0
    cur_xp = inno.get_domain_xp(nat_name, tech.domain)
    req_xp = tech.base_xp_required

    # Prerequisites text
    req_parts = []
    if missing_techs:
        req_parts.append(f"Techs: {', '.join(missing_techs)}")
    if missing_res:
        req_parts.append(f"Resources: {', '.join(r.value for r in missing_res)}")
    req_str = f"Missing: {'; '.join(req_parts)}" if req_parts else "All Prerequisites Satisfied"

    if is_pledge:
        return {
            'title': f"Pledge Royal Science Prize: {tech.name}",
            'badge': "BREAKTHROUGH BOUNTY",
            'badge_col': (245, 205, 70),
            'category': "State Innovation Incentive",
            'cost': "Cost: $300 prize bounty from sovereign treasury",
            'desc': [
                f"Pledges a state bounty to incentivize discovery of {tech.name}.",
                "Accelerates research by doubling domain experience generation from economic activities.",
                "Money Destination: The $300 prize purse is held in research escrow. Upon breakthrough discovery, the entire $300 is disbursed directly into domestic university academies, inventor guilds, and engineering workshops."
            ],
            'stats': [
                ("Target Tech", tech.name, TEXT),
                ("Domain", tech.domain.value.capitalize(), ACCENT),
                ("Accumulated XP", f"{int(cur_xp)} / {int(req_xp)} XP", GREEN if cur_xp >= req_xp else TEXT),
                ("Bottleneck Pressure", f"{pressure:.1f}x Multiplier", (245, 180, 50) if pressure > 1.5 else DIM),
            ],
            'icon': 'rare_minerals',
            'btn_id': btn_id
        }

    # Tech Card overview
    bonus_parts = []
    if tech.production_modifiers:
        bonus_parts.extend(f"+{int((v-1.0)*100)}% {k}" for k, v in tech.production_modifiers.items())
    if tech.unlocked_buildings:
        bonus_parts.append(f"Unlocks {', '.join(tech.unlocked_buildings)}")
    bonus_str = ", ".join(bonus_parts) if bonus_parts else "Fundamental knowledge breakthrough"

    status_str = "MASTERED" if is_disc else (f"DIFFUSING ({int(diff_pct*100)}%)" if diff_pct > 0 else ("PRIZE ACTIVE" if has_bounty else ("BLOCKED" if missing_techs or missing_res else "IN PROGRESS")))
    status_col = GREEN if is_disc else ((80, 200, 255) if diff_pct > 0 else ((245, 205, 70) if has_bounty else (RED if missing_techs or missing_res else ACCENT)))

    return {
        'title': f"{tech.name} (Era {tech.era})",
        'badge': tech.domain.value.upper(),
        'badge_col': ACCENT,
        'category': f"{tech.domain.value.capitalize()} Technological Innovation",
        'cost': req_str,
        'desc': [
            tech.description,
            f"Economic Impact: {bonus_str}.",
            "Practical learning-by-doing in related industries builds domain experience each turn, driving natural breakthroughs."
        ],
        'stats': [
            ("Mastery Status", status_str, status_col),
            ("Domain Experience", f"{int(cur_xp)} / {int(req_xp)} XP", GREEN if cur_xp >= req_xp else TEXT),
            ("Bottleneck Incentive", f"{pressure:.1f}x Pressure", (245, 180, 50) if pressure > 1.5 else DIM),
            ("Domain Category", tech.domain.value.capitalize(), TEXT),
        ],
        'icon': tech.domain.value,
        'btn_id': btn_id
    }


# =============================================================================
# 2. DIPLOMACY & FOREIGN RELATIONS
# =============================================================================

def build_diplomacy_tooltip(btn_id: str, world: dict, nation=None) -> dict | None:
    """Tooltip for foreign nation tabs and bilateral diplomatic decrees."""
    if btn_id.startswith('dip_target_'):
        target_name = btn_id[11:]
        return {
            'title': f"Diplomatic Focus: {target_name}",
            'badge': "FOREIGN RELATIONS",
            'badge_col': ACCENT,
            'category': "Bilateral Statecraft",
            'cost': "Click to inspect bilateral relations, treaties, and agreements",
            'desc': [
                f"Opens detailed foreign dossier and bilateral relations screen for {target_name}.",
                "Monitor mutual trade pacts, non-aggression treaties, military alliances, border tariffs, and historic diplomatic incidents."
            ],
            'stats': [
                ("Focus State", target_name, ACCENT),
            ],
            'icon': 'crown',
            'btn_id': btn_id
        }

    target_name = world.get('diplomacy_target_nation')
    diplomacy = get_diplomacy()
    active_name = nation.name if nation else ""
    rel = diplomacy.get_relation(active_name, target_name) if (active_name and target_name) else 0.0
    is_war = diplomacy.are_at_war(active_name, target_name) if (active_name and target_name) else False
    has_trade = diplomacy.has_treaty(active_name, target_name, TreatyType.TRADE_PACT.value) if (active_name and target_name) else False
    has_nap = diplomacy.has_treaty(active_name, target_name, TreatyType.NON_AGGRESSION.value) if (active_name and target_name) else False
    has_alliance = diplomacy.has_treaty(active_name, target_name, TreatyType.DEFENSIVE_ALLIANCE.value) if (active_name and target_name) else False

    if btn_id == 'dip_trade_pact':
        return {
            'title': "Cancel Trade Pact" if has_trade else "Propose Bilateral Trade Pact",
            'badge': "COMMERCIAL TREATY",
            'badge_col': GREEN if not has_trade else (240, 140, 60),
            'category': "International Trade Agreement",
            'cost': "Free Diplomatic Accord (Requires non-war status)",
            'desc': [
                "Halves mutual import tariffs between both nations (from 25% down to 12%), boosting merchant goods arbitrage and cross-border trade flow.",
                "Enables technological diffusion along trade routes, allowing both nations to reverse-engineer each other's discoveries.",
                "Cancelling reinstates full statutory border tariffs and halts cross-border innovation diffusion."
            ],
            'stats': [
                ("Treaty Status", "ACTIVE" if has_trade else "INACTIVE", GREEN if has_trade else DIM),
                ("Tariff Relief", "50% Tariff Surcharge Reduction", (120, 240, 150)),
                ("Target Sovereign", target_name or "Foreign Nation", ACCENT),
            ],
            'icon': 'ex',
            'btn_id': btn_id
        }

    if btn_id == 'dip_nap':
        return {
            'title': "Cancel Non-Aggression Pact" if has_nap else "Conclude Non-Aggression Pact",
            'badge': "SECURITY ACCORD",
            'badge_col': ACCENT if not has_nap else (240, 140, 60),
            'category': "Sovereign Peace Accord",
            'cost': "Free Mutual Commitment (Requires non-war status)",
            'desc': [
                "Mutual pledge of non-aggression between sovereign borders. Halts unprovoked border incursions and military border skirmishes.",
                "Gradually builds bilateral diplomatic trust and improves relation score by +0.02 each turn.",
                "Breaking an active pact incurs severe international infamy and distrust across all sovereign nations."
            ],
            'stats': [
                ("NAP Status", "ENFORCED" if has_nap else "NOT SIGNED", ACCENT if has_nap else DIM),
                ("Current Relation", f"{rel:+.2f}", GREEN if rel > 0 else RED),
                ("Target Sovereign", target_name or "Foreign Nation", TEXT),
            ],
            'icon': 'shield',
            'btn_id': btn_id
        }

    if btn_id == 'dip_alliance':
        return {
            'title': "Dissolve Defensive Alliance" if has_alliance else "Form Defensive Alliance",
            'badge': "MILITARY COALITION",
            'badge_col': (80, 200, 255) if not has_alliance else (240, 140, 60),
            'category': "Mutual Defense Coalition",
            'cost': "Strategic Commitment (Requires friendly relations > +0.25)",
            'desc': [
                "Binds both nations in a mutual defense coalition. If an ally is attacked by a third-party aggressor, all standing army divisions mobilize in their defense.",
                "Massively elevates military deterrent against foreign invasions and consolidates regional geopolitical stability.",
                "Dissolving the alliance removes mutual security guarantees."
            ],
            'stats': [
                ("Alliance Status", "ALLIED" if has_alliance else "NO ALLIANCE", (80, 200, 255) if has_alliance else DIM),
                ("Current Relation", f"{rel:+.2f}", GREEN if rel > 0 else RED),
                ("Target Sovereign", target_name or "Foreign Nation", TEXT),
            ],
            'icon': 'crown',
            'btn_id': btn_id
        }

    if btn_id == 'dip_war_peace':
        if is_war:
            return {
                'title': "Sign Peace Treaty",
                'badge': "RESTORE PEACE",
                'badge_col': GREEN,
                'category': "Sovereign Armistice",
                'cost': "Free Bilateral Armistice Accord",
                'desc': [
                    "Brings an immediate end to all active armed hostilities and military skirmishes.",
                    "Lifts trade embargoes and border blockades, reopening commercial goods transit across mutual borders.",
                    "Allows demobilization of exhausted divisions to lower per-turn military upkeep costs."
                ],
                'stats': [
                    ("War Status", "ACTIVE HOSTILITIES", RED),
                    ("Target Sovereign", target_name or "Foreign Nation", TEXT),
                ],
                'icon': 'check',
                'btn_id': btn_id
            }
        else:
            return {
                'title': "Declare Sovereign War",
                'badge': "DECLARATION OF WAR",
                'badge_col': RED,
                'category': "Military Statecraft",
                'cost': "Severe diplomatic rupture; terminates all active treaties",
                'desc': [
                    "Formally declares war on the foreign sovereign state. Authorizes your military divisions to march into enemy territory and conquer provincial cities.",
                    "Immediately terminates all active trade pacts and non-aggression treaties. Imposes a total trade embargo on foreign imports.",
                    "Warning: Causes significant war weariness and public economic disruption."
                ],
                'stats': [
                    ("Bilateral Status", f"Relation: {rel:+.2f}", (245, 180, 50)),
                    ("Target Sovereign", target_name or "Foreign Nation", RED),
                ],
                'icon': 'military',
                'btn_id': btn_id
            }

    if btn_id == 'dip_foreign_aid':
        gov_cash = nation.government.agent.cash if (nation and nation.government) else 0.0
        return {
            'title': "Send Foreign Aid Grant ($100)",
            'badge': "DIPLOMATIC GIFT",
            'badge_col': (120, 240, 150),
            'category': "International Diplomatic Grant",
            'cost': "Cost: $100 grant from sovereign treasury",
            'desc': [
                "Dispatches a $100 sovereign goodwill grant to ease fiscal distress in the recipient nation.",
                "Immediately generates a +0.15 bilateral relation boost, repairing strained relations or laying the groundwork for an alliance.",
                "Money Destination: Transferred directly from your sovereign treasury vault into the target nation's sovereign government treasury."
            ],
            'stats': [
                ("Current Relation", f"{rel:+.2f} -> {min(1.0, rel + 0.15):+.2f}", GREEN),
                ("Sovereign Treasury", f"${gov_cash:,.0f}", (120, 240, 150) if gov_cash >= 100 else RED),
                ("Target Sovereign", target_name or "Foreign Nation", TEXT),
            ],
            'icon': 'treasury',
            'btn_id': btn_id
        }

    return None


# =============================================================================
# 3. SOVEREIGN DEBT & ISRB RATING BUREAU
# =============================================================================

def build_debt_tooltip(btn_id: str, world: dict, nation=None) -> dict | None:
    """Tooltip for sovereign debt issuance, ISRB lobbying, and foreign bond purchases."""
    market = get_bond_market()
    isrb = market.isrb
    gov_cash = nation.government.agent.cash if (nation and nation.government) else 0.0
    sel_dur = world.get('bond_duration_selected', 20)
    rating, market_yield = isrb.get_market_yield(nation, sel_dur, world) if nation else ("BBB", 0.05)
    has_board_seat = nation.name in isrb.board_seats if nation else False

    if btn_id == 'debt_scope_domestic':
        return {
            'title': "Domestic Sovereign Debt & ISRB Bureau",
            'badge': "DOMESTIC FISCAL",
            'badge_col': ACCENT,
            'category': "Sovereign Bond Management",
            'cost': "Click to manage domestic debt, ratings, and bond offerings",
            'desc': [
                "Review sovereign credit rating from the International Sovereign Rating Bureau (ISRB), influence rating analysts, and issue public debt securities to finance state growth."
            ],
            'stats': [
                ("Current Credit Rating", rating, GREEN if rating.startswith('A') else (245, 180, 50)),
                ("Benchmark Yield", f"{market_yield*100:.2f}% / turn", ACCENT),
            ],
            'icon': 'scale',
            'btn_id': btn_id
        }

    if btn_id == 'debt_scope_foreign':
        return {
            'title': "Foreign Currency Reserves & Cross-Border Bonds",
            'badge': "FOREIGN RESERVES",
            'badge_col': (120, 240, 150),
            'category': "International Bond Portfolio",
            'cost': "Click to inspect foreign bonds and international debt secondary market",
            'desc': [
                "Inspect holdings of foreign sovereign debt securities. Foreign bonds pay steady per-turn coupon yields in foreign currencies, buffering domestic macroeconomic stability."
            ],
            'stats': [
                ("Portfolio Status", "Foreign Bonds Held", TEXT),
            ],
            'icon': 'treasury',
            'btn_id': btn_id
        }

    if btn_id == 'debt_lobby_isrb':
        return {
            'title': "Lobby ISRB Credit Rating Agency ($200)",
            'badge': "RATING UPGRADE",
            'badge_col': (120, 240, 150),
            'category': "Financial Statecraft",
            'cost': "Cost: $200 lobbying expenditure from sovereign treasury",
            'desc': [
                "Engages financial lobbyists and rating committee emissaries to temporarily elevate your sovereign credit rating by +1 grade (e.g. BBB -> A).",
                "Lowers per-turn coupon interest demanded by debt underwriters on newly issued sovereign bonds.",
                "Money Destination: Paid directly to ISRB credit rating committee executives, bureaucratic analysts, and underwriting syndicate organizers."
            ],
            'stats': [
                ("Rating Impact", f"{rating} -> Upgrade +1 Notch", GREEN),
                ("Sovereign Treasury", f"${gov_cash:,.0f}", (120, 240, 150) if gov_cash >= 200 else RED),
            ],
            'icon': 'scale',
            'btn_id': btn_id
        }

    if btn_id == 'debt_audit_rival':
        return {
            'title': "Audit Rival Sovereign Finances ($350)",
            'badge': "FINANCIAL WARFARE",
            'badge_col': (245, 180, 50),
            'category': "Financial Intelligence & Regulatory Sabotage",
            'cost': "Cost: $350 investigation fee from sovereign treasury",
            'desc': [
                "Funds an independent forensic accounting probe into foreign sovereign fiscal reserves and hidden liabilities.",
                "Exposes fiscal deficits and degrades the target rival sovereign's credit rating by -1 grade, spiking their borrowing costs.",
                "Money Destination: Disbursed to international forensic accounting syndicates, independent financial investigators, and regulatory compliance auditors."
            ],
            'stats': [
                ("Target Penalty", "-1 Rating Grade to Rival", RED),
                ("Sovereign Treasury", f"${gov_cash:,.0f}", (120, 240, 150) if gov_cash >= 350 else RED),
            ],
            'icon': 'scale',
            'btn_id': btn_id
        }

    if btn_id == 'debt_board_seat':
        return {
            'title': "Acquire Permanent ISRB Board Seat ($600)",
            'badge': "INSTITUTIONAL GOVERNANCE",
            'badge_col': (80, 200, 255),
            'category': "Global Financial Institution Governance",
            'cost': "Cost: $600 capital endowment from sovereign treasury" if not has_board_seat else "Already Owned",
            'desc': [
                "Acquires permanent voting governor status on the International Sovereign Rating Bureau executive board.",
                "Confers a permanent +1 grade credit rating bonus for your nation, permanently lowering national debt servicing costs.",
                "Money Destination: Contributed directly into the ISRB central capital reserve fund as an equity subscription."
            ],
            'stats': [
                ("Board Seat Status", "ACQUIRED" if has_board_seat else "AVAILABLE", GREEN if has_board_seat else ACCENT),
                ("Permanent Bonus", "+1 Credit Rating Grade (Indefinite)", GREEN),
                ("Sovereign Treasury", f"${gov_cash:,.0f}", (120, 240, 150) if gov_cash >= 600 else RED),
            ],
            'icon': 'crown',
            'btn_id': btn_id
        }

    if btn_id.startswith('debt_dur_'):
        d_val = int(btn_id.split('_')[-1])
        dur_desc = {
            20: "Short-term 20-turn bond. High liquidity, rapid principal maturation, and lowest baseline interest rate.",
            50: "Medium-term 50-turn bond. Balanced institutional financing term favored by commercial banks and insurance syndicates.",
            100: "Long-term 100-turn perpetual bond. Locks in fixed state financing across an entire century of infrastructure development."
        }
        return {
            'title': f"Bond Maturity Duration: {d_val} Turns",
            'badge': f"{d_val}T MATURITY",
            'badge_col': ACCENT,
            'category': "Debt Maturity Structure",
            'cost': f"Maturity Period: {d_val} turns until principal repayment",
            'desc': [
                dur_desc.get(d_val, f"Sets bond debt duration to {d_val} turns."),
                "Underwriters discount long-duration debt based on risk and inflation expectations."
            ],
            'stats': [
                ("Selected Term", f"{d_val} Turns", ACCENT),
                ("Current Rating", rating, GREEN if rating.startswith('A') else TEXT),
            ],
            'icon': 'scale',
            'btn_id': btn_id
        }

    if btn_id in ('debt_issue_500', 'debt_issue_1000'):
        amt = 500.0 if btn_id == 'debt_issue_500' else 1000.0
        coupon_est = amt * market_yield
        return {
            'title': f"Announce ${amt:,.0f} Sovereign Debt Offering",
            'badge': "DEBT ISSUANCE",
            'badge_col': GREEN if amt == 500 else ACCENT,
            'category': "Public Sovereign Debt Issuance",
            'cost': f"Servicing Obligation: ~${coupon_est:,.2f} coupon payment each turn for {sel_dur} turns",
            'desc': [
                f"Announces a 1-turn advance public offering of ${amt:,.0f} in sovereign bonds at {market_yield*100:.2f}% coupon yield.",
                "At the start of the next turn, institutional underwriter banks and wealthy private bondholders purchase the bonds, injecting liquid cash into your sovereign treasury.",
                "Money Destination: Underwriter investment syndicates and private domestic wealth holders purchase the bonds with private capital, transferring ${amt:,.0f} directly into your sovereign treasury in exchange for recurring coupon paper."
            ],
            'stats': [
                ("Gross Cash Inflow", f"+${amt:,.0f} Next Turn", GREEN),
                ("Coupon Yield", f"{market_yield*100:.2f}% / turn (~${coupon_est:,.2f}/t)", (245, 180, 50)),
                ("Maturity Term", f"{sel_dur} Turns", TEXT),
                ("Credit Rating", rating, ACCENT),
            ],
            'icon': 'scale',
            'btn_id': btn_id
        }

    if btn_id == 'debt_buy_bond':
        return {
            'title': "Purchase Foreign Sovereign Bond",
            'badge': "ASSET ACQUISITION",
            'badge_col': (120, 240, 150),
            'category': "Sovereign Reserve Diversification",
            'cost': "Principal purchase price disbursed from sovereign treasury",
            'desc': [
                "Purchases a foreign government's sovereign bond from the primary offering market.",
                "Adds valuable foreign debt to your central bank reserves, paying guaranteed per-turn coupon income in the foreign currency until maturity.",
                "Money Destination: Transferred directly into the issuing foreign nation's sovereign treasury vault."
            ],
            'stats': [
                ("Reserve Purpose", "Generates passive coupon income and foreign exchange reserves", TEXT),
                ("Sovereign Treasury", f"${gov_cash:,.0f}", (120, 240, 150)),
            ],
            'icon': 'bank',
            'btn_id': btn_id
        }

    return None


# =============================================================================
# 4. MILITARY & GARRISON RECRUITMENT
# =============================================================================

def build_military_tooltip(btn_id: str, world: dict, region=None, nation=None) -> dict | None:
    """Tooltip for military recruitment and defense mobilization."""
    if btn_id == 'mil_recruit_unit':
        pinned = region or world.get('selected_region')
        tile_name = getattr(pinned, 'display_name', getattr(pinned, 'city_name', pinned.name)) if pinned else "Selected Territory"
        gov_cash = nation.government.agent.cash if (nation and nation.government) else 0.0
        return {
            'title': f"Recruit Garrison Division in {tile_name}",
            'badge': "MILITARY LEVY",
            'badge_col': (235, 90, 90),
            'category': "Standing Military Recruitment",
            'cost': "Cost: $15 recruitment levy + $1.50/turn ongoing soldier upkeep",
            'desc': [
                f"Enlists 15 citizen recruits from {tile_name} into a new active military division stationed on the tile.",
                "Deters foreign invasion, suppresses local civil unrest, and provides an expeditionary force capable of defending national borders.",
                "Money Destination: $15 is disbursed to local arms workshops and munitions artisans for uniforms, muskets, and recruit enlistment bounties. Ongoing $1.50/turn upkeep pays soldiers' food rations and service wages."
            ],
            'stats': [
                ("Recruitment Quota", "15 Trained Soldiers", ACCENT),
                ("Ongoing Upkeep", "$1.50 / turn", (245, 180, 50)),
                ("Station Territory", tile_name, TEXT),
                ("Sovereign Treasury", f"${gov_cash:,.0f}", (120, 240, 150) if gov_cash >= 15 else RED),
            ],
            'icon': 'military',
            'btn_id': btn_id
        }

    return None
