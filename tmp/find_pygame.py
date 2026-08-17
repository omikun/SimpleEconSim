#!/usr/bin/env python3
"""Locate a python interpreter that has pygame (for headless viewer probes)."""

import shutil
import subprocess
import sys

CANDIDATES = [
    sys.executable,
    "/usr/local/bin/python3",
    "/opt/homebrew/bin/python3",
    "/usr/bin/python3",
    shutil.which("python3"),
    shutil.which("python3.13"),
    shutil.which("python3.12"),
    shutil.which("python3.11"),
]


def has_pygame(exe):
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "-c", "import pygame; print(pygame.version.ver)"],
                           capture_output=True, text=True, timeout=20)
        return r.returncode == 0, r.stdout.strip()
    except Exception as e:
        return False, str(e)


seen = set()
for exe in CANDIDATES:
    if not exe or exe in seen:
        continue
    seen.add(exe)
    ok, info = has_pygame(exe)
    print(f"{exe}: {'pygame ' + info if ok else 'NO pygame'}")
    if ok:
        print(f"FOUND: {exe}")
        sys.exit(0)

# Also check venvs under the repo.
import glob as _glob
for venv_py in _glob.glob("/Users/sli/Code/*/bin/python3") + \
               _glob.glob("/Users/sli/Code/.venv/bin/python3"):
    ok, info = has_pygame(venv_py)
    print(f"{venv_py}: {'pygame ' + info if ok else 'NO pygame'}")
    if ok:
        print(f"FOUND: {venv_py}")
        sys.exit(0)

print("NOT FOUND")
sys.exit(1)