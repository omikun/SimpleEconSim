"""scratch/test_ui_targets.py — Unit tests for ui_targets registry."""

import pygame
from ui_targets import UITarget, clear_targets, register_target, find_target, dispatch_click, resolve_hover_tooltip

pygame.init()

def test_registry_basics():
    world = {}
    clear_targets(world)
    assert world['_ui_targets'] == []

    # Register three buttons
    r1 = register_target(world, (10, 10, 100, 30), ('tab', 1), scope='compare')
    r2 = register_target(world, (120, 10, 100, 30), ('tab', 2), scope='compare')
    r3 = register_target(world, (10, 50, 100, 30), 'save', scope='actions')

    assert len(world['_ui_targets']) == 3
    assert isinstance(r1, pygame.Rect)

    # Click in button 1
    t1 = find_target(world, (50, 20), scope='compare')
    assert t1 is not None
    assert t1.action == ('tab', 1)

    # Click in button 2
    t2 = find_target(world, (150, 20), scope='compare')
    assert t2 is not None
    assert t2.action == ('tab', 2)

    # Click in button 3 with scope='compare' -> None (scoped)
    assert find_target(world, (50, 60), scope='compare') is None

    # Click in button 3 with scope='actions' -> found
    t3 = find_target(world, (50, 60), scope='actions')
    assert t3 is not None
    assert t3.action == 'save'

    # Click outside all
    assert find_target(world, (500, 500)) is None

    # Clear frame
    clear_targets(world)
    assert len(world['_ui_targets']) == 0
    print("  -> test_registry_basics passed!")


def test_callback_dispatch():
    world = {'counter': 0}
    clear_targets(world)

    def on_click(w, delta):
        w['counter'] += delta

    register_target(world, (0, 0, 50, 50), 'increment', callback=on_click, data=5)

    hit, action = dispatch_click(world, (25, 25))
    assert hit is True
    assert action == 'increment'
    assert world['counter'] == 5
    print("  -> test_callback_dispatch passed!")


def test_flexible_repositioning():
    """Verify that moving a button at render time immediately updates hit testing."""
    world = {}
    clear_targets(world)

    # Turn 1: Button is at (20, 20)
    register_target(world, (20, 20, 80, 25), 'btn_a', scope='test')
    assert find_target(world, (30, 30), scope='test') is not None
    assert find_target(world, (130, 130), scope='test') is None

    # Turn 2: UI layout moves button to (120, 120) dynamically
    clear_targets(world)
    register_target(world, (120, 120, 80, 25), 'btn_a', scope='test')
    assert find_target(world, (30, 30), scope='test') is None
    assert find_target(world, (130, 130), scope='test') is not None
    print("  -> test_flexible_repositioning passed!")


if __name__ == '__main__':
    test_registry_basics()
    test_callback_dispatch()
    test_flexible_repositioning()
    print("ALL UI TARGET REGISTRY TESTS PASSED!")
