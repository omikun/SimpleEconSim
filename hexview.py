"""
REGNUM V1/V2 — Pygame hex-map viewer for 2x3 layout.
Thin presentation layer reusing modular worldview and sim_engine components.
"""

import os
import random
import sys

os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from goods import Goods
from logger import logInit
import forex as fx
from world_trade import trader_wealth
from sim_nation import build_world
from hexmap import (LAYOUT_2X3, axial_to_pixel, hex_corners, pixel_to_axial)
import sim_engine

from worldview_charts import (
    tile_charts, draw_chart_grid, draw_chart_large,
    FOOD_C as _FOOD_C, WOOD_C as _WOOD_C, FURN_C as _FURN_C,
    POP_C as _POP_C, HUNGER_C as _HUNGER_C, EXP_C as _EXP_C,
    IMP_C as _IMP_C, TAX_C as _TAX_C, TAR_C as _TAR_C,
    INH_C as _INH_C, GINI_C as _GINI_C, MIG_C as _MIG_C,
    CHART_BOX as _CHART_BOX
)
from worldview_map import (
    NATION_COLORS, HEX_EDGE, TEXT, DIM, RED, GREEN, ACCENT, EDGE_LINE,
    BADGE_ORANGE, BADGE_RED, BADGE_TRA, BADGE_GINI, HOT_RING, COLD_RING,
    UNREST_COLORS, pops_history as _pops, nation_color as _nation_color,
    region_pop as _region_pop, homesteaders as _homesteaders,
    tile_stats as _tile_stats, draw_terrain_glyph as _draw_terrain_glyph,
    draw_activity_badges as _draw_activity_badges, draw_pop_delta as _draw_pop_delta
)
from worldview_ui import (
    PANEL_BG, selected_nation as _selected_nation,
    draw_regime_readout as _draw_regime_readout
)

WIDTH, HEIGHT = 1200, 800
MAP_RIGHT = 860
PANEL_LEFT = MAP_RIGHT + 12
HEX_SIZE = 55
FPS = 60
TURN_MS = 150
TOP_BAR_H = 52
BG = (28, 28, 34)

_OFFSET_X = (MAP_RIGHT / 2.0) - 95.0
_OFFSET_Y = (HEIGHT / 2.0) - 82.0 + TOP_BAR_H
REVERSE_LAYOUT = {v: k for k, v in LAYOUT_2X3.items()}

ELECTION_C = (110, 200, 250)
COUP_C = (235, 90, 90)


def _hex_px(q, r):
    x, y = axial_to_pixel(q, r, HEX_SIZE)
    return (int(x + _OFFSET_X), int(y + _OFFSET_Y))


def _tile_at(world, mx, my):
    """Return the Region under pixel (mx, my), or None (map area only)."""
    if mx >= MAP_RIGHT:
        return None
    q, r = pixel_to_axial(mx - _OFFSET_X, my - _OFFSET_Y, HEX_SIZE)
    name = REVERSE_LAYOUT.get((q, r))
    return world['by_name'].get(name) if name is not None else None


def build_world_view():
    tiles, nations = build_world()
    currencies = [n.currency for n in nations]
    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None]
    by_name = {r.name: r for r in tiles}
    return {
        'tiles': tiles,
        'nations': nations,
        'currencies': currencies,
        'pair_orders': pair_orders,
        'by_name': by_name,
        'selected_region': None,
        'turn': 0,
        'playing': False,
        'hover_region': None,
        'frame': 0,
        'hud': False,
        'view': 0,
        'window': 100,
        'nation_history': [],
        'currency_totals': {c: fx.audit_currency_total(tiles, c)
                            for c in currencies},
        'violations': [],
        'help_open': False,
        'help_scroll': 0,
    }


def step_world(world):
    t = world['turn'] + 1
    tiles = world['tiles']
    currencies = world['currencies']
    nations = world['nations']
    pair_orders = world['pair_orders']

    violations, _ = sim_engine.step_turn(
        t, tiles, nations=nations, pair_orders=pair_orders,
        currencies=currencies, ledger_exempt=False
    )

    # Track nation history for HUD
    for n in nations:
        owner_pop = sum(r.total_population[-1] if r.total_population else len(r.agents)
                        for r in n.tiles)
        tr = n.treasury()
        world['nation_history'].append({
            'turn': t,
            'name': n.name,
            'currency': n.currency,
            'regime': n.regime_type,
            'legitimacy': n.legitimacy,
            'ruling': getattr(n, 'ruling_faction', None),
            'pop': owner_pop,
            'treasury': tr['total'],
            'food_reserve': tr['food'],
            'event': getattr(n, '_last_event', None)
        })

    world['turn'] = t
    world['currency_totals'] = {c: fx.audit_currency_total(tiles, c)
                                for c in currencies}
    world['violations'] = violations
    return violations


def _draw_top_bar(surface, world, font_small):
    n = _selected_nation(world)
    if n is None:
        return
    pygame.draw.rect(surface, (34, 34, 42), (0, 0, WIDTH, TOP_BAR_H))
    pygame.draw.line(surface, HEX_EDGE, (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 2)
    tiles = n.tiles
    pop = sum(r.total_population[-1] if r.total_population else len(r.agents)
              for r in tiles)
    tr = n.treasury()
    col = (sum(r.cost_of_living for r in tiles) / len(tiles) if tiles else 0.0)
    gdp = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in tiles)
    exports = sum(sum(v) for r in tiles for v in r.export_val.values())
    imports = sum(sum(v) for r in tiles for v in r.import_val.values())
    net = exports - imports
    trade_w = sum(trader_wealth(r) for r in tiles)
    ruling = getattr(n, 'ruling_faction', None)
    ruler = f"  ruling {ruling}" if ruling else ""
    head = font_small.render(
        f"{n.name} ({n.currency})  {n.regime_type}  legit {n.legitimacy:.2f}"
        f"{ruler}  tiles {len(tiles)}", True, ACCENT)
    surface.blit(head, (8, 6))

    stats = [
        (f"Pop {pop}", TEXT),
        (f"Treasury ${tr['total']:,.0f} ({tr['food']} food)", TEXT),
        (f"CoL {col:.2f}", TEXT),
        (f"GDP ${gdp:,.0f}", TEXT),
        (f"Ex ${exports:,.0f}", _EXP_C),
        (f"Im ${imports:,.0f}", _IMP_C),
        (f"Net {'+' if net >= 0 else ''}{net:,.0f}",
         GREEN if net >= 0 else RED),
        (f"Trade ${trade_w:,.0f}", _MIG_C),
    ]
    x = 8
    for text, color in stats:
        label = font_small.render(text, True, color)
        surface.blit(label, (x, 30))
        x += label.get_width() + 22


def _draw_hex_map(surface, world, font, font_small):
    tiles = world['tiles']
    sel = world.get('selected_region')
    for region in tiles:
        coords = LAYOUT_2X3.get(region.name)
        if coords is None:
            continue
        cx, cy = _hex_px(*coords)
        pts = hex_corners((cx, cy), HEX_SIZE - 1)
        base = _nation_color(region)
        pygame.draw.polygon(surface, base, pts)
        edge = HEX_EDGE
        pygame.draw.polygon(surface, edge, pts, 2)
        if sel is region:
            pygame.draw.polygon(surface, ACCENT, pts, 4)
        name_surf = font.render(region.name, True, TEXT)
        surface.blit(name_surf, name_surf.get_rect(center=(cx, cy - 20)))
        line1, line2, line3 = _tile_stats(region)
        s1 = font_small.render(line1, True, TEXT)
        s2 = font_small.render(line2, True, DIM)
        surface.blit(s1, s1.get_rect(center=(cx, cy - 2)))
        surface.blit(s2, s2.get_rect(center=(cx, cy + 12)))
        if line3:
            s3 = font_small.render(line3, True, DIM)
            surface.blit(s3, s3.get_rect(center=(cx, cy + 26)))
        _draw_terrain_glyph(surface, region, cx, cy - 34)
        _draw_activity_badges(surface, region, cx, cy, font_small)
        _draw_pop_delta(surface, region, cx, cy, font_small)


def _draw_panel(surface, world, font, font_small):
    d = TOP_BAR_H
    panel_w = WIDTH - PANEL_LEFT - 6
    panel_h = HEIGHT - 20 - d
    pygame.draw.rect(surface, PANEL_BG,
                     (PANEL_LEFT - 10, 10 + d, panel_w + 4, panel_h))
    title = font.render("REGNUM — Hex View", True, ACCENT)
    surface.blit(title, (PANEL_LEFT, 20 + d))
    t_ = world['turn']
    turn_line = font_small.render(f"Turn: {t_}  win={world['window']}t", True, TEXT)
    surface.blit(turn_line, (PANEL_LEFT, 50 + d))

    cursors = world.get('currency_totals', {})
    y = 80 + d
    for c, total in cursors.items():
        line = font_small.render(f"{c}: ${total:,.0f}", True, TEXT)
        surface.blit(line, (PANEL_LEFT, y))
        y += 22

    region = world.get('selected_region') or world.get('hover_region')
    chart_top = 185 + d
    chart_bottom = HEIGHT - 96
    if region is not None:
        head = font_small.render(region.name, True, TEXT)
        surface.blit(head, (PANEL_LEFT, chart_top - 6))
        charts = tile_charts(region)
        view = world.get('view', 0)
        if view == 0:
            draw_chart_grid(surface, charts, font, font_small, world['window'],
                            chart_top + 4, chart_bottom)
        else:
            idx = max(0, min(len(charts) - 1, view - 1))
            draw_chart_large(surface, charts[idx], font, font_small,
                             world['window'], chart_top + 4, chart_bottom)
        _draw_regime_readout(surface, region, font_small, chart_bottom + 24)
    else:
        hint = font_small.render("Hover or click a hex for charts", True, DIM)
        surface.blit(hint, (PANEL_LEFT, 190 + d))

    audit_y = HEIGHT - 28
    if world.get('violations'):
        v1 = font.render("AUDIT VIOLATION", True, RED)
        surface.blit(v1, (PANEL_LEFT, audit_y - 4))
    else:
        ok = font.render("Conserved: 0 LEAK / 0 SHIFT", True, GREEN)
        surface.blit(ok, (PANEL_LEFT, audit_y))


def render_frame(surface, world):
    font = pygame.font.Font(None, 28)
    font_small = pygame.font.Font(None, 22)
    surface.fill(BG)
    _draw_top_bar(surface, world, font_small)
    _draw_hex_map(surface, world, font, font_small)
    _draw_panel(surface, world, font, font_small)


def main():
    logInit()
    random.seed(42)
    pygame.init()
    surface = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("REGNUM — Hex View (2x3)")
    clock = pygame.time.Clock()
    world = build_world_view()
    _pops.clear()
    for r in world['tiles']:
        _pops[r.name] = _region_pop(r)

    last_tick = pygame.time.get_ticks()
    running = True
    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked = _tile_at(world, *event.pos)
                if clicked is not None:
                    world['selected_region'] = clicked
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE:
                    world['playing'] = not world['playing']
                    last_tick = now
                elif event.key in (pygame.K_s, pygame.K_RIGHT):
                    if not world['playing']:
                        step_world(world)
                elif event.key == pygame.K_TAB:
                    world['view'] = 0
                elif pygame.K_1 <= event.key <= pygame.K_6:
                    world['view'] = event.key - pygame.K_1 + 1

        if world['playing'] and now - last_tick >= TURN_MS:
            step_world(world)
            last_tick = now

        world['hover_region'] = None
        mx, my = pygame.mouse.get_pos()
        if mx < MAP_RIGHT and TOP_BAR_H <= my <= HEIGHT:
            world['hover_region'] = _tile_at(world, mx, my)

        render_frame(surface, world)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()