"""world.py — the Commonweal simulation core.

One tick = one season.  Every stage is a method called in a fixed order by
`step()`.  Money and food are conserved; `audit()` proves it each tick.
Capitalism is never switched on: lending, foreclosure, wage labour, the
competition ratchet and the squeeze on free time all arise from harvest
variance acting on people's ordinary decisions.
"""
import math
import random
from collections import defaultdict

from . import config as C
from .config import Params, Dials
from .model import Plot, Debt, Person

SYL_A = ("Al", "Bran", "Cor", "Dun", "El", "Fen", "Gar", "Hal", "Ing", "Jor", "Kel", "Lor",
         "Mar", "Nor", "Os", "Per", "Ran", "Sig", "Tam", "Ulf", "Vel", "Wyn", "Yar", "Zed")
SYL_B = ("a", "en", "ic", "o", "wyn", "ric", "la", "mund", "dra", "ith", "bert", "ley")


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class World:
    # ------------------------------------------------------------------ setup
    def __init__(self, params=None, dials=None):
        self.params = params or Params()
        self.dials = dials or Dials()
        self.reset()

    def reset(self):
        P = self.params
        self.rng = random.Random(P.seed)
        self.t = 0
        self.persons = {}
        self.plots = {}
        self.next_pid = 1
        self.next_plot = 1
        self.price = P.price_start
        self.wage_rate = 0.0
        self.weather = 1.0
        self.commons = 1.0
        self.pollution = 0.0
        self.outside_cash = 0.0
        self.relief_pool = 0.0
        self.merchant_active = False
        self.tax_active = False
        self.cause_counts = defaultdict(int)
        self.death_ages = []              # (t, age_years)
        self.series = defaultdict(list)
        self.chronicle = []               # (t, text) world-level events
        self.flows = defaultdict(float)   # per-tick counters
        preset = C.PRESETS[P.preset]
        if preset["merchant_year"] is not None:
            self.outside_cash = P.merchant_cash
        n = P.n_start
        n_adult = int(n * 0.7)
        cells = [(x, y) for x in range(P.grid_w) for y in range(P.grid_h)]
        self.rng.shuffle(cells)
        adults = []
        for i in range(n_adult):
            age = self.rng.randint(C.ADULT_AGE, 55 * C.SEASONS)
            x, y = cells[i]
            p = self._new_person(age, None, x, y)
            p.cash = P.cash_start
            plot = self._new_plot(x, y, 1.0, self.rng.uniform(0.8, 1.2), p.id)
            p.plots.append(plot.id)
            adults.append(p)
        for i in range(n - n_adult):
            g = self.rng.choice(adults)
            c = self._new_person(self.rng.randint(0, C.ADULT_AGE - 1), g.id, g.x, g.y)
            g.dependents.append(c.id)
            c.know = {k: v * 0.95 for k, v in g.know.items()}
        # kin + neighbour ties
        for p in adults:
            near = sorted(adults, key=lambda q: (q.x - p.x) ** 2 + (q.y - p.y) ** 2)[1:6]
            for q in near:
                w = self.rng.uniform(0.3, 0.7)
                p.ties[q.id] = max(p.ties.get(q.id, 0), w)
                q.ties[p.id] = max(q.ties.get(p.id, 0), w)
        for p in adults:
            p.food = 2.2 * self.need(p)
        self.money0 = self.total_money()
        self.food_prev = self.total_food()
        self.record_metrics()

    def _name(self):
        return self.rng.choice(SYL_A) + self.rng.choice(SYL_B)

    def _new_person(self, age, guardian, x, y):
        p = Person(self.next_pid, self._name(), age, guardian, self.t - age, x, y)
        self.next_pid += 1
        p.know = {k: clamp(self.rng.gauss(0.85, 0.07), 0.3, 1.0) for k in C.PRACTICES}
        p.h_emp = self.params.emp_hours_start
        self.persons[p.id] = p
        return p

    def _new_plot(self, x, y, area, fert, owner):
        pl = Plot(self.next_plot, x, y, area, fert, owner)
        self.plots[pl.id] = pl
        self.next_plot += 1
        return pl

    # ------------------------------------------------------------------ helpers
    @property
    def year(self):
        return self.t // C.SEASONS

    @property
    def season(self):
        return self.t % C.SEASONS

    def alive(self):
        return [p for p in self.persons.values() if p.alive]

    def adults(self):
        return [p for p in self.persons.values() if p.alive and p.is_adult()]

    def kids(self, p):
        return [self.persons[d] for d in p.dependents if self.persons[d].alive]

    def need(self, p):
        return C.NEED_ADULT + C.NEED_CHILD * len(self.kids(p))

    def area(self, p):
        return sum(self.plots[i].area for i in p.plots)

    def eff_area(self, p):
        return sum(self.plots[i].eff() for i in p.plots)

    def land_value(self, p):
        return sum(self.plots[i].area * self.plots[i].fert * 40.0 for i in p.plots) * self.price

    def total_money(self):
        return (sum(p.cash for p in self.persons.values() if p.alive)
                + self.outside_cash + self.relief_pool)

    def total_food(self):
        return sum(p.food for p in self.persons.values() if p.alive)

    def pay(self, src, dst, amount, reason):
        """The only way money moves.  src/dst: Person, 'outside' or 'relief'."""
        if amount <= 0:
            return 0.0
        if src == "outside":
            self.outside_cash -= amount
        elif src == "relief":
            self.relief_pool -= amount
        else:
            src.cash -= amount
        if dst == "outside":
            self.outside_cash += amount
        elif dst == "relief":
            self.relief_pool += amount
        else:
            dst.cash += amount
            dst.income_by[reason] += amount
            sid = src.id if hasattr(src, "id") else (-1 if src == "outside" else -2)
            dst.income_from[sid] += amount
        return amount

    def chron(self, text):
        self.chronicle.append((self.t, text))
        if len(self.chronicle) > 300:
            del self.chronicle[:100]

    # ------------------------------------------------------------------ step
    def step(self):
        P, D = self.params, self.dials
        self.flows = defaultdict(float)
        s, yr = self.season, self.year
        if s == 0:
            self.weather = clamp(self.rng.lognormvariate(0, 0.25), 0.45, 1.5)
            if self.rng.random() < 0.12:        # drought / flood year
                self.weather *= self.rng.uniform(0.3, 0.6)
                self.chron(f"Year {yr}: a failed harvest.")
            for q in self.persons.values():     # hail, pests, sickness: household luck
                q.luck = clamp(self.rng.lognormvariate(0, 0.4), 0.25, 2.0)
            pre = C.PRESETS[P.preset]
            if pre["merchant_year"] == yr and not self.merchant_active:
                self.merchant_active = True
                self.chron("Outside merchants arrive, offering cash for surplus grain.")
            if pre["tax_year"] == yr and not self.tax_active:
                self.tax_active = True
                self.chron("An outside state demands a tax payable only in cash.")
        self._spoil()
        adults = self.adults()
        for p in self.alive():
            for k in p.hours:
                p.hours[k] = 0.0
            p.employer = None
            p.hired = []
        self._plan_own_work(adults, s)
        self._hire(adults, s)
        self._produce(adults, s)
        self._forage(adults, s)
        self._free_time(adults)
        self._mutual_aid(adults)
        self._borrow(adults)
        self._market(adults)
        self._consume()
        self._cloth(adults)
        if self.tax_active:
            self._tax(adults)
        self._debts()
        self._relief()
        self._invest_and_ratchet()
        self._social_and_culture(adults)
        self._bodies()
        self._ecology()
        self._demography()
        self.t += 1
        self.audit()
        self.record_metrics()

    # ------------------------------------------------------------------ stages
    def _spoil(self):
        for p in self.alive():
            lost = p.food * C.SPOIL
            p.food -= lost
            self.flows["spoiled"] += lost

    def _care(self, p):
        return min(5.0, 1.2 * len(self.kids(p)))

    def _land_coef(self, p):
        return (C.YIELD_A * (self.eff_area(p) ** 0.3) * (1 + self.params.tech_gain * p.tech)
                * p.luck)

    def _plan_own_work(self, adults, s):
        """Satisficing: work the land only until the household store is comfortable."""
        mult = C.LAND_MULT[s] * (self.weather if s != 3 else 1.0)
        self._mult = mult
        for p in adults:
            p.hours["care"] = self._care(p)
            avail = C.AWAKE - C.MIN_LEISURE - p.hours["care"]
            p._avail = avail
            if not p.plots or mult <= 0:
                continue
            need = self.need(p)
            target = 2.2 * need
            want = max(0.0, target - p.food + need * 0.5)
            # debts must be serviced in cash, and cash comes from selling food
            want += 0.12 * sum(d.principal for d in p.debts) / max(self.price, 0.3)
            want += 1.5 * p.cash_need / max(self.price, 0.3)   # earn cash for bought goods
            k = self._land_coef(p) * mult
            if k <= 0:
                continue
            h = (want / k) ** (1 / C.HOURS_EXP) if want > 0 else 0.0
            p.hours["land"] = clamp(h, 0.0, avail)

    def _hire(self, adults, s):
        """Owners buy hours while the marginal product beats the wage; the landless sell."""
        mult = self._mult
        P, D = self.params, self.dials
        seekers = [p for p in adults if self.area(p) < 0.5
                   or any(d.late > 0 for d in p.debts)]
        share = len(seekers) / max(1, len(adults))
        tight = clamp(1.3 - 0.8 * share / 0.3, 0.7, 1.3)
        self.wage_rate = self.price * 0.18 * tight
        if mult <= 0 or not seekers:
            return
        self.rng.shuffle(seekers)
        employers = [p for p in adults if p.plots and self.area(p) >= 0.8 and p.cash > 2]
        self.rng.shuffle(employers)
        pool = list(seekers)
        for o in employers:
            if not pool:
                break
            h = min(o.h_emp, D.hours_cap)
            wage_s = self.wage_rate * h
            coef = self._land_coef(o)
            H = o.hours["land"]
            n = 0
            while pool and o.cash >= wage_s and n < 40:
                dy = coef * mult * ((H + h) ** C.HOURS_EXP - H ** C.HOURS_EXP)
                if self.price * dy < wage_s * 1.15:
                    break
                w = pool.pop()
                if w is o:
                    continue
                hw = min(h, C.AWAKE - 2.0 - w.hours["care"])
                self.pay(o, w, wage_s, "wages")
                self.flows["wages"] += wage_s
                w.hours["wage"] = hw
                w.hours["land"] = min(w.hours["land"], max(0.0, w._avail - hw))
                w.employer = o.id
                o.hired.append(w.id)
                o.hired_days += hw * 90 / 16
                H += hw
                n += 1
                if w.income_by["wages"] == wage_s:
                    w.log(self.t, f"Took wage work for {o.name} ({hw:.0f}h/day).")
            o._H_total = H

    def _produce(self, adults, s):
        mult = self._mult
        throughput = 0.0
        for p in adults:
            if not p.plots:
                continue
            H = getattr(p, "_H_total", None)
            if H is None or H < p.hours["land"]:
                H = p.hours["land"]
            p._H_total = None
            if mult <= 0 or H <= 0:
                continue
            k = self._land_coef(p) * mult
            Y = k * H ** C.HOURS_EXP
            p.food += Y
            self.flows["produced"] += Y
            self.flows["land_output"] += Y
            if p.hired:
                y_own = k * max(p.hours["land"], 1e-9) ** C.HOURS_EXP
                wage_paid = self.wage_rate * min(p.h_emp, self.dials.hours_cap) * len(p.hired)
                p.last_margin = (self.price * (Y - y_own) - wage_paid) / max(wage_paid, 1e-9)
            throughput += p.tech * Y
            for pid in p.plots:
                pl = self.plots[pid]
                pl.soil = clamp(pl.soil - 0.0007 * (H ** C.HOURS_EXP) * (1 + 0.4 * p.tech)
                                / max(pl.area, 0.3) / max(len(p.plots), 1) + 0.0025 * (1 - pl.soil),
                                0.15, 1.0)
        self.flows["throughput"] = throughput

    def _forage(self, adults, s):
        fm = C.FORAGE_MULT[s]
        hours_total = 0.0
        for p in adults:
            need = self.need(p)
            gap = need * 1.05 - p.food
            used = p.hours["land"] + p.hours["wage"]
            left = max(0.0, p._avail - used)
            if p.hours["wage"] > 0:
                left = max(0.0, C.AWAKE - 2.0 - p.hours["care"] - used)
            if gap <= 0 or left <= 0:
                continue
            k = C.FORAGE_A * self.commons * fm
            h = clamp((gap / k) ** (1 / C.HOURS_EXP), 0, left) if k > 0 else 0
            p.hours["forage"] = h
            y = k * h ** C.HOURS_EXP
            p.food += y
            self.flows["produced"] += y
            self.flows["forage_output"] += y
            hours_total += h
        self.flows["forage_hours"] = hours_total

    def _free_time(self, adults):
        for p in adults:
            h = p.hours
            free = max(0.0, C.AWAKE - h["care"] - h["land"] - h["wage"] - h["forage"])
            h["community"] = 0.5 * free
            h["leisure"] = 0.5 * free

    def _mutual_aid(self, adults):
        for p in adults:
            deficit = self.need(p) - p.food
            if deficit <= 0 or not p.ties:
                continue
            for qid, w in sorted(p.ties.items(), key=lambda kv: -kv[1]):
                q = self.persons.get(qid)
                if q is None or not q.alive or not q.is_adult():
                    continue
                spare = q.food - 2.0 * self.need(q)
                if spare <= 0:
                    continue
                if self.rng.random() < w * (0.4 + 0.6 * q.know["mutual_aid"]):
                    g = min(deficit, 0.5 * spare)
                    q.food -= g
                    p.food += g
                    deficit -= g
                    self.flows["gifts"] += g
                    p.ties[qid] = min(1.0, w + 0.05)
                    q.ties[p.id] = min(1.0, q.ties.get(p.id, 0) + 0.05)
                    if deficit <= 0:
                        break

    def _borrow(self, adults):
        P, D = self.params, self.dials
        lenders = sorted([p for p in adults if p.cash > 28], key=lambda p: -p.cash)[:8]
        if not lenders:
            return
        for p in adults:
            deficit = self.need(p) - p.food
            cost = deficit * self.price * 1.15
            if deficit <= 0 or p.cash >= cost:
                continue
            ask = cost - p.cash
            collateral = self.land_value(p) + (3 * self.wage_rate * p.hours["wage"] if p.hours["wage"] else 0)
            existing = sum(d.principal for d in p.debts)
            if existing + ask > 0.6 * collateral:
                continue
            for L in lenders:
                if L is p or L.cash - 15 < ask:
                    continue
                self.pay(L, p, ask, "loan")
                p.debts.append(Debt(L.id, ask, self.t))
                self.flows["loans"] += ask
                p.log(self.t, f"Borrowed {ask:.1f} from {L.name} after a short harvest.")
                break

    def _market(self, adults):
        P = self.params
        sellers, buyers = [], []
        S = D = 0.0
        for p in adults:
            need = self.need(p)
            surplus = (p.food - 2.2 * need) * clamp(self.price / 0.8, 0.0, 1.0) ** 2
            if surplus > 0.05:
                sellers.append((p, surplus))
                S += surplus
            deficit = need - p.food
            if deficit > 0 and p.cash > 0:
                q = min(deficit, p.cash / max(self.price, 1e-6))
                buyers.append((p, q))
                D += q
        q_tot = min(S, D)
        if q_tot > 0:
            for p, q in buyers:
                amt = q * q_tot / D
                p.food += amt
            for p, sur in sellers:
                amt = sur * q_tot / S
                p.food -= amt
            # pay: buyers pay sellers pro-rata, in cash
            for p, q in buyers:
                cost = q * q_tot / D * self.price
                p.cash -= cost
                self.flows["market_sales"] += cost
                for sp, sur in sellers:
                    share = (sur * q_tot / S) / q_tot
                    sp.cash += cost * share
                    sp.income_by["food sales"] += cost * share
                    sp.income_from[p.id] += cost * share
        S_left = S - q_tot
        if self.merchant_active and S_left > 0:
            pex = P.export_price
            cash_cap = self.outside_cash / pex
            qx = min(S_left, cash_cap)
            if qx > 0:
                for p, sur in sellers:
                    amt = sur * (1 - q_tot / S) * qx / S_left if S > 0 else 0
                    p.food -= amt
                    self.pay("outside", p, amt * pex, "exports")
                self.flows["exported"] += qx
                self.flows["market_sales"] += qx * pex
        # price discovery
        ratio = (D - S) / (D + S + 1.0)
        self.price = clamp(self.price * (1 + 0.25 * ratio), 0.4, 4.0)
        if self.merchant_active:
            self.price = max(self.price, 0.8 * P.export_price)
        self.flows["demand"], self.flows["supply"] = D, S

    def _consume(self):
        for p in self.adults():
            need = self.need(p)
            eat = min(p.food, need)
            p.food -= eat
            self.flows["eaten"] += eat
            p.nutrition = eat / need
            for c in self.kids(p):
                c.nutrition = p.nutrition

    def _cloth(self, adults):
        """Commodity substitution: as mechanised cloth appears, households that no longer
        weave must buy it for cash.  The cash flows to owners of machinery in proportion to
        their machinery; households that cannot pay go without (and suffer)."""
        owners = [p for p in adults if p.tech > 0]
        tot = sum(p.tech for p in owners)
        sub = min(1.0, tot / (len(adults) * 0.15 + 1))
        for p in adults:
            due = 0.4 * (1 - p.know["weaving"] * 0.8) * sub * (1 + 0.5 * len(self.kids(p)))
            p.cash_need = due
            p.cloth_gap = 0.0
            if due <= 0 or not owners:
                continue
            paid = min(due, max(0.0, p.cash))
            if paid > 0:
                for o in owners:
                    if o is not p:
                        self.pay(p, o, paid * o.tech / tot, "cloth sales")
                self.flows["market_sales"] += paid
            if due - paid > 0.02:
                p.cloth_gap = (due - paid) / due

    def _tax(self, adults):
        P = self.params
        for p in adults:
            due = P.tax_per_adult
            paid = min(due, max(0.0, p.cash))
            self.pay(p, "outside", paid, "tax")
            self.flows["tax"] += paid
            short = due - paid
            if short > 0.01:
                d = next((d for d in p.debts if d.lender == -1), None)
                if d is None:
                    p.debts.append(Debt(-1, short, self.t))
                    p.log(self.t, "Fell into tax arrears to the state.")
                else:
                    d.principal += short

    def _debts(self):
        P, D = self.params, self.dials
        for p in list(self.adults()):
            for d in list(p.debts):
                rate = min(D.usury_cap, P.base_interest)
                d.principal *= 1 + rate
                lender = self.persons.get(d.lender) if d.lender >= 0 else "outside"
                if lender != "outside" and (lender is None or not lender.alive):
                    p.debts.remove(d)  # claim extinguished with the lender (heirs handled at death)
                    continue
                payable = max(0.0, p.cash - 3.0)
                pay = min(d.principal, 0.5 * payable)
                if pay > 0:
                    self.pay(p, lender, pay, "interest & repayment")
                    d.principal -= pay
                    self.flows["debt_service"] += pay
                if pay < d.principal * rate * 0.99:
                    d.late += 1
                else:
                    d.late = max(0, d.late - 1)
                if d.principal < 0.05:
                    p.debts.remove(d)
                    continue
                if d.late >= 4:
                    if D.land_alienable and p.plots:
                        self._foreclose(p, d, lender)
                    elif d.late >= 8:
                        p.debts.remove(d)  # customary jubilee: the claim lapses
                        if lender != "outside":
                            lender.log(self.t, f"Wrote off {d.principal:.1f} owed by {p.name} (customary jubilee).")

    def _foreclose(self, p, d, lender):
        pid = max(p.plots, key=lambda i: self.plots[i].area)
        pl = self.plots[pid]
        value = pl.area * pl.fert * 40.0 * self.price
        if lender == "outside":
            buyers = [q for q in self.adults() if q is not p and q.cash > value]
            if not buyers:
                p.plots.remove(pid)
                pl.owner = None
                p.debts.remove(d)
                p.log(self.t, "State seized the plot for tax arrears; it fell vacant.")
                return
            buyer = max(buyers, key=lambda q: q.cash)
            self.pay(buyer, "outside", min(value, d.principal), "land purchase")
            surplus = value - d.principal
            if surplus > 0:
                self.pay(buyer, p, surplus, "land sale")
            lender_name = "the state"
        else:
            buyer = lender
            surplus = value - d.principal
            if surplus > 0:
                self.pay(buyer, p, min(surplus, max(buyer.cash, 0)), "land sale")
            lender_name = lender.name
        p.plots.remove(pid)
        pl.owner = buyer.id
        buyer.plots.append(pid)
        p.debts.remove(d)
        p.ties[buyer.id] = 0.0
        buyer.ties[p.id] = 0.0
        p.grudges[buyer.id if lender != "outside" else -1] += 1
        self.flows["foreclosures"] += 1
        self.cause_counts["foreclosure"] += 1
        p.log(self.t, f"Lost a plot to {lender_name}: debt could not be repaid.")
        if lender != "outside":
            lender.log(self.t, f"Took a plot from {p.name} for an unpaid debt.")
        self.chron(f"{p.name}'s plot passes to {buyer.name} (foreclosure).")

    def _relief(self):
        D = self.dials
        if D.relief_levy > 0:
            for p in self.adults():
                excess = p.cash - 80
                if excess > 0:
                    self.pay(p, "relief", excess * D.relief_levy, "levy")
        if self.relief_pool > 0.5:
            needy = [p for p in self.adults() if p.nutrition < 0.8]
            if needy:
                share = self.relief_pool / len(needy)
                for p in needy:
                    self.pay("relief", p, share, "poor relief")

    def _invest_and_ratchet(self):
        P, D = self.params, self.dials
        owners = [p for p in self.adults() if p.hired]
        if not owners:
            return
        avg_tech = sum(p.tech for p in self.adults()) / max(1, len(self.adults()))
        artisans = sorted(self.adults(), key=lambda q: -q.know["weaving"])[:12]
        for o in owners:
            if o.last_margin < 0.3 and o.h_emp < D.hours_cap:
                o.h_emp = min(D.hours_cap, o.h_emp + 0.5)  # the ratchet
            o.h_emp = min(o.h_emp, D.hours_cap)
            lag = max(0.0, avg_tech - o.tech) / (avg_tech + 1)
            cost = P.tech_cost * (1 + 0.15 * o.tech)       # each further level costs more
            if o.cash > cost * 1.3 and o.last_margin > 0 and self.rng.random() < 0.08 + 0.5 * lag:
                for a in self.rng.sample(artisans, min(3, len(artisans))):
                    if a is not o:
                        self.pay(o, a, cost / 3, "craft work")
                self.flows["investment"] += cost
                o.tech += 1
                o.log(self.t, f"Invested in new tools/machinery (level {o.tech}).")

    def _social_and_culture(self, adults):
        for p in adults:
            ch = p.hours["community"]
            f = min(1.0, ch / 3.5)
            if p.ties and ch > 0.5:
                for qid in self.rng.sample(list(p.ties), min(3, len(p.ties))):
                    p.ties[qid] = min(1.0, p.ties[qid] + 0.015 * ch)
                    q = self.persons.get(qid)
                    if q and q.alive:
                        q.ties[p.id] = min(1.0, q.ties.get(p.id, 0) + 0.01 * ch)
            if ch > 2.0 and self.rng.random() < 0.1:
                cand = [q for q in adults if q is not p and abs(q.x - p.x) + abs(q.y - p.y) <= 4]
                if cand:
                    q = self.rng.choice(cand)
                    p.ties[q.id] = max(p.ties.get(q.id, 0), 0.15)
                    q.ties[p.id] = max(q.ties.get(p.id, 0), 0.15)
            for qid in list(p.ties):
                p.ties[qid] *= 0.99
                if p.ties[qid] < 0.05:
                    del p.ties[qid]
        tot_tech = sum(p.tech for p in adults)
        sub = min(1.0, tot_tech / (len(adults) * 0.3 + 1))
        mean = {k: sum(p.know[k] for p in adults) / max(1, len(adults)) for k in C.PRACTICES}
        for p in adults:
            f = min(1.0, p.hours["community"] / 5.0)
            for k in C.PRACTICES:
                v = p.know[k]
                v += 0.02 * f * (1 - v) + 0.01 * (mean[k] - v) * f - 0.003 - 0.015 * (1 - f)
                if k == "weaving":
                    v -= 0.012 * sub * (1 - 0.5 * f)
                p.know[k] = clamp(v, 0.0, 1.0)

    def _bodies(self):
        for p in self.adults():
            n = p.nutrition
            work = p.hours["land"] + p.hours["wage"] + p.hours["forage"]
            rest = min(1.0, 0.4 + (p.hours["leisure"] + p.hours["community"]) / 8.0)
            dh = 0.08 * (n - 0.9) if n < 0.9 else 0.03 * rest * (1 - p.health)
            dh -= 0.0035 * max(0.0, work - 9.0)
            dh -= 0.02 * self.pollution
            dh -= 0.004 * p.cloth_gap          # going without cloth / fuel / shelter
            dh -= 0.0002 * max(0.0, p.year_age() - 45)
            p.health = clamp(p.health + dh, 0.0, 1.0)
            autonomy = 1.0 if self.area(p) >= 0.8 and not p.hours["wage"] else (0.5 if p.plots else 0.15)
            security = min(1.0, p.food / (2.0 * self.need(p)) + 0.3 * (p.cash > 10))
            ties = min(1.0, sum(p.ties.values()) / 3.0)
            leisure = min(1.0, (p.hours["leisure"] + p.hours["community"]) / 6.0)
            culture = sum(p.know.values()) / len(p.know)
            w = 0.3 * autonomy + 0.25 * security + 0.2 * ties + 0.15 * leisure + 0.1 * culture
            p.wellbeing += 0.3 * (w * p.health ** 0.5 - p.wellbeing)
        for p in self.alive():
            if not p.is_adult():
                n = p.nutrition
                dh = 0.08 * (n - 0.9) if n < 0.9 else 0.02 * (1 - p.health)
                p.health = clamp(p.health + dh - 0.05 * self.pollution, 0.0, 1.0)

    def _ecology(self):
        K = self.commons
        H = self.flows["forage_hours"]
        K += 0.10 * K * (1 - K) + 0.01 * (1 - K) - 0.00015 * H * K
        self.commons = clamp(K, 0.02, 1.0)
        self.pollution = clamp(self.pollution * 0.95 + 0.00006 * self.flows["throughput"] * (1 - self.pollution), 0.0, 1.0)

    def _demography(self):
        P = self.params
        rng = self.rng
        for p in self.alive():
            p.age += 1
        # deaths
        for p in list(self.alive()):
            ay = p.year_age()
            risk = 0.0008 + 0.0005 * math.exp((ay - 40) / 12.0)
            if ay < 5:
                risk += 0.004
            if p.nutrition < 0.5:
                risk += 0.06 * (0.5 - p.nutrition)
            risk += 0.05 * max(0.0, 0.35 - p.health)
            if rng.random() < risk:
                cause = ("starvation" if p.nutrition < 0.5 else "exhaustion & disease" if p.health < 0.4
                         else "old age" if ay > 55 else "misfortune")
                self._die(p, cause)
        # births & maturation
        # density dependence: crowded valleys have fewer births, emptied ones more
        dd = clamp(1.6 - 0.8 * len(self.alive()) / (P.n_start * 1.2), 0.6, 1.5)
        for p in list(self.adults()):
            if 17 * C.SEASONS <= p.age <= 40 * C.SEASONS and len(self.kids(p)) < 5:
                pr = 0.026 * dd * min(1.0, p.food / (self.need(p) + 0.01) + 0.3) * (0.6 + 0.4 * p.health)
                if rng.random() < pr:
                    c = self._new_person(0, p.id, p.x, p.y)
                    f = 0.6 + 0.4 * min(1.0, p.hours["community"] / 2.5)
                    c.know = {k: v * f for k, v in p.know.items()}
                    c.nutrition = p.nutrition
                    p.dependents.append(c.id)
                    self.flows["births"] += 1
        for c in [x for x in self.alive() if x.age == C.ADULT_AGE]:
            self._mature(c)

    def _mature(self, c):
        P = self.params
        g = self.persons.get(c.guardian)
        c.nutrition = 1.0
        if g and c.id in g.dependents:
            g.dependents.remove(c.id)
        if g and g.alive:
            c.ties[g.id] = 1.0
            g.ties[c.id] = 1.0
            for qid, w in sorted(g.ties.items(), key=lambda kv: -kv[1])[:3]:
                if qid != c.id:
                    c.ties[qid] = 0.5 * w
            gift = min(g.cash * 0.2, 10.0)
            self.pay(g, c, gift, "family gift")
            for qid, n in g.grudges.items():
                c.grudges[qid] = n
            if self.area(g) > 1.3 and g.plots:
                pid = max(g.plots, key=lambda i: self.plots[i].area)
                big = self.plots[pid]
                half = big.area / 2
                if half >= 0.45:
                    big.area = half
                    new = self._new_plot(big.x, big.y, half, big.fert, c.id)
                    new.soil = big.soil
                    c.plots.append(new.id)
                    c.log(self.t, f"Came of age with half of {g.name}'s plot.")
                    return
        if self.commons > 0.45 and self.rng.random() < 0.6:
            x = clamp(c.x + self.rng.randint(-2, 2), 0, P.grid_w - 1)
            y = clamp(c.y + self.rng.randint(-2, 2), 0, P.grid_h - 1)
            new = self._new_plot(int(x), int(y), 0.6, self.rng.uniform(0.6, 1.0), c.id)
            c.plots.append(new.id)
            self.commons = max(0.02, self.commons - 0.02)
            c.log(self.t, "Cleared a new plot from the commons.")
        else:
            c.log(self.t, "Came of age with no land.")

    def _die(self, p, cause):
        p.alive = False
        p.died = self.t
        p.cause = cause
        self.cause_counts[cause] += 1
        if p.is_adult():
            self.death_ages.append((self.t, p.year_age()))   # adult lifespan: child deaths excluded
        p.log(self.t, f"Died aged {p.year_age():.0f} of {cause}.")
        adults = [q for q in self.adults() if q is not p]
        kids = self.kids(p)
        heirs = [c for c in kids if c.is_adult()]
        for c in list(p.dependents):
            pass
        # children under 15 move to the closest tie (or a random adult)
        minors = [c for c in kids if not c.is_adult()]
        if minors and adults:
            carer = None
            for qid, w in sorted(p.ties.items(), key=lambda kv: -kv[1]):
                q = self.persons.get(qid)
                if q and q.alive and q.is_adult():
                    carer = q
                    break
            carer = carer or self.rng.choice(adults)
            for c in minors:
                c.guardian = carer.id
                carer.dependents.append(c.id)
        # adult kids are heirs (tracked via guardian link on adults too)
        heirs = [q for q in adults if q.guardian == p.id]
        if not heirs:
            heirs = [self.rng.choice(adults)] if adults else []
        if heirs:
            share = 1.0 / len(heirs)
            cash, food = p.cash, p.food
            for h in heirs:
                h.cash += cash * share
                h.food += food * share
                if cash > 0:
                    h.income_by["inheritance"] += cash * share
                    h.income_from[p.id] += cash * share
            p.cash = p.food = 0.0
            plots = list(p.plots)
            for i, pid in enumerate(plots):
                h = heirs[i % len(heirs)]
                self.plots[pid].owner = h.id
                h.plots.append(pid)
            p.plots = []
            heirs[0].tech += p.tech            # machinery is inherited with the estate
            heirs[0].h_emp = max(heirs[0].h_emp, p.h_emp)
            p.tech = 0
            for d in p.debts:
                h = heirs[0]
                h.debts.append(d)
            p.debts = []
            for q, n in p.grudges.items():
                for h in heirs:
                    h.grudges[q] += n
        else:
            for pid in p.plots:
                self.plots[pid].owner = None
            p.plots = []
        for q in self.alive():
            q.ties.pop(p.id, None)

    # ------------------------------------------------------------------ audit & metrics
    def audit(self):
        m = self.total_money()
        if abs(m - self.money0) > 1e-6 * max(1.0, self.money0):
            raise AssertionError(f"MONEY LEAK t={self.t}: {m} vs {self.money0}")
        f = self.total_food()
        expect = (self.food_prev + self.flows["produced"] - self.flows["eaten"]
                  - self.flows["spoiled"] - self.flows["exported"])
        # food of the dead is passed to heirs (conserved) so only exports/eaten/spoiled leave
        if abs(f - expect) > 1e-6 * max(1.0, f) + 1e-6:
            raise AssertionError(f"FOOD LEAK t={self.t}: {f} vs {expect}")
        self.food_prev = f

    @staticmethod
    def _gini(xs):
        xs = sorted(max(0.0, x) for x in xs)
        n, s = len(xs), sum(xs)
        if n == 0 or s <= 0:
            return 0.0
        return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(xs)) / (n * s)

    @staticmethod
    def _median(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else 0.0

    def record_metrics(self):
        ad = self.adults()
        al = self.alive()
        n = max(1, len(ad))
        S = self.series
        f = self.flows
        gdp = f["market_sales"] + f["wages"] + f["investment"]
        S["t"].append(self.t)
        S["pop"].append(len(al))
        S["gdp"].append(gdp / max(1, len(al)))
        S["output"].append(f["produced"] / max(1, len(al)))
        S["capital"].append(sum(p.tech for p in ad))
        S["price"].append(self.price)
        S["wage"].append(self.wage_rate)
        S["med_health"].append(self._median([p.health for p in ad]))
        S["wellbeing"].append(sum(p.wellbeing for p in ad) / n)
        work = [p.hours["land"] + p.hours["wage"] + p.hours["forage"] for p in ad]
        S["work_hours"].append(sum(work) / n)
        S["free_hours"].append(sum(p.hours["leisure"] + p.hours["community"] for p in ad) / n)
        recent = [a for (t, a) in self.death_ages if t > self.t - 160]
        S["lifespan"].append(sum(recent) / len(recent) if recent else (S["lifespan"][-1] if S["lifespan"] else 45.0))
        S["ties"].append(sum(sum(p.ties.values()) for p in ad) / n)
        S["culture"].append(sum(sum(p.know.values()) / len(p.know) for p in ad) / n)
        S["commons"].append(self.commons)
        S["pollution"].append(self.pollution)
        S["landless"].append(sum(1 for p in ad if not p.plots) / n)
        S["in_debt"].append(sum(1 for p in ad if p.debts) / n)
        S["hunger"].append(sum(1 for p in ad if p.nutrition < 0.8) / n)
        S["land_gini"].append(self._gini([self.area(p) for p in ad]))
        S["wealth_gini"].append(self._gini([p.cash + self.land_value(p) - sum(d.principal for d in p.debts) for p in ad]))
        S["wage_labour"].append(sum(1 for p in ad if p.hours["wage"] > 0) / n)
        emp = [p.h_emp for p in ad if p.hired]
        S["emp_hours"].append(sum(emp) / len(emp) if emp else 0.0)
        S["foreclosures"].append(f["foreclosures"])
        S["weather"].append(self.weather)

    # ------------------------------------------------------------------ views for the UI
    def classify(self, p):
        a = self.area(p)
        if p.hired:
            return "employer"
        if p.hours["wage"] > 0:
            return "wage"
        if not p.plots:
            return "landless"
        return "owner" if a >= 1.5 else "smallholder"

    def state(self, tail=None):
        S = self.series
        series = {k: (v[-tail:] if tail else v) for k, v in S.items()}
        people = [
            [p.id, p.x, p.y, round(p.health, 2), round(p.wellbeing, 2), round(self.area(p), 2),
             round(p.cash, 1), self.classify(p), 1 if p.is_adult() else 0]
            for p in self.alive()
        ]
        return {
            "t": self.t, "year": self.year, "season": C.SEASON_NAMES[self.season],
            "params": {"seed": self.params.seed, "preset": self.params.preset},
            "dials": self.dials.to_dict(), "series": series, "people": people,
            "chronicle": self.chronicle[-12:], "presets": {k: v["desc"] for k, v in C.PRESETS.items()},
            "money": round(self.total_money(), 3), "weather": round(self.weather, 2),
            "causes": dict(self.cause_counts),
        }

    def person(self, pid):
        p = self.persons.get(pid)
        if not p:
            return None
        h = p.hours
        employees = [self.persons[i] for i in p.hired if i in self.persons]
        worker_cost = (sum(e.health for e in employees) / len(employees)) if employees else None
        top_from = sorted(p.income_from.items(), key=lambda kv: -kv[1])[:4]
        names = {-1: "outside state/merchants", -2: "relief fund"}
        return {
            "id": p.id, "name": p.name, "age": round(p.year_age(), 1), "alive": p.alive,
            "class": self.classify(p), "health": round(p.health, 2), "wellbeing": round(p.wellbeing, 2),
            "cash": round(p.cash, 1), "food": round(p.food, 2), "area": round(self.area(p), 2),
            "dependents": len(self.kids(p)), "tech": p.tech,
            "hours": {k: round(v, 1) for k, v in h.items()},
            "ties": len(p.ties), "tie_strength": round(sum(p.ties.values()), 2),
            "know": {k: round(v, 2) for k, v in p.know.items()},
            "debt": round(sum(d.principal for d in p.debts), 1),
            "grudges": len(p.grudges),
            "events": [[t, txt] for t, txt in p.events[-25:]],
            "trail": {
                "income_by": {k: round(v, 1) for k, v in sorted(p.income_by.items(), key=lambda kv: -kv[1])},
                "top_sources": [[names.get(i, self.persons[i].name if i in self.persons else str(i)), round(v, 1)]
                                for i, v in top_from],
                "hired_person_days": round(p.hired_days, 0),
                "employees_now": len(employees), "employees_mean_health": None if worker_cost is None else round(worker_cost, 2),
                "employer_hours": round(p.h_emp, 1) if p.hired else None,
            },
        }
