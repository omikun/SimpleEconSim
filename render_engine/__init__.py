"""
render_engine — Dedicated, standalone graphics & rendering engine for REGNUM.

Completely decoupled from economic simulation logic. Can be driven by
the game client or run independently via the graphics dev sandbox.
"""

from render_engine.camera import Camera
from render_engine.core import RenderEngine

__all__ = ['Camera', 'RenderEngine']
