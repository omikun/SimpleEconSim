"""Exercise the real urgent-dialog controls in automated governing campaigns."""


def resolve_notices(world, draw=None):
    # Headless runs use disposable rendering targets. Keep Rect/font objects
    # out of the live campaign graph that the semantic verifier serializes.
    if draw is not None:
        return _resolve(world, draw)
    missing = object()
    targets = world.get('_ui_targets', missing)
    try:
        return _resolve(world, None)
    finally:
        if targets is missing:
            world.pop('_ui_targets', None)
        else:
            world['_ui_targets'] = targets


def _resolve(world, draw):
    import pygame
    from ui_targets import clear_targets
    from client.desktop.panels.governing_campaign_ui import warning_open, draw_warning
    from client.desktop.panels.scenario_ui import guided_ui_hit
    pygame.font.init()
    decisions = []
    for _ in range(12):
        if not warning_open(world):
            return decisions
        if draw is None:
            clear_targets(world)
            draw_warning(pygame.Surface((1400, 900)), world)
        else:
            draw()
        targets = [t for t in world['_ui_targets'] if t.scope == 'scenario_warning']
        if not targets:
            raise AssertionError('Urgent campaign notice has no available response.')
        # Authored order, first legal response: a reproducible legal policy,
        # rather than a claim to the best diplomatic or political strategy.
        target = targets[0]
        before = world['scenario_warning_modal']
        decisions.append(dict(turn=world['turn'], kind=before['kind'], action=target.action[1]))
        if not guided_ui_hit(target.rect.center, world) or world.get('scenario_warning_modal') is before:
            raise AssertionError('Urgent campaign response did not resolve: ' + str(target.action))
    raise AssertionError('Too many consecutive urgent campaign decisions.')
