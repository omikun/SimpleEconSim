"""Guided scenario UI composition and reusable priority pressure cards."""

from __future__ import annotations

import math
import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from worldview_ui import get_font


def scenario_pressures(world: dict) -> list[dict]:
    """Build a compact set of readable national pressures from current sim state."""
    if world.get('scenario_id') == 'egypt_1877':
        return _egypt_scenario_pressures(world)
    nation = world.get('selected_nation')
    if nation is None:
        nation = next((n for n in world.get('nations', []) if n.name == world.get('player_nation_name')), None)
    if nation is None and world.get('nations'):
        nation = world['nations'][0]
    tiles = list(getattr(nation, 'tiles', [])) if nation else []
    if not tiles:
        return [{'title': 'Choose a nation', 'value': 'Select a nation to review its situation.',
                 'cause': 'National decisions and pressures are shown for the selected country.', 'tone': 'neutral'}]

    agents = [a for tile in tiles for a in getattr(tile, 'agents', [])
              if getattr(a, 'alive', True) and not getattr(a, 'is_government', False)
              and not getattr(a, 'is_corporation', False)]
    hungry = sum(1 for a in agents if getattr(a, 'hungry_steps', 0) > 0)
    hunger_rate = hungry / max(1, len(agents))
    treasury = nation.treasury().get('total', 0.0)
    protest = sum((r.protest_energy_log[-1] if getattr(r, 'protest_energy_log', []) else 0.0) for r in tiles) / len(tiles)
    food_price = sum(r.recipes.get(__import__('goods').Goods.food, {}).get('price', 1.0) for r in tiles) / len(tiles)
    currency = getattr(nation, 'currency', '')

    if hunger_rate >= 0.15:
        food_tone, food_text = 'urgent', f'{hunger_rate:.0%} of people went hungry last turn'
        food_cause = 'Households cannot reliably afford or gather enough food.'
    elif food_price >= 2.0:
        food_tone, food_text = 'warning', f'Food prices are high ({food_price:.1f})'
        food_cause = 'High prices can push more households into hunger.'
    else:
        food_tone, food_text = 'good', f'Food prices are stable ({food_price:.1f})'
        food_cause = 'Keep watching prices and household access as policy changes.'

    try:
        from sovereign_bonds import get_bond_market
        coupons = sum(b.per_turn_coupon for b in get_bond_market().get_bonds_owed_by(nation.name))
    except Exception:
        coupons = 0.0
    fiscal_tone = 'urgent' if treasury < max(100.0, coupons * 8) else ('warning' if coupons else 'good')
    fiscal_text = f'${treasury:,.0f} {currency} available'
    fiscal_cause = (f'Bond coupons require about ${coupons:,.0f} each turn.' if coupons
                    else 'No active bond coupon is reported for this country.')

    stability_tone = 'urgent' if protest >= 6.5 else ('warning' if protest >= 3.5 else 'good')
    stability_text = f'Popular pressure {protest:.1f} / 10'
    stability_cause = 'Hunger, land loss, and repression can raise organized resistance.'
    return [
        {'title': 'Household food access', 'value': food_text, 'cause': food_cause, 'tone': food_tone},
        {'title': 'Treasury & debt', 'value': fiscal_text, 'cause': fiscal_cause, 'tone': fiscal_tone},
        {'title': 'Political support', 'value': stability_text, 'cause': stability_cause, 'tone': stability_tone},
    ]


def _egypt_scenario_pressures(world: dict) -> list[dict]:
    nation = _egypt_nation(world)
    if nation is None:
        return [{'title': 'Government unavailable', 'value': 'Select the Egyptian administration.',
                 'cause': 'The scenario needs a player government.', 'tone': 'urgent'}]
    state = world.get('scenario_state', {})
    people = [a for tile in nation.tiles for a in getattr(tile, 'agents', [])
              if getattr(a, 'alive', True) and not getattr(a, 'is_government', False)
              and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_trader', False)]
    from nutrition import deficit_fraction, fat_kg
    hungry = sum(1 for a in people if deficit_fraction(a) > 0)
    calorie_gap = sum(deficit_fraction(a) for a in people) / max(1, len(people))
    mean_fat = sum(fat_kg(a) for a in people) / max(1, len(people))
    stock = int(getattr(nation.government, 'food_inventory', 0))
    stock_turns = stock / max(1, int(state.get('relief_units_per_turn', 30)) * 4)
    protected_rate = float(world.get('scenario', {}).get('thresholds', {}).get('protected_hunger_rate', .20))
    food_tone = ('urgent' if calorie_gap >= protected_rate else
                 'warning' if stock_turns < 2 or calorie_gap >= protected_rate * .5 else 'good')
    food_value = f'{calorie_gap:.0%} calorie gap • {stock_turns:.1f} turns of public maize'
    from scenario_political_economy import stock as private_warehouse_stock
    held_grain = private_warehouse_stock(world, nation)
    food_cause = f'{held_grain} units in private warehouses; public release uses finite state stores.'

    payment_turn = int(state.get('payment_window_turn', 6))
    remaining = max(0, payment_turn - int(world.get('turn', 0)))
    payment_status = state.get('payment_status', 'upcoming')
    cash = float(getattr(nation.government.agent, 'cash', 0.0))
    remittance = float(state.get('scheduled_remittance', 200.0))
    from scenario_debt import outstanding
    claim = outstanding(world)
    confidence = float(state.get('creditor_confidence', 0.6))
    if payment_status in ('upcoming', 'unpaid', 'deferred'):
        debt_value = (f'{claim:.0f} owed • {remittance:.0f} due now' if remaining == 0
                      else f'{claim:.0f} owed • {remittance:.0f} due in {remaining} turns')
        if payment_status == 'deferred':
            debt_cause = f'Deferral added a surcharge. Pay by turn {payment_turn}; no second deferral is available.'
        else:
            debt_cause = (f'This instalment: pay {remittance:.0f}, concede {remittance / 2:.0f}, '
                          f'or defer once; creditor confidence {confidence:.0%}.')
    else:
        debt_value = f'{payment_status.title()} • creditor confidence {confidence:.0%}'
        levy = float(state.get('creditor_levy_per_turn', 0.0))
        debt_cause = (f'The Caisse collects up to {levy:.0f} units each turn until '
                      f'{float(state.get("creditor_levy_remaining", 0.0)):.0f} units are repaid. '
                      if levy else '') + f'Fiscal autonomy {float(state.get("fiscal_autonomy", 1.0)):.0%}.'
    naval_stage = state.get('naval_crisis', {}).get('stage', 'none')
    if naval_stage == 'mobilizing':
        debt_value = 'Britain weighs a naval expedition'
        debt_cause = 'No customs levy applies. Britain must fund a credible force before its claim can be imposed.'
    elif naval_stage == 'ultimatum':
        debt_value = 'British squadron off Alexandria'
        debt_cause = 'Respond to the naval ultimatum before advancing.'
    elif naval_stage == 'blockaded':
        debt_value = 'Alexandria under blockade'
        debt_cause = 'Coastal routes are blocked. Britain pays fleet upkeep each turn; Cairo can settle or hold out.'
    elif naval_stage == 'mediation':
        debt_value = 'Ottoman mediation pending'
        debt_cause = 'The fleet remains off Alexandria for one turn while Istanbul seeks terms.'
    diplomatic = state.get('diplomatic_crisis') or {}
    debt_title = 'Debt service'
    pending_offer = diplomatic.get('egyptian_proposal')
    if pending_offer:
        debt_title = 'Foreign decision'
        debt_value = f'Paris replies on turn {diplomatic.get("proposal_due_turn", "?")}'
        offer_effects = {
            'mediation': f'If both governments agree, Cairo may settle for {claim * .5:.0f} cash.',
            'joint_guarantee': 'If all sign, creditors may collect up to 5 units per turn from actual receipts.',
            'oppose_unilateral': 'French opposition raises British mobilization cost by 20; Britain may still proceed.',
        }
        debt_cause = offer_effects.get(pending_offer, 'Paris and London will weigh Cairo’s offer.')
    debt_tone = 'urgent' if payment_status in ('deferred', 'defaulted') or (remaining <= 1 and payment_status in ('upcoming', 'unpaid')) else 'warning'
    if naval_stage in ('mobilizing', 'ultimatum', 'blockaded'):
        debt_tone = 'urgent'
    occupation = state.get('occupation', {})
    controlled = [site for site, holder in state.get('campaign', {}).get('territorial_control', {}).items()
                  if holder == 'Britain']
    if controlled and not pending_offer:
        debt_title = 'Occupation & revenue'
        debt_value = 'British foothold: ' + ', '.join(controlled)
        institutions = occupation.get('institutional_control', {})
        debt_cause = (f'Customs: {institutions.get("customs", "Egypt")}; '
                      f'cabinet: {institutions.get("cabinet", "Egypt")}. '
                      f'Resistance {float(occupation.get("resistance", 0)):.0%}.')
        debt_tone = 'urgent'

    unrest = sum(float(getattr(r, 'unrest_level', 0.0)) for r in nation.tiles) / max(1, len(nation.tiles))
    legitimacy = float(getattr(nation, 'legitimacy', 0.5))
    political_tone = 'urgent' if legitimacy < 0.30 or unrest >= 0.6 else ('warning' if legitimacy < 0.5 or unrest >= 0.3 else 'good')
    politics = state.get('politics', {})
    loyalty = float(politics.get('army_loyalty', 1.0))
    movement = float(politics.get('nationalist_movement', 0.0))
    if loyalty < 0.58 or movement >= 0.55:
        political_tone = 'urgent'
    elif loyalty < 0.70 or movement >= 0.40:
        political_tone = 'warning'
    ledger = state.get('debt_ledger', [])
    recent = [entry for entry in ledger if entry.get('kind') in ('payment', 'concession_payment',
                                                                'naval_settlement', 'assigned_revenue')]
    debt_details = [f'Outstanding Caisse bonds: {claim:,.0f} units, held by Britain and France.']
    if claim <= .01:
        debt_details.append('The Caisse claim is settled; no further instalment is scheduled.')
    elif payment_status in ('upcoming', 'unpaid', 'deferred'):
        debt_details.append(f'Next service: {remittance:,.0f} units on turn {payment_turn}; spendable treasury {cash:,.0f}.')
    else:
        debt_details.append(f'The {claim:,.0f}-unit claim is in dispute or collection; normal instalments are suspended.')
    if pending_offer:
        debt_details.insert(0, f'Cairo proposed {pending_offer.replace("_", " ")}. '
                               f'France answers on turn {diplomatic["proposal_due_turn"]}; '
                               'Britain then accepts terms, proceeds alone, or withdraws.')
    assignment = state.get('collection_assignment') or {}
    if assignment.get('status') == 'active':
        sources = assignment.get('sources', {})
        debt_details.append(f'Assigned receipts: {float(sources.get("tax", 0)):.0%} of eligible tax and '
                            f'{float(sources.get("tariff", 0)):.0%} of customs, capped at '
                            f'{float(assignment.get("per_turn_cap", 0)):,.0f} units each turn.')
        debt_details.append(f'Collected from actual receipts this turn: '
                            f'{float(state.get("debt_collected_this_turn", 0.0)):,.1f} units.')
        if assignment.get('extended'):
            debt_details.append(f'Lower collection cap traded for inspection through turn '
                                f'{assignment.get("control_until_turn", "?")}.')
    else:
        debt_details.append('No active Caisse collection assignment.')
    oversight = state.get('oversight_agreement') or {}
    if oversight.get('status') == 'active':
        debt_details.append(f'Caisse inspection covers {" and ".join(oversight["scope"])} receipts; '
                            f'next review turn {oversight["review_turn"]}. Inspection alone seizes no cash.')
    if recent:
        entry = recent[-1]
        debt_details.append(f'Latest transfer: turn {entry["turn"]}, {entry["amount"]:,.2f} to {entry["creditor"]} '
                            f'from {entry.get("source", entry["kind"])}.')
    economy = state.get('political_economy', {})
    reports = economy.get('fiscal_reports', [])
    if reports:
        report = reports[-1]
        debt_details.append('Assigned receipts this turn: ' +
                            (', '.join(f'{name} {amount:.1f}' for name, amount in report['creditors'].items())
                             or 'none') + '.')
        debt_details.append(f'Relief would need {report["relief_purchase_cost"]:.1f} for '
                            f'{report["unfunded_meals"]} meals beyond this turn’s public release capacity; '
                            f'cash shortfall {report["cash_shortfall"]:.1f}, '
                            f'of which {report["attributable_to_assignment"]:.1f} is attributable to assigned receipts.')
    transfers = economy.get('tenure_transfers', [])
    dispossessed = len(transfers)
    petitions = sum(row.get('petitioners', 0) for row in economy.get('collective_by_tile', {}).values())
    strikers = sum(row.get('strikers', 0) for row in economy.get('collective_by_tile', {}).values())
    geography = state.get('geography', {})
    fleet = geography.get('fleets', {}).get('Britain')
    if fleet:
        debt_details.append(f'British fleet: {fleet["ships"]} ships, {fleet["guns"]:.0f} guns at '
                            f'{fleet["location"]}; coal {fleet["coal"]}, '
                            f'{"supplied" if fleet["supplied"] else "unsupplied"}.')
    french_fleet = geography.get('fleets', {}).get('France')
    if french_fleet:
        authorized = diplomatic.get('french_authorization', {})
        debt_details.append(f'French fleet: {french_fleet["ships"]} ships at {french_fleet["location"]}; '
                            f'{"authorized" if authorized.get("bombard") else "not authorized"} to fire.')
    debt_details.append(f'Canal: {"open" if geography.get("canal_open", True) else "closed"} to foreign transit; '
                        f'controller {geography.get("canal_controller", "Egypt")}.' )
    diplomacy = geography.get('diplomacy', {})
    if diplomacy:
        debt_details.append('Foreign positions: ' + ', '.join(f'{name} {policy.replace("_", " ")}'
                                                             for name, policy in diplomacy.items()) + '.')
    for actor in ('France', 'Britain'):
        if diplomatic.get('reasons', {}).get(actor):
            debt_details.append(f'{actor}: {diplomatic["reasons"][actor]}')
    if controlled:
        debt_details.append(f'Occupied receipts collected this turn: {float(occupation.get("collected_this_turn", 0)):.1f}; '
                            f'garrison supply paid so far: {float(occupation.get("garrison_supply_paid", 0)):.1f}.')
        debt_details.append(f'Alexandria port damage: '
                            f'{float(state.get("campaign", {}).get("infrastructure_damage", {}).get("Alexandria", 0)):.0%}; '
                            'damaged customs infrastructure lowers collectible tariff receipts.')
        debt_details.append(f'Formal sovereignty remains {occupation.get("formal_sovereign", "Egypt")}; '
                            f'Egyptian resistance is {float(occupation.get("resistance", 0)):.0%}.')
    cards = [
        {'title': 'Household maize access', 'value': food_value, 'cause': food_cause,
         'tone': food_tone, 'details': [
             f'{hungry} of {len(people)} households are underfed; the average calorie gap is {calorie_gap:.0%} of need.',
             f'Mean fat reserve is {mean_fat:.1f} kg. Reserves delay death but do not erase hunger or grievance.',
             f'{stock} public maize units remain; one release reaches up to '
             f'{min(stock // 4, int(state.get("relief_units_per_turn", 30)), hungry)} hungry households.',
             f'{held_grain} food units are held by named private warehouse owners. They offer more when the district price approaches their reservation or neighboring export price.',
             'Buying moves held maize into public stores; requisitioning does so without paying the owner.',
             'Low Nile yields persist through turn 12. Retaining grain exports can add to local stores.',
         ]},
        {'title': debt_title,
         'value': debt_value, 'cause': debt_cause, 'tone': debt_tone,
         'details': debt_details},
        {'title': 'Political support', 'value': f'Legitimacy {legitimacy:.0%} • unrest {unrest:.0%}',
         'cause': f'{dispossessed} lost plot access • {petitions} petitioners • {strikers} strikers.',
         'tone': political_tone, 'details': [
             f'Mean district unrest is {unrest:.0%}; rising protest can force concessions or a breakdown.',
             f'{dispossessed} cultivators lost plot access; {len(economy.get("migrations", []))} moved to another district.',
             f'{petitions} households petition and {strikers} withhold work; their food and wage demands are local.',
             f'Officer access: {float(politics.get("officer_access", 0.0)):.0%}; army loyalty to the palace: {loyalty:.0%}.',
             f'Civilian backing for change: {float(politics.get("civilian_support", 0.0)):.0%}; movement strength: {movement:.0%}.',
             f'Palace authority: {float(politics.get("palace_authority", 0.0)):.0%}; cabinet authority: {float(politics.get("cabinet_authority", 0.0)):.0%}.',
             'Unpaid troops, blocked promotions, food stress, tax extraction, and foreign control can shift support.',
         ]},
    ]

    if int(state.get('chapter', 1)) < 2:
        return cards

    ruler = politics.get('ruler', 'the khedive')
    coalition = politics.get('governing_coalition', 'palace').replace('_', ' ')
    cards[2].update(
        title='Egyptian authority',
        value=f'{ruler} • {coalition} cabinet',
        cause=f'Army loyalty {loyalty:.0%} • movement {movement:.0%} • legitimacy {legitimacy:.0%}.',
    )
    campaign = state.get('campaign', {})
    fort = campaign.get('forts', {}).get('Alexandria', {})
    canal = 'open' if geography.get('canal_open', True) else 'closed'
    resistance = float(occupation.get('resistance', 0.0))
    casualties = int(campaign.get('civilian_casualties', 0))
    if controlled:
        military = {
            'title': 'Occupation & resistance',
            'value': f'{len(controlled)} sites held • resistance {resistance:.0%}',
            'cause': f'{casualties} civilians injured • British garrison costs {float(occupation.get("garrison_supply_paid", 0)):.0f}.',
            'tone': 'urgent',
            'details': [
                f'Britain holds {", ".join(controlled)}; customs and cabinet control follow the territory.',
                f'Occupied receipts collected this turn: {float(occupation.get("collected_this_turn", 0)):.1f}.',
                f'British garrison supply paid so far: {float(occupation.get("garrison_supply_paid", 0)):.1f}.',
                f'Resistance {resistance:.0%}; collaboration {float(occupation.get("collaboration", 0)):.0%}. Boycotts and strikes reduce actual receipts.',
                f'{casualties} civilians injured in the campaign. Insurgency can raise that cost.',
                f'The campaign runs through at least turn {int(world.get("scenario", {}).get("horizon_turns", 20))}.',
            ],
        }
    else:
        balance = None
        if naval_stage in ('mobilizing', 'ultimatum', 'blockaded', 'campaign'):
            from scenario_gunboat import coastal_balance
            balance = coastal_balance(world)
        fleet_location = fleet.get('location', 'at sea') if fleet else 'no British fleet present'
        military = {
            'title': 'Coastal defense & canal',
            'value': f'Alexandria fort {float(fort.get("integrity", 100)):.0f}% • canal {canal}',
            'cause': (f'British fleet: {fleet_location}. '
                      + (f'Coastal force ratio {balance["ratio"]:.2f}.' if balance else 'No landing threat is present.')),
            'tone': 'urgent' if naval_stage in ('ultimatum', 'blockaded', 'campaign') else 'warning',
            'details': [
                f'Fort ammunition: {int(fort.get("ammunition", 0))}; port damage {float(campaign.get("infrastructure_damage", {}).get("Alexandria", 0)):.0%}.',
                f'Foreign canal transit is {canal}; a canal approach must pass Port Said and Ismailia before Tel el Kebir.',
                f'British fleet: {fleet_location}; coal {fleet.get("coal", 0) if fleet else 0}; supplied {bool(fleet and fleet.get("supplied"))}.',
                f'{casualties} civilians injured in the campaign so far.',
            ],
        }
    return [cards[2], cards[1], military]


def draw_scenario_route_overlay(surface, world: dict) -> None:
    """Mark strategic canal sites above the rendered terrain in Guided play."""
    state = world.get('scenario_state', {})
    geography = state.get('geography', {})
    sites = geography.get('sites', {})
    if not sites:
        return
    from worldview_camera import world_to_screen
    clipped = surface.get_clip()
    surface.set_clip(pygame.Rect(0, TOP_BAR_H + 48, MAP_RIGHT, HEIGHT - TOP_BAR_H - TICKER_H - 48))
    points = {name: world_to_screen(world, *site['position']) for name, site in sites.items()
              if site.get('position') is not None}
    canal_color = (210, 163, 90) if geography.get('canal_open') else (164, 77, 67)
    for start, end in (('Port Said', 'Ismailia'), ('Ismailia', 'Tel el Kebir'),
                       ('Tel el Kebir', 'Cairo')):
        if start in points and end in points:
            pygame.draw.line(surface, (20, 30, 39), points[start], points[end], 5)
            pygame.draw.line(surface, canal_color if end == 'Ismailia' else (176, 168, 122),
                             points[start], points[end], 2)
    control = state.get('campaign', {}).get('territorial_control', {})
    fleet = geography.get('fleets', {}).get('Britain')
    for name in ('Port Said', 'Ismailia', 'Tel el Kebir'):
        if name not in points:
            continue
        point = points[name]
        color = (222, 107, 95) if control.get(name) == 'Britain' else canal_color
        pygame.draw.circle(surface, (18, 24, 33), point, 6)
        pygame.draw.circle(surface, color, point, 5, 2)
        label = _scenario_font(13).render(name, True, (240, 222, 183))
        surface.blit(label, (point[0] + 9, point[1] - 17))
    if fleet and fleet.get('location') in points:
        px, py = points[fleet['location']]
        pygame.draw.circle(surface, (238, 113, 96), (px - 9, py + 10), 5)
        label = _scenario_font(12).render('British fleet', True, (255, 200, 181))
        surface.blit(label, (px + 1, py + 6))
    french_fleet = geography.get('fleets', {}).get('France')
    if french_fleet and french_fleet.get('location') in points:
        px, py = points[french_fleet['location']]
        pygame.draw.circle(surface, (118, 164, 225), (px - 9, py + 23), 5)
        label = _scenario_font(12).render('French fleet', True, (180, 211, 250))
        surface.blit(label, (px + 1, py + 19))
    surface.set_clip(clipped)
    from scenario_projects import draw_map_overlay
    draw_map_overlay(surface, world)


def draw_guided_header(surface, world: dict, font_small, mouse_pos=None) -> None:
    """Draw turn objective and simple composition controls above the map."""
    pygame.draw.rect(surface, (21, 25, 34), (0, TOP_BAR_H, MAP_RIGHT, 48))
    pygame.draw.line(surface, (64, 73, 94), (0, TOP_BAR_H + 47), (MAP_RIGHT, TOP_BAR_H + 47), 1)
    chapter = int(world.get('scenario_state', {}).get('chapter', 1))
    chapter_text = ('I: Nile flood and Caisse debt' if chapter == 1
                    else 'II: Sovereignty, officers, and intervention')
    title = font_small.render(f'EGYPT 1876–82  •  {chapter_text}', True, (235, 225, 190))
    surface.blit(title, (18, TOP_BAR_H + 7))
    turn = world.get('turn', 0)
    turn_text = font_small.render(
        f'Turn {turn} / {int(world.get("scenario", {}).get("horizon_turns", 20))}', True, ACCENT)
    surface.blit(turn_text, (18, TOP_BAR_H + 27))
    analysis_rect = (MAP_RIGHT - 220, TOP_BAR_H + 8, 98, 28)
    settings_rect = (MAP_RIGHT - 112, TOP_BAR_H + 8, 96, 28)
    from ui_targets import register_target
    register_target(world, analysis_rect, 'toggle_guided_analysis', scope='guided')
    register_target(world, settings_rect, 'open_settings', scope='guided')
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for rect, label in ((analysis_rect, 'Analysis'), (settings_rect, 'Settings')):
        hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        pygame.draw.rect(surface, (48, 55, 73) if hover else (31, 37, 51), rect, border_radius=4)
        pygame.draw.rect(surface, ACCENT if hover else (76, 88, 112), rect, 1, border_radius=4)
        text = font_small.render(label, True, TEXT)
        surface.blit(text, text.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))
    scenario_ended = world.get('scenario_id') == 'egypt_1877' and bool(world.get('scenario_state', {}).get('ending'))
    controls = ([((MAP_RIGHT - 326, TOP_BAR_H + 9, 94, 28),
                  'reopen_scenario_debrief', 'Summary')]
                if scenario_ended else
                [((MAP_RIGHT - 326, TOP_BAR_H + 9, 46, 28), 'play_pause', 'Pause' if world.get('playing') else 'Play'),
                 ((MAP_RIGHT - 274, TOP_BAR_H + 9, 42, 28), 'step_next', 'Next')])
    for rect, action, label in controls:
        register_target(world, rect, action, scope='guided')
        hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        pygame.draw.rect(surface, (48, 55, 73) if hover else (31, 37, 51), rect, border_radius=3)
        txt = font_small.render(label, True, TEXT)
        surface.blit(txt, txt.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))
    if world.get('guided_analysis_open'):
        analysis_tabs = [('overview', 'Overview'), ('land', 'Land'),
                         ('people', 'People'), ('projects', 'Projects')]
        for idx, (tab, label) in enumerate(analysis_tabs):
            rect = (MAP_RIGHT + 10 + idx * 78, TOP_BAR_H + 60, 75, 24)
            register_target(world, rect, ('analysis_tab', tab), scope='guided')
            active = world.get('analysis_tab', 'overview') == tab
            pygame.draw.rect(surface, (53, 68, 92) if active else (30, 36, 48), rect, border_radius=4)
            txt = font_small.render(label, True, TEXT if active else DIM)
            surface.blit(txt, txt.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))


def draw_pressure_panel(surface, world: dict, mouse_pos=None) -> None:
    """Show three priority pressures in a narrow readable right-side stack."""
    if world.get('scenario_id') == 'egypt_1877':
        _draw_egypt_scenario_panel(surface, world, mouse_pos=mouse_pos)
        return
    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 14, WIDTH - MAP_RIGHT - 20
    h = HEIGHT - TOP_BAR_H - TICKER_H - 28
    pygame.draw.rect(surface, (25, 28, 38), (x, y, w, h), border_radius=7)
    pygame.draw.rect(surface, (58, 66, 86), (x, y, w, h), 1, border_radius=7)
    title_font, body_font, small_font = get_font(24), get_font(19), get_font(16)
    title = title_font.render('Situation', True, (245, 245, 250))
    surface.blit(title, (x + 14, y + 14))
    nation = world.get('selected_nation')
    nation_name = getattr(nation, 'name', world.get('player_nation_name', 'Select a nation'))
    sub = small_font.render(nation_name, True, ACCENT)
    surface.blit(sub, (x + 14, y + 42))
    cur_y = y + 68
    colors = {'urgent': (226, 102, 94), 'warning': (225, 178, 87), 'good': (112, 205, 145), 'neutral': (140, 160, 195)}
    for pressure in scenario_pressures(world):
        color = colors.get(pressure['tone'], ACCENT)
        card_h = 87
        rect = (x + 9, cur_y, w - 18, card_h)
        pygame.draw.rect(surface, (34, 38, 51), rect, border_radius=5)
        pygame.draw.rect(surface, color, rect, 1, border_radius=5)
        if mouse_pos and rect.collidepoint(mouse_pos):
            world['_guided_hover_tip'] = (pressure['title'], pressure.get('details', [pressure['cause']]),
                                          rect, 'action')
        head = body_font.render(pressure['title'], True, color)
        surface.blit(head, (rect[0] + 10, rect[1] + 10))
        value = small_font.render(pressure['value'], True, TEXT)
        surface.blit(value, (rect[0] + 10, rect[1] + 38))
        words = pressure['cause'].split()
        line, lines = '', []
        for word in words:
            trial = (line + ' ' + word).strip()
            if small_font.size(trial)[0] > w - 42 and line:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        for idx, text in enumerate(lines[:1]):
            rendered = small_font.render(text, True, DIM)
            surface.blit(rendered, (rect[0] + 10, rect[1] + 61 + idx * 14))
        cur_y += card_h + 6
    decisions_y = min(cur_y + 5, y + h - 166)
    decisions_title = body_font.render('Decisions', True, (245, 245, 250))
    surface.blit(decisions_title, (x + 14, decisions_y))
    choices = [
        ('analysis_tab', 'Review current policies', 'overview'),
        ('analysis_tab', 'Inspect land & commons', 'land'),
        ('open_debt_analysis', 'Inspect debt & bonds', None),
    ]
    for idx, (action, label, value) in enumerate(choices):
        rect = (x + 10, decisions_y + 32 + idx * 37, w - 20, 31)
        from ui_targets import register_target
        register_target(world, rect, (action, value) if value is not None else action, scope='guided')
        mx, my = mouse_pos if mouse_pos else (-1, -1)
        hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        pygame.draw.rect(surface, (49, 59, 77) if hover else (36, 42, 56), rect, border_radius=4)
        pygame.draw.rect(surface, (92, 112, 144), rect, 1, border_radius=4)
        txt = small_font.render(label, True, TEXT)
        surface.blit(txt, txt.get_rect(midleft=(rect[0] + 10, rect[1] + rect[3] // 2)))
    if world.get('scenario_feedback'):
        feedback = small_font.render(world['scenario_feedback'], True, ACCENT)
        surface.blit(feedback, (x + 14, y + h - 24))
    else:
        hint = small_font.render('Select a district to inspect it.', True, DIM)
        surface.blit(hint, (x + 14, y + h - 24))


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    lines = []
    line = ''
    for word in str(text).split():
        trial = f'{line} {word}'.strip()
        if line and font.size(trial)[0] > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _fit_button_text(value: str, font, max_width: int) -> str:
    """Keep narrow decision labels inside their buttons; hover holds full detail."""
    if font.size(value)[0] <= max_width:
        return value
    value = value.rstrip()
    while value and font.size(value + '…')[0] > max_width:
        value = value[:-1]
    return value.rstrip() + '…'


def _scenario_font(pixel_size: float):
    """Request a font that renders at the pixel size used by this panel."""
    # get_font applies a 0.65 calibration for the rest of the interface.
    return get_font(max(9, math.ceil(pixel_size / 0.65)))


def _egypt_nation(world: dict):
    return next((n for n in world.get('nations', []) if n.name == world.get('player_nation_name')), None)


def _guided_action_preview(world: dict, nation, action_id: str) -> tuple[str, list[str]]:
    """Describe immediate rule changes separately from later simulation effects."""
    if nation is None:
        return ('Government unavailable', ['The Egyptian administration is unavailable.'])
    from nutrition import deficit_fraction
    state = world.get('scenario_state', {})
    stock = int(getattr(nation.government, 'food_inventory', 0))
    cash = float(nation.government.agent.cash)
    confidence = float(state.get('creditor_confidence', 0.6))
    autonomy = float(state.get('fiscal_autonomy', 1.0))
    legitimacy = float(getattr(nation, 'legitimacy', 0.5))
    tiles = list(nation.tiles)
    unrest = sum(float(getattr(tile, 'unrest_level', 0.0)) for tile in tiles) / max(1, len(tiles))
    if action_id.startswith('district_'):
        from scenario_district import selected_district, district_metrics
        tile = selected_district(world, nation)
        if tile is None:
            return ('Select a district', ['Click an Egyptian tile on the map.'])
        local = district_metrics(tile)
        from scenario_political_economy import district_snapshot
        econ_local = district_snapshot(world, tile)
        name = getattr(tile, 'scenario_location', None) or getattr(tile, 'display_name', tile.name)
        if action_id == 'district_arrears_relief':
            return (f'Forgive {econ_local["arrears"]:.1f} tax arrears', [
                f'Cancel unpaid cadastral assessments in {name}; {econ_local["at_risk"]} holdings are near foreclosure.',
                'Local tax falls three points. This prevents future plot loss but reduces later receipts.'])
        if action_id == 'district_support_mutual_aid':
            return ('Share private food • no treasury cost', [
                f'Organizers in {name} move surplus household food to underfed neighbors.',
                'The transfer is limited by real donor inventories and cannot feed everyone.'])
        if action_id == 'district_bargain_workers':
            return ('Owner wages +0.5 • strike ends', [
                f'Owners in {name} offer a 0.5 wage increase and pay a grant from their own cash.',
                'Petitioners receive cash; strikers return to production and local unrest eases.'])
        if action_id == 'district_break_strike':
            return ('Strike ends • injuries • support ↓', [
                f'Police or a garrison in {name} breaks the strike.',
                'Workers receive casualty memories; immediate work resumes while grievances may return.'])
        if action_id == 'district_relief':
            fed = min(10, stock // 4, local['underfed'])
            return (f'Queue {fed} meals • maize −{fed * 4}', [
                f'Reserve {fed * 4} public maize units for up to {fed} underfed households in {name}.',
                'They eat the ration at the next consumption step; the next turn’s calorie gap includes this meal.',
            ])
        if action_id == 'district_tax_relief':
            new_rate = max(0.0, local['tax_rate'] - .04)
            return (f'Tax {local["tax_rate"]:.0%}→{new_rate:.0%}', [
                f'Lower only {name}’s local tax rate by up to four points.',
                'District protest and unrest ease; future local and national tax receipts may fall.',
            ])
        if action_id == 'district_negotiate':
            return ('−15 treasury • protest ↓', [
                f'Transfer 15 treasury units to poorer households in {name}.',
                'Organizer grievances and protest pressure fall on a curve tied to the payment and current pressure.',
            ])
        if action_id == 'district_repress':
            return ('Protest ↓ • legitimacy −15pp', [
                f'Use police or a garrison in {name} to disperse protesters.',
                'The action lowers protest now but seeds casualty and broken-promise memories that can fuel later grievance.',
            ])
    if action_id == 'release_maize':
        households = [a for tile in tiles for a in getattr(tile, 'agents', [])
                      if getattr(a, 'alive', True) and not getattr(a, 'is_government', False)
                      and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_trader', False)]
        rations = min(stock // 4, int(state.get('relief_units_per_turn', 30)),
                      sum(deficit_fraction(agent) > 0 for agent in households))
        return (f'Queue {rations} meals • stores {stock}→{stock - 4 * rations}', [
            f'Now: reserve four units each for {rations} households; public stores {stock} → {stock - 4 * rations}.',
            'The worst-fed households eat these rations next turn, before hunger and the ending are measured.',
            'The meal is consumed once; later food access still depends on harvests and prices.',
        ])
    if action_id in ('repair_delta_channels', 'repair_upper_channels'):
        from scenario_projects import PROJECT_DEFS, get_project
        site = 'Nile Delta' if action_id == 'repair_delta_channels' else 'Upper Egypt'
        definition = PROJECT_DEFS['nile_repair']
        project = get_project(world, 'nile_repair', site)
        if project:
            return (f'{site}: {project["status"]}', [
                f'Paid {project["paid_cash"]:.0f} to local workers; progress '
                f'{project["progress"]}/{project["required_work"]} staffed turns.',
                f'Current state: {project["status"]}. Operating work needs '
                f'{definition["upkeep"]:.0f} treasury units of local wages per turn.',
                'Map marker and district harvest show its effects. Private owners may still hold the extra grain.',
            ])
        return (f'−{definition["cash_cost"]:.0f} treasury • {definition["work_turns"]} turns', [
            f'Pay {definition["cash_cost"]:.0f} to three local workers in {site} now; '
            f'allow {definition["work_turns"]} staffed turns for the repair.',
            f'After completion, pay {definition["upkeep"]:.0f} per turn. '
            'Restored channels raise actual food yields during the low Nile and modestly afterward.',
            'Owners can buy and reserve some extra maize; household hunger falls only if people can access it.',
            'This spending competes with the next 200-unit Caisse instalment.',
        ])
    if action_id == 'build_revenue_office':
        from scenario_projects import PROJECT_DEFS, get_project
        definition = PROJECT_DEFS['revenue_office']
        project = get_project(world, 'revenue_office', 'Alexandria')
        if project:
            return (f'Alexandria office: {project["status"]}', [
                f'Progress {project["progress"]}/{project["required_work"]} staffed turns; '
                f'{definition["upkeep"]:.0f} in local wages each operating turn.',
                'Receipts and transfers appear in the project ledger. A signed Caisse assignment is honored first.',
            ])
        return (f'−{definition["cash_cost"]:.0f} treasury • {definition["work_turns"]} turns', [
            'Pay 60 treasury units to local workers now; staff the Alexandria office for three turns.',
            'When operating, 40% of actual local Egyptian tax and tariff receipts moves to Cairo after lawful creditor claims.',
            'Tax rates and total collection do not rise. Local governments keep the rest; Cairo pays 3 per turn in wages.',
            'The Caisse reviews the accounts one turn after completion and may demand publication.',
        ])
    if action_id in ('publish_revenue_accounts', 'refuse_revenue_inspection'):
        if action_id == 'publish_revenue_accounts':
            return ('Show receipts • creditor confidence ↑', [
                'Publish the office ledger: each payer, local collector, Cairo transfer and local remainder.',
                'The Caisse can verify the existing claim; this does not pay it or extend its legal assignment.',
                'Creditor confidence rises by 6 points. This uses this turn’s major decision.',
            ])
        return ('Keep accounts private • creditor confidence ↓', [
            'Refuse the Caisse request. The office keeps collecting lawful unassigned receipts.',
            'Creditor confidence falls by 12 points. Defaulted creditors may escalate their funded naval claim.',
            'This does not erase the debt or any signed collection assignment.',
        ])
    if action_id in ('prepare_canal_line', 'repair_canal_line'):
        from scenario_projects import PROJECT_DEFS, get_project
        definition = PROJECT_DEFS['canal_line']
        project = get_project(world, 'canal_line', 'Tel el Kebir')
        if action_id == 'repair_canal_line' and project:
            cost = definition['cash_cost'] * (1.0 - project['integrity']) * .5
            return (f'Repair costs about {cost:.0f}', [
                f'Restore Tel el Kebir works from {project["integrity"]:.0%} integrity.',
                'Pay the original local crew. The line must still receive 5 in wages and 6 public food units each turn.',
                'Repairs improve the next defensive battle only while the site is staffed, supplied and unoccupied.',
            ])
        return ('−70 treasury • two turns', [
            'Pay 70 treasury units to three local workers now; two staffed turns complete the line.',
            'Operating wages cost 5 and crew meals use 6 public maize units per turn.',
            'A supplied line adds up to 55 trench strength at Tel el Kebir; battle damage and occupation can disable it.',
            'Britain budgets for the longer route and can bargain, blockade, change approach or withdraw.',
            'Food and cash spent here cannot feed households or service the 200-unit debt instalment.',
        ])
    if action_id in ('buy_private_grain', 'requisition_private_grain', 'open_private_grain_market'):
        from scenario_political_economy import stock as warehouse_stock
        held = warehouse_stock(world, nation)
        if action_id == 'buy_private_grain':
            return (f'Buy up to {min(held, 80)} maize', [
                f'Buy up to {min(held, 80)} actual private food units at 120% of each district price, limited by {cash:.1f} treasury cash.',
                'Food enters public stores for a later relief decision. Owners receive the cash and retain a production incentive.'])
        if action_id == 'requisition_private_grain':
            return (f'Take up to {min(held, 80)} maize • legitimacy −4pp', [
                'Transfer private maize into public stores without compensation, up to 80 units.',
                'Owners lose stock; local unrest rises and government legitimacy falls four points.'])
        return (f'Offer {held} private units for sale', [
            'Private holders sell to households that can pay the current district food price.',
            'Future withholding falls sharply. Poor households can still go hungry if they lack cash.'])
    if action_id == 'extend_collection_term':
        assignment = state.get('collection_assignment') or {}
        cap = float(assignment.get('per_turn_cap', 0))
        return (f'Levy cap {cap:.1f}→{cap * .5:.1f}', [
            'Propose halving the per-turn Caisse collection cap while leaving the principal unchanged.',
            'Britain and France answer next turn. If accepted, inspection extends eight turns past the campaign horizon and fiscal autonomy falls ten points.'])
    if action_id == 'prioritize_domestic_grain':
        return (f'Keep 50% • credit {confidence:.0%}→{max(0, confidence - .10):.0%}', [
            'Now: set each Egyptian district to retain 50% of food for local supply.',
            f'Creditor confidence {confidence:.0%} → {max(0, confidence - .10):.0%}.',
            'Next turns: local food supply can improve, while export receipts may fall.',
        ])
    if action_id in ('enact_grain_entitlement', 'end_grain_entitlement'):
        reports = state.get('strategic_projects', {}).get('grain_entitlement_reports', [])
        if action_id == 'end_grain_entitlement':
            return ('End the standing grain levy', [
                'Stop future in-kind transfers from private surplus to underfed households.',
                'Cairo stops paying carriers. Households lose this access unless wages or markets replace it.',
            ])
        recent = reports[-1] if reports else None
        return ('Private maize → meals • carrier wages', [
            'Each turn, take actual maize above the protected reserve from landowners and well-stocked households.',
            'Cairo pays carriers 0.05 treasury units per food unit; the levy can stop when private stores or cash run out.',
            'Private holders lose stock; legitimacy falls 1.2 points and local unrest rises slightly on turns with deliveries.',
            'This policy continues until ended. It uses a major decision to enact and can conflict with debt service.',
            *( [f'Latest delivery: {recent["units"]} units to {recent["households_reached"]} households.'] if recent else []),
        ])
    if action_id == 'recall_district_reserves':
        from scenario_projects import reserve_recall_capacity
        capacity = reserve_recall_capacity(world)
        return (f'Up to {capacity:.1f} local cash → Cairo', [
            f'Move up to {capacity:.1f} already-collected cash from district governments to Cairo once.',
            'Each local government retains at least 20 for operations. No new tax or debt is created.',
            'Affected districts gain unrest; national legitimacy falls 3.5 points. Local services have less cash.',
            'The transfer can cover a debt instalment or carrier wages, but cannot be repeated.',
        ])
    if action_id == 'reduce_fellahin_tax':
        fractions = [min(.03, float(getattr(tile.gov, 'tax_rate', 0.0))) / .03 for tile in tiles]
        next_unrest = sum(float(getattr(tile, 'unrest_level', 0.0)) * math.exp(-.11 * fraction)
                          for tile, fraction in zip(tiles, fractions)) / max(1, len(tiles))
        next_legitimacy = min(1.0, legitimacy + .04 * sum(fractions) / max(1, len(tiles)))
        return ('Tax −3pp • unrest ↓', [
            'Now: district tax rates fall by up to 3 percentage points (floor 0).',
            f'Average unrest {unrest:.2f} → {next_unrest:.2f}; legitimacy {legitimacy:.0%} → {next_legitimacy:.0%}.',
            'Next turns: households keep more income; government tax receipts may fall.',
        ])
    if action_id == 'raise_local_taxes':
        fractions = [min(.05, max(0.0, .60 - float(getattr(tile.gov, 'tax_rate', 0.0)))) / .05 for tile in tiles]
        next_unrest = sum(1.0 - (1.0 - float(getattr(tile, 'unrest_level', 0.0))) * math.exp(-.16 * fraction)
                          for tile, fraction in zip(tiles, fractions)) / max(1, len(tiles))
        next_legitimacy = max(0.0, legitimacy - .08 * sum(fractions) / max(1, len(tiles)))
        return ('Tax +5pp • unrest ↑', [
            'Now: district tax rates rise by up to 5 percentage points (cap 60%).',
            f'Average unrest {unrest:.2f} → {next_unrest:.2f}; legitimacy {legitimacy:.0%} → {next_legitimacy:.0%}.',
            'Next turns: tax receipts may rise; this also counts as coercive extraction.',
        ])
    if action_id == 'intensify_requisitions':
        next_unrest = sum(1.0 - (1.0 - float(getattr(tile, 'unrest_level', 0.0))) * math.exp(-.16)
                          for tile in tiles) / max(1, len(tiles))
        tax_increase = any(float(getattr(tile.gov, 'tax_rate', 0)) < .60 for tile in tiles)
        return (('Tax up to +4pp' if tax_increase else 'Tax ceiling held') + ' • legitimacy −8pp', [
            ('Now: raise district tax rates by up to 4 points, capped at 60%.' if tax_increase
             else 'Now: enforce the 60% emergency tax ceiling for another turn.'),
            f'Average unrest {unrest:.2f} → {next_unrest:.2f}; legitimacy {legitimacy:.0%} → {max(0, legitimacy - .08):.0%}.',
            'Repeated requisitions can cause government breakdown; higher taxes can raise future receipts.',
        ])
    if action_id == 'comply_oversight':
        return ('−2 treasury • creditor confidence +3pp', [
            'Pay Egyptian inspectors to disclose receipts at the next Caisse review.',
            'The conditional debt write-down remains in force.',
        ])
    if action_id == 'seek_narrower_oversight':
        return ('−20 treasury • request tax-only review', [
            'Pay 20 units to Britain and France and propose removing tariff inspection.',
            'The Caisse accepts only if disclosed receipts and creditor confidence are strong.',
        ])
    if action_id == 'revoke_oversight':
        agreement = state.get('oversight_agreement') or {}
        return ('Autonomy +15pp • debt claim restored', [
            f'Revoke inspection; the conditional {float(agreement.get("conditional_write_down", 0)):,.0f}-unit write-down becomes due in two turns.',
            'Creditor confidence falls 25 points. The due-debt warning will pause play.',
        ])
    if action_id == 'request_french_mediation':
        return ('Paris replies next turn', [
            'Ask France to broker a settlement for half the entire outstanding bond claim.',
            'France weighs its bond exposure, treasury, and domestic protests; Britain may reject the proposal.',
        ])
    if action_id == 'offer_joint_guarantee':
        return ('Shared levy proposal', [
            'Offer Britain and France a capped collection assignment instead of a naval expedition.',
            'Both governments must agree; an accepted levy transfers only actual Egyptian receipts.',
        ])
    if action_id == 'seek_french_opposition':
        return ('Raise British intervention cost', [
            'Ask Paris to oppose unilateral British enforcement.',
            'Opposition raises Britain’s mobilization cost and protest sensitivity, but Britain may still act alone.',
        ])
    amount = float(state.get('scheduled_remittance', 200.0))
    from scenario_debt import outstanding
    claim = outstanding(world)
    if action_id == 'pay_remittance':
        if int(world.get('turn', 0)) < int(state.get('payment_window_turn', 6)):
            payment_turn = int(state.get('payment_window_turn', 6))
            return (f'Due on turn {payment_turn} • {amount:.0f} units', [
                f'The payment window opens on turn {payment_turn}; this button is unavailable until then.',
                f'Total Caisse claim {claim:.0f}; this is one instalment.',
                f'If paid, treasury cash will change from {cash:.0f} to {cash - amount:.0f}; creditor confidence rises by 15 percentage points.',
            ])
        return (f'Cash {cash:.0f}→{cash - amount:.0f} • debt {claim:.0f}→{max(0, claim - amount):.0f}', [
            f'Now: treasury cash {cash:.0f} → {cash - amount:.0f}; one instalment is paid.',
            f'Outstanding claim {claim:.0f} → {max(0, claim - amount):.0f}; another instalment falls due in five turns if a balance remains.',
            f'Creditor confidence {confidence:.0%} → {min(1, confidence + .15):.0%}.',
            'Tradeoff: less cash remains for domestic needs; fiscal autonomy stays intact.',
        ])
    if action_id == 'concede_revenue':
        amount *= .5
        return (f'Cash {cash:.0f}→{cash - amount:.0f} • autonomy −25pp', [
            f'Now: pay {amount:.0f}, write down {amount:.0f} under conditional oversight; claim {claim:.0f} → {max(0, claim - amount * 2):.0f}.',
            'Any remaining claim has another service window in five turns.',
            f'Creditor confidence {confidence:.0%} → {min(1, confidence + .15):.0%}.',
            f'Fiscal autonomy {autonomy:.0%} → {max(0, autonomy - .25):.0%} under creditor oversight.',
        ])
    if action_id == 'defer_remittance':
        from scenario_situation import situation_template
        rules = situation_template()['debt_rules']
        due_turn = int(world.get('turn', 0)) + int(rules['deferral_delay_turns'])
        revised = amount * float(rules['deferral_multiplier'])
        return (f'Due turn {due_turn} • {revised:.0f} units', [
            f'Now: keep {cash:.0f} treasury cash. The payment rises to {revised:.0f} and is due on turn {due_turn}.',
            f'Creditor confidence {confidence:.0%} → {max(0, confidence - .30):.0%}.',
            f'Legitimacy {legitimacy:.0%} → {min(1, legitimacy + .02):.0%}. A second deferral is unavailable.',
        ])
    if action_id == 'default_remittance':
        return ('Keep cash • creditors 0%', [
            'Default keeps cash now, sets creditor confidence to zero, and cuts legitimacy by 15 points.',
            'The Caisse will claim customs receipts next turn. Cairo can contest, consent to collection, or propose arrears; force requires naval mobilization.',
        ])
    if action_id == 'reinforce_alexandria':
        from scenario_situation import situation_template
        rules = situation_template()['naval_crisis']
        crisis = state.get('naval_crisis', {})
        current = float(crisis.get('battery_strength', rules['alexandria_battery_strength']))
        cost = float(rules['battery_reinforcement_cost'])
        stronger = current + float(rules['battery_reinforcement_strength'])
        return (f'−{cost:.0f} cash • defense {current:.0f}→{stronger:.0f}', [
            f'Pay {cost:.0f} treasury units to Egyptian workers preparing Alexandria’s batteries.',
            f'Coastal defense strength rises from {current:.0f} to {stronger:.0f}; a strong defense can deter a British fleet.',
            'This uses this turn’s major domestic decision and can be done only once while Britain mobilizes.',
        ])
    if action_id == 'close_canal':
        return ('Foreign canal transit closed • confidence −10 points', [
            'Britain cannot enter the Port Said–Ismailia route while transit is closed.',
            'A fleet already off Alexandria stays there; creditor confidence falls by 10 points.',
        ])
    occupation = state.get('occupation', {})
    if action_id == 'organize_boycott':
        return ('Occupied customs receipts ↓ for 2 turns', [
            'Merchants withhold customs cooperation for two turns; collection falls to one quarter.',
            f'Resistance {float(occupation.get("resistance", 0)):.0%} → {min(1, float(occupation.get("resistance", 0)) + .12):.0%}.'])
    if action_id == 'call_general_strike':
        return ('Occupied revenue ↓ for 2 turns • resistance ↑', [
            'Tax and customs receipts available to Britain are halved for two turns.',
            'Resistance rises 15 points and Egyptian legitimacy rises 3 points.'])
    if action_id == 'coordinate_insurgency':
        return ('British garrison −3 • civilian injuries +1', [
            'Resistance rises 18 points; Egyptian legitimacy falls 3 points.',
            'If the garrison becomes too small Britain may have to withdraw.'])
    if action_id == 'collaborate_with_occupation':
        return ('Resistance −18 • legitimacy −5 points', [
            'Local collaboration improves garrison stability and weakens resistance.',
            'It increases collaboration by 25 points and costs Egyptian legitimacy.'])
    if action_id == 'negotiate_withdrawal':
        occupation = state.get('occupation', {})
        return ('Offer 30 • reply next turn', [
            f'Current resistance {float(occupation.get("resistance", 0)):.0%}. Britain weighs resistance, seized receipts, and garrison supply next turn.',
            'Acceptance transfers 30 treasury units and restores Egyptian control. Rejection spends no cash but uses this turn’s decision.',
            'The unpaid Caisse claim remains unless separate debt terms settle it.',
        ])
    politics = state.get('politics', {})
    if action_id == 'pay_army_arrears':
        from scenario_situation import situation_template
        cost = float(situation_template()['politics']['officer_pay_cost'])
        loyalty = float(politics.get('army_loyalty', 0.0))
        return (f'−{cost:.0f} cash • army loyalty ↑', [
            f'Pay {cost:.0f} treasury units to Alexandria garrison households. Palace loyalty {loyalty:.0%} → {min(1, loyalty + .22):.0%}.',
            'Alexandria garrison morale also improves. Continued wages still depend on the treasury.',
        ])
    if action_id == 'promote_egyptian_officers':
        access = float(politics.get('officer_access', 0.0))
        return (f'Officer access {access:.0%}→{min(1, access + .4):.0%}', [
            'Open senior appointments to Egyptian officers: access rises 40 points and army loyalty rises 12 points.',
            'Palace authority falls 8 points as appointments move beyond the court.',
        ])
    if action_id == 'invite_representative_cabinet':
        return ('Cabinet authority ↑ • legitimacy +5pp', [
            'Invite a representative cabinet: cabinet authority rises 35 points and civilian support 15 points.',
            'Legitimacy rises 5 points; palace authority falls 18 points.',
        ])
    if action_id == 'dismiss_foreign_controllers':
        return ('Autonomy +15pp • credit −20pp', [
            'Dismiss foreign controllers: fiscal autonomy rises 15 points; creditor confidence falls 20 points.',
            'Nationalist support rises 12 points; palace authority falls 12 points.',
        ])
    return ('', [])


def _status_delta(stat: str, delta: float | None) -> str:
    if delta is None:
        return '—'
    if abs(delta) < 1e-9:
        return '0'
    if stat in ('hunger', 'legitimacy', 'creditors', 'autonomy'):
        return f'{delta * 100:+.1f}pp'
    if stat == 'unrest':
        return f'{delta:+.2f}'
    if abs(delta) < 1:
        return f'{delta:+.2f}'
    return f'{delta:+,.0f}'


def _status_value(stat: str, value: float, precise: bool = False) -> str:
    if stat in ('hunger', 'legitimacy', 'creditors', 'autonomy'):
        return f'{value:.1%}'
    if stat == 'unrest':
        return f'{value:.2f}'
    if stat == 'cash' and precise:
        return f'{value:,.2f}'
    return f'{value:,.0f}'


def _status_factor_lines(world: dict, current: dict, stat: str) -> list[str]:
    from scenario_status import ACTION_LABELS, PHASE_LABELS, display_change
    from scenario_situation import response_label
    delta, previous_turn, factors = display_change(world, stat, current)
    lines = [f'Current: {_status_value(stat, current[stat], precise=True)} '
             f'({_status_delta(stat, delta)} since turn {previous_turn}).']
    if stat == 'tax':
        tiers = current['tax_tiers']
        lines.append(f'Gross collected this turn: national {tiers["national"]:,.1f}, '
                     f'provincial {tiers["provincial"]:,.1f}, local {tiers["municipal"]:,.1f}.')
        state = world.get('scenario_state', {})
        if state.get('debt_collection_turn') == world.get('turn'):
            seized = float(state.get('debt_collected_this_turn', 0.0))
            if seized > .001:
                lines.append(f'Caisse collection from assigned receipts: {seized:,.1f}.')
        for tile_name, row in sorted(current['tax_by_tile'].items(),
                                     key=lambda item: item[1].get('total', 0), reverse=True):
            amount = float(row.get('total', 0.0))
            if amount > .01:
                lines.append(f'{current["tile_names"].get(tile_name, tile_name)}: {amount:,.1f}.')
        if not any(row.get('total', 0) > .01 for row in current['tax_by_tile'].values()):
            lines.append('No district tax receipts have been recorded this turn.')
    if stat == 'debt':
        state = world.get('scenario_state', {})
        if state.get('payment_status') in ('upcoming', 'unpaid', 'deferred'):
            lines.append(f'Next instalment {float(state.get("scheduled_remittance", 0)):,.0f} '
                         f'on turn {state.get("payment_window_turn", "?")}; '
                         f'{int(state.get("service_periods_paid", 0))} instalments completed.')
        else:
            lines.append(f'Status: {state.get("payment_status", "unknown")}; '
                         'normal instalments are suspended or complete.')
    if stat == 'hunger':
        lines.append(f'Hungry households {current["hungry_count"]} of {current["household_count"]}.')
    if delta is None:
        return lines
    if stat == 'creditors':
        autonomy_delta, _, autonomy_factors = display_change(world, 'autonomy', current)
        if autonomy_delta is not None:
            lines.append(f'Fiscal autonomy {_status_value("autonomy", current["autonomy"])} '
                         f'({_status_delta("autonomy", autonomy_delta)} since turn {previous_turn}).')
            factors = factors + [factor for factor in autonomy_factors if factor not in factors]
    if factors:
        lines.append('Measured contributors:')
        for factor in factors:
            source = factor['source']
            label = ACTION_LABELS.get(source, PHASE_LABELS.get(source, response_label(source) or source))
            contribution = factor['changes'].get(stat)
            if contribution is None and stat == 'creditors':
                contribution = factor['changes'].get('autonomy')
                label += ' (autonomy)'
                measure = 'autonomy'
            else:
                measure = stat
            factor_line = f'• {label}: {_status_delta(measure, contribution)}'
            if stat == 'creditors' and measure == 'creditors' and 'autonomy' in factor['changes']:
                factor_line += f' confidence, {_status_delta("autonomy", factor["changes"]["autonomy"])} autonomy'
            lines.append(factor_line)
            detail = factor.get('details', {}).get(stat)
            if detail:
                lines.append(detail)
    elif abs(delta) < 1e-9:
        lines.append('No change recorded since the previous turn.')
    else:
        lines.append('The change predates factor tracking for this saved game.')
    return lines


def _draw_guided_status_bar(surface, world: dict, mouse_pos=None) -> None:
    """Show turn deltas and the measured causes of each national stat."""
    from scenario_status import display_change, snapshot
    pygame.draw.rect(surface, (12, 14, 20), (0, 0, WIDTH, TOP_BAR_H))
    pygame.draw.line(surface, (58, 66, 86), (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 1)
    nation = _egypt_nation(world)
    current = snapshot(world)
    if nation is None or current is None:
        return
    state = world.get('scenario_state', {})
    payment = float(state.get('scheduled_remittance', 200.0))
    title = getattr(nation, 'display_name', nation.name)
    surface.blit(_scenario_font(13).render(f'{title}  •  National status', True, ACCENT), (12, 3))
    status = [
        ('cash', f'Treasury {_status_value("cash", current["cash"])}', 'Treasury cash', [
            f'Next instalment costs {payment:,.0f}; a concession costs {payment / 2:,.0f} cash plus oversight.',
        ]),
        ('tax', f'Tax {_status_value("tax", current["tax"])}', 'Tax collected', [
            'Total taxes collected across Egyptian districts this turn. Hover breakdown shows where the money came from and which government tier received it.',
        ]),
        ('debt', f'Debt {_status_value("debt", current["debt"])}', 'Caisse bond claim', [
            'This is the entire unpaid bond principal held by Britain and France, separate from the next instalment.',
        ]),
        ('maize', f'Maize {_status_value("maize", current["maize"])}', 'Public maize', [
            f'Releasing stores can reserve the next meal for up to {min(current["maize"] // 4, int(state.get("relief_units_per_turn", 30)), current["hungry_count"])} hungry households.',
        ]),
        ('hunger', f'Calorie gap {current["hunger"]:.0%}', 'Household nutrition', [
            f'{current["hungry_count"]} of {current["household_count"]} households ate below need this turn.',
            f'Average calorie gap {current["calorie_gap"]:.0%} of need; mean fat reserve {current["mean_fat_kg"]:.1f} kg.',
            'A partial meal creates proportional hunger even while stored fat delays starvation. The weak Nile harvest persists through turn 12.',
        ]),
        ('legitimacy', f'Legitimacy {current["legitimacy"]:.0%}', 'Government legitimacy', [
            'The government breaks down if legitimacy reaches 10% or less.',
        ]),
        ('unrest', f'Unrest {current["unrest"]:.2f}', 'District unrest', [
            'The government breaks down if average unrest reaches 0.85.',
        ]),
        ('creditors', f'Creditors {current["creditors"]:.0%}', 'Creditor position', [
            'Payment or concession raises confidence; deferral and default damage it.',
        ]),
    ]
    x = 12
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    label_font = _scenario_font(13)
    delta_font = _scenario_font(12)
    for stat, label, tip_title, guidance in status:
        delta, _, _ = display_change(world, stat, current)
        delta_label = f' ({_status_delta(stat, delta)})'
        label_surface = label_font.render(label, True, TEXT)
        desirable = stat not in ('hunger', 'unrest', 'debt')
        color = DIM if delta is None or abs(delta) < 1e-9 else (GREEN if (delta > 0) == desirable else RED)
        delta_surface = delta_font.render(delta_label, True, color)
        width = label_surface.get_width() + delta_surface.get_width() + 18
        rect = pygame.Rect(x - 2, 24, width - 5, 24)
        if rect.collidepoint(mx, my):
            pygame.draw.rect(surface, (45, 53, 71), rect, border_radius=3)
            world['_guided_hover_tip'] = (tip_title, _status_factor_lines(world, current, stat) + guidance, rect, 'status')
        surface.blit(label_surface, (x + 2, 27))
        surface.blit(delta_surface, (x + 2 + label_surface.get_width(), 28))
        x += width


def _draw_guided_hover_tip(surface, tip) -> None:
    title, paragraphs, anchor, kind = tip
    body_font = _scenario_font(14)
    title_font = _scenario_font(16)
    card_w = 390
    lines = []
    for paragraph in paragraphs:
        lines.extend(_wrap_text(paragraph, body_font, card_w - 28))
        if kind != 'status':
            lines.append('')
    if lines and kind != 'status':
        lines.pop()
    card_h = 42 + len(lines) * 19
    x = min(MAP_RIGHT - card_w - 8, max(8, anchor.x - 5)) if kind == 'status' else MAP_RIGHT - card_w - 14
    y = TOP_BAR_H + 51 if kind == 'status' else max(TOP_BAR_H + 55, min(HEIGHT - TICKER_H - card_h - 8, anchor.y - 4))
    rect = pygame.Rect(x, y, card_w, card_h)
    pygame.draw.rect(surface, (20, 24, 34), rect, border_radius=6)
    pygame.draw.rect(surface, ACCENT, rect, 1, border_radius=6)
    surface.blit(title_font.render(title, True, ACCENT), (x + 14, y + 9))
    for idx, line in enumerate(lines):
        if line:
            surface.blit(body_font.render(line, True, TEXT), (x + 14, y + 35 + idx * 19))


def _announce_new_scenario_options(world: dict, action_rows: list) -> None:
    """Explain newly unlocked decision groups once, after urgent warnings clear."""
    visible = {action_id for row in action_rows for action_id, _, _ in row}
    previously_visible = world.get('scenario_last_visible_action_ids')
    if previously_visible is None:
        world['scenario_last_visible_action_ids'] = sorted(visible)
        return
    newly_visible = visible - set(previously_visible)
    world['scenario_last_visible_action_ids'] = sorted(visible)
    state = world.get('scenario_state', {})
    politics = state.get('politics', {})
    crisis = state.get('naval_crisis', {})
    groups = [
        ('private_grain', {'buy_private_grain', 'requisition_private_grain', 'open_private_grain_market'},
         'Private grain warehouses', 'Landowners are holding maize while households struggle to buy food. Cairo can purchase or seize stocks, or allow private sales.'),
        ('collection_term', {'extend_collection_term'}, 'Collection terms',
         'The Caisse has an active claim on actual tax or customs receipts. A longer inspection term can lower this turn’s collection cap.'),
        ('alexandria_accounts', {'publish_revenue_accounts', 'refuse_revenue_inspection'},
         'Alexandria revenue accounts',
         'The new Egyptian office has recorded local receipts and transfers to Cairo. The Caisse still holds a claim and asks to inspect the accounts. Publishing can support a settlement; refusal can raise the cost of collection.'),
        ('requisitions', {'intensify_requisitions'}, 'Emergency requisitions',
         'Higher local taxes have opened a coercive collection option. It may increase later receipts, while unrest rises and legitimacy falls.'),
        ('officers', {'pay_army_arrears', 'promote_egyptian_officers'}, 'The officer corps',
         f'Army loyalty is {float(politics.get("army_loyalty", 1.0)):.0%} and the Egyptian movement is '
         f'{float(politics.get("nationalist_movement", 0.0)):.0%}. Paying arrears or promoting officers can change who backs the government.'),
        ('cabinet', {'invite_representative_cabinet', 'dismiss_foreign_controllers'}, 'Who governs Cairo',
         f'Palace authority is {float(politics.get("palace_authority", 1.0)):.0%}; fiscal autonomy is '
         f'{float(state.get("fiscal_autonomy", 1.0)):.0%}. A representative cabinet or dismissal of controllers changes political control and creditor relations.'),
        ('alexandria', {'reinforce_alexandria'}, 'Prepare Alexandria',
         'Britain is mobilizing a squadron. Coastal defense can change the balance at Alexandria, but preparing the batteries costs treasury cash.'),
        ('france', {'request_french_mediation', 'offer_joint_guarantee', 'seek_french_opposition'}, 'Ask France to intervene',
         'The debt dispute has drawn foreign attention. Paris may broker terms, share a guarantee with Britain, or oppose British force; its answer depends on its own interests.'),
        ('canal', {'close_canal'}, 'Suez Canal transit',
         f'Naval pressure is {crisis.get("stage", "rising")}. Closing the canal can obstruct foreign movement, while disrupting trade and diplomatic support.'),
        ('oversight', {'comply_oversight', 'seek_narrower_oversight', 'revoke_oversight'}, 'Caisse revenue inspection',
         'A debt agreement now gives creditors inspection rights. Funding, narrowing, or revoking that oversight changes Egypt’s autonomy and the enforceable claim.'),
        ('occupation', {'organize_boycott', 'call_general_strike', 'coordinate_insurgency',
                        'collaborate_with_occupation', 'negotiate_withdrawal'}, 'Life under occupation',
         'Britain controls Egyptian territory. Boycotts, strikes, resistance, collaboration, and withdrawal talks now affect civilian costs and the occupation’s durability.'),
    ]
    announced = world.setdefault('scenario_announced_option_groups', [])
    pending = world.setdefault('scenario_pending_option_groups', [])
    queued = {group['key'] for group in pending}
    for key, ids, title, detail in groups:
        if newly_visible & ids and key not in announced and key not in queued:
            first_row = next(index for index, row in enumerate(action_rows)
                             if any(action_id in ids for action_id, _, _ in row))
            pending.append({'key': key, 'ids': sorted(ids), 'title': title, 'detail': detail,
                            'choices': [label for row in action_rows for action_id, label, _ in row
                                        if action_id in newly_visible & ids],
                            'first_row': first_row})
    pending[:] = [group for group in pending if set(group['ids']) & visible]
    if (pending and not world.get('scenario_warning_modal')
            and not world.get('scenario_bookend_modal') and not state.get('ending')):
        world['scenario_warning_modal'] = {'kind': 'new_options', 'groups': pending[:3]}
        world['playing'] = False
        announced.extend(group['key'] for group in pending[:3])
        del pending[:3]


def _draw_egypt_scenario_panel(surface, world: dict, mouse_pos=None) -> None:
    """Scenario-first briefing, three pressures, and focused action choices."""
    if world.get('scenario_state', {}).get('ending'):
        _draw_egypt_scenario_debrief(surface, world)
        return
    from ui_targets import register_target
    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 14, WIDTH - MAP_RIGHT - 20
    h = HEIGHT - TOP_BAR_H - TICKER_H - 28
    pygame.draw.rect(surface, (25, 28, 38), (x, y, w, h), border_radius=7)
    pygame.draw.rect(surface, (58, 66, 86), (x, y, w, h), 1, border_radius=7)
    title_font = _scenario_font(20)
    body_font = _scenario_font(16)
    small_font = _scenario_font(14)
    nation = next((n for n in world.get('nations', []) if n.name == world.get('player_nation_name')), None)
    name = getattr(nation, 'display_name', 'Khedivate of Egypt')
    surface.blit(title_font.render('Situation', True, TEXT), (x + 14, y + 12))
    surface.blit(_scenario_font(13).render(name, True, ACCENT), (x + 14, y + 42))

    cur_y = y + 68

    colors = {'urgent': (226, 102, 94), 'warning': (225, 178, 87), 'good': (112, 205, 145), 'neutral': (140, 160, 195)}
    for pressure in scenario_pressures(world):
        card_h = 70
        rect = pygame.Rect(x + 9, cur_y, w - 18, card_h)
        color = colors.get(pressure['tone'], ACCENT)
        pygame.draw.rect(surface, (34, 38, 51), rect, border_radius=5)
        pygame.draw.rect(surface, color, rect, 1, border_radius=5)
        if mouse_pos and rect.collidepoint(mouse_pos):
            world['_guided_hover_tip'] = (pressure['title'], pressure.get('details', [pressure['cause']]),
                                          rect, 'action')
        surface.blit(small_font.render(pressure['title'], True, color), (rect.x + 9, rect.y + 6))
        value_font = _scenario_font(13)
        value_lines = _wrap_text(pressure['value'], value_font, rect.w - 18)
        for idx, line in enumerate(value_lines[:2]):
            surface.blit(value_font.render(line, True, TEXT),
                         (rect.x + 9, rect.y + 25 + idx * 16))
        cause_font = _scenario_font(11)
        cause = _wrap_text(pressure['cause'], cause_font, rect.w - 18)
        for idx, line in enumerate(cause[:1]):
            surface.blit(cause_font.render(line, True, DIM),
                         (rect.x + 9, rect.y + 48 + idx * 13))
        cur_y += card_h + 4

    cur_y += 4
    from scenario_projects import strategic_strip
    strip_font = _scenario_font(12)
    strip_label_font = _scenario_font(11)
    for index, item in enumerate(strategic_strip(world)):
        strip_rect = pygame.Rect(x + 9, cur_y, w - 18, 26)
        pygame.draw.rect(surface, (34, 40, 54), strip_rect, border_radius=4)
        pygame.draw.rect(surface, (72, 85, 107), strip_rect, 1, border_radius=4)
        tone = (ACCENT if index == 0 else
                (225, 178, 87) if index == 1 else (139, 190, 166))
        surface.blit(strip_label_font.render(item['title'], True, tone),
                     (strip_rect.x + 6, strip_rect.y + 7))
        text_x = strip_rect.x + 132
        label = _fit_button_text(item['text'], strip_font, strip_rect.right - text_x - 7)
        surface.blit(strip_font.render(label, True, TEXT), (text_x, strip_rect.y + 6))
        if mouse_pos and strip_rect.collidepoint(mouse_pos):
            world['_guided_hover_tip'] = (item['title'], item['details'], strip_rect, 'action')
        cur_y += 28
    cur_y += 2
    state = world.get('scenario_state', {})
    from scenario_district import selected_district, district_metrics
    district = selected_district(world, nation) if nation else None
    decision_scope = world.get('guided_decision_scope', 'nation')
    tab_y = cur_y
    for index, (scope_id, label) in enumerate((('nation', 'Nation decisions'), ('district', 'District decisions'))):
        tab = pygame.Rect(x + 9 + index * ((w - 18) // 2), tab_y,
                          (w - 18) // 2 - 3, 29)
        active = decision_scope == scope_id
        pygame.draw.rect(surface, (53, 65, 85) if active else (31, 36, 49), tab, border_radius=4)
        pygame.draw.rect(surface, ACCENT if active else (70, 80, 100), tab, 1, border_radius=4)
        register_target(world, tab, ('guided_scope', scope_id), scope='guided')
        surface.blit(_scenario_font(13).render(label, True, TEXT if active else DIM), (tab.x + 9, tab.y + 6))
    cur_y += 35
    if decision_scope == 'district' and district is not None:
        local = district_metrics(district)
        from scenario_political_economy import district_snapshot
        local_economy = district_snapshot(world, district)
        district_name = getattr(district, 'scenario_location', None) or getattr(district, 'display_name', district.name)
        surface.blit(_scenario_font(13).render(
            f'{district_name} • {local["underfed"]}/{local["people"]} underfed • protest {local["protest"]:.1f}/10',
            True, ACCENT), (x + 13, cur_y))
        cur_y += 18
        surface.blit(_scenario_font(12).render(
            f'Calorie gap {local["mean_deficit"]:.0%} • mean fat reserve {local["mean_fat_kg"]:.1f} kg • tax {local["tax_rate"]:.0%}',
            True, DIM), (x + 13, cur_y))
        cur_y += 19
        surface.blit(_scenario_font(12).render(
            f'Private maize {local_economy["private_stock"]} • arrears {local_economy["arrears"]:.1f} • petitioners {local_economy["petitioners"]}',
            True, DIM), (x + 13, cur_y))
        cur_y += 19
    turn = int(world.get('turn', 0))
    spent = state.get('last_action_turn') == turn
    payment_ready = turn >= int(state.get('payment_window_turn', 6)) and state.get('payment_status') in ('upcoming', 'unpaid')
    stock = int(getattr(getattr(nation, 'government', None), 'food_inventory', 0)) if nation else 0
    from nutrition import deficit_fraction
    hungry_households = sum(deficit_fraction(agent) > 0
                            for tile in getattr(nation, 'tiles', [])
                            for agent in getattr(tile, 'agents', [])
                            if getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False)
                            and not getattr(agent, 'is_corporation', False) and not getattr(agent, 'is_trader', False))
    suggested = ('Release maize reserves' if stock >= 4 and hungry_households > 0
                 else 'Keep more food in Egypt')
    if int(state.get('chapter', 1)) >= 2 and decision_scope == 'nation':
        held_sites = any(owner == 'Britain' for owner in
                         state.get('campaign', {}).get('territorial_control', {}).values())
        focus = ('Occupied receipts and resistance' if held_sites else
                 'Alexandria and foreign terms' if state.get('naval_crisis', {}).get('stage')
                 in ('mobilizing', 'ultimatum', 'blockaded', 'campaign') else
                 'Army and cabinet authority')
        surface.blit(_scenario_font(13).render(f'Current focus: {focus}', True, ACCENT),
                     (x + 13, cur_y))
        cur_y += 18
    elif not payment_ready and decision_scope == 'nation':
        surface.blit(_scenario_font(13).render(f'Suggested first move: {suggested}', True, ACCENT), (x + 13, cur_y))
        cur_y += 18
    surface.blit(body_font.render('Choose one decision this turn', True, TEXT), (x + 13, cur_y))
    cur_y += 24
    treasury_cash = float(getattr(getattr(getattr(nation, 'government', None), 'agent', None), 'cash', 0.0)) if nation else 0.0
    scheduled_payment = float(state.get('scheduled_remittance', 200.0))
    from scenario_situation import situation_template
    debt_rules = situation_template()['debt_rules']
    can_defer_again = (int(state.get('deferral_count', 0)) < int(debt_rules['maximum_deferrals'])
                       and turn + int(debt_rules['deferral_delay_turns'])
                       <= int(world.get('scenario', {}).get('horizon_turns', 20)))
    can_lower_tax = any(float(getattr(tile.gov, 'tax_rate', 0.0)) > 0.0 for tile in nation.tiles) if nation else False
    can_raise_tax = any(float(getattr(tile.gov, 'tax_rate', 0.0)) < .60 for tile in nation.tiles) if nation else False
    politics = state.get('politics', {})
    action_rows = [
        [('release_maize', 'Release maize reserves', stock >= 4 and hungry_households > 0)],
        [('prioritize_domestic_grain', 'Keep more food in Egypt', not state.get('domestic_grain_priority', False))],
    ]
    grain_entitlement_active = state.get('strategic_projects', {}).get('grain_entitlement_active', False)
    action_rows.append([('end_grain_entitlement', 'End grain entitlement', True)] if grain_entitlement_active
                       else [('enact_grain_entitlement', 'Levy private surplus for relief', True)])
    from scenario_projects import reserve_recall_capacity
    action_rows.append([('recall_district_reserves', 'Call district reserves to Cairo',
                         reserve_recall_capacity(world) >= 1.0)])
    from scenario_projects import PROJECT_DEFS, get_project
    repair_cost = PROJECT_DEFS['nile_repair']['cash_cost']
    action_rows.append([
        ('repair_delta_channels', 'Repair Delta channels',
         treasury_cash >= repair_cost and get_project(world, 'nile_repair', 'Nile Delta') is None),
        ('repair_upper_channels', 'Repair Upper channels',
         treasury_cash >= repair_cost and get_project(world, 'nile_repair', 'Upper Egypt') is None),
    ])
    office = get_project(world, 'revenue_office', 'Alexandria')
    office_cost = PROJECT_DEFS['revenue_office']['cash_cost']
    action_rows.append([('build_revenue_office', 'Staff Alexandria revenue office',
                         treasury_cash >= office_cost and office is None)])
    line = get_project(world, 'canal_line', 'Tel el Kebir')
    line_def = PROJECT_DEFS['canal_line']
    action_rows.append([('prepare_canal_line', 'Prepare Tel el Kebir defenses',
                         treasury_cash >= line_def['cash_cost'] and line is None)])
    if line and line['integrity'] < 1.0:
        repair_cost = line_def['cash_cost'] * (1.0 - line['integrity']) * .5
        action_rows.append([('repair_canal_line', 'Repair Tel el Kebir works',
                             treasury_cash >= repair_cost)])
    if (state.get('strategic_projects', {}).get('fiscal_challenge') or {}).get('status') == 'pending':
        action_rows.append([
            ('publish_revenue_accounts', 'Publish revenue accounts', True),
            ('refuse_revenue_inspection', 'Refuse Caisse inspection', True),
        ])
    from scenario_political_economy import stock as warehouse_stock, district_snapshot
    held = warehouse_stock(world, nation) if nation else 0
    grain_policy = state.get('political_economy', {}).get('grain_policy', 'hold')
    if held:
        can_buy_held = any((owner := next((a for a in tile.agents
                                            if a.id == state['political_economy']['warehouse_by_tile'].get(tile.name)
                                            and a.alive), None)) is not None
                           and owner.inv_get(Goods.food, 0) > 0
                           and treasury_cash >= 1.2 * float(tile.recipes.get(Goods.food, {}).get('price', 1.0))
                           for tile in nation.tiles)
        action_rows.append([('buy_private_grain', 'Buy private maize', can_buy_held),
                            ('requisition_private_grain', 'Requisition maize', True)])
        action_rows.append([('open_private_grain_market', 'Leave to market', grain_policy != 'open')])
    action_rows.append([('reduce_fellahin_tax', 'Reduce local taxes', can_lower_tax),
                        ('raise_local_taxes', 'Raise local taxes', can_raise_tax)])
    if state.get('extraction_level', 0) > 0:
        action_rows.append([('intensify_requisitions', 'Enforce requisitions', True)])
    if (float(politics.get('army_loyalty', 1.0)) < 0.72
            or float(politics.get('nationalist_movement', 0.0)) >= 0.35):
        army_rows = []
        if not politics.get('officers_paid'):
            army_rows.append(('pay_army_arrears', 'Pay officer arrears',
                              treasury_cash >= float(situation_template()['politics']['officer_pay_cost'])))
        if not politics.get('officers_promoted'):
            army_rows.append(('promote_egyptian_officers', 'Promote Egyptian officers', True))
        if army_rows:
            action_rows.append(army_rows)
    if (float(politics.get('palace_authority', 1.0)) < 0.72
            or float(politics.get('nationalist_movement', 0.0)) >= 0.4
            or float(state.get('fiscal_autonomy', 1.0)) < 0.9):
        cabinet_rows = []
        if not politics.get('representative_cabinet'):
            cabinet_rows.append(('invite_representative_cabinet', 'Invite representative cabinet', True))
        if not politics.get('controllers_dismissed'):
            cabinet_rows.append(('dismiss_foreign_controllers', 'Dismiss foreign controllers', True))
        if cabinet_rows:
            action_rows.append(cabinet_rows)
    if state.get('naval_crisis', {}).get('stage') == 'mobilizing':
        from scenario_situation import situation_template
        reinforce_cost = float(situation_template()['naval_crisis']['battery_reinforcement_cost'])
        action_rows.append([('reinforce_alexandria', 'Prepare Alexandria defenses',
                             not state['naval_crisis'].get('reinforced') and treasury_cash >= reinforce_cost)])
    if (state.get('payment_status') in ('defaulted', 'deferred', 'unpaid')
            and state.get('naval_crisis', {}).get('stage') in ('none', 'mobilizing')
            and not state.get('diplomatic_crisis', {}).get('egyptian_proposal')):
        action_rows.append([('request_french_mediation', 'French mediation', True),
                            ('offer_joint_guarantee', 'Joint guarantee', True)])
        action_rows.append([('seek_french_opposition', 'Seek French opposition', True)])
    if (state.get('naval_crisis', {}).get('stage') in ('mobilizing', 'ultimatum', 'blockaded')
            and state.get('geography', {}).get('canal_open')):
        action_rows.append([('close_canal', 'Close canal to foreign transit', True)])
    oversight = state.get('oversight_agreement') or {}
    if oversight.get('status') == 'active':
        action_rows.append([('comply_oversight', 'Fund inspection', treasury_cash >= 2),
                            ('seek_narrower_oversight', 'Narrow inspection',
                             treasury_cash >= 20 and not oversight.get('proposal')
                             and oversight.get('scope') != ['tax'])])
        action_rows.append([('revoke_oversight', 'Revoke oversight', True)])
    assignment = state.get('collection_assignment') or {}
    if assignment.get('status') == 'active':
        action_rows.append([('extend_collection_term', 'Lower levy, longer control',
                             not assignment.get('extended', False) and not assignment.get('extension_proposal'))])
    occupation = state.get('occupation', {})
    if any(owner == 'Britain' for owner in state.get('campaign', {}).get('territorial_control', {}).values()):
        action_rows.append([('organize_boycott', 'Organize customs boycott', True),
                            ('call_general_strike', 'Call general strike', True)])
        action_rows.append([('coordinate_insurgency', 'Coordinate resistance', True),
                            ('collaborate_with_occupation', 'Collaborate locally', True)])
        withdrawal_ready = treasury_cash >= 30 and not occupation.get('withdrawal_proposal')
        action_rows.append([('negotiate_withdrawal', 'Negotiate withdrawal', withdrawal_ready)])
    if state.get('payment_status') in ('upcoming', 'unpaid', 'deferred'):
        action_rows.append([
            ('pay_remittance', 'Pay debt service', payment_ready and treasury_cash >= scheduled_payment)
        ])
    if payment_ready:
        action_rows[-1].append(('concede_revenue', 'Concede revenue', treasury_cash >= scheduled_payment * 0.5))
        action_rows.append([
            ('defer_remittance', 'Defer debt service', can_defer_again),
            ('default_remittance', 'Default', True),
        ])
    if int(state.get('chapter', 1)) >= 2:
        occupied = any(owner == 'Britain' for owner in
                       state.get('campaign', {}).get('territorial_control', {}).values())
        occupation_actions = {'organize_boycott', 'call_general_strike', 'coordinate_insurgency',
                              'collaborate_with_occupation', 'negotiate_withdrawal'}
        defense_actions = {'reinforce_alexandria', 'close_canal', 'request_french_mediation',
                           'offer_joint_guarantee', 'seek_french_opposition'}
        political_actions = {'pay_army_arrears', 'promote_egyptian_officers',
                             'invite_representative_cabinet', 'dismiss_foreign_controllers'}
        fiscal_actions = {'pay_remittance', 'concede_revenue', 'defer_remittance',
                          'default_remittance', 'comply_oversight',
                          'seek_narrower_oversight', 'revoke_oversight', 'extend_collection_term'}
        order = ([occupation_actions, defense_actions, political_actions, fiscal_actions] if occupied else
                 [defense_actions, political_actions, fiscal_actions] if
                 state.get('naval_crisis', {}).get('stage') in ('mobilizing', 'ultimatum', 'blockaded', 'campaign') else
                 [political_actions, fiscal_actions, defense_actions])
        def row_priority(row):
            ids = {action_id for action_id, _, _ in row}
            return next((index for index, group in enumerate(order) if ids & group), len(order))
        action_rows.sort(key=row_priority)
    _announce_new_scenario_options(world, action_rows)
    if decision_scope == 'district':
        local = district_metrics(district) if district else None
        econ_local = district_snapshot(world, district) if district else None
        if (local and not world.get('scenario_district_options_briefed')
                and not world.get('scenario_warning_modal')
                and not world.get('scenario_bookend_modal')):
            district_name = getattr(district, 'scenario_location', None) or getattr(district, 'display_name', district.name)
            world['scenario_warning_modal'] = {'kind': 'new_options', 'groups': [{
                'title': f'District responses in {district_name}',
                'detail': (f'{local["underfed"]} households are underfed and protest energy is '
                           f'{local["protest"]:.1f}/10. Local relief, tax relief, negotiation, '
                'and dispersal affect this tile before the national average changes. '
                'Cultivator arrears can cost plot access, while petitions and strikes can change output.'),
                'choices': ['Feed this district', 'Cut district tax', 'Negotiate locally',
                            'Disperse protesters', 'Forgive tax arrears', 'Support mutual aid',
                            'Bargain with workers', 'Break strike'],
                'first_row': 0,
            }]}
            world['scenario_district_options_briefed'] = True
            world['playing'] = False
        action_rows = [
            [('district_relief', 'Feed this district', bool(local and local['underfed'] and stock >= 4))],
            [('district_tax_relief', 'Cut district tax', bool(local and local['tax_rate'] > 0)),
             ('district_negotiate', 'Negotiate locally', bool(local and treasury_cash >= 15))],
            [('district_repress', 'Disperse protesters', bool(local and local['military_present']))],
            [('district_arrears_relief', 'Forgive tax arrears', bool(econ_local and econ_local['arrears'] > 0))],
            [('district_support_mutual_aid', 'Support mutual aid', bool(
                local and local['underfed'] and district and any(
                    a.inv_get(Goods.food, 0) >= 5 and deficit_fraction(a) == 0
                    and getattr(a, 'alive', True)
                    and not getattr(a, 'is_lord', False) and not getattr(a, 'is_government', False)
                    and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_trader', False)
                    for a in district.agents)))],
            [('district_bargain_workers', 'Bargain with workers', bool(
                econ_local and (econ_local['petitioners'] or econ_local['strikers'])
                and any((getattr(a, 'is_corporation', False) or getattr(a, 'is_lord', False))
                        and getattr(a, 'alive', True) for a in district.agents)))],
            [('district_break_strike', 'Break strike', bool(econ_local and econ_local['strikers'] and local['military_present']))],
        ]
    button_h, gap = 35, 3
    action_bottom = y + h - 89
    if len(action_rows) > max(1, (action_bottom - cur_y) // (button_h + gap)):
        cur_y += 16  # Reserve a separate line for the scroll position.
    visible_rows = max(1, (action_bottom - cur_y) // (button_h + gap))
    max_scroll = max(0, len(action_rows) - visible_rows)
    scroll = min(max_scroll, max(0, int(world.get('guided_action_scroll', 0))))
    world['guided_action_scroll'] = scroll
    world['guided_action_scroll_max'] = max_scroll
    if max_scroll:
        hint = f'Decisions {scroll + 1}–{min(len(action_rows), scroll + visible_rows)} / {len(action_rows)} • scroll panel'
        surface.blit(_scenario_font(11).render(hint, True, ACCENT), (x + 13, cur_y - 15))
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for row in action_rows[scroll:scroll + visible_rows]:
        button_w = (w - 18 - gap * (len(row) - 1)) // len(row)
        for col, (action_id, label, available) in enumerate(row):
            rect = (x + 9 + col * (button_w + gap), cur_y, button_w, button_h)
            detail, explanation = _guided_action_preview(world, nation, action_id)
            enabled = available and not spent and nation is not None
            if action_id == 'pay_remittance' and not payment_ready:
                turns_left = max(0, int(state.get('payment_window_turn', 6)) - turn)
                detail = f'Due in {turns_left} turns • {scheduled_payment:.0f} units'
            elif not available and action_id in ('pay_remittance', 'concede_revenue'):
                needed = scheduled_payment if action_id == 'pay_remittance' else scheduled_payment * .5
                detail = f'Need {needed:.0f} • cash {treasury_cash:.0f}'
            elif len(row) > 1 and action_id == 'pay_remittance':
                detail = f'−{scheduled_payment:.0f} cash • credit ↑'
            elif len(row) > 1 and action_id == 'concede_revenue':
                detail = f'−{scheduled_payment * .5:.0f} cash • autonomy ↓'
            elif len(row) > 1 and action_id == 'buy_private_grain':
                detail = f'Up to {min(held, 80)} maize • cash ↓'
            elif len(row) > 1 and action_id == 'requisition_private_grain':
                detail = f'Up to {min(held, 80)} maize • trust ↓'
            elif len(row) > 1 and action_id == 'reduce_fellahin_tax':
                detail = 'Tax −3pp • unrest ↓'
            elif len(row) > 1 and action_id == 'raise_local_taxes':
                detail = 'Tax +5pp • unrest ↑'
            if enabled:
                register_target(world, rect, ('scenario_action', action_id), scope='guided')
            hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
            if hover:
                if spent:
                    explanation = ['A major decision has already been made this turn. Advance one turn to choose again.'] + explanation
                elif action_id == 'pay_remittance' and not payment_ready:
                    pass  # The preview already explains the future availability and cost.
                elif not available:
                    if action_id == 'release_maize':
                        reason = ('No households currently need a public maize meal.' if hungry_households == 0
                                  else 'The public maize reserve has fewer than four units left.')
                    elif action_id == 'district_relief':
                        reason = 'No underfed households here, or fewer than four public maize units remain.'
                    elif action_id == 'district_tax_relief':
                        reason = 'This district already has no local tax.'
                    elif action_id == 'district_negotiate':
                        reason = 'The treasury needs 15 units for a local settlement.'
                    elif action_id == 'district_repress':
                        reason = 'This district has no police or garrison to disperse protesters.'
                    elif action_id == 'prioritize_domestic_grain':
                        reason = 'Grain is already being retained for local supply.'
                    elif action_id == 'recall_district_reserves':
                        reason = ('District reserves were already called to Cairo.'
                                  if state.get('strategic_projects', {}).get('reserve_recall_used') else
                                  'District governments have no cash above their protected reserves.')
                    elif action_id in ('repair_delta_channels', 'repair_upper_channels',
                                       'build_revenue_office', 'prepare_canal_line'):
                        project_id, site = ({
                            'repair_delta_channels': ('nile_repair', 'Nile Delta'),
                            'repair_upper_channels': ('nile_repair', 'Upper Egypt'),
                            'build_revenue_office': ('revenue_office', 'Alexandria'),
                            'prepare_canal_line': ('canal_line', 'Tel el Kebir'),
                        })[action_id]
                        existing = get_project(world, project_id, site)
                        reason = (f'{site} already has this project.' if existing else
                                  f'The treasury needs {PROJECT_DEFS[project_id]["cash_cost"]:.0f} units to start it.')
                    elif action_id == 'repair_canal_line':
                        reason = f'The treasury needs {repair_cost:.0f} units and the original crew for repairs.'
                    elif action_id in ('reduce_fellahin_tax', 'raise_local_taxes'):
                        reason = ('Local taxes are already at zero.' if action_id == 'reduce_fellahin_tax'
                                  else 'Local taxes are already at the 60% ceiling.')
                    elif action_id == 'defer_remittance':
                        reason = ('The Caisse grants only one deferral in this situation.'
                                  if int(state.get('deferral_count', 0)) >= int(debt_rules['maximum_deferrals'])
                                  else 'The revised due date would fall after the campaign ends.')
                    elif action_id == 'reinforce_alexandria':
                        reason = ('Alexandria’s batteries have already been prepared.'
                                  if state['naval_crisis'].get('reinforced')
                                  else f'Treasury cash is below the {reinforce_cost:.0f} units required.')
                    elif action_id == 'pay_army_arrears':
                        reason = 'The treasury cannot cover the officer arrears package.'
                    elif action_id == 'negotiate_withdrawal':
                        reason = ('Britain has not answered the current offer.'
                                  if occupation.get('withdrawal_proposal') else
                                  'The treasury needs 30 units to back a withdrawal offer.')
                    else:
                        needed = scheduled_payment if action_id == 'pay_remittance' else scheduled_payment * .5
                        reason = f'Treasury cash is below the {needed:.0f} units needed for this choice.'
                    explanation = [reason] + explanation
                world['_guided_hover_tip'] = (label, explanation, pygame.Rect(rect), 'action')
            bg = (52, 66, 88) if hover and enabled else ((37, 44, 59) if enabled else (30, 33, 42))
            edge = ACCENT if hover and enabled else ((80, 96, 124) if enabled else (53, 58, 70))
            pygame.draw.rect(surface, bg, rect, border_radius=4)
            pygame.draw.rect(surface, edge, rect, 1, border_radius=4)
            color = TEXT if enabled else DIM
            button_font = _scenario_font(14) if len(row) == 1 else _scenario_font(13)
            surface.blit(button_font.render(_fit_button_text(label, button_font, rect[2] - 14), True, color),
                         (rect[0] + 7, rect[1] + 2))
            detail_font = _scenario_font(12)
            surface.blit(detail_font.render(_fit_button_text(detail, detail_font, rect[2] - 14), True, DIM),
                         (rect[0] + 7, rect[1] + 19))
        cur_y += button_h + gap

    cur_y = max(cur_y, action_bottom + 4)

    reports = state.get('foreign_reports', [])
    report_font = _scenario_font(13)
    for index, report in enumerate(reports[:2]):
        report_y = cur_y + 5 + index * 19
        if report_y + 16 >= y + h - 37:
            break
        report_rect = pygame.Rect(x + 9, report_y, w - 18, 18)
        hover = report_rect.collidepoint(mx, my)
        if hover:
            pygame.draw.rect(surface, (45, 53, 71), report_rect, border_radius=3)
            world['_guided_hover_tip'] = (
                f'{report["nation"]} situation',
                [report['summary'], report['detail']], report_rect, 'action',
            )
        delta_text = report.get('delta_label')
        if delta_text is None:
            delta_text = f'{report.get("delta", 0.0):+.1f}'
        report_line = f'{report["nation"]}: {report["stage"]} {report["energy"]:.1f} ({delta_text})'
        surface.blit(report_font.render(report_line, True, ACCENT if hover else DIM),
                     (report_rect.x + 4, report_rect.y + 2))

    message = world.get('scenario_feedback', '')
    if message:
        message_font = _scenario_font(12)
        lines = _wrap_text(message, message_font, w - 28)
        for idx, line in enumerate(lines[:2]):
            surface.blit(message_font.render(line, True, ACCENT), (x + 14, y + h - 35 + idx * 16))
    elif spent:
        surface.blit(_scenario_font(12).render('Decision recorded. Advance a turn to see its effects.', True, DIM), (x + 14, y + h - 24))
    else:
        surface.blit(_scenario_font(12).render('Select a district to inspect its details.', True, DIM), (x + 14, y + h - 24))


def _draw_egypt_scenario_debrief(surface, world: dict) -> None:
    """Keep a compact result marker after the full debrief modal is closed."""
    from ui_targets import register_target
    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 14, WIDTH - MAP_RIGHT - 20
    h = 180
    pygame.draw.rect(surface, (25, 28, 38), (x, y, w, h), border_radius=7)
    pygame.draw.rect(surface, ACCENT, (x, y, w, h), 1, border_radius=7)
    debrief = world.get('scenario_state', {}).get('debrief', {})
    surface.blit(_scenario_font(20).render(debrief.get('title', 'Campaign complete'), True, ACCENT),
                 (x + 14, y + 18))
    for index, line in enumerate(_wrap_text(debrief.get('summary', ''), _scenario_font(15), w - 30)[:2]):
        surface.blit(_scenario_font(15).render(line, True, TEXT), (x + 14, y + 53 + index * 22))
    button = pygame.Rect(x + 14, y + 119, w - 28, 43)
    register_target(world, button, 'reopen_scenario_debrief', scope='guided')
    pygame.draw.rect(surface, (48, 62, 80), button, border_radius=5)
    pygame.draw.rect(surface, ACCENT, button, 1, border_radius=5)
    label = _scenario_font(16).render('View full campaign summary', True, TEXT)
    surface.blit(label, label.get_rect(center=button.center))


def _draw_guided_projects_analysis(surface, world: dict, mouse_pos=None) -> None:
    """Show project inputs, ownership, and measured effects on the Analysis page."""
    from scenario_projects import PROJECT_DEFS

    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 96, WIDTH - MAP_RIGHT - 20
    h = HEIGHT - y - TICKER_H - 14
    panel = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, (25, 28, 38), panel, border_radius=7)
    pygame.draw.rect(surface, (58, 66, 86), panel, 1, border_radius=7)
    title_font = _scenario_font(19)
    body_font = _scenario_font(13)
    tiny_font = _scenario_font(12)
    surface.blit(title_font.render('Strategic projects', True, TEXT), (x + 12, y + 11))
    surface.blit(tiny_font.render('Actual inputs and receipts • one major order per turn', True, DIM),
                 (x + 12, y + 38))
    project_state = world.get('scenario_state', {}).get('strategic_projects', {})
    projects = project_state.get('projects', [])
    payments = project_state.get('payments', [])
    wages = sum(float(row.get('amount', 0)) for row in payments)
    crew_food = sum(int(row.get('food_units', 0)) for row in payments
                    if row.get('kind') == 'crew_food')
    transfers = sum(float(row['central_transfer']) for row in
                    project_state.get('revenue_reports', []))
    surface.blit(body_font.render(f'Crews paid {wages:.0f} • crew maize {crew_food} • Cairo receipts +{transfers:.0f}',
                                  True, ACCENT), (x + 12, y + 60))
    if not projects:
        for index, line in enumerate(('No project has been funded.',
                                      'Choose an irrigation repair, revenue office, or defense line',
                                      'in the Situation panel. Its site will appear on the map.')):
            surface.blit(body_font.render(line, True, DIM), (x + 12, y + 97 + index * 20))
        return
    for index, project in enumerate(projects[:4]):
        definition = PROJECT_DEFS[project['kind']]
        card = pygame.Rect(x + 9, y + 91 + index * 113, w - 18, 106)
        pygame.draw.rect(surface, (34, 40, 54), card, border_radius=5)
        pygame.draw.rect(surface, ACCENT if project['status'] == 'operating'
                         else (110, 125, 151), card, 1, border_radius=5)
        title = f'{definition["title"]} • {project["site"]}'
        surface.blit(body_font.render(_fit_button_text(title, body_font, card.w - 16), True, TEXT),
                     (card.x + 8, card.y + 7))
        rows = [
            f'{project["status"].title()} • work {project["progress"]}/{project["required_work"]} '
            f'• integrity {project["integrity"]:.0%}',
            f'Local wages {project["paid_cash"]:.0f} + {project["upkeep_paid"]:.0f} upkeep '
            f'• next upkeep {definition["upkeep"]:.0f}/turn',
        ]
        if project['kind'] == 'nile_repair':
            reports = [row for row in project_state.get('food_reports', [])
                       if row['project'] == project['id']]
            if reports:
                last = reports[-1]
                rows.append(f'Harvest {last["food_produced"]} • private stock '
                            f'{last["private_reserved"]} • underfed {last["underfed"]}/{last["households"]}')
            else:
                rows.append('Harvest and household access are measured after the next production turn.')
        elif project['kind'] == 'revenue_office':
            total = sum(row['central_transfer'] for row in project_state.get('revenue_reports', []))
            rows.append(f'{total:.0f} actual local receipts transferred to Cairo after prior claims.')
        else:
            meals = sum(row.get('food_units', 0) for row in payments
                        if row.get('project') == project['id'] and row.get('kind') == 'crew_food')
            rows.append(f'{meals} public maize fed crew • up to 55 trench strength when supplied.')
        for row_index, line in enumerate(rows):
            surface.blit(tiny_font.render(_fit_button_text(line, tiny_font, card.w - 18), True, DIM),
                         (card.x + 8, card.y + 29 + row_index * 21))
        if mouse_pos and card.collidepoint(mouse_pos):
            details = [title] + rows + [
                'The map marker shows whether this site remains under Egyptian control.',
                'Every payment and food transfer is recorded in strategic project state.',
            ]
            world['_guided_hover_tip'] = (definition['front'].title() + ' project', details, card, 'action')


def draw_guided_frame(surface, world: dict, font, font_small, mouse_pos=None) -> None:
    """Compose Guided mode from reusable overview components."""
    from worldview import _draw_cached_map  # lazy import avoids module-load cycle
    from worldview_map import draw_dynamic_map_overlays
    from worldview_ui import draw_ticker

    _draw_cached_map(surface, world, font, font_small)
    draw_dynamic_map_overlays(surface, world)
    labels = world.get('_ui_map_label_surface')
    if labels is not None:
        surface.blit(labels, (0, TOP_BAR_H),
                     pygame.Rect(0, TOP_BAR_H, MAP_RIGHT, HEIGHT - TOP_BAR_H - TICKER_H))
    if world.get('scenario_id') == 'egypt_1877':
        draw_scenario_route_overlay(surface, world)
    world['_guided_hover_tip'] = None
    if world.get('scenario_id') == 'egypt_1877':
        _draw_guided_status_bar(surface, world, mouse_pos=mouse_pos)
    else:
        pygame.draw.rect(surface, (12, 14, 20), (0, 0, WIDTH, TOP_BAR_H))
        pygame.draw.line(surface, (58, 66, 86), (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 1)
    draw_guided_header(surface, world, font_small, mouse_pos=mouse_pos)
    if not world.get('guided_analysis_open'):
        draw_pressure_panel(surface, world, mouse_pos=mouse_pos)
    if world.get('scenario_id') == 'egypt_1877':
        from scenario_projects import project_hover_tip
        marker_tip = project_hover_tip(world, mouse_pos)
        if marker_tip is not None:
            world['_guided_hover_tip'] = marker_tip
    draw_ticker(surface, world, font_small)

    notice = get_font(16).render('Egypt 1877 • Generated Nile and coast; outline is schematic', True, DIM)
    surface.blit(notice, (18, HEIGHT - TICKER_H - 24))

    if world.get('guided_analysis_open'):
        # Existing expert panels are reused intact inside the Analysis composition.
        from worldview_ui import draw_panel
        from worldview_charts import draw_chart_grid, draw_chart_large, tile_charts
        from worldview_cadastre import draw_cadastre_panel
        from worldview_citizens import draw_citizens_panel
        selected = world.get('selected_region')
        if world.get('analysis_tab', 'overview') == 'land':
            draw_cadastre_panel(surface, world, selected, font, font_small, mouse_pos=mouse_pos)
        elif world.get('analysis_tab') == 'people':
            draw_citizens_panel(surface, world, selected, font, font_small, mouse_pos=mouse_pos)
        elif world.get('analysis_tab') == 'projects' and world.get('scenario_id') == 'egypt_1877':
            _draw_guided_projects_analysis(surface, world, mouse_pos=mouse_pos)
        else:
            draw_panel(surface, world, font, font_small, mouse_pos=mouse_pos)

        if mouse_pos is not None and not world.get('settings_open'):
            from worldview_tooltips import draw_left_panel_tooltip
            draw_left_panel_tooltip(surface, world, font_small, mouse_pos=mouse_pos)

    if world.get('_guided_hover_tip') and not world.get('settings_open'):
        _draw_guided_hover_tip(surface, world['_guided_hover_tip'])

    if world.get('settings_open'):
        draw_settings_dialog(surface, world, font_small, mouse_pos)


def draw_scenario_bookend_modal(surface, world: dict, mouse_pos=None) -> None:
    """Present the opening, chapter transition, and measured result as modals."""
    kind = world.get('scenario_bookend_modal')
    if kind not in ('briefing', 'chapter2', 'debrief'):
        return
    from ui_targets import register_target
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((5, 7, 12, 220))
    surface.blit(veil, (0, 0))
    w = min(1100, WIDTH - 70)
    h = min(790 if kind == 'debrief' else 600, HEIGHT - 70)
    card = pygame.Rect((WIDTH - w) // 2, (HEIGHT - h) // 2, w, h)
    pygame.draw.rect(surface, (24, 29, 41), card, border_radius=10)
    pygame.draw.rect(surface, ACCENT, card, 2, border_radius=10)
    title_font = _scenario_font(27)
    body_font = _scenario_font(17)
    small_font = _scenario_font(14)
    left = card.x + 32
    right = card.right - 32
    if kind == 'briefing':
        from scenario_status import snapshot
        current = snapshot(world) or {}
        surface.blit(title_font.render('Egypt, 1877: grain and debt', True, ACCENT), (left, card.y + 28))
        paragraphs = [
            world.get('scenario', {}).get('briefing', ('',))[0],
            (f"At the start, {current.get('hungry_count', 0)} of {current.get('household_count', 0)} "
             'households lack food access. Public stores hold '
             f"{current.get('maize', 0):,.0f} maize units, enough for one release of up to "
             f"{int(world.get('scenario_state', {}).get('relief_units_per_turn', 0))} full meals."),
            (f"Cairo has {current.get('cash', 0):,.0f} spendable treasury units. Britain and France "
             f"hold a {current.get('debt', 0):,.0f}-unit Caisse claim; the first 200-unit instalment "
             'falls due on turn 6. Paying once leaves later instalments.'),
            'You can release maize, retain grain, change taxes, or preserve cash. Each turn permits one major decision. Creditor demands and major risks pause the simulation for your reply.',
            'The campaign records hunger, cash concentration, taxes, creditor transfers, and civilian injuries. Its ending will show both the political result and these costs.',
        ]
        y = card.y + 91
        for paragraph in paragraphs:
            for line in _wrap_text(paragraph, body_font, w - 70):
                surface.blit(body_font.render(line, True, TEXT), (left, y))
                y += 25
            y += 15
        label = 'Begin the campaign'
    elif kind == 'chapter2':
        from scenario_debt import outstanding
        from scenario_egypt_1877 import campaign_horizon
        state = world.get('scenario_state', {})
        politics = state.get('politics', {})
        crisis = state.get('naval_crisis', {})
        diplomacy = state.get('diplomatic_crisis', {})
        occupation = state.get('occupation', {})
        campaign = state.get('campaign', {})
        held = [site for site, owner in campaign.get('territorial_control', {}).items()
                if owner == 'Britain']
        fleet = state.get('geography', {}).get('fleets', {}).get('Britain')
        ruler = politics.get('ruler', 'the khedive')
        coalition = politics.get('governing_coalition', 'palace').replace('_', ' ')
        title = 'Egypt: sovereignty at stake'
        surface.blit(title_font.render(title, True, ACCENT), (left, card.y + 28))
        paragraphs = [
            (f"The {state.get('chapter_two_cause', 'political crisis')} has opened the second chapter. "
             f"{ruler} rules with a {coalition} coalition. Army loyalty is "
             f"{float(politics.get('army_loyalty', 0)):.0%}; the officer-civilian movement is "
             f"{float(politics.get('nationalist_movement', 0)):.0%}."),
            (f"The unpaid Caisse claim is {outstanding(world):,.0f}. "
             f"Britain's squadron is {fleet.get('location', 'not at sea') if fleet else 'not at sea'}; "
             f"France's current position is {diplomacy.get('french_policy', 'undecided').replace('_', ' ')}. "
             f"Foreign canal transit is {'open' if state.get('geography', {}).get('canal_open', True) else 'closed'}."),
            (f"Britain holds {', '.join(held) if held else 'no Egyptian strategic site'}. "
             f"Civilian injuries from bombardment and fighting: {campaign.get('civilian_casualties', 0)}. "
             f"Current resistance: {float(occupation.get('resistance', 0)):.0%}."),
            ("Review the political, foreign, and military pressure cards before choosing an order. "
             "Preparing defenses, requesting mediation, bargaining, or resisting occupation spends "
             "a major decision; ultimatums and battles pause for a separate response."),
            (f"The campaign now runs through at least turn {campaign_horizon(world)}. "
             "A late occupation also receives time for Egyptian responses before the debrief. "
             "Food access and the full debt claim remain in the national status bar."),
        ]
        y = card.y + 91
        for paragraph in paragraphs:
            for line in _wrap_text(paragraph, body_font, w - 70):
                surface.blit(body_font.render(line, True, TEXT), (left, y))
                y += 25
            y += 15
        label = 'Continue chapter II'
    else:
        debrief = world.get('scenario_state', {}).get('debrief', {})
        surface.blit(title_font.render(debrief.get('title', 'Campaign complete'), True, ACCENT),
                     (left, card.y + 23))
        for index, line in enumerate(_wrap_text(debrief.get('summary', ''), body_font, w - 70)[:2]):
            surface.blit(body_font.render(line, True, TEXT), (left, card.y + 62 + index * 24))
        stats = debrief.get('social_stats', [])
        stats_y = card.y + 114
        gap = 12
        stat_w = (w - 64 - gap) // 2
        for index, stat in enumerate(stats[:8]):
            col, row = index % 2, index // 2
            rect = pygame.Rect(left + col * (stat_w + gap), stats_y + row * 91, stat_w, 83)
            pygame.draw.rect(surface, (34, 40, 55), rect, border_radius=5)
            pygame.draw.rect(surface, (74, 88, 111), rect, 1, border_radius=5)
            surface.blit(small_font.render(stat['label'], True, ACCENT), (rect.x + 11, rect.y + 6))
            surface.blit(_scenario_font(18).render(stat['value'], True, TEXT), (rect.x + 11, rect.y + 26))
            for line_index, line in enumerate(_wrap_text(stat['note'], _scenario_font(12), rect.w - 22)[:2]):
                surface.blit(_scenario_font(12).render(line, True, DIM),
                             (rect.x + 11, rect.y + 51 + line_index * 14))
        entries = []

        def add(label, value):
            entries.append((label, ACCENT))
            entries.extend((line, TEXT) for line in _wrap_text(str(value), small_font, w - 86))
            entries.append(('', DIM))

        for stat in stats[8:]:
            add(stat['label'], f"{stat['value']} — {stat['note']}")
        for key in ('projects', 'food', 'debt', 'control', 'diplomacy', 'politics', 'authority'):
            if debrief.get(key):
                add(key.title(), debrief[key])
        if debrief.get('actions'):
            add('Decisions made', ' • '.join(debrief['actions']))
        if debrief.get('diplomacy_history'):
            add('Foreign decisions', ' • '.join(
                f"{entry['actor']}: {entry['decision'].replace('_', ' ')} — {entry['reason']}"
                for entry in debrief['diplomacy_history'][-6:]))
        if debrief.get('creditor_reactions'):
            add('Caisse responses', ' • '.join(debrief['creditor_reactions'][-4:]))
        if debrief.get('naval_events'):
            add('Alexandria crisis', ' • '.join(debrief['naval_events'][-4:]))
        if debrief.get('historical_log'):
            add('History and game model', ' • '.join(
                entry['text'] for entry in debrief['historical_log'][:2]))

        # Corporate Externalities & Decisions Victims Sections
        corps = debrief.get('corporate_externalities')
        if not corps:
            try:
                from economy.true_cost_ledger import get_true_cost_ledger
                p_name = world.get('player_nation_name') or 'Kingdom'
                corps = get_true_cost_ledger().get_national_corporate_externalities(p_name, world)
            except Exception:
                corps = None

        decisions = debrief.get('decisions_externalities')
        if not decisions:
            try:
                from economy.true_cost_ledger import get_decision_tracker
                decisions = get_decision_tracker().get_all_entries_dict()
            except Exception:
                decisions = None

        if corps and (corps.get('total_corporate_externalized_cost', 0) > 0 or corps.get('total_corporate_nominal_profit', 0) > 0):
            entries.append(('Country Corporate Externalities & Ecological Balance Sheet', ACCENT))
            nom_p = corps.get('total_corporate_nominal_profit', 0.0)
            ext_c = corps.get('total_corporate_externalized_cost', 0.0)
            net_s = corps.get('corporate_true_net_profit', 0.0)
            status = corps.get('parasitic_status', 'SUBSIDIZED_BY_NATURE')
            ratio = corps.get('corporate_externalization_ratio', 0.0)
            entries.append((f"Country Corps Nominal Profit: ${nom_p:,.2f}  |  Externalized Damage: -${ext_c:,.2f}  |  True Net Social Profit: ${net_s:,.2f} [{status}] (Ratio: {ratio*100:.1f}%)", (255, 140, 140) if net_s < 0 else (140, 240, 160)))

            dmg = corps.get('damage_breakdown', {})
            dmg_str = f"Smog: -${dmg.get('air_smog_cost', 0):,.1f} • Water: -${dmg.get('water_effluent_cost', 0):,.1f} • Soil: -${dmg.get('soil_depletion_cost', 0):,.1f} • Health: -${dmg.get('labor_health_wear_cost', 0):,.1f} • Peonage: -${dmg.get('debt_peonage_cost', 0):,.1f}"
            entries.append((f"Damage Breakdown: {dmg_str}", (200, 210, 225)))

            vics = corps.get('victims_breakdown', {})
            for vic_name, vic_data in vics.items():
                if vic_data.get('cost', 0) > 0:
                    entries.append((f"  • {vic_name}: -${vic_data['cost']:,.1f} ({vic_data['share']}%) — {vic_data['impact']}", (245, 205, 130)))
            entries.append(('', DIM))

        if decisions:
            entries.append(('Decisions Made: Externalized Costs & Victims', ACCENT))
            for dec in decisions:
                c = dec.get('externalized_cost', 0.0)
                turn_str = f"T{dec.get('turn', 0)}"
                c_str = f"-${c:,.2f}" if c > 0 else "Restorative ($0.00)"
                col = (255, 120, 120) if c > 0 else (120, 230, 150)
                entries.append((f"[{turn_str}] {dec.get('title', 'Decision')} — Externalized: {c_str}", col))
                for v in dec.get('victims', []):
                    entries.append((f"      Bore by: {v.get('victim_group', 'Public')} (-${v.get('burden_cost', 0):,.1f}) — {v.get('description', '')}", (235, 195, 130)))
            entries.append(('', DIM))

        viewport = pygame.Rect(left, stats_y + 377, w - 64, card.bottom - stats_y - 454)
        line_h = 20
        maximum = max(0, len(entries) * line_h - viewport.h)
        world['scenario_bookend_scroll_max'] = (maximum + 31) // 32
        scroll = max(0, min(int(world.get('scenario_bookend_scroll', 0)),
                            world['scenario_bookend_scroll_max']))
        world['scenario_bookend_scroll'] = scroll
        previous_clip = surface.get_clip()
        surface.set_clip(viewport)
        cursor = viewport.y - min(maximum, scroll * 32)
        for line, color in entries:
            if line and cursor + line_h >= viewport.y and cursor < viewport.bottom:
                surface.blit(small_font.render(line, True, color), (left + 4, cursor))
            cursor += line_h
        surface.set_clip(previous_clip)
        if maximum:
            hint = f'Scroll for details • {scroll + 1}/{world["scenario_bookend_scroll_max"] + 1}'
            surface.blit(small_font.render(hint, True, DIM), (left, card.bottom - 67))
        label = 'Return to the map'
    button = pygame.Rect(right - 254, card.bottom - 57, 254, 42)
    register_target(world, button, ('bookend', 'close'), scope='scenario_bookend')
    hover = button.collidepoint(mouse_pos or (-1, -1))
    pygame.draw.rect(surface, (64, 80, 105) if hover else (48, 62, 80), button, border_radius=5)
    pygame.draw.rect(surface, ACCENT, button, 1, border_radius=5)
    text = _scenario_font(16).render(label, True, TEXT)
    surface.blit(text, text.get_rect(center=button.center))


def scenario_bookend_modal_hit(pos, world: dict) -> bool:
    from ui_targets import find_target
    target = find_target(world, pos, scope='scenario_bookend')
    if target is None:
        return False
    if target.action == ('bookend', 'close'):
        world['scenario_bookend_modal'] = None
        world['needs_redraw'] = True
        return True
    return False


def draw_scenario_warning_modal(surface, world: dict, mouse_pos=None) -> None:
    """Show high-consequence scenario choices above either UI composition."""
    warning = world.get('scenario_warning_modal')
    if not warning:
        return
    from ui_targets import register_target
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((5, 7, 12, 210))
    surface.blit(veil, (0, 0))
    kind = warning.get('kind')
    card = pygame.Rect(310, 145 if kind == 'new_options' else 220, 780,
                       600 if kind == 'new_options' else
                       440 if kind in ('debt_due', 'creditor_reaction', 'naval_ultimatum', 'naval_blockade', 'landing_warning', 'capital_warning', 'dynastic_crisis', 'officer_movement', 'french_terms', 'joint_guarantee_terms') else 360)
    border = (225, 178, 87) if kind in ('debt_due', 'creditor_reaction', 'new_options') else (226, 102, 94)
    pygame.draw.rect(surface, (24, 29, 41), card, border_radius=10)
    pygame.draw.rect(surface, border, card, 2, border_radius=10)
    title_font, body_font = _scenario_font(24), _scenario_font(16)
    state = world.get('scenario_state', {})
    nation = _egypt_nation(world)
    if kind == 'new_options':
        groups = warning.get('groups', [])
        title = 'New decisions are available'
        lines = ['The situation has changed. Each of these choices uses one major decision:']
        if state.get('last_action_turn') == int(world.get('turn', 0)):
            lines.append('You have already made a major decision this turn; these choices can be taken after advancing.')
        for group in groups:
            lines.append(group['title'] + ': ' + group['detail'])
            lines.append('New choices: ' + ', '.join(group.get('choices', [])) + '.')
        lines.append('Scroll the decision panel if needed, then hover over each option for its projected consequences.')
        options = [('ack_new_options', 'Review new decisions', True)]
    elif kind == 'debt_due':
        from scenario_situation import situation_template
        debt_rules = situation_template()['debt_rules']
        delay = int(debt_rules['deferral_delay_turns'])
        multiplier = float(debt_rules['deferral_multiplier'])
        amount = float(state.get('scheduled_remittance', 200.0))
        cash = float(getattr(getattr(getattr(nation, 'government', None), 'agent', None), 'cash', 0.0)) if nation else 0.0
        can_defer = (int(state.get('deferral_count', 0)) < int(debt_rules['maximum_deferrals'])
                     and int(world.get('turn', 0)) + delay <= int(world.get('scenario', {}).get('horizon_turns', 20)))
        from scenario_debt import outstanding
        claim = outstanding(world)
        title = 'Debt instalment is due now'
        lines = [
            f'Treasury cash: {cash:,.0f}. Total unpaid Caisse bonds: {claim:,.0f}. This instalment: {amount:,.0f}.',
            'Paying this instalment leaves later service windows until the claim is cleared.',
            'Default collapses creditor confidence and reduces legitimacy by 15 percentage points.',
            'Choose how to handle this payment:',
        ]
        options = [
            ('pay_remittance', f'Pay {amount:,.0f}', cash >= amount),
            ('concede_revenue', f'Concede • pay {amount / 2:,.0f}', cash >= amount / 2),
            ('defer_remittance', 'Defer • keep cash' if can_defer else 'Defer • unavailable', can_defer),
            ('default_remittance', 'Default • severe loss', True),
        ]
    elif kind == 'creditor_reaction':
        from scenario_situation import situation_template, creditor_response_options
        action_id = warning.get('action_id', '')
        reaction = situation_template()['branches'].get(action_id, {}).get('reaction', {})
        title = reaction.get('headline', 'Creditors demand a response')
        lines = [reaction.get('body', ''), 'Choose Cairo’s response. This diplomatic reply does not use your major domestic decision this turn.']
        response_options = creditor_response_options(world, action_id)
        options = [(f'creditor_response:{response["id"]}', response['label'], response['enabled'])
                   for response in response_options]
    elif kind in ('french_terms', 'joint_guarantee_terms'):
        cash = float(getattr(getattr(getattr(nation, 'government', None), 'agent', None), 'cash', 0.0)) if nation else 0.0
        from scenario_debt import outstanding
        amount = outstanding(world) * .5
        if kind == 'french_terms':
            title = 'French settlement proposal'
            lines = [
                f'Paris and London propose settling the claim for {amount:,.0f} treasury units.',
                'Egypt retains its revenue offices and territory; France brokers the agreement.',
                'Accepting settles the bonds. Rejecting leaves the creditor dispute open.',
            ]
            enabled = cash >= amount
        else:
            title = 'Joint creditor guarantee'
            lines = [
                'Britain and France offer a capped 5-unit claim on actual Egyptian tax and tariff receipts each turn.',
                'Both creditors receive their bond share. The assignment ends when the claim is paid.',
                'Rejecting leaves the creditor dispute open.',
            ]
            enabled = True
        options = [('diplomacy_response:accept', 'Accept terms', enabled),
                   ('diplomacy_response:reject', 'Reject terms', True)]
    elif kind in ('naval_ultimatum', 'naval_blockade'):
        from scenario_gunboat import naval_response_options, coastal_balance
        crisis = state.get('naval_crisis', {})
        balance = coastal_balance(world)
        diplomatic = state.get('diplomatic_crisis') or {}
        french_fleet = state.get('geography', {}).get('fleets', {}).get('France')
        french_stance = diplomatic.get('french_policy', 'abstain').replace('_', ' ')
        french_status = (f'France: {french_stance}; a funded French fleet is present and '
                         f'{"may fire" if diplomatic.get("french_authorization", {}).get("bombard") else "may not fire"}.'
                         if french_fleet else f'France: {french_stance}; no French fleet is present.')
        title = 'British ultimatum at Alexandria' if kind == 'naval_ultimatum' else 'Alexandria is under naval blockade'
        lines = ([
            french_status,
            'London demands customs oversight or disarmament. Defending the batteries risks bombardment and a real trade blockade.',
            f'Force at Alexandria: Britain {balance["british_force"]:.0f}, Egyptian defense {balance["egyptian_defense"]:.0f}; ratio {balance["ratio"]:.2f}.',
        ] if kind == 'naval_ultimatum' else [
            'British guns have struck the coastal batteries and the shared trade system is blocking Alexandria’s routes.',
            'Britain pays for its fleet each turn. Its domestic unrest and treasury can force a withdrawal.',
        ])
        naval_options = naval_response_options(world, kind)
        options = [(f'naval_response:{response["id"]}', response['label'], response['enabled'])
                   for response in naval_options]
    elif kind == 'landing_warning':
        from scenario_campaign import landing_options
        fleet = state['geography']['fleets'].get('Britain', {})
        fort = state['campaign']['forts']['Alexandria']
        title = 'British landing preparations'
        lines = [
            f'British transports carry {fleet.get("transports", 0)} troops; Alexandria fort integrity {fort["integrity"]:.0f}%, ammunition {fort["ammunition"]}.',
            f'Civilian injuries so far: {state["campaign"]["civilian_casualties"]}. Choose where the Egyptian army makes its stand.',
            'The shared battle model resolves casualties and territorial control after the order.',
        ]
        campaign_options = landing_options(world)
        options = [(f'landing_response:{response["id"]}', response['label'], response['enabled'])
                   for response in campaign_options]
    elif kind == 'capital_warning':
        from scenario_occupation import response_options
        title = 'The British expedition approaches Cairo'
        control = state['campaign']['territorial_control']
        lines = [
            f'British foothold: {", ".join(site for site, holder in control.items() if holder == "Britain")}.',
            f'Egyptian resistance {state["occupation"]["resistance"]:.0%}; British garrison must keep paying supply costs.',
            'Defending Cairo uses the shared battle resolver. Losing the capital gives Britain control of the tax office.',
        ]
        capital_options = response_options(world)
        options = [(f'capital_response:{response["id"]}', response['label'], response['enabled'])
                   for response in capital_options]
    elif kind in ('dynastic_crisis', 'officer_movement'):
        from scenario_politics import response_options
        politics = state.get('politics', {})
        title = 'The khedive’s authority is contested' if kind == 'dynastic_crisis' else 'Egyptian officers demand a new government'
        lines = ([
            f'Ismail’s palace authority is {float(politics.get("palace_authority", 0)):.0%}; creditor supervision has weakened his position.',
            'Choose who governs Egypt. The player continues as the governing coalition after any succession.',
        ] if kind == 'dynastic_crisis' else [
            f'Army loyalty is {float(politics.get("army_loyalty", 0)):.0%}; the officer-civilian movement is {float(politics.get("nationalist_movement", 0)):.0%}.',
            'Choose whether the palace, a shared cabinet, or ‘Urabi’s coalition gives orders to the army.',
        ])
        political_options = response_options(world, kind)
        options = [(f'politics_response:{response["id"]}', response['label'], True)
                   for response in political_options]
    elif kind == 'breakdown':
        title = 'Political breakdown is imminent'
        lines = [
            f"Average unrest {warning.get('unrest', 0):.2f} (threshold 0.85); legitimacy {warning.get('legitimacy', 0):.0%} (threshold 10%).",
            'If still available, tax relief can lower unrest and raise legitimacy before the campaign ends.',
        ]
        can_relieve = (any(float(getattr(tile.gov, 'tax_rate', 0.0)) > 0.0 for tile in nation.tiles)
                       and state.get('last_action_turn') != int(world.get('turn', 0))) if nation else False
        options = ([('scenario_rescue_tax', 'Reduce local taxes now', True)] if can_relieve else [])
        options.append(('accept_breakdown', 'Accept government breakdown', True))
    elif kind == 'riot_risk':
        title = 'District riot risk is rising'
        lines = [
            f"{warning.get('nation', 'A nation')} • {warning.get('region', 'a district')}: protest energy {warning.get('energy', 0):.1f}/10.",
            f"Chance of mob-scale escalation this turn: {warning.get('riot_chance', 0):.0%}. Risk and likely crowd size rise smoothly with protest energy.",
            'Review district relief, negotiation, taxes, and local security before continuing.',
        ]
        options = [('review_risk', 'Review situation', True), ('continue_risk', 'Advance one turn anyway', True)]
    elif kind == 'political_risk':
        title = 'Political stability is at risk'
        lines = [
            f"Average unrest is {warning.get('unrest', 0):.2f} (breakdown at 0.85); legitimacy is {warning.get('legitimacy', 0):.0%} (breakdown at 10%).",
            'Review the political support card and available actions before advancing, or continue one turn at risk.',
        ]
        options = [('review_risk', 'Review decisions', True), ('continue_risk', 'Advance one turn anyway', True)]
    elif kind == 'riot_event':
        title = 'Riot or revolt reported'
        lines = [str(warning.get('message', 'Civil unrest has escalated.')),
                 'The simulation is paused. Review the affected district’s food access and local responses before continuing.']
        options = [('review_risk', 'Review situation', True), ('continue_risk', 'Continue simulation', True)]
    else:
        title = 'Crisis warning'
        lines = [str(warning.get('message', 'A serious event may occur next turn.'))]
        options = [('review_risk', 'Review situation', True), ('continue_risk', 'Advance one turn anyway', True)]
    surface.blit(title_font.render(title, True, TEXT), (card.x + 26, card.y + 24))
    y = card.y + 76
    for line in lines:
        for wrapped in _wrap_text(line, body_font, card.w - 52):
            surface.blit(body_font.render(wrapped, True, TEXT), (card.x + 26, y))
            y += 24
        y += 8
    mouse = mouse_pos if mouse_pos else (-1, -1)
    hovered_option = None
    cols = 2 if len(options) > 2 else 1
    btn_w = (card.w - 52 - 12 * (cols - 1)) // cols
    btn_h = 48
    rows = (len(options) + cols - 1) // cols
    button_y = card.bottom - btn_h * rows - 24 - 10 * (rows - 1)
    for index, (action, label, enabled) in enumerate(options):
        row, col = divmod(index, cols)
        rect = pygame.Rect(card.x + 26 + col * (btn_w + 12), button_y + row * (btn_h + 10), btn_w, btn_h)
        hover = rect.collidepoint(mouse)
        if hover:
            hovered_option = action
        pygame.draw.rect(surface, (55, 66, 86) if hover and enabled else (38, 46, 62), rect, border_radius=5)
        pygame.draw.rect(surface, ACCENT if hover else (83, 99, 126), rect, 1, border_radius=5)
        label_surface = _scenario_font(14).render(label, True, TEXT if enabled else DIM)
        surface.blit(label_surface, label_surface.get_rect(center=rect.center))
        if enabled:
            register_target(world, rect, ('scenario_warning', action), scope='scenario_warning')

    if hovered_option:
        consequences = {
            'pay_remittance': (
                (f'Unavailable: the treasury has {cash:,.0f} units and needs {amount:,.0f}. ' if cash < amount else '')
                + f'Spends {amount:,.0f} treasury units and reduces the bond claim by {amount:,.0f}. Another instalment is due in five turns if principal remains. Creditor confidence rises by up to 15 points.'
                if kind == 'debt_due' else 'Enacts this debt payment.'
            ),
            'concede_revenue': (
                (f'Unavailable: the treasury has {cash:,.0f} units and needs {amount / 2:,.0f}. ' if cash < amount / 2 else '')
                + f'Pays {amount / 2:,.0f} units and conditionally writes down another {amount / 2:,.0f}. The remaining principal stays due. Fiscal autonomy falls by 25 points and Caisse oversight begins.'
                if kind == 'debt_due' else 'Enacts this revenue concession.'
            ),
            'defer_remittance': (
                ('A second deferral is unavailable. '
                 if int(state.get('deferral_count', 0)) >= int(debt_rules['maximum_deferrals'])
                 else 'The revised due date would exceed the campaign. '
                 if int(world.get('turn', 0)) + delay > int(world.get('scenario', {}).get('horizon_turns', 20))
                 else '')
                + f'Keeps cash, but makes {amount * multiplier:,.0f} units due on turn {int(world.get("turn", 0)) + delay}. Creditor confidence falls by 30 points; legitimacy rises by 2 points.'
                if kind == 'debt_due' else 'Defers the payment.'
            ),
            'default_remittance': (
                'Keeps the cash, but creditor confidence falls to zero and legitimacy drops by 15 points. Next turn, creditors claim customs; they cannot collect without Cairo’s consent or credible force.'
                if kind == 'debt_due' else 'Defaults on the payment.'
            ),
            'scenario_rescue_tax': 'Reduces local taxes, lowering treasury revenue. It can avert breakdown if unrest and legitimacy move back across their thresholds.',
            'accept_breakdown': 'Ends the campaign immediately with government breakdown.',
            'review_risk': 'Closes this warning and pauses the simulation so you can inspect the situation.',
            'continue_risk': 'Advances one turn despite the warning. The reported crisis may worsen or trigger its consequences.',
        }
        detail = consequences.get(hovered_option)
        if hovered_option.startswith('creditor_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in response_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
                if not response['enabled']:
                    if response_id == 'offer_arrears_plan' and state.get('arrears_plan_used'):
                        detail = 'Unavailable: the Caisse has already accepted one arrears plan. ' + detail
                    elif (response_id == 'offer_arrears_plan'
                          and int(world.get('turn', 0)) + 3 > int(world.get('scenario', {}).get('horizon_turns', 20))):
                        detail = 'Unavailable: the new due date would fall after the campaign ends. ' + detail
                    else:
                        detail = f'Unavailable: requires {float(response.get("requires_cash", 0.0)):,.0f} treasury units. ' + detail
        if hovered_option.startswith('diplomacy_response:'):
            detail = ('Accept the stated treaty terms and record every payment or assigned receipt in the debt ledger.'
                      if hovered_option.endswith('accept') else
                      'Reject the proposed terms. Britain and France retain their current claims and may continue escalation.')
        if hovered_option.startswith('naval_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in naval_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
                if not response['enabled']:
                    detail = (('Unavailable: the treasury cannot cover this settlement. '
                               if response_id == 'naval_settle' else '') + detail)
        if hovered_option.startswith('politics_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in political_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
        if hovered_option.startswith('landing_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in campaign_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
                if not response['enabled']:
                    detail = 'Unavailable with current canal access or treasury cash. ' + detail
        if hovered_option.startswith('capital_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in capital_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
                if not response['enabled']:
                    detail = 'Unavailable: treasury cash is below 40 units. ' + detail
        if detail:
            tooltip_font = _scenario_font(13)
            tooltip_w = card.w - 52
            tooltip_lines = _wrap_text(detail, tooltip_font, tooltip_w - 24)
            tooltip_h = len(tooltip_lines) * 18 + 18
            tx = card.x + 26
            ty = max(card.y + 126, button_y - tooltip_h - 8)
            tooltip_rect = pygame.Rect(tx, ty, tooltip_w, tooltip_h)
            pygame.draw.rect(surface, (16, 20, 29), tooltip_rect, border_radius=5)
            pygame.draw.rect(surface, ACCENT, tooltip_rect, 1, border_radius=5)
            for line_index, line in enumerate(tooltip_lines):
                surface.blit(tooltip_font.render(line, True, TEXT), (tx + 12, ty + 9 + line_index * 18))


def scenario_warning_modal_hit(pos, world: dict) -> bool:
    """Resolve a warning choice without allowing clicks to fall through."""
    from ui_targets import find_target
    target = find_target(world, pos, scope='scenario_warning')
    if target is None:
        return True
    action = target.action[1]
    if action == 'ack_new_options':
        groups = world.get('scenario_warning_modal', {}).get('groups', [])
        if groups:
            world['guided_action_scroll'] = groups[0]['first_row']
        world['scenario_warning_modal'] = None
    elif action in ('pay_remittance', 'concede_revenue', 'defer_remittance', 'default_remittance'):
        from scenario_egypt_1877 import apply_action
        ok, message = apply_action(world, action)
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_situation import advance_creditor_reactions
            from client.desktop.engine import ticker_push
            advance_creditor_reactions(world, int(world.get('turn', 0)), ticker_push)
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('creditor_response:'):
        from scenario_situation import resolve_creditor_response, advance_creditor_reactions
        from client.desktop.engine import ticker_push
        ok, message = resolve_creditor_response(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            advance_creditor_reactions(world, int(world.get('turn', 0)), ticker_push)
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('diplomacy_response:'):
        from scenario_diplomacy import resolve_terms
        ok, message = resolve_terms(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('naval_response:'):
        from scenario_gunboat import resolve_naval_response
        previous_modal = world.get('scenario_warning_modal')
        ok, message = resolve_naval_response(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            if world.get('scenario_warning_modal') is previous_modal:
                world['scenario_warning_modal'] = None
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('politics_response:'):
        from scenario_politics import resolve
        ok, message = resolve(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_situation import advance_creditor_reactions
            from client.desktop.engine import ticker_push
            advance_creditor_reactions(world, int(world.get('turn', 0)), ticker_push)
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('landing_response:'):
        from scenario_campaign import resolve_landing
        ok, message = resolve_landing(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('capital_response:'):
        from scenario_occupation import resolve_capital
        ok, message = resolve_capital(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action == 'scenario_rescue_tax':
        from scenario_egypt_1877 import SCENARIO, _outcome_metrics, apply_action
        ok, message = apply_action(world, 'reduce_fellahin_tax')
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            metrics = _outcome_metrics(_egypt_nation(world))
            thresholds = SCENARIO['thresholds']
            if (metrics['legitimacy'] > thresholds['breakdown_legitimacy']
                    and metrics['unrest'] < thresholds['breakdown_unrest']):
                if world.get('scenario_state', {}).get('payment_status') == 'unpaid':
                    world['scenario_warning_modal'] = {'kind': 'debt_due'}
                else:
                    world['scenario_warning_modal'] = None
            else:
                world['scenario_warning_modal'] = {'kind': 'breakdown', **metrics}
    elif action == 'accept_breakdown':
        from scenario_egypt_1877 import _finish_scenario, _outcome_metrics
        nation = _egypt_nation(world)
        _finish_scenario(world, nation, 'breakdown', int(world.get('turn', 0)), _outcome_metrics(nation))
        world['scenario_warning_modal'] = None
    elif action == 'review_risk':
        region_key = world.get('scenario_warning_modal', {}).get('region_key')
        if region_key and world.get('scenario_id') == 'egypt_1877':
            tile = next((tile for tile in world.get('tiles', [])
                         if tile.name == region_key
                         and getattr(getattr(tile, 'owner_nation', None), 'name', None)
                         == world.get('player_nation_name')), None)
            if tile is not None:
                world['selected_region'] = tile
                world['guided_decision_scope'] = 'district'
                world['guided_action_scroll'] = 0
        world['scenario_warning_modal'] = None
        world['crisis_warning_ack_turn'] = int(world.get('turn', 0))
    elif action == 'continue_risk':
        world['scenario_warning_modal'] = None
        world['crisis_warning_ack_turn'] = int(world.get('turn', 0))
        from worldview_engine import step_world_with_warning
        step_world_with_warning(world)
    world['playing'] = False
    world['needs_redraw'] = True
    return True


def draw_settings_dialog(surface, world: dict, font_small, mouse_pos=None) -> None:
    """Small settings dialog for switching Guided and Advanced UI composition."""
    from ui_targets import register_target
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((7, 9, 14, 190))
    surface.blit(overlay, (0, 0))
    rect = pygame.Rect(WIDTH // 2 - 240, HEIGHT // 2 - 145, 480, 290)
    pygame.draw.rect(surface, (25, 29, 40), rect, border_radius=8)
    pygame.draw.rect(surface, (95, 108, 136), rect, 1, border_radius=8)
    title = get_font(27).render('Interface settings', True, TEXT)
    surface.blit(title, (rect.x + 22, rect.y + 20))
    desc = get_font(18).render('Choose how much of the simulation UI is shown by default.', True, DIM)
    surface.blit(desc, (rect.x + 22, rect.y + 58))
    buttons = [((rect.x + 22, rect.y + 112, 204, 64), 'guided', 'Guided', 'Scenario first'),
               ((rect.x + 254, rect.y + 112, 204, 64), 'advanced', 'Advanced', 'Full system panels')]
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for btn, mode, label, subtitle in buttons:
        register_target(world, btn, ('set_ui_mode', mode), scope='settings')
        chosen = world.get('ui_mode', 'advanced') == mode
        hover = btn[0] <= mx <= btn[0] + btn[2] and btn[1] <= my <= btn[1] + btn[3]
        color = ACCENT if chosen else ((91, 112, 151) if hover else (68, 78, 100))
        pygame.draw.rect(surface, (40, 50, 70), btn, border_radius=6)
        pygame.draw.rect(surface, color, btn, 2 if chosen else 1, border_radius=6)
        l = get_font(22).render(label, True, TEXT)
        s = get_font(16).render(subtitle, True, DIM)
        surface.blit(l, l.get_rect(center=(btn[0] + btn[2] // 2, btn[1] + 24)))
        surface.blit(s, s.get_rect(center=(btn[0] + btn[2] // 2, btn[1] + 47)))
    close_rect = (rect.x + rect.w - 110, rect.y + rect.h - 52, 88, 32)
    register_target(world, close_rect, 'close_settings', scope='settings')
    pygame.draw.rect(surface, (47, 53, 69), close_rect, border_radius=4)
    close = get_font(18).render('Done', True, TEXT)
    surface.blit(close, close.get_rect(center=(close_rect[0] + close_rect[2] // 2, close_rect[1] + close_rect[3] // 2)))


def guided_ui_hit(pos, world: dict) -> bool:
    """Handle Guided composition and settings actions."""
    from ui_targets import find_target
    target = find_target(world, pos, scope='settings' if world.get('settings_open') else 'guided')
    if target is None:
        if world.get('settings_open'):
            world['settings_open'] = False
            return True
        return False
    action = target.action
    if isinstance(action, tuple) and action[0] == 'set_ui_mode':
        from world_config import set_ui_mode
        world['ui_mode'] = set_ui_mode(action[1])
    elif action == 'open_settings':
        world['settings_open'] = True
    elif action == 'close_settings':
        world['settings_open'] = False
    elif action == 'toggle_guided_analysis':
        world['guided_analysis_open'] = not world.get('guided_analysis_open', False)
    elif action == 'reopen_scenario_debrief':
        world['scenario_bookend_modal'] = 'debrief'
        world['scenario_bookend_scroll'] = 0
    elif action == 'play_pause':
        ended = world.get('scenario_id') == 'egypt_1877' and bool(world.get('scenario_state', {}).get('ending'))
        if not ended:
            world['playing'] = not world.get('playing', False)
    elif action == 'step_next':
        from worldview_engine import step_world_with_warning
        world['playing'] = False
        step_world_with_warning(world)
    elif isinstance(action, tuple) and action[0] == 'analysis_tab':
        world['analysis_tab'] = action[1]
        world['guided_analysis_open'] = True
    elif isinstance(action, tuple) and action[0] == 'guided_scope':
        world['guided_decision_scope'] = action[1]
        world['guided_action_scroll'] = 0
    elif isinstance(action, tuple) and action[0] == 'scenario_action':
        from scenario_egypt_1877 import apply_action
        ok, message = apply_action(world, action[1])
        world['scenario_feedback'] = message
        if not ok:
            world['scenario_feedback'] = f"Not enacted: {message}"
        world['needs_redraw'] = True
    elif action == 'open_debt_analysis':
        world['debt_panel_open'] = True
        world['left_panel'] = 'debt'
        world['guided_analysis_open'] = True
        world['analysis_tab'] = 'overview'
    return True
