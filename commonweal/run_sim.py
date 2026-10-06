"""run_sim.py — headless run + summary.  Usage: python run_sim.py [years] [seed] [preset]

Prints yearly means (averaged over the last 4 seasons) every 10 years.
"""
import sys
from sim.world import World
from sim.config import Params


def avg(S, k, n=4):
    v = S[k][-n:]
    return sum(v) / len(v)


def main():
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    preset = sys.argv[3] if len(sys.argv) > 3 else "endogenous"
    w = World(Params(seed=seed, preset=preset))
    S = w.series
    print("yr  pop   gdp   out  cap health wellb work free life ties cult comm land% debt% lgini hung%")
    for t in range(years * 4):
        if not w.adults():
            print("extinct at year", w.year)
            break
        w.step()
        if (t + 1) % 40 == 0:
            print(f"{w.year:3d} {S['pop'][-1]:4d} {avg(S,'gdp'):.2f} {avg(S,'output'):.2f} {S['capital'][-1]:4d} "
                  f"{avg(S,'med_health'):.2f}  {avg(S,'wellbeing'):.2f}  {avg(S,'work_hours'):4.1f} {avg(S,'free_hours'):4.1f} "
                  f"{S['lifespan'][-1]:4.1f} {avg(S,'ties'):.2f} {avg(S,'culture'):.2f} {avg(S,'commons'):.2f} "
                  f"{avg(S,'landless')*100:3.0f} {avg(S,'in_debt')*100:3.0f} {avg(S,'land_gini'):.2f} {avg(S,'hunger')*100:3.0f}")
    print("money", round(w.total_money(), 3), "causes", dict(w.cause_counts))


if __name__ == "__main__":
    main()
