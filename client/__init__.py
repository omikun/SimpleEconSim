"""Unified Client Architecture (Web, Desktop, Headless).

Keep package exports lazy so importing a leaf module such as
``client.desktop.camera`` does not initialize every client and renderer. The
headless client imports ``render_engine``, which itself imports desktop camera
constants; eager exports here would create a package initialization cycle.
"""

from importlib import import_module

__all__ = ['RegnumWebServer', 'run_web_server', 'GameClient', 'desktop']


def __getattr__(name):
    if name in ('RegnumWebServer', 'run_web_server'):
        module = import_module('client.web')
        return getattr(module, name)
    if name == 'GameClient':
        return import_module('client.headless').GameClient
    if name == 'desktop':
        return import_module('client.desktop')
    raise AttributeError(f"module 'client' has no attribute {name!r}")
