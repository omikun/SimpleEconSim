#!/usr/bin/env python3
# Phase 6E: restore 110 agents per region (was 55)
TARGET = 'econsim_two_region.py'
src = open(TARGET).read()

old_a = '    region_a = Region("Region_A", t=0, number_of_agents=55,\n'
new_a = '    region_a = Region("Region_A", t=0, number_of_agents=110,\n'
old_b = '    region_b = Region("Region_B", t=0, number_of_agents=55,\n'
new_b = '    region_b = Region("Region_B", t=0, number_of_agents=110,\n'

assert src.count(old_a) == 1, "region_a line not found"
assert src.count(old_b) == 1, "region_b line not found"
src = src.replace(old_a, new_a)
src = src.replace(old_b, new_b)
open(TARGET, 'w').write(src)
print("patch_p6e.py applied OK")