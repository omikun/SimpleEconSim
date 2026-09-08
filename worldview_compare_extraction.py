"""
worldview_compare_extraction.py — Comparison Modal Tab 4: Class Wealth Extraction & Attrition.

Displays:
1. Wealth transfers from serfs to lords (in-kind Feudal Tribute valued at market price).
2. Wealth transfers from tenants to landlords (Ground Rent on enclosed plots).
3. Wealth transfers from wage laborers to capitalists (Surplus Value s/v).
4. Multi-tier statutory tax extraction captured across Municipal, Provincial, and National Sovereign governments.
5. Systemic mental (4D Alienation) and physical (bodily wear & tear, accidents) health degradation.
6. Interactive scope drilldown: [ By Country ], [ By Province ], [ By City / Tile ].
7. Analytical stacked extraction composition charts and health attrition curves.
"""

import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT
from worldview_map import (
    NATION_COLORS, TEXT, DIM, RED, GREEN, ACCENT, PROVINCE_COLORS
)

ROW_BG1 = (24, 24, 34)
ROW_BG2 = (28, 28, 40)
SEC_BG = (32, 32, 46)
CARD_BG = (22, 24, 36)
CARD_BORDER = (50, 55, 75)

COL_TRIBUTE = (220, 185, 65)     # Warm gold
COL_RENT = (235, 125, 55)        # Orange
COL_SURPLUS = (225, 65, 75)      # Crimson
COL_TAX = (75, 155, 235)         # Blue
COL_HEALTH = (235, 80, 90)       # Coral Red
COL_ALIEN = (175, 105, 235)      # Purple


def _get_font(size):
    from worldview_ui import get_font
    return get_font(size)


def _safe_last(lst, default=0.0):
    if not lst:
        return default
    val = lst[-1]
    return val if val is not None else default


def _get_tile_stats(tile):
    """Aggregate per-tile wealth extraction, tax distribution, and health metrics."""
    tribute = _safe_last(getattr(tile, 'tribute_collected_log', []), 0.0)
    rent = _safe_last(getattr(tile, 'rent_collected_log', []), 0.0)
    rent_arrears = _safe_last(getattr(tile, 'rent_arrears_log', []), 0.0)
    surplus = _safe_last(getattr(tile, 'surplus_value_log', []), 0.0)
    rate_expl = _safe_last(getattr(tile, 'rate_of_exploitation_log', []), 0.0)
    shift_hours = _safe_last(getattr(tile, 'avg_shift_hours_log', []), 8.0)

    # Taxes
    tax_dist = _safe_last(getattr(tile, 'tax_distribution_log', []), {})
    if isinstance(tax_dist, dict):
        tax_total = tax_dist.get('total', 0.0)
        tax_muni = tax_dist.get('municipal', 0.0)
        tax_prov = tax_dist.get('provincial', 0.0)
        tax_nat = tax_dist.get('national', 0.0)
    else:
        tax_total = tax_muni = tax_prov = tax_nat = 0.0

    # Systemic Health & Alienation
    alien = _safe_last(getattr(tile, 'avg_alienation_log', []), 0.0)
    attrition = _safe_last(getattr(tile, 'avg_health_attrition_log', []), 0.0)
    accidents = _safe_last(getattr(tile, 'workplace_accidents_log', []), 0)
    strikers = _safe_last(getattr(tile, 'strikers_log', []), 0)
    pop = getattr(tile, 'total_population', [])
    pop_count = pop[-1] if pop else len(getattr(tile, 'agents', []))

    total_class_ext = tribute + rent + surplus

    return {
        'tile': tile,
        'name': getattr(tile, 'display_name', tile.name),
        'pop': max(1, pop_count),
        'tribute': tribute,
        'rent': rent,
        'rent_arrears': rent_arrears,
        'surplus': surplus,
        'rate_expl': rate_expl,
        'shift_hours': shift_hours,
        'tax_total': tax_total,
        'tax_muni': tax_muni,
        'tax_prov': tax_prov,
        'tax_nat': tax_nat,
        'alien': alien,
        'attrition': attrition,
        'accidents': accidents,
        'strikers': strikers,
        'total_class_ext': total_class_ext,
    }


def draw_tab4_extraction(surface, world, box_x, start_y, box_w, box_h, font, cell_font, section_font, mouse_pos=None):
    """Render Tab 4: Class Wealth Extraction, Multi-Tier Taxes, and Attrition Analytics."""
    nations = world.get('nations', [])
    if not nations:
        return

    active_scope = world.get('compare_ext_scope', 'country')
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    # 1. Scope Sub-Selectors: [ By Country ]  [ By Province ]  [ By City / Tile ]
    gx = box_x + 20
    gy = start_y - 8
    scopes = [
        ('country', 'By Country'),
        ('province', 'By Province'),
        ('city', 'By City / Tile'),
    ]

    for s_key, s_label in scopes:
        is_sel = (s_key == active_scope)
        rect = (gx, gy, 120, 24)
        is_hov = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        bg = ACCENT if is_sel else ((44, 44, 58) if is_hov else (30, 30, 40))
        txt_c = (20, 20, 24) if is_sel else ((255, 255, 255) if is_hov else TEXT)
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        pygame.draw.rect(surface, (80, 80, 100), rect, 1, border_radius=4)
        tsurf = cell_font.render(s_label, True, txt_c)
        surface.blit(tsurf, tsurf.get_rect(center=(gx + 60, gy + 12)))
        gx += 130

    # Mode Sub-Selectors: [ Data Table ]  [ Circuit of Capital (M->C->P->C'->M') & TRPF ]
    active_mode = world.get('compare_ext_mode', 'table')
    mode_btns = [
        ('table', 'Data Table', 120),
        ('circuit', "Capital Circuit & TRPF Curve", 220),
    ]
    mx_x = box_x + 430
    for m_key, m_label, m_w in mode_btns:
        is_sel = (m_key == active_mode)
        rect = (mx_x, gy, m_w, 24)
        is_hov = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        bg = (235, 195, 75) if is_sel else ((44, 44, 58) if is_hov else (30, 30, 40))
        txt_c = (20, 20, 24) if is_sel else ((255, 255, 255) if is_hov else TEXT)
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        pygame.draw.rect(surface, (140, 120, 60) if is_sel else (80, 80, 100), rect, 1, border_radius=4)
        tsurf = cell_font.render(m_label, True, txt_c)
        surface.blit(tsurf, tsurf.get_rect(center=(mx_x + m_w // 2, gy + 12)))
        mx_x += m_w + 10

    if active_mode == 'circuit':
        from worldview_vis_circuits import draw_circuit_of_capital_sankey
        draw_circuit_of_capital_sankey(surface, world, box_x, start_y + 16, box_w, box_h - (start_y + 16 - 20) - 20, font, cell_font, section_font, mouse_pos=mouse_pos)
        return

    y = start_y + 24

    # Collect and aggregate tile stats
    all_tile_stats = []
    prov_aggregates = []
    nation_aggregates = []

    for n in nations:
        n_tiles = n.tiles
        n_t_stats = [_get_tile_stats(t) for t in n_tiles]
        all_tile_stats.extend(n_t_stats)

        # Aggregate for nation
        n_tribute = sum(s['tribute'] for s in n_t_stats)
        n_rent = sum(s['rent'] for s in n_t_stats)
        n_surplus = sum(s['surplus'] for s in n_t_stats)
        n_tax_tot = sum(s['tax_total'] for s in n_t_stats)
        n_tax_muni = sum(s['tax_muni'] for s in n_t_stats)
        n_tax_prov = sum(s['tax_prov'] for s in n_t_stats)
        n_tax_nat = sum(s['tax_nat'] for s in n_t_stats)
        n_pop = sum(s['pop'] for s in n_t_stats)
        n_alien = (sum(s['alien'] * s['pop'] for s in n_t_stats) / max(1, n_pop)) if n_t_stats else 0.0
        n_attr = (sum(s['attrition'] * s['pop'] for s in n_t_stats) / max(1, n_pop)) if n_t_stats else 0.0
        n_acc = sum(s['accidents'] for s in n_t_stats)
        n_expl = (sum(s['rate_expl'] for s in n_t_stats) / len(n_t_stats)) if n_t_stats else 0.0

        nation_aggregates.append({
            'name': n.name,
            'color': NATION_COLORS.get(n.name, TEXT),
            'pop': n_pop,
            'tribute': n_tribute,
            'rent': n_rent,
            'surplus': n_surplus,
            'tax_total': n_tax_tot,
            'tax_muni': n_tax_muni,
            'tax_prov': n_tax_prov,
            'tax_nat': n_tax_nat,
            'total_class_ext': n_tribute + n_rent + n_surplus,
            'rate_expl': n_expl,
            'alien': n_alien,
            'attrition': n_attr,
            'accidents': n_acc,
        })

        # Aggregate provinces
        for p_idx, prov in enumerate(n.provinces):
            p_tiles = prov.tiles
            if not p_tiles:
                continue
            p_t_stats = [_get_tile_stats(t) for t in p_tiles]
            p_pop = sum(s['pop'] for s in p_t_stats)
            p_tribute = sum(s['tribute'] for s in p_t_stats)
            p_rent = sum(s['rent'] for s in p_t_stats)
            p_surplus = sum(s['surplus'] for s in p_t_stats)
            p_tax_tot = sum(s['tax_total'] for s in p_t_stats)
            p_tax_muni = sum(s['tax_muni'] for s in p_t_stats)
            p_tax_prov = sum(s['tax_prov'] for s in p_t_stats)
            p_tax_nat = sum(s['tax_nat'] for s in p_t_stats)
            p_alien = (sum(s['alien'] * s['pop'] for s in p_t_stats) / max(1, p_pop)) if p_t_stats else 0.0
            p_attr = (sum(s['attrition'] * s['pop'] for s in p_t_stats) / max(1, p_pop)) if p_t_stats else 0.0
            p_acc = sum(s['accidents'] for s in p_t_stats)
            p_expl = (sum(s['rate_expl'] for s in p_t_stats) / len(p_t_stats)) if p_t_stats else 0.0

            p_color = PROVINCE_COLORS[p_idx % len(PROVINCE_COLORS)] if PROVINCE_COLORS else NATION_COLORS.get(n.name, TEXT)
            prov_aggregates.append({
                'name': prov.name,
                'nation': n.name,
                'color': p_color,
                'pop': p_pop,
                'tribute': p_tribute,
                'rent': p_rent,
                'surplus': p_surplus,
                'tax_total': p_tax_tot,
                'tax_muni': p_tax_muni,
                'tax_prov': p_tax_prov,
                'tax_nat': p_tax_nat,
                'total_class_ext': p_tribute + p_rent + p_surplus,
                'rate_expl': p_expl,
                'alien': p_alien,
                'attrition': p_attr,
                'accidents': p_acc,
            })

    # Empire totals
    tot_tribute = sum(d['tribute'] for d in nation_aggregates)
    tot_rent = sum(d['rent'] for d in nation_aggregates)
    tot_surplus = sum(d['surplus'] for d in nation_aggregates)
    tot_ext = tot_tribute + tot_rent + tot_surplus
    tot_tax = sum(d['tax_total'] for d in nation_aggregates)
    tot_muni_tax = sum(d['tax_muni'] for d in nation_aggregates)
    tot_prov_tax = sum(d['tax_prov'] for d in nation_aggregates)
    tot_nat_tax = sum(d['tax_nat'] for d in nation_aggregates)
    world_pop = sum(d['pop'] for d in nation_aggregates)
    avg_alien = (sum(d['alien'] * d['pop'] for d in nation_aggregates) / max(1, world_pop)) if world_pop else 0.0
    avg_attr = (sum(d['attrition'] * d['pop'] for d in nation_aggregates) / max(1, world_pop)) if world_pop else 0.0
    tot_accidents = sum(d['accidents'] for d in nation_aggregates)

    # 2. KPI Top Scorecards Row (6 Cards)
    card_w = (box_w - 40 - 5 * 10) // 6
    card_h = 60
    cx = box_x + 20

    kpis = [
        ("FEUDAL TRIBUTE (SERFS)", f"${tot_tribute:,.1f}/t", f"{tot_tribute/max(0.1, tot_ext)*100:.1f}% share", COL_TRIBUTE),
        ("GROUND RENT (TENANTS)", f"${tot_rent:,.1f}/t", f"{tot_rent/max(0.1, tot_ext)*100:.1f}% share", COL_RENT),
        ("SURPLUS VALUE (s/v)", f"${tot_surplus:,.1f}/t", f"{tot_surplus/max(0.1, tot_ext)*100:.1f}% share", COL_SURPLUS),
        ("TOTAL CLASS EXTRACTION", f"${tot_ext:,.1f}/t", f"${tot_ext/max(1, world_pop):.2f}/capita", (255, 220, 120)),
        ("MULTI-TIER TAX REVENUE", f"${tot_tax:,.1f}/t", f"M:{tot_muni_tax:.0f} P:{tot_prov_tax:.0f} N:{tot_nat_tax:.0f}", COL_TAX),
        ("SYSTEMIC ATTRITION & WEAR", f"{avg_attr:.2f} Wear", f"Alien: {avg_alien*100:.0f}% | {tot_accidents} Inj", COL_HEALTH),
    ]

    for title, val_txt, sub_txt, color in kpis:
        c_rect = (cx, y, card_w, card_h)
        pygame.draw.rect(surface, CARD_BG, c_rect, border_radius=6)
        pygame.draw.rect(surface, CARD_BORDER, c_rect, 1, border_radius=6)

        surface.blit(_get_font(12).render(title, True, DIM), (cx + 8, y + 6))
        surface.blit(_get_font(20).render(val_txt, True, color), (cx + 8, y + 22))
        surface.blit(_get_font(12).render(sub_txt, True, (160, 160, 180)), (cx + 8, y + 42))
        cx += card_w + 10

    y += card_h + 14

    # 3. Comparative Extraction & Attrition Table
    cols = [
        ("Jurisdiction / Entity", 170),
        ("Tribute (Lords)", 115),
        ("Rent (Landlords)", 115),
        ("Surplus Value (s/v)", 125),
        ("Exploit (s/v)", 85),
        ("Municipal Tax", 100),
        ("Province Tax", 100),
        ("Sovereign Tax", 100),
        ("Total Extraction", 125),
        ("Physical Wear", 95),
        ("Alienation %", 90),
    ]

    # Header row
    hdr_rect = (box_x + 16, y, box_w - 32, 24)
    pygame.draw.rect(surface, (34, 34, 48), hdr_rect)
    tx = box_x + 24
    for title, width in cols:
        surface.blit(cell_font.render(title, True, ACCENT), (tx, y + 4))
        tx += width
    y += 26

    # Choose rows based on active_scope
    rows_data = []
    if active_scope == 'country':
        for d in nation_aggregates:
            rows_data.append({
                'label': d['name'],
                'color': d['color'],
                'tribute': d['tribute'],
                'rent': d['rent'],
                'surplus': d['surplus'],
                'rate_expl': d['rate_expl'],
                'tax_muni': d['tax_muni'],
                'tax_prov': d['tax_prov'],
                'tax_nat': d['tax_nat'],
                'total_ext': d['total_class_ext'],
                'attr': d['attrition'],
                'acc': d['accidents'],
                'alien': d['alien'],
            })
    elif active_scope == 'province':
        for d in prov_aggregates:
            rows_data.append({
                'label': f"{d['name']} ({d['nation'][:3]})",
                'color': d['color'],
                'tribute': d['tribute'],
                'rent': d['rent'],
                'surplus': d['surplus'],
                'rate_expl': d['rate_expl'],
                'tax_muni': d['tax_muni'],
                'tax_prov': d['tax_prov'],
                'tax_nat': d['tax_nat'],
                'total_ext': d['total_class_ext'],
                'attr': d['attrition'],
                'acc': d['accidents'],
                'alien': d['alien'],
            })
    else:  # 'city'
        sorted_tiles = sorted(all_tile_stats, key=lambda s: s['total_class_ext'], reverse=True)
        for d in sorted_tiles[:14]:  # Top 14 cities
            nat_name = getattr(d['tile'].owner_nation, 'name', '-') if getattr(d['tile'], 'owner_nation', None) else '-'
            rows_data.append({
                'label': f"{d['name']} [{nat_name[:3]}]",
                'color': NATION_COLORS.get(nat_name, TEXT),
                'tribute': d['tribute'],
                'rent': d['rent'],
                'surplus': d['surplus'],
                'rate_expl': d['rate_expl'],
                'tax_muni': d['tax_muni'],
                'tax_prov': d['tax_prov'],
                'tax_nat': d['tax_nat'],
                'total_ext': d['total_class_ext'],
                'attr': d['attrition'],
                'acc': d['accidents'],
                'alien': d['alien'],
            })

    row_h = 22
    for idx, row in enumerate(rows_data):
        r_rect = (box_x + 16, y, box_w - 32, row_h)
        bg = ROW_BG1 if idx % 2 == 0 else ROW_BG2
        pygame.draw.rect(surface, bg, r_rect)

        tx = box_x + 24
        # Jurisdiction
        lbl = cell_font.render(row['label'], True, row['color'])
        surface.blit(lbl, (tx, y + 3))
        tx += cols[0][1]

        # Tribute
        surface.blit(cell_font.render(f"${row['tribute']:,.1f}", True, COL_TRIBUTE if row['tribute'] > 0 else DIM), (tx, y + 3))
        tx += cols[1][1]

        # Rent
        surface.blit(cell_font.render(f"${row['rent']:,.1f}", True, COL_RENT if row['rent'] > 0 else DIM), (tx, y + 3))
        tx += cols[2][1]

        # Surplus Value
        surface.blit(cell_font.render(f"${row['surplus']:,.1f}", True, COL_SURPLUS if row['surplus'] > 0 else DIM), (tx, y + 3))
        tx += cols[3][1]

        # Exploitation Rate
        expl_txt = f"{row['rate_expl']*100:.0f}%" if row['rate_expl'] > 0 else "-"
        expl_c = RED if row['rate_expl'] > 1.0 else (ACCENT if row['rate_expl'] > 0.4 else DIM)
        surface.blit(cell_font.render(expl_txt, True, expl_c), (tx, y + 3))
        tx += cols[4][1]

        # Municipal Tax
        surface.blit(cell_font.render(f"${row['tax_muni']:,.1f}", True, COL_TAX if row['tax_muni'] > 0 else DIM), (tx, y + 3))
        tx += cols[5][1]

        # Provincial Tax
        surface.blit(cell_font.render(f"${row['tax_prov']:,.1f}", True, COL_TAX if row['tax_prov'] > 0 else DIM), (tx, y + 3))
        tx += cols[6][1]

        # Sovereign Tax
        surface.blit(cell_font.render(f"${row['tax_nat']:,.1f}", True, COL_TAX if row['tax_nat'] > 0 else DIM), (tx, y + 3))
        tx += cols[7][1]

        # Total Extraction
        surface.blit(cell_font.render(f"${row['total_ext']:,.1f}", True, (255, 235, 150)), (tx, y + 3))
        tx += cols[8][1]

        # Physical Wear (score + accidents)
        attr_txt = f"{row['attr']:.2f}" + (f" ({row['acc']}c)" if row['acc'] > 0 else "")
        attr_c = RED if row['attr'] > 0.8 or row['acc'] > 0 else ((240, 180, 80) if row['attr'] > 0.3 else GREEN)
        surface.blit(cell_font.render(attr_txt, True, attr_c), (tx, y + 3))
        tx += cols[9][1]

        # Alienation %
        alien_pct = row['alien'] * 100.0
        alien_c = RED if alien_pct > 65 else ((240, 180, 80) if alien_pct > 35 else GREEN)
        surface.blit(cell_font.render(f"{alien_pct:.1f}%", True, alien_c), (tx, y + 3))

        y += row_h

    y += 14

    # 4. Analytical Charts Section (2 Charts Side-by-Side)
    chart_y = y
    half_w = (box_w - 50) // 2
    box_y = 20
    chart_h = max(110, (box_y + box_h) - chart_y - 20)

    # --- Chart A: Stacked Wealth Extraction Composition (Tribute vs Rent vs Surplus vs Taxes) ---
    c1_rect = (box_x + 16, chart_y, half_w, chart_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=6)

    surface.blit(section_font.render("Wealth Extraction Channels (Tribute / Rent / s/v / Taxes)", True, ACCENT), (box_x + 26, chart_y + 8))

    # Legend
    leg_x = box_x + 26
    leg_y = chart_y + 28
    legends = [("Tribute", COL_TRIBUTE), ("Rent", COL_RENT), ("Surplus s/v", COL_SURPLUS), ("Gov Taxes", COL_TAX)]
    for l_lbl, l_col in legends:
        pygame.draw.rect(surface, l_col, (leg_x, leg_y + 2, 10, 10), border_radius=2)
        surface.blit(_get_font(12).render(l_lbl, True, TEXT), (leg_x + 14, leg_y))
        leg_x += 80

    # Draw stacked bars for top entities
    bar_top_y = leg_y + 20
    bar_avail_h = chart_h - 55
    sorted_tiles = sorted(all_tile_stats, key=lambda s: s['total_class_ext'], reverse=True)
    entities_to_plot = nation_aggregates if active_scope == 'country' else (prov_aggregates[:8] if active_scope == 'province' else sorted_tiles[:8])
    num_e = max(1, len(entities_to_plot))
    bar_row_h = min(22, bar_avail_h // num_e)

    for i, ent in enumerate(entities_to_plot):
        by = bar_top_y + i * bar_row_h
        ent_lbl = _get_font(12).render(ent['name'][:14], True, ent.get('color', TEXT))
        surface.blit(ent_lbl, (box_x + 26, by + 1))

        # Values
        trib = ent.get('tribute', 0.0)
        rnt = ent.get('rent', 0.0)
        surp = ent.get('surplus', 0.0)
        txs = ent.get('tax_total', 0.0)
        sum_val = trib + rnt + surp + txs

        bar_x = box_x + 130
        max_bar_w = half_w - 145
        if sum_val > 0:
            w_trib = int((trib / sum_val) * max_bar_w)
            w_rnt = int((rnt / sum_val) * max_bar_w)
            w_surp = int((surp / sum_val) * max_bar_w)
            w_txs = max_bar_w - w_trib - w_rnt - w_surp

            cur_bx = bar_x
            if w_trib > 0:
                pygame.draw.rect(surface, COL_TRIBUTE, (cur_bx, by + 2, w_trib, bar_row_h - 5))
                cur_bx += w_trib
            if w_rnt > 0:
                pygame.draw.rect(surface, COL_RENT, (cur_bx, by + 2, w_rnt, bar_row_h - 5))
                cur_bx += w_rnt
            if w_surp > 0:
                pygame.draw.rect(surface, COL_SURPLUS, (cur_bx, by + 2, w_surp, bar_row_h - 5))
                cur_bx += w_surp
            if w_txs > 0:
                pygame.draw.rect(surface, COL_TAX, (cur_bx, by + 2, w_txs, bar_row_h - 5))
        else:
            pygame.draw.rect(surface, (40, 42, 55), (bar_x, by + 2, max_bar_w, bar_row_h - 5))

    # --- Chart B: Systemic Health & Alienation Curves ---
    c2_x = box_x + 26 + half_w
    c2_rect = (c2_x, chart_y, half_w - 10, chart_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=6)

    surface.blit(section_font.render("Systemic Health Wear vs 4D Alienation Spectrum", True, ACCENT), (c2_x + 10, chart_y + 8))

    # Legend
    leg2_x = c2_x + 10
    leg2_y = chart_y + 28
    legends2 = [("Mental Alienation %", COL_ALIEN), ("Bodily Wear & Tear", COL_HEALTH)]
    for l_lbl, l_col in legends2:
        pygame.draw.rect(surface, l_col, (leg2_x, leg2_y + 2, 10, 10), border_radius=2)
        surface.blit(_get_font(12).render(l_lbl, True, TEXT), (leg2_x + 14, leg2_y))
        leg2_x += 140

    for i, ent in enumerate(entities_to_plot):
        by = bar_top_y + i * bar_row_h
        ent_lbl = _get_font(12).render(ent['name'][:14], True, ent.get('color', TEXT))
        surface.blit(ent_lbl, (c2_x + 10, by + 1))

        bar_x = c2_x + 115
        max_bar_w = half_w - 140

        alien_w = int(min(1.0, ent.get('alien', 0.0)) * max_bar_w)
        attr_w = int(min(1.0, ent.get('attrition', 0.0) / 2.0) * max_bar_w)

        # Dual thin bars
        b_h = max(4, (bar_row_h - 6) // 2)
        pygame.draw.rect(surface, (38, 40, 52), (bar_x, by + 2, max_bar_w, b_h))
        if alien_w > 0:
            pygame.draw.rect(surface, COL_ALIEN, (bar_x, by + 2, alien_w, b_h))

        pygame.draw.rect(surface, (38, 40, 52), (bar_x, by + 3 + b_h, max_bar_w, b_h))
        if attr_w > 0:
            pygame.draw.rect(surface, COL_HEALTH, (bar_x, by + 3 + b_h, attr_w, b_h))
