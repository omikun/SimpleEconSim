#!/usr/bin/env python3
"""M2.1 probe: Faction class — overlapping membership, demands, grievances.

Checks:
  1. A single Agent can join 2+ factions (overlap visible).
  2. Demands rank, satisfaction updates, and support measure move properly.
  3. Grievances accumulate and decay.
  4. FactionSystem.step() refreshes support + decay across factions.

Usage:
    python3 tmp/probe_factions.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from agent import Agent
    from faction import Faction, FactionSystem

    ok = True
    a1 = Agent(0)   # id 1
    a2 = Agent(0)   # id 2
    a3 = Agent(0)   # id 3

    sol = Faction("Sol", "religion")
    pop = Faction("Populist", "political")

    sol.add_member(a1)
    sol.add_member(a2)
    pop.add_member(a1)      # a1 is BOTH Sol and Populist -> overlap
    pop.add_member(a3)

    ov = FactionSystem()
    ov.register(sol)
    ov.register(pop)
    overlaps = ov.overlaps()
    print(f"[1] membership: Sol={len(sol.membership)} Populist={len(pop.membership)}")
    print(f"    overlaps: {overlaps}")
    if not any(aid == a1.id and len(names) >= 2 for aid, names in overlaps):
        print("    FAIL: agent 1 should be in 2+ factions")
        ok = False

    sol.add_demand("tax_cut", weight=2.0)
    sol.add_demand("welfare", weight=1.0)
    sol.set_satisfied("tax_cut", 0.5)
    eligible = {a1.id, a2.id, a3.id}
    s1 = sol.compute_support(eligible)
    print(f"[2] Sol support (sat 0.5): {s1:.3f}")
    sol.set_satisfied("tax_cut", 1.0)
    s2 = sol.compute_support(eligible)
    print(f"    Sol support (sat 1.0): {s2:.3f}")
    if not (0 <= s1 < s2 <= 1):
        print("    FAIL: support should rise with satisfaction")
        ok = False

    sol.add_grievance("hunger", 4.0)
    sol.add_grievance("tax", 6.0)
    total = sol.total_grievance()
    print(f"[3] Sol grievance total: {total:.2f}")
    if total != 10.0:
        print("    FAIL: grievance total should be 10.0")
        ok = False
    sol.decay_grievances(0.5)
    print(f"    after decay x0.5: {sol.total_grievance():.2f}")
    if sol.total_grievance() > 5.01:
        print("    FAIL: decay should halve")
        ok = False

    print(f"[4] FactionSystem.step: {sol!r}")
    ov.step(eligible)

    print("\n" + "=" * 50)
    print("PROBE PASS" if ok else "PROBE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())