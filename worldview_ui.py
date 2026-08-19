"""
UI components: top stats bar, right panel, regime readout, ticker, zoom HUD, and help overlay.
"""

from collections import Counter
import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_charts import (PANEL_LEFT, draw_chart_grid, draw_chart_large,
                              tile_charts, EXP_C, IMP_C)
from worldview_map import (HEX_EDGE, ACCENT, TEXT, DIM, RED, GREEN, UNREST_COLORS,
                           PROVINCE_COLORS, NATION_COLORS)
from worldview_compare import draw_nations_comparison, compare_tab_hit

PANEL_BG = (40, 40, 48)

# Zoom HUD button rectangles: (x, y, w, h)
ZOOM_BTN_IN = (MAP_RIGHT - 110, TOP_BAR_H + 12, 30, 26)
ZOOM_BTN_OUT = (MAP_RIGHT - 75, TOP_BAR_H + 12, 30, 26)
ZOOM_BTN_RESET = (MAP_RIGHT - 40, TOP_BAR_H + 12, 32, 26)

# Compare Nations button in top bar
COMPARE_BTN = (MAP_RIGHT - 150, 12, 138, 28)


def draw_zoom_hud(surface, font_small, mouse_pos=None):
    """Draw on-screen zoom control buttons in the top-right corner of the map area."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    buttons = [
        (ZOOM_BTN_IN, "+", "Zoom In"),
        (ZOOM_BTN_OUT, "-", "Zoom Out"),
        (ZOOM_BTN_RESET, "1:1", "Reset Zoom"),
    ]
    for rect, label, _tip in buttons:
        is_hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        bg_color = (60, 60, 75) if is_hover else (38, 38, 48)
        border_color = ACCENT if is_hover else (80, 80, 95)
        pygame.draw.rect(surface, bg_color, rect, border_radius=4)
        pygame.draw.rect(surface, border_color, rect, 1, border_radius=4)
        tsurf = font_small.render(label, True, (255, 255, 255) if is_hover else TEXT)
        surface.blit(tsurf, tsurf.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))


def zoom_hud_hit(pos):
    """Return 'in', 'out', 'reset', or None if a zoom button was clicked."""
    mx, my = pos
    if ZOOM_BTN_IN[0] <= mx <= ZOOM_BTN_IN[0] + ZOOM_BTN_IN[2] and ZOOM_BTN_IN[1] <= my <= ZOOM_BTN_IN[1] + ZOOM_BTN_IN[3]:
        return 'in'
    if ZOOM_BTN_OUT[0] <= mx <= ZOOM_BTN_OUT[0] + ZOOM_BTN_OUT[2] and ZOOM_BTN_OUT[1] <= my <= ZOOM_BTN_OUT[1] + ZOOM_BTN_OUT[3]:
        return 'out'
    if ZOOM_BTN_RESET[0] <= mx <= ZOOM_BTN_RESET[0] + ZOOM_BTN_RESET[2] and ZOOM_BTN_RESET[1] <= my <= ZOOM_BTN_RESET[1] + ZOOM_BTN_RESET[3]:
        return 'reset'
    return None


def compare_btn_hit(pos):
    """Return True if the top-bar Compare Nations button was clicked."""
    mx, my = pos
    return COMPARE_BTN[0] <= mx <= COMPARE_BTN[0] + COMPARE_BTN[2] and COMPARE_BTN[1] <= my <= COMPARE_BTN[1] + COMPARE_BTN[3]


def selected_nation(world):
    pinned = world.get('selected_region')
    if pinned is not None and getattr(pinned, 'owner_nation', None) is not None:
        return pinned.owner_nation
    return world['nations'][0] if world['nations'] else None


def draw_top_bar(surface, world, font_small, mouse_pos=None):
    """Civ-style top strip: stats for the currently selected nation + compare button."""
    n = selected_nation(world)
    pygame.draw.rect(surface, (34, 34, 42), (0, 0, MAP_RIGHT, TOP_BAR_H))
    pygame.draw.line(surface, HEX_EDGE, (0, TOP_BAR_H), (MAP_RIGHT, TOP_BAR_H), 2)
    font = font_small
    if n is None:
        head = font.render("REGNUM v3 — 9x9 Hex World", True, ACCENT)
        surface.blit(head, (8, 14))
    else:
        tiles = n.tiles
        pop = sum(r.total_population[-1] if r.total_population else len(r.agents)
                  for r in tiles)
        tr = n.treasury()
        col = (sum(r.cost_of_living for r in tiles) / len(tiles)
               if tiles else 0.0)
        gdp = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in tiles)
        exports = sum(sum(v) for r in tiles for v in r.export_val.values())
        imports = sum(sum(v) for r in tiles for v in r.import_val.values())
        net = exports - imports
        ruling = getattr(n, 'ruling_faction', None)
        ruler = f"  ruling {ruling}" if ruling else ""
        head = font.render(
            f"{n.name} ({n.currency})  {n.regime_type}  legit {n.legitimacy:.2f}"
            f"{ruler}  provinces {len(n.provinces)}  tiles {len(tiles)}", True, ACCENT)
        surface.blit(head, (8, 6))
        stats = [
            (f"Pop {pop}", TEXT),
            (f"Treasury ${tr['total']:,.0f} ({tr['food']} food)", TEXT),
            (f"CoL {col:.2f}", TEXT),
            (f"GDP ${gdp:,.0f}", TEXT),
            (f"Ex ${exports:,.0f}", EXP_C),
            (f"Im ${imports:,.0f}", IMP_C),
            (f"Net {'+' if net >= 0 else ''}{net:,.0f}",
             GREEN if net >= 0 else RED),
        ]
        x = 8
        for text, color in stats:
            label = font.render(text, True, color)
            surface.blit(label, (x, 30))
            x += label.get_width() + 18

    # Compare Nations Button
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    is_hover = compare_btn_hit((mx, my))
    is_open = world.get('compare_open', False)
    btn_bg = (70, 70, 90) if is_open else ((55, 55, 70) if is_hover else (38, 38, 48))
    btn_border = ACCENT if (is_hover or is_open) else (90, 90, 105)
    pygame.draw.rect(surface, btn_bg, COMPARE_BTN, border_radius=5)
    pygame.draw.rect(surface, btn_border, COMPARE_BTN, 1, border_radius=5)
    btn_txt = font_small.render("Compare (C)", True, (255, 255, 255) if (is_hover or is_open) else TEXT)
    surface.blit(btn_txt, btn_txt.get_rect(center=(COMPARE_BTN[0] + COMPARE_BTN[2] // 2, COMPARE_BTN[1] + COMPARE_BTN[3] // 2)))


def draw_regime_readout(surface, region, font_small, y):
    """Protest / unrest / top faction / owner nation readout."""
    if getattr(region, 'owner_nation', None) is None:
        hs = sum(1 for a in region.agents if getattr(a, 'is_homesteader', False))
        line = font_small.render(f"unclaimed wilderness  (homesteaders: {hs})", True, DIM)
        surface.blit(line, (PANEL_LEFT, y))
        return
    protest = (region.protest_energy_log[-1]
               if region.protest_energy_log else 0.0)
    unrest = region.unrest_log[-1] if region.unrest_log else {}
    stage = unrest.get('stage', 'calm')
    top = None
    if region.faction_support_log:
        snap = region.faction_support_log[-1]
        if snap:
            top = max(snap, key=lambda k: snap[k])
    owner = getattr(region, 'owner_nation', None)
    owner_s = ""
    if owner is not None:
        ruling = getattr(owner, 'ruling_faction', None)
        owner_s = f"  {owner.name}: legit {owner.legitimacy:.2f}" \
                  + (f" ruling {ruling}" if ruling else "")
    line = font_small.render(
        f"protest {protest:.1f}  unrest {stage}"
        + (f"  top {top}" if top else "")
        + owner_s, True, DIM)
    surface.blit(line, (PANEL_LEFT, y))


def draw_panel(surface, world, font, font_small, mouse_pos=None):
    """Right-hand panel: header, play state, audit, per-tile charts, wilderness card."""
    d = TOP_BAR_H
    panel_w = WIDTH - PANEL_LEFT - 6
    panel_h = HEIGHT - 20 - d - TICKER_H
    pygame.draw.rect(surface, PANEL_BG,
                     (PANEL_LEFT - 10, 10 + d, panel_w + 4, panel_h))

    title = font.render("REGNUM — Hex World", True, ACCENT)
    surface.blit(title, (PANEL_LEFT, 20 + d))

    t_ = world['turn']
    turn_line = font_small.render(f"Turn: {t_}  win={world['window']}t  zoom={world['cam']['zoom']:.2f}x", True, TEXT)
    surface.blit(turn_line, (PANEL_LEFT, 50 + d))

    cursors = world.get('currency_totals', {})
    y = 76 + d
    for c, total in cursors.items():
        line = font_small.render(f"{c}: ${total:,.0f}", True, TEXT)
        surface.blit(line, (PANEL_LEFT, y))
        y += 20

    if world.get('playing'):
        pn = font_small.render("[ PLAYING ]  Space=pause", True, GREEN)
    else:
        pn = font_small.render("[ PAUSED ]  S=step  Space=play", True, DIM)
    surface.blit(pn, (PANEL_LEFT, 142 + d))

    region = world.get('selected_region') or world.get('hover_region')
    chart_top = 178 + d
    chart_bottom = HEIGHT - TICKER_H - 96

    if world.get('scope', 'tile') == 'nation':
        n = selected_nation(world)
        if n is not None:
            owner_pop = sum(r.total_population[-1] if r.total_population
                            else len(r.agents) for r in n.tiles)
            tr = n.treasury()
            col = (sum(r.cost_of_living for r in n.tiles) / max(1, len(n.tiles)))
            gdp = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in n.tiles)
            lines = [
                (f"{n.name} ({n.currency})  {n.regime_type}", ACCENT),
                (f"legit {n.legitimacy:.2f}  provinces {len(n.provinces)}  tiles {len(n.tiles)}", TEXT),
                (f"pop {owner_pop}", TEXT),
                (f"treasury ${tr['total']:,.0f} ({tr['food']} food)", TEXT),
                (f"avg CoL {col:.2f}", DIM),
                (f"GDP/turn ${gdp:,.0f}", GREEN),
            ]
            yy = chart_top + 4
            for text, color in lines:
                line = font_small.render(text, True, color)
                surface.blit(line, (PANEL_LEFT, yy))
                yy += 20
            hint = font_small.render(
                f"NATION scope (V=tile)  press V to toggle", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_bottom + 6))
            draw_regime_readout(surface, region if region is not None else n.tiles[0],
                                font_small, chart_bottom + 24)
        return

    # Check if region is Wilderness
    if region is not None and getattr(region, 'owner_nation', None) is None:
        head = font.render(f"{region.name} — Frontier Wilderness", True, ACCENT)
        surface.blit(head, (PANEL_LEFT, chart_top - 6))
        col_line = font_small.render(
            f"Climate: {region.climate.capitalize()}  |  CoL: {region.cost_of_living:.2f}", True, DIM)
        surface.blit(col_line, (PANEL_LEFT, chart_top + 20))

        hs_agents = [a for a in region.agents if getattr(a, 'is_homesteader', False)]
        wild_native = getattr(region, 'wilderness_pop', 0)
        total_settlers = len(hs_agents) + wild_native
        origin_counts = Counter(getattr(a, 'origin_nation', 'Unknown') for a in hs_agents)

        yy = chart_top + 48
        surface.blit(font_small.render("FRONTIER DEMOGRAPHICS", True, ACCENT), (PANEL_LEFT, yy))
        yy += 20
        surface.blit(font_small.render(f"Homesteaders: {len(hs_agents)}", True, TEXT), (PANEL_LEFT, yy))
        yy += 18
        surface.blit(font_small.render(f"Native Wilderness Pop: {wild_native}", True, TEXT), (PANEL_LEFT, yy))
        yy += 18
        surface.blit(font_small.render(f"Total Frontier Pop: {total_settlers}", True, (255, 255, 255)), (PANEL_LEFT, yy))
        yy += 24

        surface.blit(font_small.render("SETTLER HOMELANDS (50% Claim Rule)", True, ACCENT), (PANEL_LEFT, yy))
        yy += 20
        if origin_counts:
            for nation_name, cnt in origin_counts.most_common():
                pct = (cnt / total_settlers) * 100 if total_settlers > 0 else 0
                claimable = " (CLAIM MAJORITY!)" if cnt / float(total_settlers) > 0.50 else ""
                color = GREEN if claimable else TEXT
                surface.blit(font_small.render(f"• {nation_name}: {cnt} ({pct:.1f}%){claimable}", True, color), (PANEL_LEFT, yy))
                yy += 18
        else:
            surface.blit(font_small.render("No homesteaders present yet", True, DIM), (PANEL_LEFT, yy))
            yy += 18

        yy += 10
        surface.blit(font_small.render("NATURAL PRODUCTIVITY", True, ACCENT), (PANEL_LEFT, yy))
        yy += 20
        food_bonus = region.terrain.get(Goods.food, 1.0)
        wood_bonus = region.terrain.get(Goods.wood, 1.0)
        surface.blit(font_small.render(f"Farmland Fertility: {food_bonus:.2f}x {'(High)' if food_bonus > 1.3 else ''}", True, TEXT), (PANEL_LEFT, yy))
        yy += 18
        surface.blit(font_small.render(f"Forest Density: {wood_bonus:.2f}x {'(Dense)' if wood_bonus > 1.3 else ''}", True, TEXT), (PANEL_LEFT, yy))
        yy += 24

        surface.blit(font_small.render("NEIGHBORING CLAIMED HOSTS", True, ACCENT), (PANEL_LEFT, yy))
        yy += 20
        claimed_neighbors = [n for n in region.neighbors.values() if getattr(n, 'owner_nation', None) is not None]
        if claimed_neighbors:
            for nb in claimed_neighbors[:4]:
                prov_name = nb.province.name if getattr(nb, 'province', None) else nb.owner_nation.name
                surface.blit(font_small.render(f"• {nb.name} ({nb.owner_nation.name} - {prov_name})", True, DIM), (PANEL_LEFT, yy))
                yy += 18
        else:
            surface.blit(font_small.render("Deep frontier wilderness", True, DIM), (PANEL_LEFT, yy))
            yy += 18

        draw_regime_readout(surface, region, font_small, chart_bottom + 24)
        return

    # Claimed Tile 10-Chart Dashboard
    if region is not None:
        prov_s = ""
        prov_color = TEXT
        if getattr(region, 'province', None) is not None:
            prov = region.province
            nation = getattr(region, 'owner_nation', None)
            if nation and getattr(nation, 'provinces', None):
                try:
                    p_idx = nation.provinces.index(prov)
                    prov_color = PROVINCE_COLORS[p_idx % len(PROVINCE_COLORS)]
                except ValueError:
                    prov_color = ACCENT
            prov_s = f"  [{prov.name}]"

        head = font_small.render(f"{region.name}{prov_s}", True, prov_color)
        surface.blit(head, (PANEL_LEFT, chart_top - 6))
        col_line = font_small.render(
            f"CoL {region.cost_of_living:.2f}  {region.climate}  (V=nation)", True, DIM)
        surface.blit(col_line, (PANEL_LEFT, chart_top - 6 + 16))
        charts = tile_charts(region)
        view = world.get('view', 0)
        if view == 0:
            draw_chart_grid(surface, charts, font, font_small, world['window'],
                            chart_top + 30, chart_bottom, mouse_pos=mouse_pos)
            hint = font_small.render(
                f"Click/1-9,0: Zoom chart  Tab: Grid", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_bottom + 6))
        else:
            idx = max(0, min(len(charts) - 1, view - 1))
            draw_chart_large(surface, charts[idx], font, font_small,
                             world['window'], chart_top + 16, chart_bottom)
            hint = font_small.render(
                f"{charts[idx][0]}  (Click or Tab/Esc = Grid)", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_bottom + 6))
        draw_regime_readout(surface, region, font_small, chart_bottom + 24)
    else:
        hint = font_small.render("Hover or click a hex for charts", True, DIM)
        surface.blit(hint, (PANEL_LEFT, 190 + d))

    audit_y = HEIGHT - TICKER_H - 28
    if world.get('violations'):
        v1 = font.render("AUDIT VIOLATION", True, RED)
        surface.blit(v1, (PANEL_LEFT, audit_y - 4))
        vline = font_small.render(
            "; ".join(f"T{v[0]} {v[1]} {v[2]:+.2f}"
                      for v in world['violations']),
            True, RED)
        surface.blit(vline, (PANEL_LEFT, audit_y + 18))
    else:
        ok = font.render("Conserved: 0 LEAK / 0 SHIFT", True, GREEN)
        surface.blit(ok, (PANEL_LEFT, audit_y))


def draw_ticker(surface, world, font_small):
    """Bottom strip: scrolling archive of MIGRATE / CLAIM / DESTROY events."""
    y0 = HEIGHT - TICKER_H
    pygame.draw.rect(surface, (34, 34, 42), (0, y0, WIDTH, TICKER_H))
    pygame.draw.line(surface, HEX_EDGE, (0, y0), (WIDTH, y0), 2)
    title = font_small.render("Ticker", True, ACCENT)
    surface.blit(title, (8, y0 + 4))
    events = world['ticker_events']
    visible = 3
    start = max(0, len(events) - visible)
    yy = y0 + 6
    for ev in events[start:]:
        line = font_small.render(f"T{ev['t']}  {ev['text']}", True, ev['color'])
        surface.blit(line, (78, yy))
        yy += 18


def draw_help(surface, world, font_small):
    if not world.get('help_open', False):
        return
    title_font = pygame.font.Font(None, 32)
    header_font = pygame.font.Font(None, 24)
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((14, 14, 20, 246))
    surface.blit(overlay, (0, 0))

    # Modal Header
    surface.blit(title_font.render('REGNUM v3 — Comprehensive Map & Controls Guide (Press H or Esc to Close)', True, ACCENT),
                 (32, 20))
    pygame.draw.line(surface, (70, 70, 85), (32, 54), (WIDTH - 32, 54), 1)

    # 3-Column Layout: (Col1: Controls & Accounts Suite), (Col2: Hex Map & Labels), (Col3: Badges, Rings & Glyphs)
    col_w = (WIDTH - 96) // 3
    col1_x = 32
    col2_x = 32 + col_w + 16
    col3_x = 32 + (col_w + 16) * 2

    # Column 1: Controls & Navigation
    y = 68
    surface.blit(header_font.render('1. CONTROLS & NAVIGATION', True, ACCENT), (col1_x, y))
    y += 28
    col1_items = [
        ("Space", "Play / pause auto-step (~150ms)"),
        ("N or .", "Step 1 turn (while paused)"),
        ("WASD / Arrows", "Pan map camera in 4 directions"),
        ("Middle/Right Drag", "Hold & drag mouse to pan map"),
        ("Mouse Wheel", "Smooth zoom anchored at cursor"),
        ("0 or R / Home", "Reset zoom & center map (1:1)"),
        ("C or [Compare]", "Open 3-Tab Economic Accounts Suite"),
        ("1, 2, 3 in Table", "Switch Macro / Goods / FX tabs"),
        ("F, W, U in Table", "Switch Food / Wood / Furniture"),
        ("On-Screen [+] / [-]", "Map zoom HUD buttons (top-right)"),
        ("Tab / Esc", "Return to 10-chart grid view"),
        ("1 .. 9, 0", "Zoom into individual sidebar chart"),
        ("Click Mini-Chart", "Instant click-to-zoom for chart"),
        ("Click Hex Tile", "Pin tile (multi-province highlights)"),
        ("V", "Toggle Tile vs Nation scope view"),
        ("H or ?", "Toggle this help guide overlay"),
        ("Q or Esc", "Close modal / Quit"),
    ]
    for key, desc in col1_items:
        k_surf = font_small.render(f"{key:<17}", True, (255, 255, 255))
        d_surf = font_small.render(desc, True, DIM)
        surface.blit(k_surf, (col1_x, y))
        surface.blit(d_surf, (col1_x + 130, y))
        y += 20

    y += 8
    surface.blit(header_font.render('ECONOMIC ACCOUNTS SUITE (C)', True, ACCENT), (col1_x, y))
    y += 22
    suite_desc = [
        "Tab 1: Macro Accounts & Leaderboard (GDP/CoL/Pop)",
        "Tab 2: Goods & Provincial Economy (Prices/Inv/D vs S)",
        "Tab 3: External Sector, FX & Banking (Rates/Equity)",
        "* All metrics feature real-time turn deltas (+/-Delta)",
    ]
    for item in suite_desc:
        surface.blit(font_small.render(item, True, ACCENT if '*' in item else TEXT), (col1_x, y))
        y += 18

    # Column 2: Hex Colors & Labels
    y = 68
    surface.blit(header_font.render('2. MAP COLORS & LABELS', True, ACCENT), (col2_x, y))
    y += 28

    color_items = [
        ("Mint Green Hex", "Nation Alpha sovereign territory", (141, 211, 199)),
        ("Pale Yellow Hex", "Nation Beta sovereign territory", (255, 255, 179)),
        ("Lavender Hex", "Nation Gamma sovereign territory", (190, 186, 218)),
        ("Dark Grey Hex", "Unclaimed wilderness (unsettled)", (120, 120, 128)),
        ("Luminance Glow", "Pop heatmap (brighter = denser pop)", (255, 255, 220)),
        ("Province Outlines", "Multi-color province borders per nation", (60, 210, 230)),
    ]
    for title, desc, col in color_items:
        pygame.draw.rect(surface, col, (col2_x, y + 2, 12, 12), border_radius=2)
        surface.blit(font_small.render(title, True, col), (col2_x + 20, y))
        surface.blit(font_small.render(desc, True, DIM), (col2_x + 20, y + 15))
        y += 34

    y += 6
    surface.blit(header_font.render('TILE TEXT SUMMARY', True, ACCENT), (col2_x, y))
    y += 24
    text_items = [
        ("rXcY", "Hex axial coordinates (Row X, Col Y)"),
        ("pop <N>", "Total living agents residing on tile"),
        ("food $<P>", "Local market clearing price for food"),
        ("tr <N>", "Count of active merchant traders based here"),
        ("hs <H>+<W>n", "Homesteaders (H) + wilderness pop (W)"),
        ("+N / -N", "Net pop delta from last turn (Green/Red)"),
    ]
    for tag, desc in text_items:
        surface.blit(font_small.render(f"{tag:<12}", True, (255, 255, 255)), (col2_x, y))
        surface.blit(font_small.render(desc, True, DIM), (col2_x + 90, y))
        y += 20

    y += 10
    surface.blit(header_font.render('TRADE NETWORK & TICKER', True, ACCENT), (col2_x, y))
    y += 24
    net_items = [
        ("Grey Lines", "Overland trade routes connecting hexes"),
        ("Cyan Arrows", "Active bilateral trade (width = volume)"),
        ("Pulsing Dots", "Trade animation showing shipment direction"),
        ("MIGRATE (Cyan)", "Agents moving across tiles / homesteading"),
        ("CLAIM (Gold)", "Wilderness tile annexed by a nation"),
        ("DESTROY (Red)", "Business bankruptcy or debt liquidation"),
    ]
    for tag, desc in net_items:
        surface.blit(font_small.render(tag, True, TEXT), (col2_x, y))
        surface.blit(font_small.render(desc, True, DIM), (col2_x, y + 14))
        y += 30

    # Column 3: Badges, Rings & Glyphs
    y = 68
    surface.blit(header_font.render('3. BADGES, RINGS & GLYPHS', True, ACCENT), (col3_x, y))
    y += 28

    badge_items = [
        ("Green [ W ]", "Frontier wilderness border tile", (90, 210, 120)),
        ("Orange [ U ]", "Unrest stage (discontent brewing)", (230, 170, 60)),
        ("Deep Orange [ P ]", "Protest stage (street demonstrations)", (240, 140, 40)),
        ("Bright Red [ M ]", "Mob stage (riots / unrest violence)", (235, 70, 70)),
        ("Lime Green [ C ]", "Compromise stage (regime concessions)", (160, 230, 90)),
        ("Purple [ T ]", "Takeover stage (regime overthrown)", (180, 100, 230)),
        ("Orange Top Dot", "Food demand scarcity alert (ratio > 1.5)", (240, 150, 60)),
        ("Red Left Dot", "Severe hunger warning (>5 starving agents)", (235, 70, 70)),
        ("Green Tag T<N>", "Active traders operating on tile", (90, 210, 120)),
        ("Purple Left Dot", "High wealth inequality warning (Gini > 0.6)", (190, 110, 230)),
    ]
    for tag, desc, col in badge_items:
        pygame.draw.circle(surface, col, (col3_x + 6, y + 8), 5)
        surface.blit(font_small.render(tag, True, col), (col3_x + 18, y))
        surface.blit(font_small.render(desc, True, DIM), (col3_x + 18, y + 14))
        y += 30

    y += 6
    surface.blit(header_font.render('TERRAIN GLYPHS & ARBITRAGE', True, ACCENT), (col3_x, y))
    y += 24
    glyph_items = [
        ("Gold Triangle", "Fertile Farmland (food productivity bonus > 1.3x)", (240, 200, 90)),
        ("Green Triangle", "Dense Forest (timber productivity bonus > 1.3x)", (110, 190, 110)),
        ("White Circle", "Cold Climate (higher heating/food living cost)", (240, 245, 250)),
        ("Orange Hot Ring", "Local food price is >15% higher than neighbors", (235, 120, 60)),
        ("Blue Cold Ring", "Local food price is >15% cheaper than neighbors", (110, 170, 235)),
    ]
    for tag, desc, col in glyph_items:
        pygame.draw.circle(surface, col, (col3_x + 6, y + 8), 5)
        surface.blit(font_small.render(tag, True, col), (col3_x + 18, y))
        surface.blit(font_small.render(desc, True, DIM), (col3_x + 18, y + 14))
        y += 30
