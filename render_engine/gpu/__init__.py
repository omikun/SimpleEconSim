"""
render_engine/gpu/__init__.py — GPU terrain rendering engine entry point.
"""

from typing import Optional
from render_engine.gpu.base import BaseGPUTerrainPipeline
from render_engine.gpu.moderngl_pipeline import ModernGLTerrainPipeline, MODERNGL_AVAILABLE
from render_engine.gpu.fallback_pipeline import CPUFallbackPipeline

_GLOBAL_PIPELINE: Optional[BaseGPUTerrainPipeline] = None


def is_gpu_available() -> bool:
    """Check if hardware GPU acceleration is ready to use."""
    if not MODERNGL_AVAILABLE:
        return False
    pipeline = get_gpu_pipeline()
    return pipeline.is_available() and isinstance(pipeline, ModernGLTerrainPipeline)


def get_gpu_pipeline(force_cpu: bool = False) -> BaseGPUTerrainPipeline:
    """Return the active terrain pipeline (ModernGL if available, else CPU fallback)."""
    global _GLOBAL_PIPELINE

    if force_cpu:
        return CPUFallbackPipeline()

    if _GLOBAL_PIPELINE is not None:
        return _GLOBAL_PIPELINE

    if MODERNGL_AVAILABLE:
        try:
            pipeline = ModernGLTerrainPipeline()
            if pipeline.is_available():
                _GLOBAL_PIPELINE = pipeline
                return _GLOBAL_PIPELINE
        except Exception as e:
            print(f"[render_engine.gpu] ModernGL initialization failed: {e}. Using CPU fallback.")

    _GLOBAL_PIPELINE = CPUFallbackPipeline()
    return _GLOBAL_PIPELINE


from render_engine.gpu.settings import (
    load_gpu_settings,
    save_gpu_settings,
    has_backup,
    revert_gpu_settings_backup,
    DEFAULT_SHADER_UNIFORMS,
)
