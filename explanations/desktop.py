"""Pygame adapter. Only a deliberate gesture calls request(); workers never draw."""
import json
import webbrowser
from concurrent.futures import ThreadPoolExecutor

import pygame

from explanations.context import capture
from explanations.service import default_service, TERMINAL
from metric_catalog import METRICS

_catalog_executor = None
_COMMON = ('people.population', 'people.residents', 'people.hungry',
           'economy.gdp_nominal', 'finance.treasury', 'finance.total_cash',
           'goods.price', 'politics.protest_energy', 'health.average_health')


def _map_entity(world):
    tile = world.get('selected_region')
    return 'tile:' + tile.name if tile else None


def _load_catalog(world, state):
    """Freeze only local metadata on the UI thread. Indexing runs off-thread."""
    global _catalog_executor
    future = state.pop('catalog_future', None)
    if future: future.cancel()
    state.update(options=[], index=0, scroll=0, buttons=[], catalog_error=None)
    trace = world.get('run_trace')
    if trace is None or trace.write_error:
        state['catalog_error'] = 'Causal recording is unavailable for this run.'
        return
    try:
        boundary = trace.publish()
        kind, _, name = state['entity'].partition(':')
        from trace_index import TraceIndex
        if _catalog_executor is None:
            _catalog_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='stat-picker')
        state['catalog_future'] = _catalog_executor.submit(
            TraceIndex(trace.path).available_metrics, turn=state['turn'],
            subject={'type': kind, 'id': name}, boundary=boundary)
    except (ValueError, OSError) as error:
        state['catalog_error'] = str(error)


def _set_entity(world, state, entity):
    state.update(entity=entity, text='', choosing_entity=False, map_entity=_map_entity(world))
    _load_catalog(world, state)


def _entities(world):
    return ['nation:' + n.name for n in world.get('nations', [])] + ['tile:' + t.name for t in world.get('tiles', [])]


def _entity_matches(world, state):
    query = state['text'].lower()
    return [entity for entity in _entities(world) if query in entity.lower()]


def _label(option):
    dims = ', '.join(f'{key}={value}' for key, value in option['subject'].items() if key not in ('type', 'id'))
    return option['metric_id'] + (' · ' + dims if dims else '')


def _selection(world):
    chart = world.get('_chart_trace_selection')
    panel = world.get('_causal_panel')
    row = panel.get('row') if panel else None
    if row:
        subject = row.get('subject') or {}
        return {'entity': subject.get('type', 'tile').split('/')[0] + ':' + str(subject.get('id', '')),
                'turn': row['turn'], 'metric_id': row.get('metric_id'),
                'boundary': panel['boundary'], 'epoch': row.get('epoch', 0),
                'dimensions': {key: value for key, value in subject.items() if key not in ('type', 'id')}}
    if chart:
        subject = (chart.get('events') or [{}])[0].get('subject') or {}
        selection = {'entity': ('nation:' + chart['nation'] if chart.get('nation') else 'tile:' + chart['tile']),
                     'turn': chart['turn'], 'metric_id': chart['metric_id'],
                     'dimensions': {key: value for key, value in subject.items() if key not in ('type', 'id')}}
        if chart.get('plot_transform') or chart.get('source_window') or chart.get('component'):
            selection['display'] = str({'transform': chart.get('plot_transform'),
                'component': chart.get('component'), 'window': (chart.get('source_window') or {}).get('window_turns')})[:300]
        return selection
    return None


def close(world):
    state = world.pop('_ai_explainer', None)
    if state and state.get('catalog_future'):
        state['catalog_future'].cancel()
    if state and state.get('job', {}).get('viewer'):
        job = state['job']; default_service().cancel(job['job_id'], job['viewer'])


def request(world, selection, pinned=True):
    close(world)
    state = {'selection': selection, 'pinned': pinned, 'scroll': 0, 'last_poll': 0,
             'map_entity': _map_entity(world),
             'run_id': getattr(world.get('run_trace'), 'run_id', None),
             'job': {'state': 'collecting_evidence', 'message': 'Reading recorded causes…'}}
    world['_ai_explainer'] = state
    try:
        state['job'] = default_service().request(capture(world, selection))
    except (ValueError, OSError) as error:
        state['job'] = {'state': 'failed', 'message': str(error)}


def chooser(world):
    close(world)
    # F11 consumes map clicks while open; F12 replaces that inspector.
    world['_causal_panel'] = None
    nation = world.get('selected_nation')
    tile = world.get('selected_region')
    if nation is None:
        nation = getattr(tile, 'owner_nation', None) or next(iter(world.get('nations', [])), None)
    entity = 'tile:' + tile.name if tile else 'nation:' + getattr(nation, 'name', '')
    state = {'chooser': True, 'text': '', 'index': 0, 'entity': entity,
        'turn': world.get('turn', 0), 'scroll': 0, 'pinned': True,
        'map_entity': _map_entity(world),
        'run_id': getattr(world.get('run_trace'), 'run_id', None)}
    world['_ai_explainer'] = state
    _load_catalog(world, state)


def _matches(state):
    query = state['text'].lower()
    return [option for option in state.get('options', []) if query in _label(option).lower()]


def _choose(world, option=None):
    state = world['_ai_explainer']
    selected = _map_entity(world)
    if selected and selected != state.get('map_entity'):
        _set_entity(world, state, selected)
        return
    matches = _matches(state)
    option = option or (matches[min(state['index'], len(matches) - 1)] if matches else None)
    if option is None or option not in state.get('options', []):
        return
    selection = {'entity': state['entity'], 'turn': state['turn'], 'metric_id': option['metric_id'],
                 'dimensions': {key: value for key, value in option['subject'].items() if key not in ('type', 'id')}}
    request(world, selection)


def handle_event(event, world):
    if event.type == pygame.KEYDOWN and event.key == pygame.K_F12:
        if world.get('_ai_explainer'):
            close(world)
        else:
            chooser(world)
        return True
    state = world.get('_ai_explainer')
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if pygame.Rect(world.get('_ai_control_rect', (0, 0, 0, 0))).collidepoint(event.pos):
            selection = _selection(world)
            if selection:
                # Hover then click pins the already requested explanation.
                if state and state.get('selection') == selection:
                    state['pinned'] = True
                else:
                    request(world, selection)
            else:
                chooser(world)
            return True
    if not state:
        return False
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        close(world); return True
    if state.get('chooser') and event.type == pygame.KEYDOWN:
        choosing_entity = state.get('choosing_entity')
        if event.key == pygame.K_RETURN:
            if choosing_entity:
                matches = _entity_matches(world, state)
                if matches: _set_entity(world, state, matches[min(state['index'], len(matches) - 1)])
            else:
                _choose(world)
        elif event.key == pygame.K_BACKSPACE:
            state['text'] = state['text'][:-1]; state['index'] = 0
        elif event.key in (pygame.K_UP, pygame.K_DOWN):
            matches = _entity_matches(world, state) if choosing_entity else _matches(state)
            state['index'] = max(0, min(len(matches) - 1, state['index'] + (1 if event.key == pygame.K_DOWN else -1)))
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            state['turn'] = max(0, min(world.get('turn', 0), state['turn'] + (1 if event.key == pygame.K_RIGHT else -1)))
            _load_catalog(world, state)
        elif event.key == pygame.K_TAB:
            entities = _entities(world)
            if entities:
                direction = -1 if getattr(event, 'mod', 0) & pygame.KMOD_SHIFT else 1
                _set_entity(world, state, entities[(entities.index(state['entity']) + direction) % len(entities)] if state['entity'] in entities else entities[0])
        elif event.unicode and event.unicode.isprintable() and len(state['text']) < 250:
            state['text'] += event.unicode; state['index'] = 0
        return True
    pos = getattr(event, 'pos', pygame.mouse.get_pos())
    inside = pygame.Rect(state.get('rect', (0, 0, 0, 0))).collidepoint(pos)
    if event.type == pygame.MOUSEWHEEL and inside:
        state['scroll'] = max(0, state['scroll'] - event.y * 45); return True
    if event.type == pygame.MOUSEBUTTONDOWN and inside:
        state['pinned'] = True
        if event.button in (4, 5):
            state['scroll'] = max(0, state['scroll'] + (45 if event.button == 5 else -45))
        for rect, action, value in state.get('buttons', []):
            if pygame.Rect(rect).collidepoint(pos):
                if action == 'close': close(world)
                elif action == 'retry': request(world, state['selection'])
                elif action == 'metric': _choose(world, value)
                elif action == 'entities': state.update(choosing_entity=True, text='', index=0, scroll=0)
                elif action == 'entity': _set_entity(world, state, value)
                elif action == 'stats': state.update(choosing_entity=False, text='', index=0, scroll=0)
                elif action == 'chooser': chooser(world)
                elif action == 'turn':
                    state['turn'] = max(0, min(world.get('turn', 0), state['turn'] + value))
                    _load_catalog(world, state)
                elif action == 'refresh': _load_catalog(world, state)
                elif action == 'source': webbrowser.open(value)
                elif action == 'log':
                    job = state['job']
                    state['job'] = default_service().retry_logging(job['job_id'], job['viewer'])
                elif action == 'hover': world['_ai_hover_disabled'] = not world.get('_ai_hover_disabled', False)
                elif action == 'policy':
                    # Navigation only. The existing policy handler still owns execution.
                    from explanations.mechanics import current
                    availability = current(world, state['job']['result']['packet'])
                    if any(a['id'] == value for a in availability['actions']):
                        descriptor = next(a for a in availability['actions'] if a['id'] == value)
                        target = descriptor['target']
                        from client.desktop.panels.left_dock import open_left_panel
                        open_left_panel(world, 'governance')
                        world['policy_scope'] = 'nation' if value == 'nat_emergency_granary' else 'province'
                        if world['policy_scope'] == 'nation':
                            nation = next((n for n in world.get('nations', []) if n.name == target), None)
                            world['selected_nation'] = nation
                            if nation and nation.tiles:
                                world['selected_region'] = nation.tiles[0]
                        else:
                            world['selected_region'] = next((t for t in world.get('tiles', []) if t.name == descriptor.get('navigation_tile')), None)
                        close(world)
                elif action == 'evidence':
                    packet = state['job']['result']['packet']
                    from desktop_evidence_panel import open_panel, load
                    close(world); open_panel(world)
                    world['_causal_panel'].update(event_id=value, turn=packet['selection']['turn'], boundary=packet['selection']['boundary'])
                    load(world)
                break
        return True
    return False


def tick(world):
    """Called by the main loop; local status reads never create model work."""
    now = pygame.time.get_ticks()
    state = world.get('_ai_explainer')
    if state:
        if state['run_id'] != getattr(world.get('run_trace'), 'run_id', None):
            close(world); return True
        selected = _map_entity(world)
        if not state.get('chooser') and selected and selected != state.get('map_entity'):
            # A new map selection returns to its picker, never auto-generates
            # another narrative or relabels the previous tile's answer.
            chooser(world)
            return True
        if state.get('chooser'):
            if selected != state.get('map_entity'):
                state['map_entity'] = selected
                if selected:
                    _set_entity(world, state, selected)
                    return True
            future = state.get('catalog_future')
            if future and future.done():
                state.pop('catalog_future')
                try:
                    state['options'] = sorted((option for option in future.result()
                        if option['metric_id'] in METRICS), key=lambda option:
                        (_COMMON.index(option['metric_id']) if option['metric_id'] in _COMMON else len(_COMMON), _label(option)))
                except Exception as error:
                    state['catalog_error'] = 'Could not read recorded stats: ' + str(error)
                return True
            return False
        if not state.get('pinned'):
            pos = pygame.mouse.get_pos()
            inside = any(pygame.Rect(rect).collidepoint(pos) for rect in
                         (state.get('rect', (0, 0, 0, 0)), world.get('_ai_control_rect', (0, 0, 0, 0))))
            if inside: state.pop('left_at', None)
            else:
                state.setdefault('left_at', now)
                if now - state['left_at'] > 450:
                    close(world); return True
        job = state.get('job', {})
        if job.get('job_id') and job.get('state') not in TERMINAL and now - state['last_poll'] >= 350:
            state['last_poll'] = now
            try: state['job'] = default_service().status(job['job_id'], job['viewer'])
            except ValueError as error: state['job'] = {'state': 'failed', 'message': str(error)}
            return True
        return False
    selection = _selection(world)
    rect = world.get('_ai_control_rect', (0, 0, 0, 0))
    hover_key = json.dumps(selection, sort_keys=True) if selection else None
    if (selection and not world.get('_ai_hover_disabled') and pygame.Rect(rect).collidepoint(pygame.mouse.get_pos())
            and hover_key != world.get('_ai_last_hover_request')):
        if world.get('_ai_hover_key') != hover_key:
            world['_ai_hover_key'] = hover_key; world['_ai_hover_start'] = now
        elif now - world.get('_ai_hover_start', now) >= 700:
            world['_ai_last_hover_request'] = hover_key
            request(world, selection, pinned=False)
            return True
    else:
        world.pop('_ai_hover_key', None)
    return False


def draw(surface, world):
    font = pygame.font.SysFont('Arial', 17)
    width, height = surface.get_size()
    rect = (max(8, width - 258), height - 42, 246, 34)
    world['_ai_control_rect'] = rect
    pygame.draw.rect(surface, (37, 64, 91), rect, border_radius=5)
    text = 'Explain with AI / F12' if _selection(world) else 'AI: choose a stat / F12'
    surface.blit(font.render(text, True, (235, 240, 250)), (rect[0] + 10, rect[1] + 7))
    state = world.get('_ai_explainer')
    if not state:
        return
    panel = pygame.Rect(max(8, width - 660), 24, min(648, width - 16), height - 78)
    state['rect'] = tuple(panel); state['buttons'] = []
    pygame.draw.rect(surface, (12, 23, 38), panel, border_radius=8)
    pygame.draw.rect(surface, (112, 143, 175), panel, 1, border_radius=8)
    def button(label, x, y, w, action, value=None):
        box = (x, y, w, 32); pygame.draw.rect(surface, (42, 65, 90), box, border_radius=4)
        surface.blit(font.render(label, True, (230, 240, 250)), (x + 6, y + 6))
        hit = pygame.Rect(box).clip(surface.get_clip())
        if hit.w and hit.h:
            state['buttons'].append((tuple(hit), action, value))
    surface.blit(font.render('AI historian / adviser', True, (245, 214, 150)), (panel.x + 12, panel.y + 12))
    button('Close / Esc', panel.right - 116, panel.y + 5, 104, 'close')
    clip = pygame.Rect(panel.x + 12, panel.y + 48, panel.w - 24, panel.h - 60)
    old_clip = surface.get_clip(); surface.set_clip(clip)
    y = clip.y - state.get('scroll', 0)
    def line(text, heading=False):
        nonlocal y
        words = str(text).split(); current = ''
        for word in words + ['']:
            if word and font.size(current + ' ' + word)[0] < clip.w:
                current = (current + ' ' + word).strip(); continue
            if current:
                surface.blit(font.render(current, True, (245, 214, 150) if heading else (222, 231, 242)), (clip.x, y)); y += 22
            current = word
        y += 8
    if state.get('chooser'):
        line('Click an uncovered map tile to select it, or search using Change tile / nation. Tab also switches entity.')
        line(f"{state['entity']} · Turn {state['turn']}", True)
        button('Change tile / nation', clip.x, y, 180, 'entities')
        button('Turn -', clip.x + 190, y, 82, 'turn', -1)
        button('Turn +', clip.x + 282, y, 82, 'turn', 1)
        button('Refresh', clip.x + 374, y, 88, 'refresh'); y += 42
        line('Type to filter; Up/Down selects; Enter opens the selection.' if state.get('choosing_entity') else
             'Only recorded stats are listed. Click a stat or press Enter to generate.')
        line('Search: ' + state['text'] + '_')
        if state.get('choosing_entity'):
            matches = _entity_matches(world, state)
            start = max(0, state['index'] - 3)
            for index, entity in enumerate(matches[start:start + 8], start):
                button(('> ' if index == state['index'] else '') + entity, clip.x, y, clip.w, 'entity', entity); y += 38
            button('Back to stats', clip.x, y, 140, 'stats'); y += 38
        else:
            matches = _matches(state); start = max(0, state['index'] - 3)
            if state.get('catalog_future'):
                line('Reading recorded stats… You can keep selecting tiles.')
            elif state.get('catalog_error'):
                line(state['catalog_error'])
            elif not matches:
                line('No matching records for this entity and turn. Try another tile, turn, or search. Turn 0 may have no completed sample.')
            for index, option in enumerate(matches[start:start + 8], start):
                button(('> ' if index == state['index'] else '') + _label(option), clip.x, y, clip.w, 'metric', option); y += 38
        button('Hover: ' + ('off' if world.get('_ai_hover_disabled') else 'on'), clip.x, y, 140, 'hover'); y += 38
    else:
        selection = state['selection']; job = state['job']
        line(f"{selection['entity']} · Turn {selection['turn']} · {selection['metric_id']}", True)
        button('Choose another stat / tile', clip.x, y, 240, 'chooser'); y += 42
        if job['state'] not in TERMINAL:
            line(job['message'] + ' ' + '·' * ((pygame.time.get_ticks() // 350) % 4))
            line('Working on this requested explanation. You can keep playing.')
        elif job['state'] != 'ready':
            line(job['message']); button('Retry explanation', clip.x, y, 170, 'retry'); y += 38
        else:
            result = job['result']; packet = result['packet']; narrative = result['narrative']; values = packet['values']
            line('What changed', True); line(f"{values['before']} → {values['after']} {values['unit']}; delta {values['delta']}")
            line('Why it changed', True)
            for claim in narrative['claims']: line(claim['text'] + ' [' + claim['level'] + ']')
            line('A historical parallel', True)
            parallel = narrative['historical_parallel']
            entry = next((h for h in packet['historical_candidates'] if parallel and h['id'] == parallel['entry_id']), None)
            if entry:
                line(f"{entry['title']} ({entry['start_year']}–{entry['end_year']})", True)
                if entry['later_than_scenario']: line('This comparison occurs after the scenario date.')
                for text in (entry['cause'], entry['response'], entry['outcome'], parallel['comparison'], parallel['difference'], entry['difference']): line(text)
                for source in entry['sources']:
                    button('Open historical source', clip.x, y, 220, 'source', source['url']); y += 38
            else: line('No suitable reviewed historical parallel selected.')
            line('Options in this game', True)
            for advice in narrative['suggested_actions']:
                action = next(a for a in packet['actions'] if a['id'] == advice['action_id'])
                line(action['label'], True); line(advice['rationale'])
                line(('Available' if action['available'] else 'Blocked') + ' at request time: ' + action['prerequisites'])
                line(action['tradeoffs']); line('Find control: ' + action['navigation'])
                from explanations.mechanics import current
                available_now = current(world, packet)
                fresh = next((a for a in available_now['actions'] if a['id'] == action['id']), None)
                line('Current control: ' + ('available' if fresh and fresh['available'] else 'blocked or target changed'))
                button('Open policies', clip.x, y, 150, 'policy', action['id']); y += 38
            if not narrative['suggested_actions']: line('No supported playable response selected from the known catalog.')
            line('Check the current policy control: affordability and availability may have changed.')
            for i, proposal in enumerate(narrative['future_mechanics']):
                line('Possible future mechanic — not implemented', True); line(proposal['title'], True)
                for key in ('unmet_need', 'gap_reason', 'proposal', 'tradeoffs'): line(proposal[key])
                for criterion in proposal['acceptance_criteria']: line('Acceptance: ' + criterion)
                line('Provisional catalog gap: requires code/design review.')
                logs = result.get('proposal_logs', [])
                log = logs[i] if i < len(logs) else {}
                line('Logged: ' + log['path'] if log.get('status') == 'logged' else 'Not logged: retry planning persistence.')
                if log.get('status') != 'logged': button('Retry planning log', clip.x, y, 180, 'log'); y += 38
            line('Evidence and limitations', True)
            for gap in packet['limitations']: line(gap)
            line(packet['catalog_coverage'])
            for evidence in packet['evidence']:
                line(f"T{evidence['turn']} {evidence['kind']} · {evidence['status']} · {evidence['event_id']}")
                button('Inspect recorded source', clip.x, y, 215, 'evidence', evidence['event_id']); y += 38
            for warning in result.get('warnings', []): line(warning)
    state['max_scroll'] = max(0, y + state.get('scroll', 0) - clip.bottom)
    state['scroll'] = min(state.get('scroll', 0), state['max_scroll'])
    surface.set_clip(old_clip)
