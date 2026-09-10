"""ui_targets.py — Dynamic UI Target Registry & Flexible Hit-Testing System.

Decouples UI layout from hit-testing by registering visible pygame.Rects at render time.
Input handlers query the registry directly, eliminating hardcoded coordinate offsets.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
import pygame


@dataclass
class UITarget:
    rect: pygame.Rect
    action: Any
    tooltip_id: str | None = None
    scope: str = 'global'
    callback: Callable[[dict, Any], None] | None = None
    data: Any = None
    priority: int = 0

    def collidepoint(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    @property
    def target_id(self) -> Any:
        """Alias for action to support target_id conventions."""
        return self.action


def clear_targets(world: dict | None) -> None:
    """Clear all registered UI targets for the current frame."""
    if world is not None:
        world['_ui_targets'] = []


def register_target(
    world: dict | None,
    rect: pygame.Rect | tuple[int, int, int, int] | list[int],
    action: Any,
    tooltip_id: str | None = None,
    scope: str = 'global',
    callback: Callable[[dict, Any], None] | None = None,
    data: Any = None,
    priority: int = 0,
) -> pygame.Rect:
    """Register an interactive bounding box in the current frame's registry.

    Returns the pygame.Rect so it can be immediately used for drawing.
    """
    if isinstance(rect, pygame.Rect):
        pg_rect = rect
    else:
        pg_rect = pygame.Rect(*rect)

    if world is not None:
        targets = world.setdefault('_ui_targets', [])
        target = UITarget(
            rect=pg_rect,
            action=action,
            tooltip_id=tooltip_id,
            scope=scope,
            callback=callback,
            data=data,
            priority=priority,
        )
        targets.append(target)

    return pg_rect


def find_target(
    world: dict | None,
    pos: tuple[int, int],
    scope: str | None = None,
) -> UITarget | None:
    """Find the topmost registered target containing pos.

    If scope is provided, only targets with that exact scope are evaluated.
    Targets are tested in reverse registration order (most recently drawn first).
    """
    if not world:
        return None
    targets = world.get('_ui_targets')
    if not targets:
        return None

    for target in reversed(targets):
        if scope is not None and target.scope != scope:
            continue
        if target.collidepoint(pos):
            return target

    return None


def find_hover_target(
    world: dict | None,
    pos: tuple[int, int],
    scope: str | None = None,
) -> UITarget | None:
    """Convenience alias for find_target when processing hover events."""
    return find_target(world, pos, scope=scope)


def resolve_hover_tooltip(
    world: dict | None,
    pos: tuple[int, int],
    scope: str | None = None,
) -> bool:
    """Detect if pos hovers over a registered target with a tooltip_id.

    If found and no tooltip is currently set, populates world['_hovered_left_tooltip'].
    Returns True if a tooltip was successfully set.
    """
    if not world:
        return False
    if world.get('_hovered_left_tooltip'):
        return True

    target = find_target(world, pos, scope=scope)
    if target and target.tooltip_id:
        from worldview_tooltips import get_button_tooltip_data
        tdata = get_button_tooltip_data(target.tooltip_id, world)
        if tdata:
            tdata['btn_rect'] = target.rect
            world['_hovered_left_tooltip'] = tdata
            return True

    return False


def dispatch_click(
    world: dict | None,
    pos: tuple[int, int],
    scope: str | None = None,
) -> tuple[bool, Any]:
    """Hit-test against registered targets and invoke callback if present.

    Returns (hit_found, action).
    """
    target = find_target(world, pos, scope=scope)
    if target is None:
        return False, None

    if target.callback is not None and world is not None:
        target.callback(world, target.data)

    return True, target.action
