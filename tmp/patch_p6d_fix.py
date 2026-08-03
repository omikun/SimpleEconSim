#!/usr/bin/env python3
# Fix: move stray `import math` out of the docstring to module level
T = 'forex.py'
src = open(T).read()

old = 'ForexDesk — central-bank quote with reserve constraints (Phase 1).\n\nimport math\n\nReal-world analog:'
new = 'ForexDesk — central-bank quote with reserve constraints (Phase 1).\n\nReal-world analog:'
assert src.count(old) == 1, "docstring stray import not found"
src = src.replace(old, new)

# Add a real module-level import after the docstring if absent
if '\nimport math\n' not in src:
    old_tail = 'Phase 3 (interbank order book) can layer on top by quoting inside the\nband exposed here (mid / spread / band) without restructuring.\n"""\n'
    new_tail = 'Phase 3 (interbank order book) can layer on top by quoting inside the\nband exposed here (mid / spread / band) without restructuring.\n"""\n\nimport math\n'
    assert src.count(old_tail) == 1, "docstring tail not found"
    src = src.replace(old_tail, new_tail)

open(T, 'w').write(src)
print("patch_p6d_fix.py applied OK")