"""Test suite package for Call of Capital / SimpleEconSim."""
from pathlib import Path as _Path
import sys as _sys

_ROOT = _Path(__file__).resolve().parents[1]
_SUBDIRS = ['core', 'agents', 'micro', 'meso', 'macro', 'economy', 'terrain', 'scenarios', 'trace', 'client/worldview', 'tests', 'scripts', 'benchmarks']
for _rel in reversed(_SUBDIRS):
    _p = str(_ROOT / _rel)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
