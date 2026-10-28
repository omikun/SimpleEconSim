"""Desktop presentation exports, loaded only when requested.

Leaf clients such as network_lab must not initialize the economic world, GPU
renderers, or every political/economic panel just to import their package.
"""
from importlib import import_module

__all__ = ['build_world_view', 'step_world', 'render_frame', 'main']


def __getattr__(name):
    if name in ('build_world_view', 'step_world'):
        return getattr(import_module('client.desktop.engine'), name)
    if name in ('render_frame', 'main'):
        return getattr(import_module('client.desktop.app'), name)
    camera = import_module('client.desktop.camera')
    try:
        return getattr(camera, name)
    except AttributeError:
        raise AttributeError(f"module 'client.desktop' has no attribute {name!r}") from None
