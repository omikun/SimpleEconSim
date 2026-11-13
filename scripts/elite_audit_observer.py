"""Read-only observers for long-run elite audits; no policy or RNG changes."""
from collections import Counter, defaultdict
import gzip
import json
import sys
from pathlib import Path


def plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return {'type': type(value).__name__, 'id': getattr(value, 'id', None)}


class EliteAudit:
    def __init__(self, server, directory):
        self.server = server
        self.actors, self.locations, self.first_seen = {}, {}, {}
        self.events, self.decisions = [], []
        self.counts = Counter()
        self.files = {kind:gzip.open(directory / (kind + '.jsonl.gz'), 'wt', compresslevel=1)
                      for kind in ('decisions', 'economic_events', 'actors', 'statements', 'searches')}
        self.bank_currency = {}
        self.register(0)

    def write(self, kind, row):
        self.files[kind].write(json.dumps(plain(row), allow_nan=False, separators=(',', ':')) + '\n')

    def register(self, turn):
        for region in self.server.tiles:
            if region.bank is not None:
                self.bank_currency[id(region.bank)] = getattr(region.bank, 'home_currency', None) or region.home_currency
            for actor in region.agents:
                if actor.is_corporation or actor.is_lord or getattr(actor, 'company_owned', None) is not None:
                    self.actors[actor.id] = actor
                    self.locations[actor.id] = region
                    self.first_seen.setdefault(actor.id, turn)

    def view(self, actor, region):
        from labor_contract import preview_labor_agreement
        from goods import Goods
        currency = getattr(actor, 'home_currency', None) or region.home_currency
        debt, deposits = defaultdict(float), defaultdict(float)
        for loan in actor.loans:
            unit = self.bank_currency.get(id(loan.bank), currency)
            debt[unit] += max(0, loan.principle - loan.principle_paid)
        banks = {id(r.bank):r.bank for r in self.server.tiles if r.bank is not None}
        for key, bank in banks.items():
            amount = bank.deposits.get(actor, 0)
            if amount:
                deposits[self.bank_currency[key]] += amount
        workers = [w for w in actor.employees if w.alive and not w.is_striking and not w.in_revolt]
        payroll = sum(max(0, preview_labor_agreement(w, actor, self.server.turn).pay_rate) for w in workers)
        recipe = region.recipes.get(actor.output, {})
        required = max(0, recipe.get('numInput', 0)) * len(workers)
        held = actor.inv_get(recipe.get('input'), 0) if required else 0
        company = getattr(actor, 'company_owned', None)
        inventory = {g.name:actor.inv_get(g, 0) for g in Goods if actor.inv_get(g, 0)}
        return dict(id=actor.id, role=('corporation' if actor.is_corporation else 'lord' if actor.is_lord
                  else 'capitalist_owner' if company is not None else 'other_elite'),
            name=getattr(actor, 'company_name', None) or getattr(actor, 'display_name', None),
            tile=region.name, currency=currency, alive=actor.alive, cash=actor.cash,
            is_lord=actor.is_lord, is_corporation=actor.is_corporation,
            bank_debt_by_currency=dict(debt), deposits_by_currency=dict(deposits),
            liquid_home=actor.cash+deposits[currency], financial_home=actor.cash+deposits[currency]-debt[currency],
            wallets=dict(getattr(actor, 'wallets', {}) or {}),
            inventory=inventory, output=actor.output.name, employees=len(actor.employees),
            working_employees=len(workers), payroll=payroll, input_good=getattr(recipe.get('input'), 'name', None),
            nominal_input_gap=max(0, required-held), wage=actor.wage,
            wage_arrears=getattr(actor, 'wage_arrears_balance', 0),
            machinery=getattr(actor, 'machinery_level', 1), broken_machinery=getattr(actor, 'broken_machinery', 0),
            owner_id=getattr(getattr(actor, 'owner', None), 'id', None),
            company_id=getattr(company, 'id', None), company_alive=getattr(company, 'alive', None),
            estates=len(getattr(actor, 'frontier_estates', ())),
            first_seen=self.first_seen.get(actor.id, self.server.turn))

    def install(self):
        from economy import actor_accounts
        from economy.capitalist_planner import EliteCapitalistPlanner
        from economy import elite_plan_execution
        self.original_record = actor_accounts.record
        self.original_plan = EliteCapitalistPlanner.plan_and_execute_elite
        self.original_search = elite_plan_execution.search_firm
        audit = self
        def record(*args, **kwargs):
            event = audit.original_record(*args, **kwargs)
            audit.events.append(event)
            return event
        def plan(planner, actor, region, turn):
            before = audit.view(actor, region)
            result = audit.original_plan(planner, actor, region, turn)
            tracked = actor.is_corporation or actor.is_lord or getattr(actor, 'company_owned', None) is not None
            if tracked:
                audit.actors[actor.id], audit.locations[actor.id] = actor, region
                audit.first_seen.setdefault(actor.id, turn)
                role = audit.view(actor, region)['role']
                row = dict(turn=turn, actor_id=actor.id, role=role, before=before,
                           after=audit.view(actor, region), result=result)
                audit.decisions.append(row)
                audit.write('decisions', row)
                audit.counts[role + ':' + (result.get('action_taken') or 'do_nothing')] += 1
            return result
        def search(actor, region, turn):
            state, result, reason = audit.original_search(actor, region, turn)
            audit.write('searches', dict(turn=turn, actor_id=actor.id, tile=region.name,
                reason=reason, status=getattr(result, 'status', None),
                expanded=getattr(result, 'expanded', 0)))
            audit.counts['search:' + reason] += 1
            return state, result, reason
        self.aliases = []
        root = Path(__file__).resolve().parents[1]
        for module in tuple(sys.modules.values()):
            filename = getattr(module, '__file__', None)
            if module is sys.modules[__name__] or not filename or not Path(filename).resolve().is_relative_to(root):
                continue
            for key, value in tuple(vars(module).items()):
                if value is self.original_record:
                    self.aliases.append((module, key))
                    setattr(module, key, record)
        EliteCapitalistPlanner.plan_and_execute_elite = plan
        elite_plan_execution.search_firm = search

    def collect(self, turn):
        self.register(turn)
        present = {a.id for r in self.server.tiles for a in r.agents}
        snapshots = []
        for ident, actor in self.actors.items():
            row = self.view(actor, self.locations[ident])
            row.update(turn=turn, present=ident in present)
            snapshots.append(row)
            self.write('actors', row)
        for event in self.events:
            if event['payer_id'] in self.actors or event['recipient_id'] in self.actors:
                self.write('economic_events', event)
        seen = set()
        for region in self.server.tiles:
            for row in getattr(region, 'actor_turn_accounts', ()):
                key = row['turn'], row['actor_id']
                if row['turn'] == turn and row['actor_id'] in self.actors and key not in seen:
                    self.write('statements', row)
                    seen.add(key)
        self.events.clear()
        self.decisions.clear()
        return snapshots

    def close(self):
        from economy.capitalist_planner import EliteCapitalistPlanner
        from economy import elite_plan_execution
        for module, name in self.aliases:
            setattr(module, name, self.original_record)
        EliteCapitalistPlanner.plan_and_execute_elite = self.original_plan
        elite_plan_execution.search_firm = self.original_search
        for handle in self.files.values():
            handle.close()
