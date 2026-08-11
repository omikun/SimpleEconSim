#!/usr/bin/env python3
"""
REGNUM V1 — Pygame hex-map viewer (Civ-style connected hexagons).

Thin presentation layer over the conserved-money engine (gdd.md): it reads
sim_nation.build_world(), steps the world with the exact same turn order +
per-currency audit as sim_nation.main(), and renders an axial pointy-top
hex map tinted by owner nation.

Controls:
    Space  : play / pause (auto-advance ~150 ms/turn)
    S / -> : step one turn (when paused)
    Esc/Q  : quit
    Hover  : shows a tile tooltip panel

Usage:
    python3 hexview.py
"""

import os
import random
import sys

# IMPORTANT: keep this line BEFORE pygame so headless tests (SDL_VIDEODRIVER=dummy)
# and interactive runs both work.
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from goods import Goods
from logger import logInit
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade, trader_wealth
from sim_nation import build_world
from hexmap import (LAYOUT_2X3, axial_to_pixel, hex_corners, pixel_to_axial)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 1200, 800
MAP_RIGHT = 860            # map area spans x in [0, MAP_RIGHT)
PANEL_LEFT = MAP_RIGHT + 12

HEX_SIZE = 55
FPS = 60
TURN_MS = 150

# Nation palette matching sim_nation.draw_map (matplotlib map).
NATION_COLORS = {
    'Alpha': (141, 211, 199),    # #8dd3c7
    'Beta':  (255, 255, 179),    # #ffffb3
    'Gamma': (190, 186, 218),    # #bebada
}
HEX_EDGE = (20, 20, 20)
BG = (28, 28, 34)
PANEL_BG = (40, 40, 48)
TEXT = (235, 235, 235)
DIM = (170, 170, 180)
RED = (235, 90, 90)
GREEN = (120, 210, 120)
ACCENT = (240, 200, 90)

# Map offset so the 2x3 layout is centered in the map area.
# center of layout: A1(0,0)->(0,0); G2(1,2)->(190.5, 165); pad by hex radius.
_OFFSET_X = (MAP_RIGHT / 2.0) - 95.0
_OFFSET_Y = (HEIGHT / 2.0) - 82.0

REVERSE_LAYOUT = {v: k for k, v in LAYOUT_2X3.items()}


def _hex_px(q, r):
    x, y = axial_to_pixel(q, r, HEX_SIZE)
    return (int(x + _OFFSET_X), int(y + _OFFSET_Y))


# ---------------------------------------------------------------------------
# World stepping (mirrors sim_nation.main() exactly)
# ---------------------------------------------------------------------------

def build_world_view():
    """Build the world + prepare viewer state."""
    tiles, nations = build_world()
    currencies = [n.currency for n in nations]
    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None]
    # name -> tile for hover lookup
    by_name = {r.name: r for r in tiles}
    return {
        'tiles': tiles,
        'nations': nations,
        'currencies': currencies,
        'pair_orders': pair_orders,
        'by_name': by_name,
        'turn': 0,
        'currency_totals': {c: fx.audit_currency_total(tiles, c)
                            for c in currencies},
        'violations': [],
    }


def step_world(world):
    """Advance one turn of the engine; mirror sim_nation.main() turn body."""
    t = world['turn'] + 1
    tiles = world['tiles']
    currencies = world['currencies']
    pair_orders = world['pair_orders']

    curr_before = {c: fx.audit_currency_total(tiles, c) for c in currencies}
    cash_before = sum(curr_before.values())
    violations = []

    for r in tiles:
        pending = {}
        for other in tiles:
            if other is r or other not in r.neighbors.values():
                continue
            for g, entries in pending_imports(r, other).items():
                pending.setdefault(g, []).extend(entries)
        r.pending_imports = pending
        r._auction_import_sales = {}

    for r in tiles:
        r.step(t)

    for r in tiles:
        for rt in r._all_routes():
            rt.advance()
            rt.deliver_pending()

    resolve_parked(tiles)

    for r, other in pair_orders:
        settle_trade(t, other, r)

    fx.cycle_all_markets(tiles, t)

    for r, other in pair_orders:
        desk = r.forex_desks.get(other.name)
        if desk is not None:
            ppp = max(0.1, other.cost_of_living) / max(0.1, r.cost_of_living)
            desk.update(0, bank=r.bank, fx_regime='managed', ppp_target=ppp)
            if getattr(r, 'destination_region', None) is other:
                desk.save_rate(r)

    for c in currencies:
        delta = fx.audit_currency_total(tiles, c) - curr_before[c]
        if abs(delta) > 5.0:
            violations.append((t, c, delta))
    cash_after = sum(fx.audit_currency_total(tiles, c) for c in currencies)
    if abs(cash_after - cash_before) > 5.0:
        violations.append((t, 'ALL', cash_after - cash_before))

    for r in tiles:
        for other in tiles:
            if other is r or other not in r.neighbors.values():
                continue
            turn_export = sum(r.export_val[g][-1]
                              for g in [Goods.food, Goods.wood, Goods.furniture]
                              if r.export_val[g])
            turn_import = sum(r.import_val[g][-1]
                              for g in [Goods.food, Goods.wood, Goods.furniture]
                              if r.import_val[g])
            r.cumulative_trade_balance += (turn_export - turn_import)
            r.trade_flow_log.append(turn_export - turn_import)

    world['turn'] = t
    world['currency_totals'] = {c: fx.audit_currency_total(tiles, c)
                                for c in currencies}
    world['violations'] = violations
    return violations


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _nation_color(region):
    owner = getattr(region, 'owner_nation', None)
    if owner is not None:
        return NATION_COLORS.get(owner.name, (150, 150, 150))
    return (150, 150, 150)


def _tile_stats(region):
    """Summary line(s) printed on each hex: pop, food price, traders."""
    pop = region.total_population[-1] if region.total_population else len(region.agents)
    food = region.recipes[Goods.food]['price']
    traders = sum(1 for a in region.agents if a.is_trader)
    return f"pop {pop}", f"food ${food:.2f}", f"tr {traders}"


def _draw_terrain_glyph(surface, region, cx, cy):
    """Small vector terrain markers under the hex center.

    wheat  -> amber wedge  (food terrain > 1.3)
    forest -> green wedge  (wood terrain > 1.3)
    cold   -> white dot    (climate == 'cold')
    """
    y = cy + 22
    if region.terrain.get(Goods.food, 1.0) > 1.3:
        pts = [(cx, y - 8), (cx - 9, y + 6), (cx + 9, y + 6)]
        pygame.draw.polygon(surface, (240, 200, 90), pts)
    if region.terrain.get(Goods.wood, 1.0) > 1.3:
        pts = [(cx, y - 8), (cx - 9, y + 6), (cx + 9, y + 6)]
        pygame.draw.polygon(surface, (110, 190, 110), pts)
    if region.climate == 'cold':
        pygame.draw.circle(surface, (240, 245, 250), (cx, y), 4)


def _draw_hex_map(surface, world, font, font_small):
    tiles = world['tiles']
    for region in tiles:
        coords = LAYOUT_2X3.get(region.name)
        if coords is None:
            continue
        cx, cy = _hex_px(*coords)
        pts = hex_corners((cx, cy), HEX_SIZE - 1)
        color = _nation_color(region)
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, HEX_EDGE, pts, 2)
        # Name headline
        name_surf = font.render(region.name, True, TEXT)
        surface.blit(name_surf, name_surf.get_rect(center=(cx, cy - 20)))
        # pop / food / traders
        line1, line2, line3 = _tile_stats(region)
        s1 = font_small.render(line1, True, TEXT)
        s2 = font_small.render(line2, True, DIM)
        s3 = font_small.render(line3, True, DIM)
        surface.blit(s1, s1.get_rect(center=(cx, cy - 2)))
        surface.blit(s2, s2.get_rect(center=(cx, cy + 12)))
        surface.blit(s3, s3.get_rect(center=(cx, cy + 26)))
        _draw_terrain_glyph(surface, region, cx, cy - 34)


def _audit_panel(surface, world, font, font_small):
    """Right-hand panel: turn, per-currency totals + deltas, play state."""
    pygame.draw.rect(surface, PANEL_BG, (PANEL_LEFT - 10, 10, WIDTH - PANEL_LEFT - 6, HEIGHT - 20))

    title = font.render("REGNUM — Hex View", True, ACCENT)
    surface.blit(title, (PANEL_LEFT, 20))

    t_ = world['turn']
    turn_line = font_small.render(f"Turn: {t_}", True, TEXT)
    surface.blit(turn_line, (PANEL_LEFT, 50))

    cursors = world.get('currency_totals', {})
    y = 80
    for c, total in cursors.items():
        line = font_small.render(f"{c}: ${total:,.0f}", True, TEXT)
        surface.blit(line, (PANEL_LEFT, y))
        y += 22

    # Hover tile tooltip
    region = world.get('hover_region')
    y = 190
    if region is not None:
        n1 = font.render(region.name, True, ACCENT)
        surface.blit(n1, (PANEL_LEFT, y))
        y += 30
        owner = getattr(region, 'owner_nation', None)
        if owner is not None:
            oline = font_small.render(f"Nation: {owner.name} ({owner.currency})", True, TEXT)
            surface.blit(oline, (PANEL_LEFT, y)); y += 20
            rline = font_small.render(f"Regime: {owner.regime_type}", True, DIM)
            surface.blit(rline, (PANEL_LEFT, y)); y += 20
            lline = font_small.render(f"Legitimacy: {owner.legitimacy:.2f}", True, DIM)
            surface.blit(lline, (PANEL_LEFT, y)); y += 20
            tr = owner.treasury()
            tline = font_small.render(
                f"Treasury: ${tr['total']:,.0f} "
                f"(cash ${tr['cash']:,.0f} / dep ${tr['deposits']:,.0f} / "
                f"{tr['food']} food)", True, TEXT)
            surface.blit(tline, (PANEL_LEFT, y)); y += 20
        for g in (Goods.food, Goods.wood, Goods.furniture):
            pline = font_small.render(f"{g.name}: ${region.recipes[g]['price']:.2f}",
                                      True, TEXT)
            surface.blit(pline, (PANEL_LEFT, y)); y += 18
        pop = region.total_population[-1] if region.total_population else len(region.agents)
        pline = font_small.render(f"Pop: {pop}", True, TEXT)
        surface.blit(pline, (PANEL_LEFT, y)); y += 18
        trline = font_small.render(
            f"Traders: {sum(1 for a in region.agents if a.is_trader)}", True, TEXT)
        surface.blit(trline, (PANEL_LEFT, y)); y += 18
        mig = region.migration_intent_log
        mline = font_small.render(
            f"Mig-intent: {mig[-1]:.2f}" if mig else "Mig-intent: --", True, TEXT)
        surface.blit(mline, (PANEL_LEFT, y)); y += 24

    # Play state + violations
    if world.get('playing'):
        pn = font_small.render("[ PLAYING ]  Space=pause  Q=quit", True, GREEN)
    else:
        pn = font_small.render("[ PAUSED ]  S=step  Space=play", True, DIM)
    surface.blit(pn, (PANEL_LEFT, 148))

    if world.get('violations'):
        v1 = font.render("AUDIT VIOLATION", True, RED)
        surface.blit(v1, (PANEL_LEFT, HEIGHT - 90))
        vline = font_small.render(
            "; ".join(f"T{v[0]} {v[1]} {v[2]:+.2f}" for v in world['violations']),
            True, RED)
        surface.blit(vline, (PANEL_LEFT, HEIGHT - 64))
    else:
        ok = font.render("Conserved: 0 LEAK / 0 SHIFT", True, GREEN)
        surface.blit(ok, (PANEL_LEFT, HEIGHT - 64))


def render_frame(surface, world):
    """Draw one full frame (map + panel).  Reusable by the headless probe."""
    font = pygame.font.Font(None, 28)
    font_small = pygame.font.Font(None, 22)
    surface.fill(BG)
    _draw_hex_map(surface, world, font, font_small)
    _audit_panel(surface, world, font, font_small)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    logInit()
    random.seed(42)
    pygame.init()
    surface = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("REGNUM V1 — Hex Map Viewer")
    clock = pygame.time.Clock()

    world = build_world_view()
    world['playing'] = False
    world['hover_region'] = None

    last_tick = pygame.time.get_ticks()
    running = True
    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE:
                    world['playing'] = not world['playing']
                    last_tick = now
                elif event.key in (pygame.K_s, pygame.K_RIGHT):
                    if not world['playing']:
                        step_world(world)

        # Auto-advance when playing
        if world['playing'] and now - last_tick >= TURN_MS:
            step_world(world)
            last_tick = now

        # Hover hit-test (map area only)
        mx, my = pygame.mouse.get_pos()
        world['hover_region'] = None
        if mx < MAP_RIGHT:
            size = HEX_SIZE
            q, r = pixel_to_axial(mx - _OFFSET_X, my - _OFFSET_Y, size)
            name = REVERSE_LAYOUT.get((q, r))
            if name is not None:
                world['hover_region'] = world['by_name'].get(name)

        render_frame(surface, world)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()