"""Test suite package for Call of Capital / SimpleEconSim."""
from pathlib import Path as _Path
import sys as _sys

_TESTS_DIR = _Path(__file__).resolve().parent
_ROOT_DIR = _TESTS_DIR.parent
for _p in (str(_ROOT_DIR), str(_TESTS_DIR), str(_ROOT_DIR / "scripts"), str(_ROOT_DIR / "benchmarks")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
