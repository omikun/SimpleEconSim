#!/usr/bin/env python3
# Phase 6H: widen FX band so the managed float has room (was pinned at ceiling)
TARGET = 'forex.py'
src = open(TARGET).read()

old = "DESK_BAND = (0.5, 2.0)           # rate bounds (policy floor/ceiling)"
new = ("DESK_BAND = (0.4, 2.5)           # rate bounds (policy floor/ceiling);\n"
       "# widened from (0.5, 2.0): sustained reserve pressure pinned both desks\n"
       "# at the ceiling even after damping — more room lets the float express\n"
       "# relative competitiveness instead of resting on the band wall")

assert src.count(old) == 1, "DESK_BAND not found"
src = src.replace(old, new)
open(TARGET, 'w').write(src)
print("patch_p6h.py applied OK")