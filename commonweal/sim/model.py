"""model.py — plain data holders: Plot, Debt, Person."""
from collections import defaultdict
from . import config as C


class Plot:
    __slots__ = ("id", "x", "y", "area", "fert", "soil", "owner")

    def __init__(self, id, x, y, area, fert, owner=None):
        self.id, self.x, self.y = id, x, y
        self.area, self.fert, self.soil = area, fert, 1.0
        self.owner = owner

    def eff(self):
        return self.area * self.fert * self.soil


class Debt:
    __slots__ = ("lender", "principal", "late", "born")

    def __init__(self, lender, principal, born):
        self.lender = lender          # person id, or -1 for the outside state
        self.principal = principal
        self.late = 0
        self.born = born


class Person:
    def __init__(self, id, name, age, guardian, born, x, y):
        self.id, self.name, self.age = id, name, age
        self.guardian = guardian      # parent / carer id (None for founders)
        self.born = born
        self.x, self.y = x, y
        self.alive = True
        self.died = None
        self.cause = None
        self.cash = 0.0
        self.food = 0.0
        self.health = 1.0
        self.wellbeing = 0.7
        self.plots = []               # plot ids
        self.dependents = []          # child person ids
        self.debts = []               # Debt objects (as borrower)
        self.ties = {}                # person id -> weight
        self.know = {}                # practice -> 0..1
        self.grudges = defaultdict(int)  # person id -> count (inherited)
        self.tech = 0                 # owner's capital level
        self.h_emp = 8.0              # working day this owner imposes on hired labour
        self.employer = None
        self.hired = []
        self.hired_days = 0.0         # cumulative person-days of hired labour bought
        self.last_margin = 0.0
        self.nutrition = 1.0
        self.cash_need = 0.0
        self.cloth_gap = 0.0
        self.luck = 1.0               # this year's idiosyncratic harvest multiplier
        self.hours = dict(land=0.0, wage=0.0, forage=0.0, care=0.0, community=0.0, leisure=0.0)
        self.income_by = defaultdict(float)    # reason -> cash received (lifetime)
        self.income_from = defaultdict(float)  # source id -> cash received
        self.events = []

    # convenience -------------------------------------------------
    def log(self, t, text):
        self.events.append((t, text))
        if len(self.events) > 80:
            del self.events[:20]

    def year_age(self):
        return self.age / C.SEASONS

    def is_adult(self):
        return self.age >= C.ADULT_AGE
