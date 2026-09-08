"""
worldview_compare_protest.py — Comparison Modal Tab 5: Protest Energy & Grievance Sources.

Displays:
1. Origin and distribution of protest energy across the realm.
2. Percentage and raw breakdown by grievance sources:
   - Overworked Shifts (excessive shift hours > 8h up to 16h).
   - Precariousness due to Rent Extraction & Commons Enclosure Dispossession.
   - Food Deprivation / Starvation.
   - Workplace Resistance (wildcat strikes & machinery casualties).
   - State Taxes & Repression Trauma.
   - Wealth Inequality (Gini).
3. Interactive drilldown: [ By Country ], [ By Province ], [ By City / Tile ].
4. 100% proportional stacked grievance breakdown bars and territorial protest ranking heatmap.
"""

import pygame
from worldview_camera import WIDTH, HEIGHT
from worldview_map import (
    NATION_COLORS, TEXT, DIM, RED, GREEN, ACCENT, PROVINCE_COLORS
)

ROW_BG1 = (24, 24, 34)
ROW_BG2 = (28, 28, 40)
SEC_BG = (32, 32, 46)
CARD_BG = (22, 24, 36)
CARD_BORDER = (50, 55, 75)

COL_OVERWORK = (235, 70, 70)      # Crimson Red
COL_ENCLOSURE = (240, 140, 50)    # Orange
COL_HUNGER = (235, 210, 60)       # Amber Gold
COL_STRIKES = (180, 90, 220)      # Purple / Amethyst
COL_STATE = (70, 150, 230)        # Blue
COL_INEQ = (80, 210, 140)         # Mint Green


def _get_font(size):
    from worldview_ui import get_font
    return get_font(size)


def _safe_last(lst, default=None):
    if not lst:
        return default
    val = lst[-1]
    return val if val is not None else default


def _extract_tile_grievances(tile):
    """Retrieve or compute normalized grievance source breakdowns for a tile."""
    # Check if logged in grievance_sources_log
    g_log = getattr(tile, 'grievance_sources_log', [])
    last_entry = _safe_last(g_log)

    protest_e = _safe_last(getattr(tile, 'protest_energy_log', []), 0.0)

    if last_entry and isinstance(last_entry, dict) and 'raw' in last_entry:
        raw = last_entry['raw']
    else:
        # Fallback estimation from tile state if stepped prior to logging
        shifts = getattr(tile, 'avg_shift_hours_log', [])
        avg_s = shifts[-1] if shifts else 8.0
        shift_s = min(2.0, max(0.0, (avg_s - 8.0) / 4.0))

        evic = sum(a.mem_avg('mem_eviction', 0.0) for a in getattr(tile, 'agents', []) if not getattr(a, 'is_corporation', False) and not getattr(a, 'is_government', False))
        evic_s = min(2.5, evic / 40.0) * 1.5

        hungry_count = sum(1 for a in getattr(tile, 'agents', []) if getattr(a, 'hungry_steps', 0) > 0)
        pop_count = max(1, len(getattr(tile, 'agents', [])))
        hunger_s = min(3.0, (hungry_count / pop_count) * 4.0)

        acc = _safe_last(getattr(tile, 'workplace_accidents_log', []), 0)
        strikers = _safe_last(getattr(tile, 'strikers_log', []), 0)
        labor_s = min(2.0, acc * 0.4) + min(2.5, strikers / 8.0)

        tax_rate = getattr(getattr(tile, 'gov', None), 'tax_rate', 0.15)
        raw = {
            'overworked': float(shift_s),
            'rent_enclosure': float(evic_s),
            'hunger': float(hunger_s),
            'labor_resistance': float(labor_s),
            'unemployment': 0.1,
            'tax': float(tax_rate),
            'repression': 0.0,
            'inequality': 0.15,
        }

    tot = sum(raw.values())
    pct = {k: (v / tot * 100.0) if tot > 0 else 0.0 for k, v in raw.items()}

    # Determine dominant driver
    dominant = max(raw.items(), key=lambda x: x[1])[0] if tot > 0 else 'calm'
    driver_labels = {
        'overworked': 'Overworked Shifts',
        'rent_enclosure': 'Rent & Enclosure',
        'hunger': 'Food Deprivation',
        'labor_resistance': 'Strikes & Casualties',
        'tax': 'Taxation Burden',
        'repression': 'State Repression',
        'inequality': 'Wealth Inequality',
        'unemployment': 'Unemployment',
        'calm': 'Peaceful / Minimal',
    }

    return {
        'tile': tile,
        'name': getattr(tile, 'display_name', tile.name),
        'pop': max(1, len(getattr(tile, 'agents', []))),
        'protest': protest_e,
        'raw': raw,
        'pct': pct,
        'total': tot,
        'dominant': driver_labels.get(dominant, dominant),
    }


def draw_tab5_protest(surface, world, box_x, start_y, box_w, box_h, font, cell_font, section_font, mouse_pos=None):
    """Render Tab 5: Protest Energy & Grievance Sources Analytics."""
    nations = world.get('nations', [])
    if not nations:
        return

    active_scope = world.get('compare_protest_scope', 'country')
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

    y = start_y + 24

    # Aggregate tile grievances
    all_tile_grievances = []
    prov_aggregates = []
    nation_aggregates = []

    for n in nations:
        n_tiles = n.tiles
        n_t_g = [_extract_tile_grievances(t) for t in n_tiles]
        all_tile_grievances.extend(n_t_g)

        n_pop = sum(g['pop'] for g in n_t_g)
        n_protest = (sum(g['protest'] * g['pop'] for g in n_t_g) / max(1, n_pop)) if n_t_g else 0.0

        n_raw = {}
        for key in ['overworked', 'rent_enclosure', 'hunger', 'labor_resistance', 'tax', 'repression', 'inequality', 'unemployment']:
            n_raw[key] = sum(g['raw'].get(key, 0.0) for g in n_t_g)
        n_tot = sum(n_raw.values())
        n_pct = {k: (v / n_tot * 100.0) if n_tot > 0 else 0.0 for k, v in n_raw.items()}
        dom_k = max(n_raw.items(), key=lambda x: x[1])[0] if n_tot > 0 else 'calm'
        dom_labels = {'overworked': 'Overworked Shifts', 'rent_enclosure': 'Rent & Enclosure', 'hunger': 'Food Deprivation', 'labor_resistance': 'Strikes & Casualties', 'tax': 'Taxes', 'repression': 'Repression', 'inequality': 'Inequality', 'unemployment': 'Unemployment', 'calm': 'Peaceful'}

        nation_aggregates.append({
            'name': n.name,
            'color': NATION_COLORS.get(n.name, TEXT),
            'pop': n_pop,
            'protest': n_protest,
            'raw': n_raw,
            'pct': n_pct,
            'total': n_tot,
            'dominant': dom_labels.get(dom_k, dom_k),
        })

        for p_idx, prov in enumerate(n.provinces):
            p_tiles = prov.tiles
            if not p_tiles:
                continue
            p_t_g = [_extract_tile_grievances(t) for t in p_tiles]
            p_pop = sum(g['pop'] for g in p_t_g)
            p_protest = (sum(g['protest'] * g['pop'] for g in p_t_g) / max(1, p_pop)) if p_t_g else 0.0

            p_raw = {}
            for key in ['overworked', 'rent_enclosure', 'hunger', 'labor_resistance', 'tax', 'repression', 'inequality', 'unemployment']:
                p_raw[key] = sum(g['raw'].get(key, 0.0) for g in p_t_g)
            p_tot = sum(p_raw.values())
            p_pct = {k: (v / p_tot * 100.0) if p_tot > 0 else 0.0 for k, v in p_raw.items()}
            dom_p = max(p_raw.items(), key=lambda x: x[1])[0] if p_tot > 0 else 'calm'

            p_color = PROVINCE_COLORS[p_idx % len(PROVINCE_COLORS)] if PROVINCE_COLORS else NATION_COLORS.get(n.name, TEXT)
            prov_aggregates.append({
                'name': prov.name,
                'nation': n.name,
                'color': p_color,
                'pop': p_pop,
                'protest': p_protest,
                'raw': p_raw,
                'pct': p_pct,
                'total': p_tot,
                'dominant': dom_labels.get(dom_p, dom_p),
            })

    # Empire totals
    world_pop = sum(d['pop'] for d in nation_aggregates)
    mean_protest = (sum(d['protest'] * d['pop'] for d in nation_aggregates) / max(1, world_pop)) if world_pop else 0.0
    tot_strikers = sum(_safe_last(getattr(t, 'strikers_log', []), 0) for t in all_tile_stats_tiles(world))
    tot_broken = sum(_safe_last(getattr(t, 'broken_machinery_log', []), 0) for t in all_tile_stats_tiles(world))

    world_raw = {}
    for key in ['overworked', 'rent_enclosure', 'hunger', 'labor_resistance', 'tax', 'repression', 'inequality', 'unemployment']:
        world_raw[key] = sum(d['raw'].get(key, 0.0) for d in nation_aggregates)
    w_tot = sum(world_raw.values())
    w_dom = max(world_raw.items(), key=lambda x: x[1])[0] if w_tot > 0 else 'calm'
    w_dom_pct = (world_raw[w_dom] / w_tot * 100.0) if w_tot > 0 else 0.0

    dom_names = {'overworked': 'Overworked Shifts', 'rent_enclosure': 'Rent Extraction & Enclosure', 'hunger': 'Food Deprivation', 'labor_resistance': 'Strikes & Machine Casualties', 'tax': 'Tax Burden', 'repression': 'State Repression', 'inequality': 'Inequality'}

    # 2. KPI Scorecards Row (6 Cards)
    card_w = (box_w - 40 - 5 * 10) // 6
    card_h = 60
    cx = box_x + 20

    kpis = [
        ("EMPIRE PROTEST ENERGY", f"{mean_protest:.2f} / 10.0", "Unrest Intensity", RED if mean_protest > 4.0 else ((240, 180, 80) if mean_protest > 2.0 else GREEN)),
        ("PRIMARY GRIEVANCE DRIVER", f"{dom_names.get(w_dom, w_dom)[:14]}", f"{w_dom_pct:.1f}% of all unrest", (255, 220, 120)),
        ("OVERWORKED WORKDAYS", f"{world_raw.get('overworked', 0.0):.1f} Score", f"{(world_raw.get('overworked', 0.0)/max(0.1, w_tot))*100:.1f}% Realm Burden", COL_OVERWORK),
        ("RENT & DISPOSSESSION", f"{world_raw.get('rent_enclosure', 0.0):.1f} Score", f"{(world_raw.get('rent_enclosure', 0.0)/max(0.1, w_tot))*100:.1f}% Realm Burden", COL_ENCLOSURE),
        ("ACTIVE WORKPLACE RESISTANCE", f"{tot_strikers} Strikers", f"{tot_broken} Smashed Machines", COL_STRIKES),
        ("FOOD DEPRIVATION", f"{world_raw.get('hunger', 0.0):.1f} Score", f"{(world_raw.get('hunger', 0.0)/max(0.1, w_tot))*100:.1f}% Realm Burden", COL_HUNGER),
    ]

    for title, val_txt, sub_txt, color in kpis:
        c_rect = (cx, y, card_w, card_h)
        pygame.draw.rect(surface, CARD_BG, c_rect, border_radius=6)
        pygame.draw.rect(surface, CARD_BORDER, c_rect, 1, border_radius=6)

        surface.blit(_get_font(12).render(title, True, DIM), (cx + 8, y + 6))
        surface.blit(_get_font(18).render(val_txt, True, color), (cx + 8, y + 22))
        surface.blit(_get_font(12).render(sub_txt, True, (160, 160, 180)), (cx + 8, y + 42))
        cx += card_w + 10

    y += card_h + 14

    # 3. Detailed Grievance Breakdown Table
    cols = [
        ("Territory / Entity", 175),
        ("Protest Score", 105),
        ("Overworked Shifts", 130),
        ("Rent & Enclosure", 130),
        ("Food Deprivation", 125),
        ("Strikes & Accidents", 135),
        ("Taxes & State", 115),
        ("Primary Grievance Driver", 170),
    ]

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
                'protest': d['protest'],
                'overworked': d['pct'].get('overworked', 0.0),
                'enclosure': d['pct'].get('rent_enclosure', 0.0),
                'hunger': d['pct'].get('hunger', 0.0),
                'labor': d['pct'].get('labor_resistance', 0.0),
                'state': d['pct'].get('tax', 0.0) + d['pct'].get('repression', 0.0),
                'dominant': d['dominant'],
            })
    elif active_scope == 'province':
        for d in prov_aggregates:
            rows_data.append({
                'label': f"{d['name']} ({d['nation'][:3]})",
                'color': d['color'],
                'protest': d['protest'],
                'overworked': d['pct'].get('overworked', 0.0),
                'enclosure': d['pct'].get('rent_enclosure', 0.0),
                'hunger': d['pct'].get('hunger', 0.0),
                'labor': d['pct'].get('labor_resistance', 0.0),
                'state': d['pct'].get('tax', 0.0) + d['pct'].get('repression', 0.0),
                'dominant': d['dominant'],
            })
    else:  # 'city'
        sorted_tiles = sorted(all_tile_grievances, key=lambda s: s['protest'], reverse=True)
        for d in sorted_tiles[:14]:
            nat_name = getattr(d['tile'].owner_nation, 'name', '-') if getattr(d['tile'], 'owner_nation', None) else '-'
            rows_data.append({
                'label': f"{d['name']} [{nat_name[:3]}]",
                'color': NATION_COLORS.get(nat_name, TEXT),
                'protest': d['protest'],
                'overworked': d['pct'].get('overworked', 0.0),
                'enclosure': d['pct'].get('rent_enclosure', 0.0),
                'hunger': d['pct'].get('hunger', 0.0),
                'labor': d['pct'].get('labor_resistance', 0.0),
                'state': d['pct'].get('tax', 0.0) + d['pct'].get('repression', 0.0),
                'dominant': d['dominant'],
            })

    row_h = 22
    for idx, row in enumerate(rows_data):
        r_rect = (box_x + 16, y, box_w - 32, row_h)
        bg = ROW_BG1 if idx % 2 == 0 else ROW_BG2
        pygame.draw.rect(surface, bg, r_rect)

        tx = box_x + 24
        # Territory
        lbl = cell_font.render(row['label'], True, row['color'])
        surface.blit(lbl, (tx, y + 3))
        tx += cols[0][1]

        # Protest Score
        p_val = row['protest']
        p_col = RED if p_val > 4.0 else ((240, 180, 80) if p_val > 2.0 else GREEN)
        surface.blit(cell_font.render(f"{p_val:.2f} / 10", True, p_col), (tx, y + 3))
        tx += cols[1][1]

        # Overworked %
        ow_pct = row['overworked']
        surface.blit(cell_font.render(f"{ow_pct:.1f}%", True, COL_OVERWORK if ow_pct > 20 else DIM), (tx, y + 3))
        tx += cols[2][1]

        # Rent & Enclosure %
        enc_pct = row['enclosure']
        surface.blit(cell_font.render(f"{enc_pct:.1f}%", True, COL_ENCLOSURE if enc_pct > 20 else DIM), (tx, y + 3))
        tx += cols[3][1]

        # Hunger %
        h_pct = row['hunger']
        surface.blit(cell_font.render(f"{h_pct:.1f}%", True, COL_HUNGER if h_pct > 20 else DIM), (tx, y + 3))
        tx += cols[4][1]

        # Labor Resistance %
        lab_pct = row['labor']
        surface.blit(cell_font.render(f"{lab_pct:.1f}%", True, COL_STRIKES if lab_pct > 20 else DIM), (tx, y + 3))
        tx += cols[5][1]

        # State Taxes / Repression %
        st_pct = row['state']
        surface.blit(cell_font.render(f"{st_pct:.1f}%", True, COL_STATE if st_pct > 20 else DIM), (tx, y + 3))
        tx += cols[6][1]

        # Dominant Driver
        surface.blit(cell_font.render(row['dominant'], True, (255, 230, 150)), (tx, y + 3))

        y += row_h

    y += 14

    # 4. Analytical Charts Section (2 Charts Side-by-Side)
    chart_y = y
    half_w = (box_w - 50) // 2
    box_y = 20
    chart_h = max(110, (box_y + box_h) - chart_y - 20)

    # --- Chart A: 100% Proportional Stacked Grievance Breakdown Bar ---
    c1_rect = (box_x + 16, chart_y, half_w, chart_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=6)

    surface.blit(section_font.render("Grievance Source Composition (% 100 Stacked)", True, ACCENT), (box_x + 26, chart_y + 8))

    # Legend
    leg_x = box_x + 26
    leg_y = chart_y + 28
    legends = [
        ("Overwork", COL_OVERWORK),
        ("Enclosure", COL_ENCLOSURE),
        ("Hunger", COL_HUNGER),
        ("Strikes", COL_STRIKES),
        ("State Tax", COL_STATE),
    ]
    for l_lbl, l_col in legends:
        pygame.draw.rect(surface, l_col, (leg_x, leg_y + 2, 10, 10), border_radius=2)
        surface.blit(_get_font(12).render(l_lbl, True, TEXT), (leg_x + 14, leg_y))
        leg_x += 80

    bar_top_y = leg_y + 20
    bar_avail_h = chart_h - 55
    sorted_tiles = sorted(all_tile_grievances, key=lambda s: s['protest'], reverse=True)
    entities_to_plot = nation_aggregates if active_scope == 'country' else (prov_aggregates[:8] if active_scope == 'province' else sorted_tiles[:8])
    num_e = max(1, len(entities_to_plot))
    bar_row_h = min(22, bar_avail_h // num_e)

    for i, ent in enumerate(entities_to_plot):
        by = bar_top_y + i * bar_row_h
        ent_lbl = _get_font(12).render(ent['name'][:14], True, ent.get('color', TEXT))
        surface.blit(ent_lbl, (box_x + 26, by + 1))

        pcts = ent.get('pct', {})
        w_ow = pcts.get('overworked', 0.0)
        w_enc = pcts.get('rent_enclosure', 0.0)
        w_hng = pcts.get('hunger', 0.0)
        w_lab = pcts.get('labor_resistance', 0.0)
        w_st = pcts.get('tax', 0.0) + pcts.get('repression', 0.0)
        sum_pct = w_ow + w_enc + w_hng + w_lab + w_st

        bar_x = box_x + 130
        max_bar_w = half_w - 145

        if sum_pct > 0:
            px_ow = int((w_ow / sum_pct) * max_bar_w)
            px_enc = int((w_enc / sum_pct) * max_bar_w)
            px_hng = int((w_hng / sum_pct) * max_bar_w)
            px_lab = int((w_lab / sum_pct) * max_bar_w)
            px_st = max_bar_w - px_ow - px_enc - px_hng - px_lab

            cur_bx = bar_x
            if px_ow > 0:
                pygame.draw.rect(surface, COL_OVERWORK, (cur_bx, by + 2, px_ow, bar_row_h - 5))
                cur_bx += px_ow
            if px_enc > 0:
                pygame.draw.rect(surface, COL_ENCLOSURE, (cur_bx, by + 2, px_enc, bar_row_h - 5))
                cur_bx += px_enc
            if px_hng > 0:
                pygame.draw.rect(surface, COL_HUNGER, (cur_bx, by + 2, px_hng, bar_row_h - 5))
                cur_bx += px_hng
            if px_lab > 0:
                pygame.draw.rect(surface, COL_STRIKES, (cur_bx, by + 2, px_lab, bar_row_h - 5))
                cur_bx += px_lab
            if px_st > 0:
                pygame.draw.rect(surface, COL_STATE, (cur_bx, by + 2, px_st, bar_row_h - 5))
        else:
            pygame.draw.rect(surface, (40, 42, 55), (bar_x, by + 2, max_bar_w, bar_row_h - 5))

    # --- Chart B: Territorial Protest Intensity Heatmap / Ranking ---
    c2_x = box_x + 26 + half_w
    c2_rect = (c2_x, chart_y, half_w - 10, chart_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=6)

    surface.blit(section_font.render("Territorial Protest Intensity & Hotspot Ranking", True, ACCENT), (c2_x + 10, chart_y + 8))

    # Legend
    leg2_x = c2_x + 10
    leg2_y = chart_y + 28
    legends2 = [("< 2.0 Calm", GREEN), ("2.0-4.0 Simmering", (240, 180, 80)), ("> 4.0 Critical", RED)]
    for l_lbl, l_col in legends2:
        pygame.draw.rect(surface, l_col, (leg2_x, leg2_y + 2, 10, 10), border_radius=2)
        surface.blit(_get_font(12).render(l_lbl, True, TEXT), (leg2_x + 14, leg2_y))
        leg2_x += 120

    for i, ent in enumerate(entities_to_plot):
        by = bar_top_y + i * bar_row_h
        ent_lbl = _get_font(12).render(ent['name'][:14], True, ent.get('color', TEXT))
        surface.blit(ent_lbl, (c2_x + 10, by + 1))

        bar_x = c2_x + 115
        max_bar_w = half_w - 140

        score = ent.get('protest', 0.0)
        bar_w = int(min(1.0, score / 10.0) * max_bar_w)
        b_col = RED if score > 4.0 else ((240, 180, 80) if score > 2.0 else GREEN)

        pygame.draw.rect(surface, (38, 40, 52), (bar_x, by + 3, max_bar_w, bar_row_h - 6))
        if bar_w > 0:
            pygame.draw.rect(surface, b_col, (bar_x, by + 3, bar_w, bar_row_h - 6))

        # Score text at end of bar
        s_txt = _get_font(11).render(f"{score:.2f}", True, b_col)
        surface.blit(s_txt, (bar_x + max_bar_w + 4, by + 2))


def all_tile_stats_tiles(world):
    """Helper to get all tiles across all nations."""
    res = []
    for n in world.get('nations', []):
        res.extend(n.tiles)
    return res
