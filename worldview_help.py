"""
worldview_help.py — Full 3-Page Interactive System Manual & Seed Registry for REGNUM.

Pages:
- Page 1: Simulation Controls, Camera, Map Info Layers, Badges & Terrain Glyphs
- Page 2: 3-Tab Economic Accounts & Financial Glossary (Macro, Goods, FX/Banking)
- Page 3: Procedural World Seeds, CLI Options, and Sovereign Nations & Capitals Registry
"""

import pygame
from worldview_camera import WIDTH, HEIGHT
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN, UNREST_COLORS, NATION_COLORS

HELP_PANEL_RECT = (120, 45, 1160, 810)
CLOSE_BTN_RECT = (1245, 55, 26, 26)

HELP_TAB1_RECT = (144, 55, 230, 26)
HELP_TAB2_RECT = (384, 55, 245, 26)
HELP_TAB3_RECT = (639, 55, 275, 26)


def draw_help_modal(surface, world, font, font_small):
    """Draw comprehensive 3-page paginated modal for controls, economics, and seeds."""
    if not world.get('help_open', False):
        return

    # 0. Semi-transparent backdrop overlay
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((8, 10, 16, 210))
    surface.blit(overlay, (0, 0))

    bx, by, bw, bh = HELP_PANEL_RECT
    cur_page = world.get('help_page', 1)

    # 1. Main Card Container
    card = pygame.Surface((bw, bh), pygame.SRCALPHA)
    card.fill((16, 20, 30, 250))
    surface.blit(card, (bx, by))
    pygame.draw.rect(surface, (70, 130, 200), (bx, by, bw, bh), 2, border_radius=8)

    # 2. Navigation Tabs (3 Pages)
    tabs = [
        (HELP_TAB1_RECT, 1, "1. Controls & Map Visuals"),
        (HELP_TAB2_RECT, 2, "2. Economic Accounts Glossary"),
        (HELP_TAB3_RECT, 3, "3. World Seeds & Registry"),
    ]

    for rect, p_num, label in tabs:
        tx, ty, tw, th = rect
        is_sel = (cur_page == p_num)
        bg = (55, 75, 110) if is_sel else (28, 34, 48)
        border_c = ACCENT if is_sel else (55, 65, 85)
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        pygame.draw.rect(surface, border_c, rect, 1, border_radius=4)
        t_col = (255, 255, 255) if is_sel else DIM
        txt = font_small.render(label, True, t_col)
        surface.blit(txt, txt.get_rect(center=(tx + tw // 2, ty + th // 2)))

    # Close Button (X)
    cx, cy, cw, ch = CLOSE_BTN_RECT
    pygame.draw.rect(surface, (45, 55, 75), (cx, cy, cw, ch), border_radius=4)
    pygame.draw.rect(surface, (140, 160, 190), (cx, cy, cw, ch), 1, border_radius=4)
    x_tag = font_small.render("X", True, (240, 240, 240))
    surface.blit(x_tag, x_tag.get_rect(center=(cx + cw // 2, cy + ch // 2)))

    # 3-Column Geometry
    col_w = (bw - 64) // 3
    col1_x = bx + 24
    col2_x = col1_x + col_w + 12
    col3_x = col2_x + col_w + 12

    # =========================================================================
    # PAGE 1: CONTROLS, SHORTCUTS, MAP LAYERS & BADGES
    # =========================================================================
    if cur_page == 1:
        # Column 1: Controls & Shortcuts
        y = by + 52
        surface.blit(font_small.render("1. CORE CONTROLS & NAVIGATION", True, ACCENT), (col1_x, y))
        y += 20
        col1_items = [
            ("Space", "Play / pause auto-step (~150ms)"),
            ("N / .", "Step 1 simulation turn (while paused)"),
            ("WASD / Arrows", "Pan map camera across landmass"),
            ("Right Drag", "Smooth continuous viewport drag"),
            ("Scroll / +/-", "Zoom camera in and out smoothly"),
            ("0 / R", "Reset camera zoom & center (1:1)"),
            ("L", "Toggle Map Info Layers dock collapse"),
            ("1..6 / F1..F6", "Switch Map Layers (Overview, Pop, Econ..)"),
            ("P / Tab", "Toggle Charts vs Policies side panel"),
            ("V", "Cycle Policy scope (City / Province / Nation)"),
            ("C", "Open 3-Tab Nations Comparison Matrix"),
            ("H / ?", "Toggle this 3-Page System Guide"),
            ("Left Click", "Select & inspect hex tile economy"),
            ("Esc", "Close modals / clear selection"),
        ]
        for key, desc in col1_items:
            k_surf = font_small.render(f"[{key}]", True, (240, 205, 110))
            d_surf = font_small.render(desc, True, (210, 215, 225))
            surface.blit(k_surf, (col1_x, y))
            surface.blit(d_surf, (col1_x + 95, y))
            y += 18

        y += 8
        surface.blit(font_small.render("SOVEREIGN COMMANDS & ACTIONS", True, ACCENT), (col1_x, y))
        y += 18
        cmd_desc = [
            ("Diplomacy (D)", "Pacts, Non-Aggression, Alliances, War"),
            ("Military (M)", "Recruit garrisons, inspect army strength"),
            ("Policies (P)", "City welfare, provincial grants, tax baseline"),
            ("Help (H)", "Active seeds, nation registry & hotkeys"),
        ]
        for title, desc in cmd_desc:
            surface.blit(font_small.render(title, True, TEXT), (col1_x, y))
            surface.blit(font_small.render(desc, True, DIM), (col1_x, y + 13))
            y += 27

        # Column 2: Map Reading & Information Layers
        y = by + 52
        surface.blit(font_small.render("2. MAP INFORMATION LAYERS (1..6)", True, ACCENT), (col2_x, y))
        y += 20

        layers_info = [
            ("1. Overview", "Geographic hierarchy, nation capitals (*), province seats (+), pop & food price"),
            ("2. Physical", "Topographic elevation in meters, terrain biomes, and soil productivity bonuses"),
            ("3. Population", "Living citizens, hungry agents count, and civil unrest stage (Calm, Protest, Mob)"),
            ("4. Economy", "Nominal GDP, statutory tax rate, and provincial commercial bank capital reserves"),
            ("5. Production", "Real physical yields (Food/Wood/Furniture), active industries, and worker counts"),
            ("6. Military", "Stationed garrison units, total soldier strength, defense status, and border threat"),
        ]
        for l_title, l_desc in layers_info:
            surface.blit(font_small.render(l_title, True, (245, 220, 120)), (col2_x, y))
            y += 14
            # Multi-line wrap
            words = l_desc.split()
            line = ""
            for w in words:
                test_line = line + (" " if line else "") + w
                if font_small.size(test_line)[0] > col_w - 8:
                    surface.blit(font_small.render(line, True, DIM), (col2_x, y))
                    y += 13
                    line = w
                else:
                    line = test_line
            if line:
                surface.blit(font_small.render(line, True, DIM), (col2_x, y))
                y += 13
            y += 6

        y += 4
        surface.blit(font_small.render("TERRITORY & TRADE OVERLAYS", True, ACCENT), (col2_x, y))
        y += 18
        net_items = [
            ("Tint Overlay", "Nation sovereign territory (translucent color)"),
            ("Solid Border", "Multi-colored province administrative limits"),
            ("Grey Lines", "Overland trade routes connecting cities"),
            ("Cyan Arrows", "Bilateral commodity trade flow & direction"),
        ]
        for tag, desc in net_items:
            surface.blit(font_small.render(tag, True, TEXT), (col2_x, y))
            surface.blit(font_small.render(desc, True, DIM), (col2_x, y + 13))
            y += 26

        # Column 3: Badges, Rings & Glyphs
        y = by + 52
        surface.blit(font_small.render("3. BADGES, UNREST & GLYPHS", True, ACCENT), (col3_x, y))
        y += 20

        badge_items = [
            ("Green [ W ]", "Frontier wilderness border tile", (90, 210, 120)),
            ("Orange [ U ]", "Unrest stage (discontent brewing)", (230, 170, 60)),
            ("Deep Orange [ P ]", "Protest stage (street demonstrations)", (240, 140, 40)),
            ("Bright Red [ M ]", "Mob stage (riots / unrest violence)", (235, 70, 70)),
            ("Lime Green [ C ]", "Compromise stage (regime concessions)", (160, 230, 90)),
            ("Purple [ T ]", "Takeover stage (regime overthrown)", (180, 100, 230)),
            ("Orange Dot", "High food demand scarcity alert", (240, 150, 60)),
            ("Red Left Dot", "Severe hunger warning (>5 starving agents)", (235, 70, 70)),
            ("Green Tag T<N>", "Active traders operating on tile", (90, 210, 120)),
            ("Purple Dot", "High wealth inequality (Gini > 0.6)", (190, 110, 230)),
        ]
        for tag, desc, col in badge_items:
            pygame.draw.circle(surface, col, (col3_x + 5, y + 6), 3)
            surface.blit(font_small.render(tag, True, col), (col3_x + 14, y))
            surface.blit(font_small.render(desc, True, DIM), (col3_x + 14, y + 12))
            y += 25

        y += 4
        surface.blit(font_small.render("TERRAIN GLYPHS & ARBITRAGE", True, ACCENT), (col3_x, y))
        y += 18
        glyph_items = [
            ("Gold Triangle", "Fertile Farmland (food productivity bonus > 1.3x)", (240, 200, 90)),
            ("Green Triangle", "Dense Forest (timber productivity bonus > 1.3x)", (110, 190, 110)),
            ("White Circle", "Cold Climate (higher heating/food living cost)", (240, 245, 250)),
            ("Orange Hot Ring", "Local food price is >15% higher than neighbors", (235, 120, 60)),
            ("Blue Cold Ring", "Local food price is >15% cheaper than neighbors", (110, 170, 235)),
        ]
        for tag, desc, col in glyph_items:
            pygame.draw.circle(surface, col, (col3_x + 5, y + 6), 3)
            surface.blit(font_small.render(tag, True, col), (col3_x + 14, y))
            surface.blit(font_small.render(desc, True, DIM), (col3_x + 14, y + 12))
            y += 25

    # =========================================================================
    # PAGE 2: ECONOMIC METRICS & 3-TAB ACCOUNTS GLOSSARY
    # =========================================================================
    elif cur_page == 2:
        # Column 1: Tab 1 - Macro Accounts & Leaderboard
        y = by + 52
        surface.blit(font_small.render("TAB 1: MACRO ACCOUNTS & LEADERBOARD", True, ACCENT), (col1_x, y))
        y += 20
        tab1_glossary = [
            ("Nominal GDP ($/turn)", "Total value of all finished goods produced and cleared in market auctions at current clearing prices."),
            ("Real Chained GDP ($)", "Physical production valued at baseline basket prices. Isolates true physical output from inflation."),
            ("GDP per Capita ($)", "Average gross economic output produced per living citizen (Nominal GDP / Living Population)."),
            ("Cost of Living (CoL)", "Price index of essential subsistence basket (Food rations, Wood heating, Shelter)."),
            ("Gini Inequality Index", "Wealth concentration ratio (0.0 = perfect equality, 1.0 = hyper-inequality with extreme elite capture)."),
            ("Severe Hunger Count", "Count of impoverished citizens unable to purchase minimum subsistence rations (starvation risk)."),
            ("Social Protest Energy", "Civil discontent accumulated from inequality, food costs, and corruption towards riots/coups."),
            ("Treasury Reserves ($)", "Sovereign liquidity held by government in cash reserves and central bank deposits."),
            ("Strategic Food Reserve", "Physical grain stockpiles held in government silos for emergency famine relief."),
            ("Regime Legitimacy (0-1.0)", "Public acceptance of authority. High legitimacy deters civil unrest, unrest, and coups."),
        ]
        for term, explanation in tab1_glossary:
            surface.blit(font_small.render(term, True, (255, 255, 255)), (col1_x, y))
            y += 14
            words = explanation.split()
            line = ""
            for w in words:
                test_line = line + (" " if line else "") + w
                if font_small.size(test_line)[0] > col_w - 8:
                    surface.blit(font_small.render(line, True, DIM), (col1_x, y))
                    y += 12
                    line = w
                else:
                    line = test_line
            if line:
                surface.blit(font_small.render(line, True, DIM), (col1_x, y))
                y += 12
            y += 5

        # Column 2: Tab 2 - Goods & Provincial Economy
        y = by + 52
        surface.blit(font_small.render("TAB 2: GOODS MARKET & PROVINCES", True, ACCENT), (col2_x, y))
        y += 20
        tab2_glossary = [
            ("Market Clearing Price ($)", "Equilibrium price established in double auctions where local buyers and sellers match."),
            ("Physical Output (Units)", "Total gross quantity of physical units harvested, cut, or crafted by producers this turn."),
            ("Labor Productivity", "Output units generated per active worker agent in that specific commodity profession."),
            ("Inventory per Capita", "Total warehouse inventory divided by total living population (community reserve buffer)."),
            ("Inventory per Producer", "Warehouse buffer stock held per farmer, lumberjack, or craftsperson (safety cushion)."),
            ("Demand vs Supply (D / S)", "Total units of buy orders submitted vs sell orders offered in local pay-as-bid auctions."),
            ("Demand Ratio (D/S)", "Market scarcity index (>1.0 = scarcity / price inflation; <1.0 = supply glut / deflation)."),
            ("Sector Net Trade ($)", "Export revenues minus import expenditures for that specific commodity category."),
        ]
        for term, explanation in tab2_glossary:
            surface.blit(font_small.render(term, True, (255, 255, 255)), (col2_x, y))
            y += 14
            words = explanation.split()
            line = ""
            for w in words:
                test_line = line + (" " if line else "") + w
                if font_small.size(test_line)[0] > col_w - 8:
                    surface.blit(font_small.render(line, True, DIM), (col2_x, y))
                    y += 12
                    line = w
                else:
                    line = test_line
            if line:
                surface.blit(font_small.render(line, True, DIM), (col2_x, y))
                y += 12
            y += 6

        # Column 3: Tab 3 - External Sector, Forex & Banking
        y = by + 52
        surface.blit(font_small.render("TAB 3: FX, MONETARY & BANKING", True, ACCENT), (col3_x, y))
        y += 20
        tab3_glossary = [
            ("ForexDesk Mid Quote", "Central bank exchange rate: units of domestic currency required to purchase 1 foreign unit."),
            ("PPP Valuation Gap (%)", "Deviation from Purchasing Power Parity. (+% = undervalued / cheap exports, -% = overvalued)."),
            ("Bank Domestic FX Pool ($)", "Domestic cash set aside by provincial bank to buy foreign currency from exporters."),
            ("Foreign Reserves War Chest", "Foreign paper currency stored in bank vaults to supply local traders purchasing imports."),
            ("Commercial Bank Deposits ($)", "Customer savings liabilities owed by the provincial bank to citizens and corporations."),
            ("Bank Equity Capital ($)", "Share capital and retained earnings absorbing loan defaults and bad debts (solvency cushion)."),
            ("Solvency Ratio (Equity/Dep)", "Capital adequacy ratio (>15% = solid credit buffer, <5% = distress / insolvency risk)."),
            ("Net Trade Balance ($)", "Aggregate foreign trade surplus (+) or deficit (-) across all commodities."),
        ]
        for term, explanation in tab3_glossary:
            surface.blit(font_small.render(term, True, (255, 255, 255)), (col3_x, y))
            y += 14
            words = explanation.split()
            line = ""
            for w in words:
                test_line = line + (" " if line else "") + w
                if font_small.size(test_line)[0] > col_w - 8:
                    surface.blit(font_small.render(line, True, DIM), (col3_x, y))
                    y += 12
                    line = w
                else:
                    line = test_line
            if line:
                surface.blit(font_small.render(line, True, DIM), (col3_x, y))
                y += 12
            y += 6

    # =========================================================================
    # PAGE 3: PROCEDURAL SEEDS, CLI FLAGS & SOVEREIGN NATIONS REGISTRY
    # =========================================================================
    elif cur_page == 3:
        # Section 1: Active Procedural Seeds & CLI Parameters
        y = by + 52
        pygame.draw.rect(surface, (28, 38, 56), (bx + 20, y, bw - 40, 110), border_radius=6)
        pygame.draw.rect(surface, (50, 75, 110), (bx + 20, y, bw - 40, 110), 1, border_radius=6)
        
        surface.blit(font_small.render("ACTIVE PROCEDURAL WORLD SEEDS & RUNTIME PARAMETERS", True, ACCENT), (bx + 34, y + 10))

        seed_val = world.get('seed', 'Default')
        t_seed = world.get('terrain_seed', 'Auto')
        n_seed = world.get('nation_seed', 'Auto')

        surface.blit(font_small.render(f"- Master Simulation Seed: {seed_val}    (Pass with CLI: --seed <int>)", True, (235, 240, 250)), (bx + 34, y + 32))
        surface.blit(font_small.render(f"- Terrain & Landmass Seed: {t_seed}    (Pass with CLI: --terrain-seed <int>)", True, (180, 230, 180)), (bx + 34, y + 54))
        surface.blit(font_small.render(f"- Nations & Placement Seed: {n_seed}    (Pass with CLI: --nation-seed <int>)", True, (255, 205, 150)), (bx + 34, y + 76))
        
        cli_hint = font_small.render("Example: python3 worldview.py --seed 42 --terrain-seed 101 --nation-seed 777", True, (160, 190, 225))
        surface.blit(cli_hint, (bx + 540, y + 76))

        y += 125

        # Section 2: Sovereign Nations & Capitals Registry
        nations = world.get('nations', [])
        sec2_h = bh - 200
        pygame.draw.rect(surface, (28, 38, 56), (bx + 20, y, bw - 40, sec2_h), border_radius=6)
        pygame.draw.rect(surface, (50, 75, 110), (bx + 20, y, bw - 40, sec2_h), 1, border_radius=6)

        surface.blit(font_small.render("SOVEREIGN NATIONS, PROVINCES & CAPITALS REGISTRY", True, ACCENT), (bx + 34, y + 12))

        ny = y + 36
        for n in nations:
            cap_tile = getattr(n, 'capital', n.tiles[0] if n.tiles else None)
            cap_city = getattr(cap_tile, 'display_name', cap_tile.name) if cap_tile else 'Unknown'
            provs = getattr(n, 'provinces', [])
            prov_names = []
            for p in provs:
                p_disp = getattr(p, 'display_name', p.name)
                p_cap = getattr(p, 'capital', p.tiles[0] if p.tiles else None)
                p_cap_city = getattr(p_cap, 'display_name', p_cap.name) if p_cap else 'Unknown'
                prov_names.append(f"{p_disp} (Seat: {p_cap_city})")
            prov_str = ", ".join(prov_names) if prov_names else "No Provinces"

            n_col = NATION_COLORS.get(n.name, (245, 220, 120))
            n_line = f"* {n.name} ({n.currency}) — Regime: {n.regime_type.title()} | National Capital: * {cap_city} | Claimed Tiles: {len(n.tiles)}"
            surface.blit(font_small.render(n_line, True, n_col), (bx + 34, ny))
            
            p_line = f"   Provinces ({len(provs)}): {prov_str}"
            surface.blit(font_small.render(p_line, True, (180, 195, 215)), (bx + 34, ny + 18))
            ny += 44

    # 4. Bottom Navigation Hint Strip
    hint_text = f"Page {cur_page} / 3  |  Click Tabs above or press [1], [2], [3], [Tab], or [H]/[Esc] to close"
    hint_surf = font_small.render(hint_text, True, (150, 170, 195))
    surface.blit(hint_surf, hint_surf.get_rect(center=(bx + bw // 2, by + bh - 18)))


def help_modal_hit(pos, world):
    """Check if mouse click switches help tabs or closes the modal."""
    if not world.get('help_open', False):
        return False

    px, py = pos

    # 1. Close button (X)
    cx, cy, cw, ch = CLOSE_BTN_RECT
    if cx <= px <= cx + cw and cy <= py <= cy + ch:
        world['help_open'] = False
        return True

    # 2. Page Navigation Tabs
    tabs = [
        (HELP_TAB1_RECT, 1),
        (HELP_TAB2_RECT, 2),
        (HELP_TAB3_RECT, 3),
    ]
    for rect, p_num in tabs:
        tx, ty, tw, th = rect
        if tx <= px <= tx + tw and ty <= py <= ty + th:
            world['help_page'] = p_num
            return True

    # 3. Click outside modal closes it
    bx, by, bw, bh = HELP_PANEL_RECT
    if not (bx <= px <= bx + bw and by <= py <= by + bh):
        world['help_open'] = False
        return True

    return True
