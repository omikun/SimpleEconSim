"""
worldview_cadastre.py — Visual Plot Inspector & Estate Cadastre UI for REGNUM.

Provides an interactive estate cadastre and land tenure inspection panel in the right sidebar:
  1. Parish Land Summary (Commons Usufruct %, Feudal Manorial %, Enclosed Private %, Pasture vs Arable).
  2. Discrete Plot Inspection: Authentic country plot name, acreage fraction, tenure status badge.
  3. Land Use & Labor Allocation (Arable grain crops vs Pasture sheep grazing).
  4. Bound Tenant Roster (Social class, living status, cash, survey debts).
  5. Statutory Foreclosure Countdown (Pending enclosure surveying fees & foreclosure deadlines).
  6. Contextual Land Decrees: [Enclose Feudal Plot], [Convert to Pasture/Arable], [Restore Commons].
"""

from __future__ import annotations
import logging
import pygame
from goods import Goods
from land_tenure import TenureStatus, LandPlot
from enclosure import calculate_charter_fee, execute_enclosure
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import TEXT, DIM, RED, GREEN, ACCENT, HEX_EDGE
from ui_icons import get_icon

PANEL_LEFT = MAP_RIGHT + 12
PANEL_W = WIDTH - PANEL_LEFT - 6
_log = logging.getLogger(__name__)
_resistance_dossier_warning_logged = False

# Color palette for cadastre tenure
C_COMMONS = (100, 215, 130)       # Lush customary green
C_FEUDAL = (220, 180, 75)         # Warm feudal gold
C_ENCLOSED = (215, 120, 60)       # Parched enclosed amber/brown
C_PASTURE = (160, 210, 150)       # Sage wool pasture
C_ARABLE = (235, 205, 110)        # Golden grain wheat
C_COTTON = (245, 235, 220)        # Linen cotton white

CARD_BG = (24, 28, 38)
CARD_BORDER = (45, 52, 70)
BTN_BG = (38, 44, 60)
BTN_HOVER = (55, 65, 90)

_CADASTRE_BUTTONS = []


def _draw_btn(surface, rect, text, font_small, mx, my, enabled=True, color=TEXT, border_color=None):
    """Draw interactive button with hover highlight."""
    rx, ry, rw, rh = rect
    hov = enabled and (rx <= mx <= rx + rw and ry <= my <= ry + rh)
    bg = BTN_HOVER if hov else BTN_BG
    if not enabled:
        bg = (24, 26, 34)
    pygame.draw.rect(surface, bg, rect, border_radius=4)
    b_col = border_color or (ACCENT if hov else ((65, 75, 100) if enabled else (40, 44, 56)))
    pygame.draw.rect(surface, b_col, rect, 1, border_radius=4)
    txt_col = (255, 255, 255) if hov else (color if enabled else DIM)
    lbl = font_small.render(text, True, txt_col)
    surface.blit(lbl, lbl.get_rect(center=(rx + rw // 2, ry + rh // 2)))


def draw_cadastre_panel(surface, world: dict, region, font, font_small, mouse_pos=None):
    """Draw the Estate Cadastre & Land Plot Inspector in the right-hand panel."""
    global _CADASTRE_BUTTONS
    _CADASTRE_BUTTONS.clear()

    d = TOP_BAR_H
    panel_top = 180 + d
    panel_bottom = HEIGHT - TICKER_H - 24
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    if region is None and world.get('nations') and world['nations'][0].tiles:
        region = world['nations'][0].tiles[0]

    if region is None:
        surface.blit(font_small.render("No tile selected for cadastre inspection.", True, DIM), (PANEL_LEFT + 10, panel_top + 20))
        return

    tenure = getattr(region, 'tenure', None)
    cur_y = panel_top + 4

    # 1. Header Summary Card: Parish Land Breakdown
    h_card_h = 72
    h_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, h_card_h)
    pygame.draw.rect(surface, CARD_BG, h_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, h_rect, 1, border_radius=5)

    c_name = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
    surface.blit(font_small.render(f"Cadastre: {c_name}", True, (240, 200, 110)), (PANEL_LEFT + 12, cur_y + 6))

    if tenure and tenure.plots:
        com_pct = tenure.commons_access * 100
        feu_pct = tenure.feudal_fraction * 100
        enc_pct = tenure.enclosed_fraction * 100
        pas_pct = tenure.pasture_fraction * 100
        ara_pct = tenure.arable_fraction * 100
        cot_plots = [p for p in tenure.plots if getattr(p, 'production_type', '') == 'cotton']
        cot_pct = sum(p.fraction for p in cot_plots) * 100

        l1 = f"Commons: {com_pct:.0f}%  •  Feudal: {feu_pct:.0f}%  •  Enclosed: {enc_pct:.0f}%"
        surface.blit(font_small.render(l1, True, (130, 210, 140) if com_pct > 40 else (230, 140, 70)), (PANEL_LEFT + 12, cur_y + 24))

        l2 = f"Crops: Grain {ara_pct:.0f}%  |  Wool {pas_pct:.0f}%"
        if cot_pct > 0:
            l2 += f"  |  Cotton {cot_pct:.0f}%"
        surface.blit(font_small.render(l2, True, DIM), (PANEL_LEFT + 12, cur_y + 39))

        # Mini stacked color bar for crop allocation
        bar_x = PANEL_LEFT + 12
        bar_y = cur_y + 54
        bar_w = PANEL_W - 24
        bar_h = 8
        pygame.draw.rect(surface, (35, 40, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        offset_x = bar_x
        tot_f = max(0.01, sum(p.fraction for p in tenure.plots) + tenure.commons_access)
        if ara_pct > 0:
            w_ara = int(bar_w * (tenure.arable_fraction / tot_f))
            pygame.draw.rect(surface, C_ARABLE, (offset_x, bar_y, w_ara, bar_h))
            offset_x += w_ara
        if pas_pct > 0:
            w_pas = int(bar_w * (tenure.pasture_fraction / tot_f))
            pygame.draw.rect(surface, C_PASTURE, (offset_x, bar_y, w_pas, bar_h))
            offset_x += w_pas
        if cot_pct > 0:
            w_cot = int(bar_w * (sum(p.fraction for p in cot_plots) / tot_f))
            pygame.draw.rect(surface, (245, 240, 230), (offset_x, bar_y, w_cot, bar_h))
            offset_x += w_cot
        if com_pct > 0:
            w_com = int(bar_w * (tenure.commons_access / tot_f))
            pygame.draw.rect(surface, C_COMMONS, (offset_x, bar_y, w_com, bar_h))
    else:
        surface.blit(font_small.render("Wilderness or unchartered territory (Customary Commons).", True, (120, 200, 130)), (PANEL_LEFT + 12, cur_y + 28))

    cur_y += h_card_h + 8

    # Sub-tab toggle: [ Parcels & Land ] vs [ Capital & Credit ]
    subtab = world.get('cadastre_subtab', 'plots')
    tab_btn_w = (PANEL_W - 14) // 2
    btn_p_rect = (PANEL_LEFT + 4, cur_y, tab_btn_w, 22)
    btn_f_rect = (PANEL_LEFT + 8 + tab_btn_w, cur_y, tab_btn_w, 22)

    _draw_btn(surface, btn_p_rect, "Parcels & Land", font_small, mx, my,
              enabled=True, color=(255, 255, 255) if subtab == 'plots' else DIM,
              border_color=ACCENT if subtab == 'plots' else None)
    _CADASTRE_BUTTONS.append((btn_p_rect, 'cadastre_subtab_plots', None))

    _draw_btn(surface, btn_f_rect, "Capital & Credit", font_small, mx, my,
              enabled=True, color=(255, 255, 255) if subtab == 'finance' else DIM,
              border_color=ACCENT if subtab == 'finance' else None)
    _CADASTRE_BUTTONS.append((btn_f_rect, 'cadastre_subtab_finance', None))

    cur_y += 28

    if subtab == 'finance':
        # ---------------------------------------------------------------------
        # FINANCE & CAPITAL SUB-TAB
        # ---------------------------------------------------------------------
        agents = getattr(region, 'agents', [])
        corps = [a for a in agents if getattr(a, 'is_corporation', False) and getattr(a, 'alive', True)]

        # 1. Mechanized Industry & Fixed Capital Card
        ludd_mgr = world.get('scenario_state', {}).get('luddite_manager_ref') or getattr(region, 'luddite_manager', None)
        l_st = ludd_mgr.get_state(region.name) if ludd_mgr else None
        has_ludd = l_st and l_st.combination_strength >= 20.0
        ind_h = 124 if (corps and has_ludd) else 96
        ind_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, ind_h)
        pygame.draw.rect(surface, CARD_BG, ind_rect, border_radius=5)
        pygame.draw.rect(surface, (230, 80, 80) if (has_ludd and l_st.combination_strength >= 50.0) else CARD_BORDER, ind_rect, 1, border_radius=5)

        surface.blit(font_small.render("Industrial Manufacturing & Machinery", True, (100, 190, 240)), (PANEL_LEFT + 12, cur_y + 6))

        if corps:
            c0 = corps[0]
            out_name = c0.output.name.capitalize() if hasattr(c0.output, 'name') else str(c0.output).capitalize()
            m_lvl = getattr(c0, 'machinery_level', 1)
            is_brk = getattr(c0, 'machinery_broken', False) or getattr(c0, 'broken_machinery', 0) > 0
            wear = getattr(c0, 'machinery_wear', 0)

            l_info = f"Firm #{c0.id}: {out_name} Mill  •  Machinery: Lvl {m_lvl}"
            surface.blit(font_small.render(l_info, True, (240, 240, 240)), (PANEL_LEFT + 12, cur_y + 24))

            if is_brk:
                warn_txt = "⚠️ MACHINERY BREAKDOWN (-50% Output)"
                surface.blit(font_small.render(warn_txt, True, (245, 70, 70)), (PANEL_LEFT + 12, cur_y + 42))
                b_rep = (PANEL_LEFT + 12, cur_y + 62, 160, 22)
                _draw_btn(surface, b_rep, "Repair ($10 + 1 Iron)", font_small, mx, my, enabled=True, color=(245, 180, 60))
                _CADASTRE_BUTTONS.append((b_rep, 'cadastre_repair_machinery', (region, c0.id)))
            else:
                w_str = f"Wear: {wear}/12 Cycles  •  Status: Operational"
                surface.blit(font_small.render(w_str, True, (130, 215, 140)), (PANEL_LEFT + 12, cur_y + 42))
                emp_str = f"Wage: ${getattr(c0, 'wage', 2.0):.2f}/t  •  Capacity: {getattr(c0, 'max_employees', 15)} Hands"
                surface.blit(font_small.render(emp_str, True, DIM), (PANEL_LEFT + 12, cur_y + 60))

            if has_ludd:
                l_col = (245, 70, 70) if l_st.combination_strength >= 50.0 else (240, 180, 60)
                l_txt = f"⚡ Luddites: {l_st.active_threat_level} ({l_st.combination_strength:.0f}%) • Guards: {l_st.factory_guards}"
                surface.blit(font_small.render(l_txt, True, l_col), (PANEL_LEFT + 12, cur_y + 78))
                b_grd = (PANEL_LEFT + 12, cur_y + 96, 115, 20)
                _draw_btn(surface, b_grd, "Hire Guards ($15)", font_small, mx, my, enabled=True, color=(180, 90, 60))
                _CADASTRE_BUTTONS.append((b_grd, 'cadastre_hire_guards', (region, c0.id)))
                b_rel = (PANEL_LEFT + 135, cur_y + 96, 115, 20)
                _draw_btn(surface, b_rel, "Bread Relief ($15)", font_small, mx, my, enabled=True, color=(100, 180, 120))
                _CADASTRE_BUTTONS.append((b_rel, 'cadastre_bread_relief', (region, c0.id)))
        else:
            surface.blit(font_small.render("No corporate manufacturing factories on this parish.", True, DIM), (PANEL_LEFT + 12, cur_y + 26))
            surface.blit(font_small.render("Incorporate steam mills via scenario actions or elite capital.", True, (140, 160, 180)), (PANEL_LEFT + 12, cur_y + 44))

        cur_y += ind_h + 8

        # 2. Commercial Bills of Exchange & Credit Market Card
        state = world.get('scenario_state', {})
        credit_mgr = state.get('credit_manager_ref')
        if not credit_mgr and hasattr(world, 'credit_manager'):
            credit_mgr = world.credit_manager

        cred_stats = credit_mgr.get_credit_market_stats(region) if credit_mgr else {
            'leverage_ratio': 1.0, 'active_bills_count': 0, 'is_credit_bubble': False, 'total_face_value': 0.0
        }
        lev = cred_stats.get('leverage_ratio', 1.0)
        is_bubb = cred_stats.get('is_credit_bubble', False)

        bills_h = 100
        bills_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, bills_h)
        pygame.draw.rect(surface, CARD_BG, bills_rect, border_radius=5)
        pygame.draw.rect(surface, (230, 80, 80) if is_bubb else CARD_BORDER, bills_rect, 1, border_radius=5)

        surface.blit(font_small.render("Lombard Street Credit & Commercial Bills", True, (240, 205, 100)), (PANEL_LEFT + 12, cur_y + 6))

        lev_col = (245, 70, 70) if is_bubb or lev >= 2.0 else ((240, 180, 60) if lev >= 1.5 else (120, 220, 150))
        bubb_tag = "[⚠️ BUBBLE SPECULATION]" if is_bubb else "[HEALTHY CREDIT]"
        surface.blit(font_small.render(f"Leverage: {lev:.2f}x  {bubb_tag}", True, lev_col), (PANEL_LEFT + 12, cur_y + 24))

        active_cnt = cred_stats.get('active_bills_count', 0)
        tot_face = cred_stats.get('total_face_value', 0.0)
        surface.blit(font_small.render(f"Active Bills: {active_cnt}  •  Total Volume: ${tot_face:,.0f}", True, (210, 210, 210)), (PANEL_LEFT + 12, cur_y + 42))

        reg_agent_ids = {a.id for a in agents}
        tile_bills = [b for b in getattr(credit_mgr, 'active_bills', {}).values() if b.payee_id in reg_agent_ids or b.drawer_id in reg_agent_ids] if credit_mgr else []
        turn = int(world.get('turn', 0))
        if tile_bills:
            b0 = tile_bills[0]
            pv = b0.calculate_discounted_value(turn)
            t_rem = max(0, b0.maturity_turn - turn)
            b_line = f"Bill #{b0.id[:6]}: Face ${b0.face_value:.0f}  ->  PV ${pv:.1f} (in {t_rem}t, r={b0.discount_rate*100:.1f}%)"
            surface.blit(font_small.render(b_line, True, (160, 215, 240)), (PANEL_LEFT + 12, cur_y + 60))
        else:
            surface.blit(font_small.render("Commercial Discount Yield Curve: 4.0% - 5.5% p.a.", True, DIM), (PANEL_LEFT + 12, cur_y + 60))
        surface.blit(font_small.render("Bills circulate as negotiable elastic currency substitutes.", True, (140, 150, 165)), (PANEL_LEFT + 12, cur_y + 78))

        cur_y += bills_h + 8

        # 3. War Capitalism & Frontier Colonial Estates Card
        estates = []
        for a in agents:
            for e in getattr(a, 'frontier_estates', []):
                estates.append((a, e))

        fc_h = 84
        fc_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, fc_h)
        pygame.draw.rect(surface, CARD_BG, fc_rect, border_radius=5)
        pygame.draw.rect(surface, (180, 60, 60) if estates else CARD_BORDER, fc_rect, 1, border_radius=5)

        surface.blit(font_small.render("War Capitalism & Frontier Enclaves", True, (240, 130, 90)), (PANEL_LEFT + 12, cur_y + 6))

        if estates:
            owner_a, e0 = estates[0]
            t_reg = e0.get('target_region', 'Colonial_Frontier')
            comm = e0.get('primary_commodity', 'cotton').capitalize()
            capt = e0.get('captive_labor', 0)
            surface.blit(font_small.render(f"Enclave: {t_reg}  •  Primary Crop: {comm}", True, (230, 230, 230)), (PANEL_LEFT + 12, cur_y + 24))
            surface.blit(font_small.render(f"Captive Unfree Labor: {capt} Hands", True, (255, 110, 110)), (PANEL_LEFT + 12, cur_y + 42))
            surface.blit(font_small.render("Regime: Plantation Gang Extraction (0 Wages, -1 Attrition/t)", True, (210, 160, 110)), (PANEL_LEFT + 12, cur_y + 60))
        else:
            surface.blit(font_small.render("No overseas chartered plantation concessions active.", True, DIM), (PANEL_LEFT + 12, cur_y + 26))
            surface.blit(font_small.render("Charter armed frontier expeditions to secure primary crops.", True, (150, 160, 175)), (PANEL_LEFT + 12, cur_y + 44))

        cur_y += fc_h + 8

        # 4. Global Commerce, Oceanic Trade Triangles & Aristocratic Prestige Card
        trg_h = 100
        trg_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, trg_h)
        pygame.draw.rect(surface, CARD_BG, trg_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, trg_rect, 1, border_radius=5)

        surface.blit(font_small.render("Oceanic Trade Triangles & Aristocratic Prestige", True, (130, 200, 255)), (PANEL_LEFT + 12, cur_y + 6))

        trade_mgr = getattr(region, 'trade_manager', None)
        if not trade_mgr:
            state = world.get('scenario_state', {})
            trade_mgr = state.get('trade_manager_ref')

        # Find elite agent with prestige or cash
        elites = [a for a in agents if getattr(a, 'alive', True) and (getattr(a, 'is_lord', False) or getattr(a, 'cash', 0.0) >= 30.0)]
        e0 = elites[0] if elites else None
        p_score = getattr(e0, 'prestige_score', 0.0) if e0 else 0.0
        p_tier = getattr(e0, 'status_tier', 'Provincial Gentry') if e0 else 'Provincial Gentry'

        p_line = f"Prestige: {p_score:.1f} pts  •  Title: {p_tier}"
        surface.blit(font_small.render(p_line, True, (245, 220, 130)), (PANEL_LEFT + 12, cur_y + 24))

        voyages = [v for v in getattr(trade_mgr, 'active_voyages', []) if getattr(v, 'home_region', '') == region.name] if trade_mgr else []
        if voyages:
            v0 = voyages[0]
            v_info = f"Voyage #{v0.voyage_id[-6:]}: {v0.expected_luxury} (ETA: {v0.turns_remaining}t)"
            surface.blit(font_small.render(v_info, True, (160, 230, 210)), (PANEL_LEFT + 12, cur_y + 42))
        else:
            circ_count = len(getattr(trade_mgr, 'circuits', {})) if trade_mgr else 0
            surface.blit(font_small.render(f"Discovered Circuits: {circ_count}  •  No active voyages", True, DIM), (PANEL_LEFT + 12, cur_y + 42))

        # Interactive Charter Button
        if trade_mgr and e0:
            b_trg = (PANEL_LEFT + 12, cur_y + 64, 185, 22)
            _draw_btn(surface, b_trg, "Charter Voyage ($14 + 5 Cloth)", font_small, mx, my, enabled=True, color=(100, 180, 240))
            _CADASTRE_BUTTONS.append((b_trg, 'cadastre_charter_voyage', (region, e0.id)))
        else:
            surface.blit(font_small.render("Charter merchant voyages to export cloth & import fine luxuries.", True, (140, 160, 175)), (PANEL_LEFT + 12, cur_y + 64))

        cur_y += trg_h + 8

        # 5. True Cost & Externalities Ledger Card
        tc_h = 110
        tc_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, tc_h)
        pygame.draw.rect(surface, CARD_BG, tc_rect, border_radius=5)

        try:
            from economy.true_cost_ledger import get_true_cost_ledger
            tc_ledger = get_true_cost_ledger()
            tile_agg = tc_ledger.get_tile_aggregate(region.name)
            nom_p = tile_agg.get('nominal_profit', 0.0)
            ext_c = tile_agg.get('total_externalized_cost', 0.0)
            true_p = tile_agg.get('true_net_profit', 0.0)
            ratio = tile_agg.get('avg_externalization_ratio', 0.0)

            if true_p > 0 and ratio < 0.25:
                border_col = (80, 200, 120)
                badge_text = "ECO-RESTORATIVE"
                badge_col = (80, 220, 120)
            elif true_p >= 0:
                border_col = (220, 180, 80)
                badge_text = "SUBSIDIZED BY NATURE"
                badge_col = (230, 190, 80)
            else:
                border_col = (220, 60, 60)
                badge_text = "EXTRACTIVE PARASITE"
                badge_col = (255, 90, 90)

            pygame.draw.rect(surface, border_col, tc_rect, 1, border_radius=5)
            surface.blit(font_small.render("True Cost & Externalities Ledger", True, (240, 210, 140)), (PANEL_LEFT + 12, cur_y + 6))
            surface.blit(font_small.render(f"[{badge_text}]", True, badge_col), (PANEL_LEFT + PANEL_W - 170, cur_y + 6))

            l1 = f"Nominal Accounting Profit: ${nom_p:+.2f}  |  Externalized Damage: -${ext_c:.2f}"
            surface.blit(font_small.render(l1, True, (220, 220, 220)), (PANEL_LEFT + 12, cur_y + 26))

            true_col = (100, 230, 130) if true_p >= 0 else (255, 100, 100)
            l2 = f"True Net Social Profit: ${true_p:+.2f}  (Ext Ratio: {ratio*100:.1f}%)"
            surface.blit(font_small.render(l2, True, true_col), (PANEL_LEFT + 12, cur_y + 46))

            firms_on_tile = [a for a in agents if getattr(a, 'is_corporation', False) and getattr(a, 'alive', True)]
            f0_rec = tc_ledger.get_record(firms_on_tile[0].id) if firms_on_tile else None
            if f0_rec:
                ext_obj = f0_rec.externalities
                breakdown = f"Smog: -${ext_obj.air_pollution_cost:.1f}  Water: -${ext_obj.water_effluent_cost:.1f}  Health: -${ext_obj.labor_health_wear_cost:.1f}  Soil: -${ext_obj.soil_depletion_cost:.1f}"
                surface.blit(font_small.render(breakdown, True, (170, 185, 200)), (PANEL_LEFT + 12, cur_y + 66))
                surface.blit(font_small.render(f"Pigouvian Internalization Tax Gap: ${f0_rec.pigouvian_tax_gap:.2f}", True, (245, 160, 110)), (PANEL_LEFT + 12, cur_y + 86))
            else:
                surface.blit(font_small.render("Tracking enterprise metabolic extraction & unpaid public health burdens.", True, DIM), (PANEL_LEFT + 12, cur_y + 66))
                surface.blit(font_small.render(f"Parasitic Enterprises: {tile_agg.get('parasitic_count', 0)}  •  Restorative: {tile_agg.get('restorative_count', 0)}", True, (160, 180, 195)), (PANEL_LEFT + 12, cur_y + 86))
        except Exception:
            pygame.draw.rect(surface, CARD_BORDER, tc_rect, 1, border_radius=5)
            surface.blit(font_small.render("True Cost & Externalities Ledger", True, (240, 210, 140)), (PANEL_LEFT + 12, cur_y + 6))
            surface.blit(font_small.render("Initializing enterprise accounting...", True, DIM), (PANEL_LEFT + 12, cur_y + 26))

        return

    # 1b. Bailiff & Special Branch Intelligence Dossier Card (Fog of War)
    try:
        from popular_resistance import get_popular_resistance_manager
        res_mgr = get_popular_resistance_manager()
        r_state = res_mgr.get_state(region.name)
        intel = res_mgr.get_player_intelligence_report(region)
        has_agitator = intel.get('leader_known', False)
        has_martyrs = len(getattr(r_state, 'martyrs', [])) > 0
        is_revolting = r_state.enclosure_stage not in ('dormant', 'leveling')

        if has_agitator or has_martyrs or is_revolting:
            dos_h = 76
            dos_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, dos_h)
            pygame.draw.rect(surface, (28, 22, 28), dos_rect, border_radius=5)
            # Amber border if fermenting, Crimson if revolt active
            d_border = (230, 80, 80) if is_revolting else (210, 140, 60)
            pygame.draw.rect(surface, d_border, dos_rect, 1, border_radius=5)

            # Header: Alias & Status
            alias = intel.get('leader_alias', 'Unknown Agitator')
            notoriety = intel.get('leader_notoriety', 'Faint Rumors')
            hdr_txt = f"Dossier: {alias} ({notoriety})"
            surface.blit(font_small.render(hdr_txt, True, (240, 210, 140)), (PANEL_LEFT + 12, cur_y + 5))

            # Line 1: Public atmosphere
            atmo = intel.get('public_atmosphere', 'Quiet')
            surface.blit(font_small.render(f"Mood: {atmo}", True, (200, 200, 210)), (PANEL_LEFT + 12, cur_y + 22))

            # Line 2: Martyrdom Risk Warning
            risk = intel.get('martyrdom_risk_assessment', 'Low')
            r_col = (255, 90, 90) if "HIGH" in risk or "CATASTROPHIC" in risk else ((240, 180, 70) if "Moderate" in risk else (130, 220, 150))
            surface.blit(font_small.render(f"Risk: {risk}", True, r_col), (PANEL_LEFT + 12, cur_y + 38))

            # Line 3: Covert Contract Status
            c_plot = intel.get('covert_plot_status', 'No covert contracts active.')
            if has_martyrs:
                m_names = ", ".join(r_state.martyrs[:2])
                c_plot += f" | Martyrs: {m_names}"
            surface.blit(font_small.render(c_plot, True, (160, 190, 220)), (PANEL_LEFT + 12, cur_y + 54))

            cur_y += dos_h + 8
    except Exception as error:
        global _resistance_dossier_warning_logged
        if not _resistance_dossier_warning_logged:
            _log.warning("Could not render resistance dossier for %s: %s", region.name, error)
            _resistance_dossier_warning_logged = True

    # 2. Scroll controls for Plot List
    scroll = world.get('cadastre_scroll', 0)
    plots = tenure.plots if tenure else []
    
    if not plots:
        surface.blit(font_small.render("No surveyed plots found on this parish.", True, DIM), (PANEL_LEFT + 12, cur_y + 10))
        return

    # Scroll header
    s_lbl = font_small.render(f"Surveyed Parcels ({len(plots)} Plots)", True, (200, 210, 225))
    surface.blit(s_lbl, (PANEL_LEFT + 10, cur_y))
    
    btn_up = (PANEL_LEFT + PANEL_W - 52, cur_y - 2, 22, 18)
    btn_dn = (PANEL_LEFT + PANEL_W - 26, cur_y - 2, 22, 18)
    _draw_btn(surface, btn_up, "▲", font_small, mx, my, enabled=(scroll > 0))
    _draw_btn(surface, btn_dn, "▼", font_small, mx, my, enabled=(scroll + 2 < len(plots)))
    _CADASTRE_BUTTONS.append((btn_up, 'cadastre_scroll_up', None))
    _CADASTRE_BUTTONS.append((btn_dn, 'cadastre_scroll_down', None))

    cur_y += 22

    # 3. Render Visible Plot Cards
    visible_plots = plots[scroll:scroll + 3]
    for plot in visible_plots:
        card_h = 106
        if cur_y + card_h > panel_bottom:
            break

        c_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, card_h)
        pygame.draw.rect(surface, CARD_BG, c_rect, border_radius=5)

        # Border colored by tenure
        b_col = C_COMMONS if plot.tenure == TenureStatus.COMMONS else (C_FEUDAL if plot.tenure == TenureStatus.FEUDAL else C_ENCLOSED)
        pygame.draw.rect(surface, b_col, c_rect, 1, border_radius=5)

        # Line 1: Authentic Plot Name + Fraction
        p_name = plot.display_name or f"Parcel #{plot.plot_id}"
        frac_txt = f"{plot.fraction*100:.0f}% Area"
        surface.blit(font_small.render(p_name, True, (240, 240, 240)), (PANEL_LEFT + 12, cur_y + 6))
        
        # Tenure badge
        t_badge = plot.tenure.value
        t_badge_lbl = font_small.render(f"[{t_badge}]", True, b_col)
        surface.blit(t_badge_lbl, (PANEL_LEFT + PANEL_W - t_badge_lbl.get_width() - 14, cur_y + 6))

        # Line 2: Land Use & Lord (Clean procedural icons, no broken emojis)
        p_type = getattr(plot, 'production_type', 'arable')
        type_col = C_PASTURE if p_type == 'pasture' else C_ARABLE
        type_str = "Pasture (Wool)" if p_type == 'pasture' else "Arable (Grain)"
        from ui_icons import get_icon
        ico_type = get_icon('pasture' if p_type == 'pasture' else 'arable', 13)
        surface.blit(ico_type, (PANEL_LEFT + 12, cur_y + 24))
        surface.blit(font_small.render(f"{type_str}  •  {frac_txt}", True, type_col), (PANEL_LEFT + 28, cur_y + 24))

        lord = next((a for a in region.agents if a.id == plot.lord_id), None)
        lord_str = f"Lord: {getattr(lord, 'name', f'Agent #{plot.lord_id}')} (${lord.cash:.0f})" if lord else "Lord: Crown / Common"
        surface.blit(font_small.render(lord_str, True, DIM), (PANEL_LEFT + 12, cur_y + 40))

        # Line 3: Tenants & Debts
        t_count = len(plot.tenant_ids)
        debts = [d for d in getattr(region, 'enclosure_survey_debts', []) if d.get('plot_id') == plot.plot_id]
        
        t_info = f"Bound Tenants: {t_count}"
        if debts:
            d_first = debts[0]
            t_rem = max(0, d_first['deadline'] - world.get('turn', 0))
            t_info += f"  •  Foreclosure in {t_rem}t ($15 due)"
            surface.blit(font_small.render(t_info, True, (245, 140, 80)), (PANEL_LEFT + 12, cur_y + 56))
        else:
            surface.blit(font_small.render(t_info, True, (160, 200, 220)), (PANEL_LEFT + 12, cur_y + 56))

        # Line 4: Context Action Buttons
        by = cur_y + 76
        if plot.tenure == TenureStatus.FEUDAL:
            fee = calculate_charter_fee(plot)
            can_enc = (lord is not None and lord.cash >= fee)
            b_enc = (PANEL_LEFT + 12, by, 130, 22)
            _draw_btn(surface, b_enc, f"Enclose (${fee:.0f})", font_small, mx, my,
                      enabled=can_enc, color=(240, 140, 70) if can_enc else DIM)
            _CADASTRE_BUTTONS.append((b_enc, 'cadastre_enclose', (region, plot.plot_id)))
        elif plot.tenure == TenureStatus.ENCLOSED:
            # Pasture / Arable Toggle
            is_pas = (p_type == 'pasture')
            b_mode = (PANEL_LEFT + 12, by, 116, 22)
            lbl_mode = "To Arable" if is_pas else "To Pasture"
            _draw_btn(surface, b_mode, lbl_mode, font_small, mx, my, enabled=True, color=(230, 200, 100) if is_pas else (160, 210, 150))
            _CADASTRE_BUTTONS.append((b_mode, 'cadastre_toggle_pasture', (region, plot.plot_id)))

            # Restore Commons Button
            b_rest = (PANEL_LEFT + 134, by, 116, 22)
            _draw_btn(surface, b_rest, "Restore Commons", font_small, mx, my, enabled=True, color=(120, 220, 140))
            _CADASTRE_BUTTONS.append((b_rest, 'cadastre_restore_commons', (region, plot.plot_id)))
        else:
            # Customary Commons
            surface.blit(font_small.render("Traditional usufruct foraging active.", True, (130, 210, 140)), (PANEL_LEFT + 14, by + 4))

        cur_y += card_h + 8

    # Tooltip detection on cadastre action buttons
    if mouse_pos and not world.get('_hovered_left_tooltip'):
        for rect, act_id, payload in _CADASTRE_BUTTONS:
            rx, ry, rw, rh = rect
            if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                from worldview_tooltips import get_button_tooltip_data
                plot_id = payload[1] if isinstance(payload, tuple) and len(payload) > 1 else None
                tdata = get_button_tooltip_data(act_id, world, region=region, plot_id=plot_id)
                if tdata:
                    tdata['btn_rect'] = rect
                    world['_hovered_left_tooltip'] = tdata
                break


def cadastre_panel_hit(pos, world: dict) -> bool:
    """Handle mouse clicks on the Estate Cadastre panel."""
    global _CADASTRE_BUTTONS
    mx, my = pos
    for rect, act_id, payload in _CADASTRE_BUTTONS:
        rx, ry, rw, rh = rect
        if rx <= mx <= rx + rw and ry <= my <= ry + rh:
            if act_id == 'cadastre_subtab_plots':
                world['cadastre_subtab'] = 'plots'
                return True
            elif act_id == 'cadastre_subtab_finance':
                world['cadastre_subtab'] = 'finance'
                return True
            elif act_id == 'cadastre_repair_machinery':
                reg, corp_id = payload
                corp = next((a for a in getattr(reg, 'agents', []) if a.id == corp_id), None)
                if corp:
                    from economy.transformation_graph import TransformationGraph
                    repair_op = TransformationGraph.get_operator('maintain_repair_machinery')
                    turn = int(world.get('turn', 0))
                    if repair_op:
                        res = repair_op.on_execute(corp, reg, turn)
                        succ = res.get('success', False)
                        if succ:
                            corp.machinery_broken = False
                            corp.broken_machinery = 0
                            corp.machinery_wear = 0
                        msg = res.get('message', 'Machinery repaired')
                        world['policy_feedback'] = (msg, GREEN if succ else RED)
                        try:
                            from worldview_engine import ticker_push
                            ticker_push(world, turn, 'REPAIR', msg, (100, 220, 150) if succ else RED)
                        except ImportError:
                            pass
                return True
            elif act_id == 'cadastre_charter_voyage':
                reg, elite_id = payload
                elite = next((a for a in getattr(reg, 'agents', []) if a.id == elite_id), None)
                trade_mgr = getattr(reg, 'trade_manager', None)
                if not trade_mgr:
                    state = world.get('scenario_state', {})
                    trade_mgr = state.get('trade_manager_ref')
                if elite and trade_mgr:
                    target_cid = next((cid for cid, c in trade_mgr.circuits.items() if c.export_good == 'cloth'), list(trade_mgr.circuits.keys())[0])
                    res = trade_mgr.charter_voyage(elite, reg, target_cid, is_pioneer=True)
                    succ = res.get('success', False)
                    msg = res.get('message', f"Merchant voyage chartered on {target_cid}!")
                    world['policy_feedback'] = (msg, GREEN if succ else RED)
                    try:
                        from worldview_engine import ticker_push
                        ticker_push(world, int(world.get('turn', 0)), 'VOYAGE', msg, (100, 200, 255) if succ else RED)
                    except ImportError:
                        pass
                return True
            elif act_id == 'cadastre_hire_guards':
                reg, firm_id = payload
                ludd_mgr = world.get('scenario_state', {}).get('luddite_manager_ref') or getattr(reg, 'luddite_manager', None)
                firm = next((a for a in getattr(reg, 'agents', []) if a.id == firm_id), None)
                if firm and ludd_mgr:
                    res = ludd_mgr.hire_factory_guards(firm, reg, count=1)
                    succ = res.get('success', False)
                    msg = res.get('message', "Hired factory guard")
                    world['policy_feedback'] = (msg, GREEN if succ else RED)
                    try:
                        from worldview_engine import ticker_push
                        ticker_push(world, int(world.get('turn', 0)), 'GUARDS', msg, (240, 150, 80) if succ else RED)
                    except ImportError:
                        pass
                return True
            elif act_id == 'cadastre_bread_relief':
                reg, firm_id = payload
                ludd_mgr = world.get('scenario_state', {}).get('luddite_manager_ref') or getattr(reg, 'luddite_manager', None)
                firm = next((a for a in getattr(reg, 'agents', []) if a.id == firm_id), None)
                if firm and ludd_mgr:
                    res = ludd_mgr.grant_parish_bread_relief(firm, reg, amount=15.0)
                    succ = res.get('success', False)
                    msg = res.get('message', "Granted bread relief")
                    world['policy_feedback'] = (msg, GREEN if succ else RED)
                    try:
                        from worldview_engine import ticker_push
                        ticker_push(world, int(world.get('turn', 0)), 'RELIEF', msg, (100, 220, 150) if succ else RED)
                    except ImportError:
                        pass
                return True
            elif act_id == 'cadastre_scroll_up':
                world['cadastre_scroll'] = max(0, world.get('cadastre_scroll', 0) - 1)
                return True
            elif act_id == 'cadastre_scroll_down':
                world['cadastre_scroll'] = world.get('cadastre_scroll', 0) + 1
                return True
            elif act_id == 'cadastre_enclose':
                reg, plot_id = payload
                from enclosure import execute_enclosure
                ok, msg, _evs = execute_enclosure(reg, plot_id, world.get('turn', 0))
                world['policy_feedback'] = (msg, (230, 140, 70) if ok else RED)
                try:
                    from worldview_engine import ticker_push
                    ticker_push(world, world.get('turn', 0), 'ENCLOSURE', msg, (230, 140, 70))
                except ImportError:
                    pass
                return True
            elif act_id == 'cadastre_toggle_pasture':
                reg, plot_id = payload
                plot = reg.tenure.find_plot(plot_id) if hasattr(reg, 'tenure') else None
                if plot:
                    new_t = 'pasture' if getattr(plot, 'production_type', 'arable') != 'pasture' else 'arable'
                    reg.tenure.convert_production_type(plot_id, new_t, world.get('turn', 0))
                    msg = f"Plot {plot.display_name} switched to {new_t.upper()}."
                    if new_t == 'pasture':
                        msg += " 75% tenants dispossessed."
                    world['policy_feedback'] = (msg, (210, 180, 100))
                    try:
                        from worldview_engine import ticker_push
                        ticker_push(world, world.get('turn', 0), 'LAND_USE', msg, (210, 180, 100))
                    except ImportError:
                        pass
                return True
            elif act_id == 'cadastre_restore_commons':
                reg, plot_id = payload
                if hasattr(reg, 'tenure'):
                    reg.tenure.revert_plot_to_commons(plot_id, world.get('turn', 0))
                    reg.unrest_level = max(0.0, getattr(reg, 'unrest_level', 0.0) - 0.25)
                    msg = f"Plot restored to Customary Commons on {reg.name}!"
                    world['policy_feedback'] = (msg, GREEN)
                    try:
                        from worldview_engine import ticker_push
                        ticker_push(world, world.get('turn', 0), 'COMMONS', msg, (120, 220, 140))
                    except ImportError:
                        pass
                return True
    return False
