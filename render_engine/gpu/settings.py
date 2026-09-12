"""
render_engine/gpu/settings.py — Persistent configuration & backup for GPU terrain shader parameters.

Shared between standalone render_dev_viewer and the main game client.
"""

import os
import json
import shutil
from typing import Dict, Any, Tuple, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SETTINGS_FILE = os.path.join(PROJECT_ROOT, "gpu_terrain_settings.json")
BACKUP_FILE = os.path.join(PROJECT_ROOT, "gpu_terrain_settings.backup.json")

# Fallback defaults if no settings file has been saved yet
DEFAULT_SHADER_UNIFORMS: Dict[str, float] = {
    'mountain_roughness': 1.0,
    'shelf_width_mult': 1.0,
    'ocean_depth_mult': 1.0,
    'river_width_mult': 1.0,
    'river_depth_mult': 1.0,
    'lake_depth_mult': 1.0,
    'forest_density': 1.0,
    'canopy_roughness': 1.0,
    'tree_scale': 1.0,
    'plains_grain': 1.0,
    'soil_patchiness': 1.0,
    'grass_warmth': 1.0,
    'sun_intensity': 1.15,
    'ambient_intensity': 0.45,
    'sun_azimuth': -135.0,
    'sun_elevation': 42.0,
}


def load_gpu_settings() -> Dict[str, float]:
    """Load persistent GPU shader uniforms, falling back to defaults for any missing keys."""
    settings = dict(DEFAULT_SHADER_UNIFORMS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in settings and isinstance(v, (int, float)):
                        settings[k] = float(v)
        except Exception as e:
            print(f"[GPUSettings] Warning: Failed to parse {SETTINGS_FILE}: {e}")
    return settings


def save_gpu_settings(uniforms: Dict[str, float]) -> Tuple[bool, str]:
    """
    Save uniform settings as the new persistent default.
    Creates a backup of the existing settings file if present before overwriting.
    """
    try:
        # 1. Create backup if an existing file is present
        if os.path.exists(SETTINGS_FILE):
            shutil.copyfile(SETTINGS_FILE, BACKUP_FILE)

        # 2. Filter & format valid keys
        to_save = {}
        for k in DEFAULT_SHADER_UNIFORMS.keys():
            if k in uniforms:
                to_save[k] = round(float(uniforms[k]), 4)

        # 3. Write formatted JSON
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=2, sort_keys=True)

        return True, "Settings saved successfully (backup created)"
    except Exception as e:
        return False, f"Failed to save settings: {e}"


def has_backup() -> bool:
    """Return True if a backup settings file exists."""
    return os.path.exists(BACKUP_FILE)


def revert_gpu_settings_backup() -> Tuple[bool, str, Optional[Dict[str, float]]]:
    """
    Revert settings to the previous backup file if one exists.
    Returns (success, message, restored_uniforms).
    """
    if not os.path.exists(BACKUP_FILE):
        return False, "No backup file found to restore", None

    try:
        # Copy backup over current settings file
        shutil.copyfile(BACKUP_FILE, SETTINGS_FILE)
        restored = load_gpu_settings()
        return True, "Restored settings from backup", restored
    except Exception as e:
        return False, f"Failed to restore backup: {e}", None
