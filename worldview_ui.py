"""
UI components: top stats bar, right panel, regime readout, ticker, zoom HUD, and help overlay.
"""

import pygame
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_charts import (PANEL_LEFT, draw_chart_grid, draw_chart_large,
                              tile_charts, EXP_C, IMP_C)
from worldview_map import HEX_EDGE, ACCENT, TEXT, DIM, RED, GREEN, UNREST_COLORS

PANEL_BG = (40, 40, 48)

# Zoom HUD button rectangles: (x, y, w, h)
ZOOM_BTN_IN = (MAP_RIGHT - 110, TOP_BAR_H + 12, 30, 26)
ZOOM_BTN_OUT = (MAP_RIGHT - 75, TOP_BAR_H + 12, 30, 26)
ZOOM_BTN_RESET = (MAP_RIGHT - 40, TOP_BAR_H + 12, 32, 26)


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


def selected_nation(world):
    pinned = world.get('selected_region')
    if pinned is not None and getattr(pinned, 'owner_nation', None) is not None:
        return pinned.owner_nation
    return world['nations'][0] if world['nations'] else None


def draw_top_bar(surface, world, font_small):
    """Civ-style top strip: stats for the currently selected nation."""
    n = selected_nation(world)
    pygame.draw.rect(surface, (34, 34, 42), (0, 0, MAP_RIGHT, TOP_BAR_H))
    pygame.draw.line(surface, HEX_EDGE, (0, TOP_BAR_H), (MAP_RIGHT, TOP_BAR_H), 2)
    font = font_small
    if n is None:
        head = font.render("REGNUM v3 — 9x9 Hex World", True, ACCENT)
        surface.blit(head, (8, 14))
        return
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
        f"{ruler}  tiles {len(tiles)}", True, ACCENT)
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
        x += label.get_width() + 22


def draw_regime_readout(surface, region, font_small, y):
    """Protest / unrest / top faction / owner nation readout."""
    if getattr(region, 'owner_nation', None) is None:
        line = font_small.render("unclaimed wilderness", True, DIM)
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
    """Right-hand panel: header, play state, audit, per-tile charts."""
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
                (f"legit {n.legitimacy:.2f}  tiles {len(n.tiles)}", TEXT),
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
    if region is not None:
        prov_s = ""
        if getattr(region, 'province', None) is not None:
            prov_s = f"  [{region.province.name}]"
        head = font_small.render(f"{region.name}{prov_s}", True, TEXT)
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
    title_font = pygame.font.Font(None, 30)
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((16, 16, 22, 242))
    surface.blit(overlay, (0, 0))
    surface.blit(title_font.render('REGNUM v3 — Hex World Controls', True, ACCENT),
                 (24, 14))
    lines = [
        'Space .......... play / pause (~150 ms/turn)',
        'N or . ......... step one turn (while paused)',
        'WASD / Arrows .. pan the camera',
        'Middle / Right . drag to pan the map',
        '+ / - / wheel .. smooth cursor-anchored zoom in / out',
        '0 or R ......... reset map zoom (1:1 center)',
        'Tab / Esc ...... return to 10-chart grid view',
        '1 .. 9, 0 ...... zoom into any of the 10 sidebar charts',
        'Click chart .... click any mini-chart to zoom into detailed view',
        'Click hex ...... pin a tile (charts stay anchored)',
        'H or ? ......... toggle this help',
        'Esc ............ close help first; Q quits either way',
        '',
        'Right panel features 10 live graphs: Prices, Pop/Hunger, Production,',
        'Trade Flow, Gov Income, Gini/Migration, Inventories, Protest Energy,',
        'GDP Output, and Demand Ratios.',
    ]
    max_w = WIDTH - 72
    wrapped = []
    for ln in lines:
        cur = ''
        for w in ln.split(' '):
            test = (cur + ' ' + w).strip()
            if font_small.size(test)[0] <= max_w or not cur:
                cur = test
            else:
                wrapped.append(cur)
                cur = w
        wrapped.append(cur)
    y = 52
    for text in wrapped:
        color = TEXT if text else (16, 16, 22)
        surface.blit(font_small.render(text, True, color), (24, y))
        y += 20
