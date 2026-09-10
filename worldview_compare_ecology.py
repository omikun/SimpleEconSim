"""
worldview_compare_ecology.py — Comparison Modal Tab 6: Environmental Degradation & Public Health Epidemics.

Displays:
1. Environmental Degradation & Metabolic Rift:
   - Soil Fertility Depletion (monoculture vs crop rotation).
   - Food Nutrition Density Dilution (synthetic fertilizer effects).
   - Industrial Smog & Coal Particulate Inhalation Index.
   - River Sewage & Nitrate Effluent Contamination.
   - Toxic Chemical Pesticide Residue & Sludge.
2. Epidemiological Infection Rates & Disease Breakdown:
   - Malnutrition & Scurvy cases.
   - Waterborne Cholera & Dysentery cases.
   - Smog Bronchitis & Black Lung cases.
   - Chemical Pesticide Neurotoxicity cases.
   - Population Infection Prevalence (% of living citizens infected).
3. Healthcare Economics & Financial Burden:
   - Private Out-of-Pocket Medical Bills paid by working-class patients.
   - Public Healthcare Subsidies disbursed from Municipal/Provincial Treasuries.
   - Untreated / Impoverished Sick Citizens unable to afford medicine.
   - Complication Fatalities.
4. Multi-tier Scope Drilldown: [ By Country ], [ By Province ], [ By City / Tile ].
"""

from __future__ import annotations
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

# Theme colors for ecology and diseases
COL_FERT = (130, 215, 120)       # Fresh Green
COL_NUTR = (225, 195, 70)        # Golden Grain
COL_SMOG = (160, 160, 175)       # Smog Grey
COL_WATER = (80, 180, 230)       # Cyan River
COL_CHEM = (210, 100, 240)       # Toxic Purple

COL_MALNUTR = (240, 170, 60)     # Orange-Yellow
COL_CHOLERA = (70, 190, 220)     # Cyan-Blue
COL_BRONCH = (220, 90, 90)       # Rust Red
COL_TOXIC = (195, 70, 225)       # Magenta
COL_PUBLIC = (90, 210, 140)      # Mint Green
COL_PRIVATE = (240, 120, 80)     # Coral


def _get_font(size):
    from worldview_ui import get_font
    return get_font(size)


def _safe_last(lst, default=None):
    if not lst:
        return default
    val = lst[-1]
    return val if val is not None else default


def _extract_tile_stats(tile) -> dict:
    """Extract live environmental, epidemiological, and medical metrics from a tile."""
    pop = len(getattr(tile, 'agents', []))
    fert = _safe_last(getattr(tile, 'soil_fertility_log', []), getattr(tile, 'soil_fertility', 1.0))
    nutr = _safe_last(getattr(tile, 'nutrition_density_log', []), getattr(tile, 'nutrition_density', 1.0))
    air = _safe_last(getattr(tile, 'pollution_air_log', []), getattr(tile, 'pollution_air', 0.0))
    water = _safe_last(getattr(tile, 'pollution_water_log', []), getattr(tile, 'pollution_water', 0.0))
    soil = _safe_last(getattr(tile, 'pollution_soil_log', []), getattr(tile, 'pollution_soil', 0.0))

    d_cases = _safe_last(getattr(tile, 'disease_cases_log', []), {})
    if not isinstance(d_cases, dict):
        d_cases = {}

    malnutr = d_cases.get('malnutrition', 0)
    cholera = d_cases.get('waterborne', 0)
    respir = d_cases.get('respiratory', 0)
    chem = d_cases.get('chemical', 0)
    total_sick = d_cases.get('total', malnutr + cholera + respir + chem)

    spend_priv = _safe_last(getattr(tile, 'medical_spending_private_log', []), 0.0)
    spend_pub = _safe_last(getattr(tile, 'medical_spending_public_log', []), 0.0)
    untreated = _safe_last(getattr(tile, 'untreated_cases_log', []), 0)
    fatalities = _safe_last(getattr(tile, 'disease_fatalities_log', []), 0)

    infected_pct = (total_sick / max(1, pop)) * 100.0

    return {
        'pop': pop,
        'fertility': fert,
        'nutrition': nutr,
        'air_smog': air,
        'water_effluent': water,
        'soil_pesticide': soil,
        'malnutrition': malnutr,
        'cholera': cholera,
        'respiratory': respir,
        'chemical': chem,
        'total_sick': total_sick,
        'infected_pct': infected_pct,
        'spend_private': spend_priv,
        'spend_public': spend_pub,
        'untreated': untreated,
        'fatalities': fatalities,
    }


def draw_tab6_ecology(surface, world, box_x, box_y, box_w, box_h, font, font_small, mouse_pos=None):
    """Render Tab 6: Environmental Degradation & Public Health Epidemics."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    subtab = world.get('compare_eco_scope', 'country')

    # Sub-header: Scope Switcher [ By Country ] [ By Province ] [ By City / Tile ]
    tab_y = box_y - 8
    tab_h = 24
    btn_w = 120

    scopes = [
        ('country', "By Country", 'compare_eco_scope_country'),
        ('province', "By Province", 'compare_eco_scope_province'),
        ('city', "By City / Tile", 'compare_eco_scope_city'),
    ]

    for i, (sc_id, sc_lbl, btn_key) in enumerate(scopes):
        bx = box_x + 20 + i * 130
        b_rect = pygame.Rect(bx, tab_y, btn_w, tab_h)
        from ui_targets import register_target
        register_target(world, b_rect, ('scope_eco', sc_id), tooltip_id=btn_key, scope='compare')
        is_active = (subtab == sc_id)
        is_hover = b_rect.collidepoint(mx, my)

        if is_hover:
            from worldview_tooltips import get_button_tooltip_data
            tip = get_button_tooltip_data(btn_key, world)
            if tip:
                tip['btn_rect'] = b_rect
                world['_hovered_left_tooltip'] = tip

        bg = (55, 65, 95) if is_active else ((40, 48, 70) if is_hover else (28, 32, 46))
        border = ACCENT if is_active else ((80, 100, 140) if is_hover else CARD_BORDER)
        pygame.draw.rect(surface, bg, b_rect, border_radius=4)
        pygame.draw.rect(surface, border, b_rect, 1, border_radius=4)

        t_col = ACCENT if is_active else (TEXT if is_hover else DIM)
        txt = font_small.render(sc_lbl, True, t_col)
        surface.blit(txt, txt.get_rect(center=b_rect.center))

    # Analytical Summary Strip
    content_y = box_y + 24
    _draw_ecology_summary_cards(surface, world, box_x + 16, content_y, box_w - 32, font, font_small)

    table_y = content_y + 68
    table_h = (box_y + box_h) - table_y - 12

    if subtab == 'country':
        _draw_country_table(surface, world, box_x + 16, table_y, box_w - 32, table_h, font, font_small, mouse_pos)
    elif subtab == 'province':
        _draw_province_table(surface, world, box_x + 16, table_y, box_w - 32, table_h, font, font_small, mouse_pos)
    else:
        _draw_city_table(surface, world, box_x + 16, table_y, box_w - 32, table_h, font, font_small, mouse_pos)


def _draw_ecology_summary_cards(surface, world, x, y, w, font, font_small):
    """Draw top overview cards summarizing total realm environmental and epidemiological health."""
    nations = world.get('nations', [])
    all_tiles = []
    for n in nations:
        all_tiles.extend(getattr(n, 'tiles', []))

    if not all_tiles:
        return

    n_tiles = max(1, len(all_tiles))
    avg_fert = sum(getattr(t, 'soil_fertility', 1.0) for t in all_tiles) / n_tiles
    avg_nutr = sum(getattr(t, 'nutrition_density', 1.0) for t in all_tiles) / n_tiles
    avg_smog = sum(getattr(t, 'pollution_air', 0.0) for t in all_tiles) / n_tiles
    avg_water = sum(getattr(t, 'pollution_water', 0.0) for t in all_tiles) / n_tiles

    total_pop = 0
    total_sick = 0
    total_spend_priv = 0.0
    total_spend_pub = 0.0
    total_untreated = 0

    for t in all_tiles:
        stats = _extract_tile_stats(t)
        total_pop += stats['pop']
        total_sick += stats['total_sick']
        total_spend_priv += stats['spend_private']
        total_spend_pub += stats['spend_public']
        total_untreated += stats['untreated']

    realm_inf_rate = (total_sick / max(1, total_pop)) * 100.0

    card_w = (w - 36) // 4
    card_h = 56

    cards_data = [
        ("Soil & Nutrition Health", f"Fert {avg_fert*100:.0f}% | Nut {avg_nutr*100:.0f}%",
         "Synthetic fertilizers trade nutrition for yield", COL_FERT),
        ("Atmosphere & Water Toxicity", f"Smog {avg_smog:.1f} | Effluent {avg_water:.1f}",
         "Coal coking smog and nitrate sewage runoff", (230, 110, 100) if avg_smog > 15 else COL_WATER),
        ("Epidemic Infection Burden", f"{total_sick:,} infected ({realm_inf_rate:.1f}%)",
         f"{total_untreated} impoverished cases untreated", (240, 90, 90) if realm_inf_rate > 15 else COL_BRONCH),
        ("Medical Economics", f"Priv ${total_spend_priv:,.0f} | Pub ${total_spend_pub:,.0f}",
         f"Zero-leak healthcare transfers (0 LEAK)", COL_PUBLIC),
    ]

    for i, (title, val_str, sub_txt, col) in enumerate(cards_data):
        cx = x + i * (card_w + 12)
        c_rect = pygame.Rect(cx, y, card_w, card_h)
        pygame.draw.rect(surface, CARD_BG, c_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, c_rect, 1, border_radius=5)

        surface.blit(font_small.render(title, True, DIM), (cx + 8, y + 5))
        surface.blit(font.render(val_str, True, col), (cx + 8, y + 20))
        surface.blit(font_small.render(sub_txt, True, (120, 130, 150)), (cx + 8, y + 38))


def _draw_country_table(surface, world, x, y, w, h, font, font_small, mouse_pos):
    """Aggregate environmental depletion and epidemics by Sovereign Nation."""
    nations = world.get('nations', [])
    headers = [
        ("Nation / Realm", 180, 'left'),
        ("Pop", 60, 'right'),
        ("Soil Fert", 75, 'right'),
        ("Nutrition", 75, 'right'),
        ("Smog", 65, 'right'),
        ("Water", 65, 'right'),
        ("Malnutr", 75, 'right'),
        ("Cholera", 75, 'right'),
        ("Smog Bronch", 90, 'right'),
        ("Pesticide", 75, 'right'),
        ("Infected %", 80, 'right'),
        ("Patient Bills", 95, 'right'),
        ("Gov Subsidy", 95, 'right'),
        ("Untreated", 75, 'right'),
    ]

    _draw_table_header(surface, x, y, w, headers, font_small)
    row_y = y + 26
    row_h = 24

    for idx, nat in enumerate(nations):
        tiles = getattr(nat, 'tiles', [])
        if not tiles:
            continue

        n_tiles = len(tiles)
        pop = sum(len(t.agents) for t in tiles)
        fert = sum(getattr(t, 'soil_fertility', 1.0) for t in tiles) / n_tiles
        nutr = sum(getattr(t, 'nutrition_density', 1.0) for t in tiles) / n_tiles
        smog = sum(getattr(t, 'pollution_air', 0.0) for t in tiles) / n_tiles
        water = sum(getattr(t, 'pollution_water', 0.0) for t in tiles) / n_tiles

        mal = 0
        cho = 0
        res = 0
        chm = 0
        tot_sick = 0
        priv = 0.0
        pub = 0.0
        untr = 0

        for t in tiles:
            st = _extract_tile_stats(t)
            mal += st['malnutrition']
            cho += st['cholera']
            res += st['respiratory']
            chm += st['chemical']
            tot_sick += st['total_sick']
            priv += st['spend_private']
            pub += st['spend_public']
            untr += st['untreated']

        inf_pct = (tot_sick / max(1, pop)) * 100.0
        nat_col = NATION_COLORS.get(nat.name, TEXT)

        bg = ROW_BG1 if idx % 2 == 0 else ROW_BG2
        pygame.draw.rect(surface, bg, (x, row_y, w, row_h))

        cols = [
            (nat.name, 180, nat_col, 'left'),
            (f"{pop:,}", 60, TEXT, 'right'),
            (f"{fert*100:.0f}%", 75, COL_FERT if fert >= 0.90 else (235, 120, 80), 'right'),
            (f"{nutr*100:.0f}%", 75, COL_NUTR if nutr >= 0.85 else (235, 120, 80), 'right'),
            (f"{smog:.1f}", 65, (235, 90, 90) if smog > 15 else COL_SMOG, 'right'),
            (f"{water:.1f}", 65, (235, 90, 90) if water > 20 else COL_WATER, 'right'),
            (f"{mal:,}", 75, COL_MALNUTR if mal > 0 else DIM, 'right'),
            (f"{cho:,}", 75, COL_CHOLERA if cho > 0 else DIM, 'right'),
            (f"{res:,}", 90, COL_BRONCH if res > 0 else DIM, 'right'),
            (f"{chm:,}", 75, COL_TOXIC if chm > 0 else DIM, 'right'),
            (f"{inf_pct:.1f}%", 80, (235, 80, 80) if inf_pct > 15 else ACCENT, 'right'),
            (f"${priv:,.0f}", 95, COL_PRIVATE, 'right'),
            (f"${pub:,.0f}", 95, COL_PUBLIC, 'right'),
            (f"{untr:,}", 75, (235, 80, 80) if untr > 0 else DIM, 'right'),
        ]

        _draw_table_row(surface, x, row_y, cols, font_small)
        row_y += row_h
        if row_y > y + h - row_h:
            break


def _draw_province_table(surface, world, x, y, w, h, font, font_small, mouse_pos):
    """Aggregate environmental depletion and epidemics by Province."""
    nations = world.get('nations', [])
    all_provs = []
    for nat in nations:
        all_provs.extend(getattr(nat, 'provinces', []))

    headers = [
        ("Province", 150, 'left'),
        ("Realm", 110, 'left'),
        ("Pop", 55, 'right'),
        ("Soil Fert", 75, 'right'),
        ("Nutrition", 75, 'right'),
        ("Smog", 65, 'right'),
        ("Water", 65, 'right'),
        ("Malnutr", 70, 'right'),
        ("Cholera", 70, 'right'),
        ("Smog Bronch", 85, 'right'),
        ("Pesticide", 70, 'right'),
        ("Infected %", 80, 'right'),
        ("Patient Bills", 95, 'right'),
        ("Gov Subsidy", 95, 'right'),
        ("Untreated", 70, 'right'),
    ]

    _draw_table_header(surface, x, y, w, headers, font_small)
    row_y = y + 26
    row_h = 24

    for idx, prov in enumerate(all_provs):
        tiles = getattr(prov, 'tiles', [])
        if not tiles:
            continue

        n_tiles = len(tiles)
        pop = sum(len(t.agents) for t in tiles)
        fert = sum(getattr(t, 'soil_fertility', 1.0) for t in tiles) / n_tiles
        nutr = sum(getattr(t, 'nutrition_density', 1.0) for t in tiles) / n_tiles
        smog = sum(getattr(t, 'pollution_air', 0.0) for t in tiles) / n_tiles
        water = sum(getattr(t, 'pollution_water', 0.0) for t in tiles) / n_tiles

        mal = sum(_extract_tile_stats(t)['malnutrition'] for t in tiles)
        cho = sum(_extract_tile_stats(t)['cholera'] for t in tiles)
        res = sum(_extract_tile_stats(t)['respiratory'] for t in tiles)
        chm = sum(_extract_tile_stats(t)['chemical'] for t in tiles)
        tot_sick = mal + cho + res + chm
        priv = sum(_extract_tile_stats(t)['spend_private'] for t in tiles)
        pub = sum(_extract_tile_stats(t)['spend_public'] for t in tiles)
        untr = sum(_extract_tile_stats(t)['untreated'] for t in tiles)

        inf_pct = (tot_sick / max(1, pop)) * 100.0
        nat_name = getattr(prov.nation, 'name', '-') if getattr(prov, 'nation', None) else '-'
        nat_col = NATION_COLORS.get(nat_name, TEXT)

        bg = ROW_BG1 if idx % 2 == 0 else ROW_BG2
        pygame.draw.rect(surface, bg, (x, row_y, w, row_h))

        cols = [
            (prov.display_name if hasattr(prov, 'display_name') else prov.name, 150, (140, 200, 255), 'left'),
            (nat_name, 110, nat_col, 'left'),
            (f"{pop:,}", 55, TEXT, 'right'),
            (f"{fert*100:.0f}%", 75, COL_FERT if fert >= 0.90 else (235, 120, 80), 'right'),
            (f"{nutr*100:.0f}%", 75, COL_NUTR if nutr >= 0.85 else (235, 120, 80), 'right'),
            (f"{smog:.1f}", 65, (235, 90, 90) if smog > 15 else COL_SMOG, 'right'),
            (f"{water:.1f}", 65, (235, 90, 90) if water > 20 else COL_WATER, 'right'),
            (f"{mal:,}", 70, COL_MALNUTR if mal > 0 else DIM, 'right'),
            (f"{cho:,}", 70, COL_CHOLERA if cho > 0 else DIM, 'right'),
            (f"{res:,}", 85, COL_BRONCH if res > 0 else DIM, 'right'),
            (f"{chm:,}", 70, COL_TOXIC if chm > 0 else DIM, 'right'),
            (f"{inf_pct:.1f}%", 80, (235, 80, 80) if inf_pct > 15 else ACCENT, 'right'),
            (f"${priv:,.0f}", 95, COL_PRIVATE, 'right'),
            (f"${pub:,.0f}", 95, COL_PUBLIC, 'right'),
            (f"{untr:,}", 70, (235, 80, 80) if untr > 0 else DIM, 'right'),
        ]

        _draw_table_row(surface, x, row_y, cols, font_small)
        row_y += row_h
        if row_y > y + h - row_h:
            break


def _draw_city_table(surface, world, x, y, w, h, font, font_small, mouse_pos):
    """List detailed environmental degradation and disease cases per City / Tile."""
    nations = world.get('nations', [])
    all_tiles = []
    for nat in nations:
        for t in getattr(nat, 'tiles', []):
            all_tiles.append((t, nat.name))

    headers = [
        ("City / Settlement", 140, 'left'),
        ("Realm", 100, 'left'),
        ("Pop", 55, 'right'),
        ("Soil Fert", 75, 'right'),
        ("Nutrition", 75, 'right'),
        ("Smog", 65, 'right'),
        ("Water", 65, 'right'),
        ("Malnutr", 70, 'right'),
        ("Cholera", 70, 'right'),
        ("Smog Bronch", 85, 'right'),
        ("Pesticide", 70, 'right'),
        ("Infected %", 80, 'right'),
        ("Patient Bills", 95, 'right'),
        ("Gov Subsidy", 95, 'right'),
        ("Untreated", 70, 'right'),
    ]

    _draw_table_header(surface, x, y, w, headers, font_small)
    row_y = y + 26
    row_h = 24

    for idx, (t, nat_name) in enumerate(all_tiles):
        st = _extract_tile_stats(t)
        nat_col = NATION_COLORS.get(nat_name, TEXT)

        bg = ROW_BG1 if idx % 2 == 0 else ROW_BG2
        pygame.draw.rect(surface, bg, (x, row_y, w, row_h))

        cols = [
            (t.name, 140, TEXT, 'left'),
            (nat_name, 100, nat_col, 'left'),
            (f"{st['pop']:,}", 55, TEXT, 'right'),
            (f"{st['fertility']*100:.0f}%", 75, COL_FERT if st['fertility'] >= 0.90 else (235, 120, 80), 'right'),
            (f"{st['nutrition']*100:.0f}%", 75, COL_NUTR if st['nutrition'] >= 0.85 else (235, 120, 80), 'right'),
            (f"{st['air_smog']:.1f}", 65, (235, 90, 90) if st['air_smog'] > 15 else COL_SMOG, 'right'),
            (f"{st['water_effluent']:.1f}", 65, (235, 90, 90) if st['water_effluent'] > 20 else COL_WATER, 'right'),
            (f"{st['malnutrition']:,}", 70, COL_MALNUTR if st['malnutrition'] > 0 else DIM, 'right'),
            (f"{st['cholera']:,}", 70, COL_CHOLERA if st['cholera'] > 0 else DIM, 'right'),
            (f"{st['respiratory']:,}", 85, COL_BRONCH if st['respiratory'] > 0 else DIM, 'right'),
            (f"{st['chemical']:,}", 70, COL_TOXIC if st['chemical'] > 0 else DIM, 'right'),
            (f"{st['infected_pct']:.1f}%", 80, (235, 80, 80) if st['infected_pct'] > 15 else ACCENT, 'right'),
            (f"${st['spend_private']:,.0f}", 95, COL_PRIVATE, 'right'),
            (f"${st['spend_public']:,.0f}", 95, COL_PUBLIC, 'right'),
            (f"{st['untreated']:,}", 70, (235, 80, 80) if st['untreated'] > 0 else DIM, 'right'),
        ]

        _draw_table_row(surface, x, row_y, cols, font_small)
        row_y += row_h
        if row_y > y + h - row_h:
            break


def _draw_table_header(surface, x, y, w, headers, font_small):
    """Render table column headers."""
    pygame.draw.rect(surface, SEC_BG, (x, y, w, 22))
    cur_x = x + 8
    for title, col_w, align in headers:
        txt = font_small.render(title, True, (160, 175, 205))
        if align == 'right':
            surface.blit(txt, (cur_x + col_w - txt.get_width(), y + 4))
        else:
            surface.blit(txt, (cur_x, y + 4))
        cur_x += col_w + 6


def _draw_table_row(surface, x, y, cols, font_small):
    """Render a single table row with aligned text."""
    cur_x = x + 8
    for text, col_w, color, align in cols:
        txt = font_small.render(str(text), True, color)
        if align == 'right':
            surface.blit(txt, (cur_x + col_w - txt.get_width(), y + 4))
        else:
            surface.blit(txt, (cur_x, y + 4))
        cur_x += col_w + 6


def handle_tab6_click(world, mx, my, box_x, box_y, box_w):
    """Handle click events on Tab 6 scope switcher buttons."""
    if world is not None:
        from ui_targets import find_target
        target = find_target(world, (mx, my), scope='compare')
        if target and isinstance(target.action, tuple) and target.action[0] == 'scope_eco':
            world['compare_eco_scope'] = target.action[1]
            return True

    # Legacy fallback calculation
    tab_y = box_y + 88
    tab_h = 24
    btn_w = 120

    scopes = ['country', 'province', 'city']
    for i, sc_id in enumerate(scopes):
        bx = box_x + 20 + i * 130
        b_rect = pygame.Rect(bx, tab_y, btn_w, tab_h)
        if b_rect.collidepoint(mx, my):
            world['compare_eco_scope'] = sc_id
            return True
    return False
