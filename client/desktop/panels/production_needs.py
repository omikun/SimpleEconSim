"""Native economic-needs inspector and funded program orders."""
import pygame


def open_dialog(world, region):
    world['production_needs_dialog'] = {'region': region, 'good': 'food',
        'kind': 'procurement', 'budget': 25, 'quantity': 10, 'duration': 2,
        'page': 0, 'message': '', 'buttons': []}


def draw(surface, world, font, small, mouse):
    state = world.get('production_needs_dialog')
    if not state:
        return
    from production_needs import needs
    region = state['region']
    width, height = min(880, surface.get_width() - 24), min(620, surface.get_height() - 24)
    x, y = (surface.get_width() - width) // 2, (surface.get_height() - height) // 2
    pygame.draw.rect(surface, (18, 25, 29), (x, y, width, height), border_radius=9)
    pygame.draw.rect(surface, (110, 145, 125), (x, y, width, height), 2, border_radius=9)
    state['buttons'] = []

    def text(label, tx, ty, color=(220, 230, 222)):
        # All long explanations are clipped to their column, never outside the modal.
        while label and small.size(label)[0] > width - 36:
            label = label[:-1]
        surface.blit(small.render(label, True, color), (tx, ty))

    def button(rect, label, action):
        hovered = pygame.Rect(rect).collidepoint(mouse or (-1, -1))
        pygame.draw.rect(surface, (48, 69, 60) if hovered else (34, 46, 42), rect, border_radius=4)
        text(label, rect[0] + 6, rect[1] + 5)
        state['buttons'].append((rect, action))

    surface.blit(font.render(f'Economic needs: {region.name}', True, (190, 225, 170)), (x + 16, y + 13))
    button((x + width - 45, y + 10, 30, 25), 'X', ('close', 0))
    text('Good                Workers      Output / need per turn       Stocks       Constraint', x + 16, y + 50)
    rows = needs(region)
    page = min(state['page'], max(0, (len(rows) - 1) // 8))
    state['page'] = page
    for index, row in enumerate(rows[page * 8:page * 8 + 8]):
        cy = y + 74 + index * 27
        if row['good'] == state['good']:
            pygame.draw.rect(surface, (37, 60, 46), (x + 12, cy, width - 24, 25))
        label = f"{row['good'][:18]:18}  {row['workers']:>4}       {row['output_per_turn']:>6.1f} / {row['requirements_per_turn']:<6.1f}       {row['stocks']:>7.1f}    {row['constraint'].replace('_', ' ')}"
        text(label, x + 16, cy + 4)
        state['buttons'].append(((x + 12, cy, width - 24, 25), ('good', row['good'])))
    button((x + 16, y + 297, 70, 25), 'Previous', ('page', -1))
    button((x + 94, y + 297, 70, 25), 'Next', ('page', 1))
    text('Choose a commodity, program, quantity, budget, and expiry.', x + 16, y + 335)
    kinds = [('procurement', 'Buy reserve'), ('working_capital', 'Productive loans'),
             ('seasonal_hiring', 'Seasonal farm work'), ('relief', 'Meal relief')]
    bw = (width - 48) // 4
    for index, (kind, label) in enumerate(kinds):
        button((x + 16 + index * (bw + 4), y + 358, bw, 28),
               ('* ' if state['kind'] == kind else '') + label, ('kind', kind))
    for index, (key, label, step) in enumerate((('quantity', 'Quantity', 5), ('budget', 'Budget', 10), ('duration', 'Turns', 1))):
        cx = x + 16 + index * (width - 32) // 3
        text(f'{label}: {state[key]}', cx, y + 400)
        button((cx, y + 423, 34, 25), '-', (key, -step))
        button((cx + 40, y + 423, 34, 25), '+', (key, step))
    text(f"{state['kind'].replace('_', ' ')} for {state['good']}: reserve up to {state['budget']} now, expires in {state['duration']} turns.", x + 16, y + 465)
    text('Loans count principal; seasonal hiring counts work turns. Actual goods/work are required.', x + 16, y + 486)
    text('Unspent funds return on completion or expiry. Public orders do not change professions.', x + 16, y + 507)
    text(state['message'], x + 16, y + 529, (240, 205, 130))
    if world.get('scenario_id') == 'labor_frontier_rivalry':
        text('Use the scenario decisions to direct public spending.', x + 16, y + height - 40)
    else:
        button((x + 16, y + height - 45, 170, 28), 'Fund program', ('fund', 0))


def hit(pos, world):
    state = world.get('production_needs_dialog')
    if not state:
        return False
    for rect, (action, value) in reversed(state.get('buttons', ())):
        if not pygame.Rect(rect).collidepoint(pos):
            continue
        if action == 'close':
            world.pop('production_needs_dialog', None)
        elif action in ('good', 'kind'):
            state[action] = value
            if state['kind'] in ('seasonal_hiring', 'relief'):
                state['good'] = 'food'
        elif action == 'page':
            state['page'] = max(0, state['page'] + value)
        elif action == 'fund':
            from production_policy import submit
            try:
                row = submit(state['region'], state['kind'], state['good'], state['quantity'],
                             state['budget'], state['duration'], int(world.get('turn', 0)))
                state['message'] = f"Funded {row['id']}; begins next turn."
            except ValueError as error:
                state['message'] = str(error)
        else:
            state[action] = max(1, state[action] + value)
            if action == 'duration':
                state[action] = min(30, state[action])
        break
    return True
