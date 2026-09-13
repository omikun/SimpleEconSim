"""
sim_server/sim_server.py — Authoritative Simulation Server implementation.
"""

import time
import random
import threading
from typing import Any, Dict, List, Optional

import sim_engine
from sim_world import build_world, GRID_ROWS, GRID_COLS
from hexmap import rectangular_hex_layout, hex_bbox
from worldview_camera import HEX_SIZE
import forex as fx
from goods import Goods
from buildings import BUILDING_RECIPES
from diplomacy import get_diplomacy, TreatyType
from sovereign_bonds import get_bond_market
from innovation import get_innovation_system, TECH_CATALOG
from worldview_map import NATION_COLORS
from world_names import assign_world_identities
from sim_server.protocol import CommandType, CommandMessage, ServerEvent


class SimServer:
    """Authoritative headless simulation server for REGNUM."""

    def __init__(self, seed: Optional[int] = None, terrain_seed: Optional[int] = None,
                 nation_seed: Optional[int] = None):
        self.seed = seed
        self.terrain_seed = terrain_seed if terrain_seed is not None else (seed if seed is not None else 4242)
        self.nation_seed = nation_seed if nation_seed is not None else random.randint(1, 999999)

        self.turn = 0
        self.playing = False
        self.turn_interval_sec = 0.150  # 150 ms per turn
        self.last_tick_time = time.time()

        self._lock = threading.RLock()
        self._ticker_events: List[Dict[str, Any]] = []
        self._subscribers = []
        self.player_nation_name = None
        self._nation_history = {}

        self.init_world()

    def init_world(self):
        """Build and initialize authoritative world state."""
        with self._lock:
            tiles, nations, _grid = build_world(
                seed=self.seed,
                terrain_seed=self.terrain_seed,
                nation_seed=self.nation_seed
            )
            assign_world_identities(tiles, nations, seed=self.nation_seed)

            self.tiles = tiles
            self.nations = nations
            self.currencies = [n.currency for n in nations if getattr(n, 'currency', None)]
            self.hex_size = HEX_SIZE
            self.layout = rectangular_hex_layout(GRID_ROWS, GRID_COLS)
            self.reverse_layout = {v: k for k, v in self.layout.items()}
            self.bbox = hex_bbox(self.layout, HEX_SIZE)

            self.by_name = {r.name: r for r in tiles}
            self.pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                                and r.neighbors.get(o.name) is not None
                                and not getattr(o, 'wilderness', False)
                                and not getattr(r, 'wilderness', False)]

            self.currency_totals = {c: fx.audit_currency_total(tiles, c) for c in self.currencies}
            self.violations = []
            self.turn = 0
            self.playing = False
            self._ticker_events.clear()
            self.player_nation_name = self.nations[0].name if self.nations else None
            self._nation_history = {}
            for n in self.nations:
                self._nation_history[n.name] = {
                    'turns': [], 'treasury': [], 'gdp': [], 'pop': [], 'food_price': [], 'unrest': []
                }
            self._record_history(0)

    def step(self) -> int:
        """Advance the simulation by exactly one turn."""
        with self._lock:
            self.turn += 1
            t = self.turn

            def on_event(turn, kind, text):
                color = (120, 240, 150)
                if kind in ('OVERRUN', 'DELAY'):
                    color = (245, 180, 80)
                elif kind in ('REVOLT', 'CANCEL', 'STRIKE'):
                    color = (240, 90, 90)
                self.push_ticker(turn, kind, text, color)

            violations, claim_events = sim_engine.step_turn(
                t=t,
                tiles=self.tiles,
                nations=self.nations,
                pair_orders=self.pair_orders,
                currencies=self.currencies,
                on_event=on_event,
                ledger_exempt=True
            )
            self.violations = violations

            if claim_events:
                self.pair_orders = [(r, o) for r in self.tiles for o in self.tiles if o is not r
                                    and r.neighbors.get(o.name) is not None
                                    and not getattr(o, 'wilderness', False)
                                    and not getattr(r, 'wilderness', False)]
                for ev in claim_events:
                    self.push_ticker(t, 'CLAIM', ev, (245, 210, 95))

            # Step Sovereign Bond Market (coupons, maturities, defaults)
            try:
                from sovereign_bonds import get_bond_market
                get_bond_market().step(self.get_world_dict(), t)
            except Exception:
                pass

            self._record_history(t)
            self._broadcast(ServerEvent.TURN_ADVANCED, {'turn': t})
            return t

    def _record_history(self, t: int):
        """Record macro time series for charting."""
        for n in self.nations:
            hist = self._nation_history.setdefault(n.name, {
                'turns': [], 'treasury': [], 'gdp': [], 'pop': [], 'food_price': [], 'unrest': []
            })
            tr = n.treasury()
            tiles = getattr(n, 'tiles', [])
            gdp = sum(r.gdp_log[-1] if getattr(r, 'gdp_log', None) else 0.0 for r in tiles)
            pop = sum(r.total_population[-1] if getattr(r, 'total_population', None) else len(r.agents) for r in tiles)
            avg_food = (sum(r.recipes[Goods.food]['price'] for r in tiles if Goods.food in getattr(r, 'recipes', {})) / max(1, len(tiles))) if tiles else 1.0
            unrest = (sum(r.protest_energy_log[-1] if getattr(r, 'protest_energy_log', None) else 0.0 for r in tiles) / max(1, len(tiles))) if tiles else 0.0

            hist['turns'].append(t)
            hist['treasury'].append(round(float(tr['total']), 1))
            hist['gdp'].append(round(float(gdp), 1))
            hist['pop'].append(int(pop))
            hist['food_price'].append(round(float(avg_food), 2))
            hist['unrest'].append(round(float(unrest), 2))

            if len(hist['turns']) > 50:
                for k in hist:
                    del hist[k][:len(hist[k]) - 50]

    def _calc_nation_macro(self, n) -> Dict[str, Any]:
        """Calculate complete macroeconomic indicators for a sovereign nation."""
        tiles = getattr(n, 'tiles', [])
        tr = n.treasury()
        tr_cur = tr['total']
        tr_food = tr['food']

        pop_cur = sum(r.total_population[-1] if getattr(r, 'total_population', None) else len(r.agents) for r in tiles)
        pop_prev = sum(r.total_population[-2] if getattr(r, 'total_population', None) and len(r.total_population) >= 2 else (r.total_population[-1] if getattr(r, 'total_population', None) else len(r.agents)) for r in tiles)
        d_pop = pop_cur - pop_prev

        gdp_cur = sum(r.gdp_log[-1] if getattr(r, 'gdp_log', None) else 0.0 for r in tiles)
        gdp_prev = sum(r.gdp_log[-2] if getattr(r, 'gdp_log', None) and len(r.gdp_log) >= 2 else (r.gdp_log[-1] if getattr(r, 'gdp_log', None) else 0.0) for r in tiles)
        d_gdp = gdp_cur - gdp_prev
        gdp_pc = gdp_cur / max(1, pop_cur)

        unrest_cur = (sum(r.protest_energy_log[-1] if getattr(r, 'protest_energy_log', None) else 0.0 for r in tiles) / max(1, len(tiles))) if tiles else 0.0
        unrest_prev = (sum(r.protest_energy_log[-2] if getattr(r, 'protest_energy_log', None) and len(r.protest_energy_log) >= 2 else (r.protest_energy_log[-1] if getattr(r, 'protest_energy_log', None) else 0.0) for r in tiles) / max(1, len(tiles))) if tiles else 0.0
        d_unrest = unrest_cur - unrest_prev

        stage = "Calm"
        if unrest_cur >= 9.5:
            stage = "Takeover"
        elif unrest_cur >= 8.0:
            stage = "Compromise"
        elif unrest_cur >= 6.5:
            stage = "Mob/Riot"
        elif unrest_cur >= 4.0:
            stage = "Protest"
        elif unrest_cur >= 2.0:
            stage = "Unrest"

        avg_gini = 0.0
        for r in tiles:
            for g in (Goods.food, Goods.wood, Goods.furniture):
                vals = sorted(a.cash for a in getattr(r, 'agents', []) if getattr(a, 'output', None) == g)
                if len(vals) > 5:
                    n_v = len(vals)
                    s_v = sum(vals)
                    if s_v > 0:
                        wsum = sum((i + 1) * v for i, v in enumerate(vals))
                        avg_gini = max(avg_gini, (2 * wsum) / (n_v * s_v) - (n_v + 1) / n_v)

        col_cur = (sum(r.cost_of_living for r in tiles) / max(1, len(tiles))) if tiles else 1.0

        exports_cur = sum(sum(v[-1] for v in r.export_val.values() if v) for r in tiles)
        imports_cur = sum(sum(v[-1] for v in r.import_val.values() if v) for r in tiles)
        trade_net = exports_cur - imports_cur
        exports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.export_val.values() if v) for r in tiles)
        imports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.import_val.values() if v) for r in tiles)
        trade_prev = exports_prev - imports_prev
        d_trade = trade_net - trade_prev

        # Treasury delta
        hist_tr = self._nation_history.get(n.name, {}).get('treasury', [])
        d_tr = (tr_cur - hist_tr[-1]) if hist_tr else 0.0

        tot_debt = sum(getattr(r.gov, 'debt', 0.0) for r in tiles)
        tot_garrison = sum(int(getattr(r, 'garrison', 0)) for r in tiles)
        standing_armies = len(getattr(n, 'armies', []))

        credit_rating = "BBB"
        market_yield = 0.0018
        try:
            from sovereign_bonds import get_bond_market
            market = get_bond_market()
            credit_rating, market_yield = market.isrb.get_market_yield(n, 20, self.get_world_dict())
        except Exception:
            pass

        rgb = NATION_COLORS.get(n.name, (80, 160, 240))
        flag_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        return {
            'name': n.name,
            'currency': getattr(n, 'currency', 'USD'),
            'regime_type': getattr(n, 'regime_type', 'Monarchy'),
            'flag_color': flag_hex,
            'treasury_cash': round(float(tr_cur), 1),
            'treasury_delta': round(float(d_tr), 1),
            'treasury_food': int(tr_food),
            'population': int(pop_cur),
            'population_delta': int(d_pop),
            'gdp': round(float(gdp_cur), 1),
            'gdp_delta': round(float(d_gdp), 1),
            'gdp_per_capita': round(float(gdp_pc), 1),
            'unrest_energy': round(float(unrest_cur), 2),
            'unrest_stage': stage,
            'unrest_delta': round(float(d_unrest), 2),
            'gini': round(float(avg_gini), 2),
            'gini_delta': 0.0,
            'cost_of_living': round(float(col_cur), 2),
            'exports': round(float(exports_cur), 1),
            'imports': round(float(imports_cur), 1),
            'trade_balance': round(float(trade_net), 1),
            'trade_delta': round(float(d_trade), 1),
            'tax_rate': float(getattr(n, 'tax_rate', 0.15)),
            'tariff_rate': float(getattr(n, 'tariff_rate', 0.10)),
            'max_workday_hours': float(getattr(n, 'max_workday_hours', 12.0)),
            'ten_hour_act': bool(getattr(n, 'ten_hour_act', False)),
            'credit_rating': str(credit_rating),
            'bond_yield': round(float(market_yield * 100), 2),
            'public_debt': round(float(tot_debt), 1),
            'garrison': int(tot_garrison),
            'standing_armies': int(standing_armies),
            'tiles_count': len(tiles),
        }

    def play(self):
        with self._lock:
            self.playing = True

    def pause(self):
        with self._lock:
            self.playing = False

    def toggle_play(self) -> bool:
        with self._lock:
            self.playing = not self.playing
            return self.playing

    def set_speed(self, interval_sec: float):
        with self._lock:
            self.turn_interval_sec = max(0.02, float(interval_sec))

    def push_ticker(self, turn: int, kind: str, text: str, color=(240, 240, 240), limit: int = 140):
        with self._lock:
            self._ticker_events.append({
                't': turn, 'kind': kind, 'text': text, 'color': color
            })
            if len(self._ticker_events) > limit:
                del self._ticker_events[:len(self._ticker_events) - limit]
            self._broadcast(ServerEvent.TICKER_MESSAGE, {
                't': turn, 'kind': kind, 'text': text, 'color': color
            })

    def execute_command(self, cmd: CommandMessage) -> Dict[str, Any]:
        """Dispatch and execute an authoritative player / AI command."""
        with self._lock:
            c_type = cmd.cmd_type
            p = cmd.payload

            if c_type == CommandType.STEP:
                new_turn = self.step()
                return {'success': True, 'turn': new_turn}

            elif c_type == CommandType.PLAY:
                self.play()
                return {'success': True, 'playing': True}

            elif c_type == CommandType.PAUSE:
                self.pause()
                return {'success': True, 'playing': False}

            elif c_type == CommandType.SET_SPEED:
                self.set_speed(p.get('interval', 0.150))
                return {'success': True, 'interval': self.turn_interval_sec}

            elif c_type == CommandType.RELOAD_WORLD:
                self.seed = p.get('seed', self.seed)
                self.terrain_seed = p.get('terrain_seed', self.terrain_seed)
                self.nation_seed = p.get('nation_seed', self.nation_seed)
                self.init_world()
                return {'success': True, 'turn': 0}

            elif c_type == CommandType.SELECT_NATION:
                target_nation = p.get('nation')
                if any(n.name == target_nation for n in self.nations):
                    self.player_nation_name = target_nation
                    self.push_ticker(self.turn, 'SOVEREIGN', f"Assumed sovereign control of {target_nation}.", (140, 210, 255))
                    return {'success': True, 'nation': target_nation}
                return {'success': False, 'error': f"Nation '{target_nation}' not found."}

            elif c_type == CommandType.BUILD_PROJECT:
                tile_name = p.get('tile')
                b_type = p.get('building')
                nat_name = p.get('nation') or self.player_nation_name
                tile = self.by_name.get(tile_name)
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not tile and nation and nation.tiles:
                    tile = nation.tiles[0]

                if not tile or not nation:
                    return {'success': False, 'error': "Invalid target territory or nation."}
                if b_type not in BUILDING_RECIPES:
                    return {'success': False, 'error': f"Unknown building recipe '{b_type}'."}

                from intents import BuildIntent
                intent = BuildIntent(nat_name, tile.name, b_type, submitted_turn=self.turn)
                nation.submit_intent(intent, self.turn)
                ok, msg = intent.execute(self.by_name, {n.name: n for n in self.nations}, self.turn)
                self.push_ticker(self.turn, 'BUILD', msg, (120, 240, 150) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.SET_POLICY:
                target_nation = next((n for n in self.nations if n.name == (p.get('nation') or self.player_nation_name)), None)
                if not target_nation:
                    return {'success': False, 'error': "Target nation not found"}
                key = p.get('key')
                val = p.get('val')

                if key in ('tax_rate', 'income_tax'):
                    val_f = float(val)
                    setattr(target_nation, 'tax_rate', val_f)
                    self.push_ticker(self.turn, 'POLICY', f"{target_nation.name} adjusted income tax to {val_f:.1%}.", (245, 210, 90))
                    return {'success': True, 'key': 'tax_rate', 'val': val_f, 'message': f"Income tax rate set to {val_f:.1%}"}

                elif key in ('tariff_rate', 'import_tariff'):
                    val_f = float(val)
                    setattr(target_nation, 'tariff_rate', val_f)
                    self.push_ticker(self.turn, 'POLICY', f"{target_nation.name} adjusted import tariffs to {val_f:.1%}.", (245, 210, 90))
                    return {'success': True, 'key': 'tariff_rate', 'val': val_f, 'message': f"Import tariff rate set to {val_f:.1%}"}

                elif key in ('workday', 'max_workday_hours'):
                    val_f = float(val)
                    target_nation.max_workday_hours = val_f
                    target_nation.ten_hour_act = (val_f <= 10.0)
                    for t in target_nation.tiles:
                        t.max_workday_hours = val_f
                        t.ten_hour_act = target_nation.ten_hour_act
                    self.push_ticker(self.turn, 'POLICY', f"{target_nation.name} regulated workday to {val_f:.1f} hours.", (140, 220, 160))
                    return {'success': True, 'key': 'workday', 'val': val_f, 'message': f"Max workday set to {val_f:.1f}h"}

                elif key == 'ten_hour_act':
                    val_b = bool(val)
                    target_nation.ten_hour_act = val_b
                    if val_b:
                        target_nation.max_workday_hours = min(10.0, getattr(target_nation, 'max_workday_hours', 12.0))
                    for t in target_nation.tiles:
                        t.ten_hour_act = val_b
                    self.push_ticker(self.turn, 'POLICY', f"{target_nation.name} {'enacted' if val_b else 'repealed'} the Ten-Hour Act.", (140, 220, 160))
                    return {'success': True, 'key': 'ten_hour_act', 'val': val_b, 'message': f"Ten-Hour Act {'enacted' if val_b else 'repealed'}"}

                elif key == 'granary_relief':
                    tr = target_nation.treasury()
                    if tr['food'] >= 20:
                        disbursed = min(50, tr['food'])
                        target_nation.government.agent.food -= disbursed
                        hungry_agents = [a for t in target_nation.tiles for a in t.agents if getattr(a, 'hungry_steps', 0) > 0]
                        fed_count = 0
                        for a in hungry_agents[:disbursed]:
                            a.hungry_steps = 0
                            a.food += 1.0
                            fed_count += 1
                        self.push_ticker(self.turn, 'RELIEF', f"{target_nation.name} opened state granaries, feeding {fed_count} citizens.", (100, 240, 160))
                        return {'success': True, 'message': f"Disbursed {disbursed} food units to relief granaries (fed {fed_count} citizens)."}
                    return {'success': False, 'error': "Insufficient emergency food in state granary."}

                elif key == 'law_enforcement':
                    if target_nation.government.agent.cash >= 50.0:
                        target_nation.government.agent.cash -= 50.0
                        for t in target_nation.tiles:
                            if t.protest_energy_log:
                                t.protest_energy_log[-1] = max(0.0, t.protest_energy_log[-1] - 1.5)
                        self.push_ticker(self.turn, 'ORDER', f"{target_nation.name} deployed public order decree (-1.5 protest energy).", (240, 200, 100))
                        return {'success': True, 'message': "Public order decree enacted (-1.5 protest energy across nation)."}
                    return {'success': False, 'error': "Insufficient treasury funds ($50 required)."}

                else:
                    if hasattr(target_nation, 'policies') and isinstance(target_nation.policies, dict):
                        target_nation.policies[key] = val
                    else:
                        setattr(target_nation, key, val)
                    return {'success': True, 'nation': target_nation.name, 'key': key, 'val': val}

            elif c_type == CommandType.DIPLOMATIC_ACTION:
                action = p.get('action')
                target = p.get('target')
                source = p.get('nation') or self.player_nation_name
                dip = get_diplomacy()

                if action == 'propose_trade':
                    ok, msg = dip.propose_treaty(source, target, TreatyType.TRADE_PACT, self.turn)
                elif action == 'propose_nap':
                    ok, msg = dip.propose_treaty(source, target, TreatyType.NON_AGGRESSION, self.turn)
                elif action == 'propose_alliance':
                    ok, msg = dip.propose_treaty(source, target, TreatyType.DEFENSIVE_ALLIANCE, self.turn)
                elif action == 'break_treaty':
                    t_type = p.get('treaty_type', TreatyType.TRADE_PACT)
                    res = dip.break_treaty(source, target, t_type, self.turn)
                    ok, msg = res['success'], res['message']
                elif action == 'declare_war':
                    events = dip.declare_war(source, target, self.turn, reason=p.get('reason', 'Geopolitical confrontation'))
                    ok, msg = True, f"War declared on {target} by {source}."
                else:
                    return {'success': False, 'error': f"Unknown diplomatic action '{action}'."}

                self.push_ticker(self.turn, 'DIPLO', msg, (100, 220, 255) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.SOVEREIGN_BOND:
                action = p.get('action')
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found"}
                market = get_bond_market()

                if action == 'issue_bond':
                    amount = float(p.get('amount', 500.0))
                    duration = int(p.get('duration', 20))
                    ok, msg, off = market.announce_bond_offering(nation, amount, duration, self.turn, world=self.get_world_dict())
                    if ok:
                        self.push_ticker(self.turn, 'BOND', f"{nation.name} announced ${amount:,.0f} sovereign bond tranche ({duration}t maturity).", (245, 210, 90))
                    return {'success': ok, 'message': msg}

                elif action == 'lobby_upgrade':
                    if nation.government.agent.cash >= 200.0:
                        nation.government.agent.cash -= 200.0
                        ok = market.isrb.lobby_upgrade(nation.name, cost=200.0)
                        msg = f"ISRB rating upgraded for {nation.name}." if ok else "Lobbying failed."
                        self.push_ticker(self.turn, 'ISRB', msg, (120, 240, 160) if ok else (240, 90, 90))
                        return {'success': ok, 'message': msg}
                    return {'success': False, 'error': "Insufficient treasury funds ($200 required)."}

                return {'success': False, 'error': f"Unknown bond action '{action}'."}

            elif c_type == CommandType.RESEARCH_TECH:
                action = p.get('action', 'pledge_prize')
                tech_id = p.get('tech_id')
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found"}
                innov = get_innovation_system()

                if action == 'pledge_prize':
                    amount = float(p.get('amount', 300.0))
                    ok = innov.post_royal_bounty(nation, tech_id, amount, self.turn)
                    tech_meta = TECH_CATALOG.get(tech_id)
                    tech_title = tech_meta.name if tech_meta else tech_id
                    msg = f"Pledged ${amount:,.0f} Royal Science Prize for '{tech_title}'." if ok else "Failed to pledge prize (insufficient treasury or already discovered)."
                    if ok:
                        self.push_ticker(self.turn, 'SCIENCE', msg, (180, 140, 255))
                    return {'success': ok, 'message': msg}

                return {'success': False, 'error': f"Unknown science action '{action}'."}

            elif c_type == CommandType.RECRUIT_UNIT:
                tile_name = p.get('tile')
                soldiers = int(p.get('soldiers', 15))
                wage = float(p.get('wage', 1.0))
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                tile = self.by_name.get(tile_name)
                if not tile or tile not in getattr(nation, 'tiles', []):
                    tile = nation.tiles[0] if nation and nation.tiles else None

                if not tile or not nation:
                    return {'success': False, 'error': "Territory or nation not found."}

                from intents import RecruitArmyIntent
                intent = RecruitArmyIntent(nation.name, tile.name, soldiers, wage=wage, submitted_turn=self.turn)
                ok, msg = intent.execute(self.by_name, {n.name: n for n in self.nations}, self.turn)
                if ok:
                    self.push_ticker(self.turn, 'MILITARY', msg, (240, 110, 110))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.ENCLOSE_PLOT:
                tile_name = p.get('tile') or p.get('region')
                plot_id = str(p.get('plot_id', ''))
                tile = self.by_name.get(tile_name)
                if not tile:
                    return {'success': False, 'error': f"Tile '{tile_name}' not found."}
                from enclosure import execute_enclosure
                ok, msg, _evs = execute_enclosure(tile, plot_id, self.turn)
                self.push_ticker(self.turn, 'ENCLOSURE', msg, (230, 140, 70) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.CADASTRE_TOGGLE_LAND_USE:
                tile_name = p.get('tile') or p.get('region')
                plot_id = str(p.get('plot_id', ''))
                tile = self.by_name.get(tile_name)
                if not tile or not hasattr(tile, 'tenure'):
                    return {'success': False, 'error': f"Tile '{tile_name}' has no cadastre tenure."}
                pl = tile.tenure.find_plot(plot_id)
                if not pl:
                    return {'success': False, 'error': f"Plot #{plot_id} not found."}
                new_t = p.get('production_type')
                if not new_t:
                    new_t = 'pasture' if getattr(pl, 'production_type', 'arable') != 'pasture' else 'arable'
                tile.tenure.convert_production_type(plot_id, new_t, self.turn)
                msg = f"Plot {pl.display_name} switched to {new_t.upper()} on {tile.name}."
                if new_t == 'pasture':
                    msg += " 75% tenants dispossessed."
                self.push_ticker(self.turn, 'LAND_USE', msg, (210, 180, 100))
                return {'success': True, 'message': msg, 'production_type': new_t}

            elif c_type == CommandType.RESTORE_COMMONS:
                tile_name = p.get('tile') or p.get('region')
                plot_id = str(p.get('plot_id', ''))
                tile = self.by_name.get(tile_name)
                if not tile or not hasattr(tile, 'tenure'):
                    return {'success': False, 'error': f"Tile '{tile_name}' has no cadastre tenure."}
                tile.tenure.revert_plot_to_commons(plot_id, self.turn)
                tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 0.25)
                msg = f"Plot #{plot_id} restored to Customary Commons on {tile.name}!"
                self.push_ticker(self.turn, 'COMMONS', msg, (120, 220, 140))
                return {'success': True, 'message': msg}

            elif c_type == CommandType.PROVINCE_DECREE:
                prov_name = p.get('province')
                decree = p.get('decree')
                province = next((pr for n in self.nations for pr in getattr(n, 'provinces', []) if pr.name == prov_name), None)
                if not province:
                    return {'success': False, 'error': f"Province '{prov_name}' not found."}
                pgov = getattr(province, 'gov', None)
                pcash = pgov.agent.cash if pgov and hasattr(pgov, 'agent') else 0.0

                if decree == 'pave_highway':
                    if pcash >= 120.0:
                        pgov.agent.cash -= 120.0
                        for t in province.tiles:
                            t.road_quality = min(1.0, getattr(t, 'road_quality', 0.5) + 0.25)
                        msg = f"Paved regional highway across {province.name} (trade speed +25%)."
                        self.push_ticker(self.turn, 'PROVINCE', msg, (120, 220, 150))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient provincial treasury ($120 required)."}

                elif decree == 'healthcare':
                    if pcash >= 150.0:
                        pgov.agent.cash -= 150.0
                        for t in province.tiles:
                            setattr(t, 'medical_spending_public', getattr(t, 'medical_spending_public', 0.0) + 25.0)
                        msg = f"Regional Healthcare Initiative launched across {province.name}."
                        self.push_ticker(self.turn, 'HEALTH', msg, (100, 240, 180))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient provincial treasury ($150 required)."}

                elif decree == 'equalization':
                    if pcash >= 200.0:
                        pgov.agent.cash -= 200.0
                        share = 200.0 / max(1, len(province.tiles))
                        for t in province.tiles:
                            if hasattr(t, 'gov') and hasattr(t.gov, 'agent'):
                                t.gov.agent.cash += share
                        msg = f"Provincial equalization transfer (${share:,.0f} per city) disbursed in {province.name}."
                        self.push_ticker(self.turn, 'FISCAL', msg, (245, 210, 100))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient provincial treasury ($200 required)."}

                elif decree == 'standardize_routes':
                    for t in province.tiles:
                        t.trade_efficiency = min(1.0, getattr(t, 'trade_efficiency', 0.7) + 0.15)
                    msg = f"Trade routes standardized across {province.name}."
                    self.push_ticker(self.turn, 'PROVINCE', msg, (200, 230, 150))
                    return {'success': True, 'message': msg}

                elif decree == 'harmonize_taxes':
                    avg_tax = sum(t.gov.tax_rate for t in province.tiles if hasattr(t, 'gov')) / max(1, len(province.tiles))
                    for t in province.tiles:
                        if hasattr(t, 'gov'):
                            t.gov.tax_rate = avg_tax
                    msg = f"Tax rates harmonized to {avg_tax*100:.1f}% across {province.name}."
                    self.push_ticker(self.turn, 'PROVINCE', msg, (240, 200, 120))
                    return {'success': True, 'message': msg}

                elif decree == 'soil_conservation':
                    if pcash >= 150.0:
                        pgov.agent.cash -= 150.0
                        for t in province.tiles:
                            t.soil_fertility = min(1.0, getattr(t, 'soil_fertility', 0.8) + 0.10)
                        msg = f"Provincial soil conservation campaign funded in {province.name}."
                        self.push_ticker(self.turn, 'ECOLOGY', msg, (130, 240, 160))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient provincial treasury ($150 required)."}

                return {'success': False, 'error': f"Unknown provincial decree '{decree}'."}

            elif c_type == CommandType.FRONTIER_EXPEDITION:
                tile_name = p.get('tile') or p.get('region')
                action = p.get('action', 'sponsor_settlers')
                tile = self.by_name.get(tile_name)
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), self.nations[0] if self.nations else None)
                if not tile:
                    return {'success': False, 'error': f"Tile '{tile_name}' not found."}

                if action == 'sponsor_settlers':
                    if nation and nation.government.agent.cash >= 100.0:
                        nation.government.agent.cash -= 100.0
                        from agent import Agent
                        for _ in range(3):
                            a = Agent(tile, is_homesteader=True, cash=25.0)
                            tile.agents.append(a)
                        msg = f"Sponsored 3 homesteading pioneer families to {tile.name} ($100)."
                        self.push_ticker(self.turn, 'FRONTIER', msg, (100, 240, 160))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient national treasury ($100 required)."}

                elif action == 'pioneer_aid':
                    if nation and nation.government.agent.cash >= 40.0:
                        nation.government.agent.cash -= 40.0
                        for a in tile.agents:
                            if getattr(a, 'is_homesteader', False):
                                a.food += 2.0
                                a.hungry_steps = 0
                        msg = f"Pioneer food aid delivered to settlers on {tile.name} ($40)."
                        self.push_ticker(self.turn, 'FRONTIER', msg, (160, 220, 150))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient national treasury ($40 required)."}

                return {'success': False, 'error': f"Unknown frontier action '{action}'."}

            elif c_type == CommandType.PURCHASE_FOREIGN_BOND:
                seller_name = p.get('seller_nation')
                buyer_name = p.get('buyer_nation') or self.player_nation_name
                amount = float(p.get('amount', 500.0))
                term = int(p.get('term', 20))
                market = get_bond_market()
                buyer = next((n for n in self.nations if n.name == buyer_name), None)
                seller = next((n for n in self.nations if n.name == seller_name), None)
                if not buyer or not seller:
                    return {'success': False, 'error': "Buyer or seller nation not found."}
                ok, msg = market.buy_foreign_bond(buyer, seller, amount, term, self.turn)
                if ok:
                    self.push_ticker(self.turn, 'BOND', f"{buyer.name} purchased ${amount:,.0f} of {seller.name} bonds.", (120, 240, 180))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.SET_BORDER_POLICY:
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found."}
                open_b = bool(p.get('open_borders', True))
                setattr(nation, 'open_borders', open_b)
                msg = f"Border immigration {'OPENED' if open_b else 'CLOSED'} for {nation.name}."
                self.push_ticker(self.turn, 'BORDER', msg, (120, 200, 255))
                return {'success': True, 'message': msg, 'open_borders': open_b}

            elif c_type == CommandType.SET_FACTORY_SAFETY:
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found."}
                val = bool(p.get('enabled', True))
                setattr(nation, 'factory_safety_act', val)
                msg = f"Factory Safety Act {'ENACTED' if val else 'REPEALED'} in {nation.name}."
                self.push_ticker(self.turn, 'LABOR', msg, (130, 220, 140))
                return {'success': True, 'message': msg, 'factory_safety_act': val}

            elif c_type == CommandType.SET_TRUCK_ACT:
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found."}
                val = bool(p.get('enabled', True))
                setattr(nation, 'truck_act_enacted', val)
                msg = f"Truck Act (Scrip Wage Ban) {'ENACTED' if val else 'REPEALED'} in {nation.name}."
                self.push_ticker(self.turn, 'LABOR', msg, (240, 190, 80))
                return {'success': True, 'message': msg, 'truck_act_enacted': val}

            elif c_type == CommandType.FISCAL_TRANSFER_RESOLVE:
                funding_source = p.get('funding_source')
                tile_name = p.get('tile')
                tile = self.by_name.get(tile_name)
                recipe_name = p.get('recipe_name')
                cost = float(p.get('cost', 250.0))
                nation = getattr(tile, 'owner_nation', None)
                province = getattr(tile, 'province', None)
                if not tile:
                    return {'success': False, 'error': "Tile not found."}

                on_hand = tile.gov.agent.cash if hasattr(tile, 'gov') and hasattr(tile.gov, 'agent') else 0.0
                shortfall = max(0.0, cost - on_hand)

                if funding_source == 'province_grant':
                    pgov = getattr(province, 'gov', None)
                    if pgov and pgov.agent.cash >= shortfall:
                        pgov.agent.cash -= shortfall
                        tile.gov.agent.cash += shortfall
                    else:
                        return {'success': False, 'error': "Provincial treasury has insufficient funds."}
                elif funding_source == 'national_bailout':
                    if nation and nation.government.agent.cash >= shortfall:
                        nation.government.agent.cash -= shortfall
                        tile.gov.agent.cash += shortfall
                    else:
                        return {'success': False, 'error': "National sovereign treasury has insufficient funds."}
                elif funding_source == 'bank_loan':
                    if hasattr(tile, 'gov') and hasattr(tile.gov, 'agent'):
                        tile.gov.agent.cash += shortfall

                recipe = BUILDING_RECIPES.get(recipe_name)
                if recipe:
                    from intents import BuildIntent
                    intent = BuildIntent(tile.name, recipe.name, submitted_turn=self.turn)
                    ok, msg = intent.execute(self.by_name, {n.name: n for n in self.nations}, self.turn)
                    return {'success': ok, 'message': f"Shortfall resolved via {funding_source}: {msg}"}
                return {'success': True, 'message': f"Shortfall resolved via {funding_source}."}

            elif c_type == CommandType.GET_STATE:
                target_tile = p.get('tile')
                if target_tile:
                    tile_obj = self.by_name.get(target_tile)
                    if tile_obj:
                        return {'success': True, 'tile': self.serialize_tile(tile_obj, layout=self.layout, turn=self.turn)}
                    return {'success': False, 'error': f"Tile '{target_tile}' not found"}
                return {'success': True, 'world': self.serialize_world()}

            return {'success': False, 'error': f"Unknown command {c_type}"}

    def subscribe(self, callback):
        """Register a callback for server broadcast events."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback):
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _broadcast(self, event_type: ServerEvent, data: Dict[str, Any]):
        for cb in list(self._subscribers):
            try:
                cb(event_type, data)
            except Exception as e:
                print(f"[SimServer] Broadcast error: {e}")

    def get_world_dict(self) -> Dict[str, Any]:
        """Produce a world representation compatible with legacy worldview panels."""
        with self._lock:
            return {
                'tiles': self.tiles,
                'nations': self.nations,
                'currencies': self.currencies,
                'pair_orders': self.pair_orders,
                'by_name': self.by_name,
                'layout': self.layout,
                'reverse': self.reverse_layout,
                'bbox': self.bbox,
                'turn': self.turn,
                'playing': self.playing,
                'ticker_events': self._ticker_events,
                'currency_totals': self.currency_totals,
                'violations': self.violations,
                'seed': self.seed,
                'terrain_seed': self.terrain_seed,
                'nation_seed': self.nation_seed,
            }

    @staticmethod
    def serialize_plot(plot) -> Dict[str, Any]:
        """Serialize a LandPlot into a JSON-compatible dictionary."""
        return {
            'plot_id': plot.plot_id,
            'name': getattr(plot, 'name', '') or plot.plot_id,
            'display_name': getattr(plot, 'display_name', plot.plot_id),
            'tile_name': plot.tile_name,
            'lord_id': plot.lord_id,
            'fraction': float(plot.fraction),
            'tenure': plot.tenure.value if hasattr(plot.tenure, 'value') else str(plot.tenure),
            'rent_rate': float(plot.rent_rate),
            'production_type': getattr(plot, 'production_type', 'arable'),
            'pasture_since': getattr(plot, 'pasture_since', -1),
            'tenant_ids': list(getattr(plot, 'tenant_ids', [])),
            'tenant_count': len(getattr(plot, 'tenant_ids', [])),
        }

    @classmethod
    def serialize_tile(cls, tile, layout: Optional[Dict[str, Any]] = None, turn: int = 0) -> Dict[str, Any]:
        """Serialize a Region / Tile into a JSON-compatible dictionary with full macro & citizen inspection."""
        tenure = getattr(tile, 'tenure', None)
        plots_data = [cls.serialize_plot(p) for p in getattr(tenure, 'plots', [])] if tenure else []

        from workhouse import has_workhouse, get_workhouse_census, get_workhouse_inmates
        wh_active = has_workhouse(tile)
        wh_inmates = [a.id for a in get_workhouse_inmates(tile)]
        wh_census = get_workhouse_census(tile) if wh_active else []

        survey_debts = [
            {
                'agent_id': d.get('agent_id'),
                'plot_id': d.get('plot_id'),
                'fee': float(d.get('fee', 15.0)),
                'deadline': int(d.get('deadline', 0)),
            }
            for d in getattr(tile, 'enclosure_survey_debts', [])
        ]

        shift_h = float(tile.avg_shift_hours_log[-1]) if getattr(tile, 'avg_shift_hours_log', None) else 8.0
        max_workday = float(getattr(tile, 'max_workday_hours', 12.0))
        sv = float(tile.surplus_value_log[-1]) if getattr(tile, 'surplus_value_log', None) else 0.0
        roe = float(tile.rate_of_exploitation_log[-1]) if getattr(tile, 'rate_of_exploitation_log', None) else 0.0

        grid_r = getattr(tile, 'grid_r', getattr(tile, 'row', 0))
        grid_c = getattr(tile, 'grid_c', getattr(tile, 'col', 0))

        if layout and tile.name in layout:
            q, r = layout[tile.name]
        elif grid_r is not None and grid_c is not None:
            from hexmap import offset_to_axial
            q, r = offset_to_axial(grid_c, grid_r)
        else:
            q = getattr(tile, 'q', 0)
            r = getattr(tile, 'r', 0)

        # Market prices
        market_prices = {}
        for g, rec in getattr(tile, 'recipes', {}).items():
            g_name = g.name if hasattr(g, 'name') else str(g)
            if isinstance(rec, dict) and 'price' in rec:
                market_prices[g_name] = round(float(rec['price']), 2)

        # Stockpiles
        stockpiles = {}
        for g, amt in getattr(tile, 'stockpiles', {}).items():
            g_name = g.name if hasattr(g, 'name') else str(g)
            stockpiles[g_name] = round(float(amt), 1)

        # Completed Buildings
        buildings_list = []
        for b in getattr(tile, 'buildings', []):
            b_name = getattr(b, 'display_name', getattr(b, 'name', str(b)))
            buildings_list.append(b_name)

        # Active Construction Projects
        projects_list = []
        for p in getattr(tile, 'construction_projects', []):
            p_name = getattr(p.recipe, 'display_name', getattr(p.recipe, 'name', 'Project'))
            base_t = max(1, getattr(p.recipe, 'base_turns', 1))
            prog = max(0.0, min(1.0, 1.0 - (p.turns_left / base_t)))
            projects_list.append({
                'name': p_name,
                'turns_left': int(p.turns_left),
                'total_turns': int(base_t),
                'progress': round(prog * 100, 0)
            })

        # Ecological Metrics
        eco = {
            'soil_fertility': round(float(getattr(tile, 'soil_fertility', 1.0)) * 100, 0),
            'pollution_air': round(float(getattr(tile, 'pollution_air', 0.0)), 1),
            'nutrition_density': round(float(getattr(tile, 'nutrition_density', 1.0)) * 100, 0)
        }

        # Citizens Roster (first 25 living non-corp agents)
        citizens = []
        for a in getattr(tile, 'agents', []):
            if not getattr(a, 'alive', True) or getattr(a, 'is_corporation', False) or getattr(a, 'is_government', False):
                continue
            f_obj = getattr(a, 'faction', None)
            f_name = f_obj.name if f_obj and hasattr(f_obj, 'name') else 'None'
            citizens.append({
                'id': str(a.id),
                'age': int(a.age(turn)) if hasattr(a, 'age') else 30,
                'career': getattr(a, 'career', 'Laborer') if getattr(a, 'career', None) else ('Trader' if getattr(a, 'is_trader', False) else ('Homesteader' if getattr(a, 'is_homesteader', False) else 'Citizen')),
                'wage': round(float(getattr(a, 'wage', 0.0)), 2),
                'cash': round(float(getattr(a, 'cash', 0.0)), 1),
                'hungry': bool(getattr(a, 'hungry_steps', 0) > 0),
                'happiness': round(float(getattr(a, 'happiness', 1.0)), 2),
                'faction': f_name
            })
            if len(citizens) >= 25:
                break

        gdp_val = float(tile.gdp_log[-1]) if getattr(tile, 'gdp_log', None) else 0.0
        unrest_val = float(tile.protest_energy_log[-1]) if getattr(tile, 'protest_energy_log', None) else 0.0

        # Economic charts data (10 series)
        from goods import Goods
        g_price = lambda gd: [round(float(p), 2) for p in tile.price_log.get(gd, [])[-30:]]
        g_prod = lambda gd: [round(float(p), 2) for p in tile.production_log.get(gd, [])[-30:]]
        g_inv = lambda gd: [round(float(p), 1) for p in tile.inventory_log.get(gd, [])[-30:]]
        g_dem = lambda gd: [round(float(p), 2) for p in tile.demand_ratio_log.get(gd, [])[-30:]]

        pop_series = (tile.total_population or [])[-30:]
        hs = [tile.hungry_log.get(gd, []) for gd in (Goods.food, Goods.wood, Goods.furniture)]
        hungry_series = [sum(row) for row in zip(*hs)][-30:] if any(hs) else []
        exp = [tile.export_val.get(gd, []) for gd in (Goods.food, Goods.wood, Goods.furniture)]
        imp = [tile.import_val.get(gd, []) for gd in (Goods.food, Goods.wood, Goods.furniture)]
        tot_exp = [round(sum(row), 1) for row in zip(*exp)][-30:] if any(exp) else []
        tot_imp = [round(sum(row), 1) for row in zip(*imp)][-30:] if any(imp) else []

        t_gov = getattr(tile, 'gov', None)
        t_income = getattr(t_gov, 'income_log', []) if t_gov is not None else []
        tax_series = [round(e.get('tax', 0.0), 2) for e in t_income][-30:]
        tariff_series = [round(e.get('tariff', 0.0), 2) for e in t_income][-30:]
        inherit_series = [round(e.get('inheritance', 0.0), 2) for e in t_income][-30:]

        protest_series = [round(float(p), 2) for p in (tile.protest_energy_log or [])][-30:]
        gdp_series = [round(float(g), 1) for g in (tile.gdp_log or [])][-30:]
        gini_series = [round(float(g) * 100.0, 1) for g in (tile.gini_log.get(Goods.food, []) or [])][-30:]
        migr_series = [round(float(m), 1) for m in (getattr(tile, 'migration_intent_log', []) or [])][-30:]
        commons_series = [round(float(c) * 100.0, 1) for c in (getattr(tile, 'tenure_log', []) or [])][-30:]

        # Ecological & Epidemics charts (6 series)
        fert_series = [round(float(f) * 100.0, 1) for f in (getattr(tile, 'soil_fertility_log', []) or [])][-30:]
        nutr_series = [round(float(n) * 100.0, 1) for n in (getattr(tile, 'nutrition_density_log', []) or [])][-30:]
        smog_series = [round(float(s), 1) for s in (getattr(tile, 'pollution_air_log', []) or [])][-30:]
        water_series = [round(float(w), 1) for w in (getattr(tile, 'pollution_water_log', []) or [])][-30:]
        soil_series = [round(float(s), 1) for s in (getattr(tile, 'pollution_soil_log', []) or [])][-30:]

        d_cases = (getattr(tile, 'disease_cases_log', []) or [])[-30:]
        malnutr_series = [c.get('malnutrition', 0) if isinstance(c, dict) else 0 for c in d_cases]
        cholera_series = [c.get('waterborne', 0) if isinstance(c, dict) else 0 for c in d_cases]
        respir_series = [c.get('respiratory', 0) if isinstance(c, dict) else 0 for c in d_cases]
        chem_series = [c.get('chemical', 0) if isinstance(c, dict) else 0 for c in d_cases]

        priv_spend = [round(float(s), 1) for s in (getattr(tile, 'medical_spending_private_log', []) or [])][-30:]
        pub_spend = [round(float(s), 1) for s in (getattr(tile, 'medical_spending_public_log', []) or [])][-30:]
        untreated_series = (getattr(tile, 'untreated_cases_log', []) or [])[-30:]
        fatalities_series = (getattr(tile, 'disease_fatalities_log', []) or [])[-30:]
        health_attr_series = [round(float(h) * 100.0, 1) for h in (getattr(tile, 'avg_health_attrition_log', []) or [])][-30:]

        # Labor & Alienation charts (4 series)
        shifts_series = [round(float(s), 1) for s in (getattr(tile, 'labor_shift_log', []) or [])][-30:]
        sv_rates_series = [round(float(v) * 100.0, 1) for v in (getattr(tile, 'labor_sv_log', []) or [])][-30:]
        legal_caps = [round(float(getattr(tile, 'max_workday_hours', 16.0)), 1)] * len(shifts_series)
        alienation_series = [round(float(a) * 100.0, 1) for a in (getattr(tile, 'alienation_log', []) or [])][-30:]
        health_series = [round(float(h) * 1000.0, 1) for h in (getattr(tile, 'health_attrition_log', []) or [])][-30:]
        vice_series = [round(float(v), 1) for v in (getattr(tile, 'vice_spending_log', []) or [])][-30:]
        consc_series = [round(float(c) * 100.0, 1) for c in (getattr(tile, 'class_consciousness_log', []) or [])][-30:]
        entertain_series = [round(float(e) * 100.0, 1) for e in (getattr(tile, 'entertainment_level_log', []) or [])][-30:]
        strikers_series = (getattr(tile, 'strikes_log', []) or [])[-30:]
        broken_series = (getattr(tile, 'sabotage_log', []) or [])[-30:]
        machines_series = (getattr(tile, 'machinery_stock_log', []) or [])[-30:]

        # Social Class charts (4 series)
        clogs = (getattr(tile, 'social_class_log', []) or [])[-30:]
        serfs_series = [d.get('serf', 0) for d in clogs]
        tenants_series = [d.get('tenant', 0) for d in clogs]
        proles_series = [d.get('proletarian', 0) for d in clogs]
        disposs_series = [d.get('dispossessed', 0) for d in clogs]
        gentry_series = [d.get('lord', 0) + d.get('landlord', 0) for d in clogs]
        bourg_series = [d.get('petty_bourgeois', 0) + d.get('industrialist', 0) for d in clogs]
        foraged_series = (getattr(tile, 'food_foraged_log', []) or [])[-30:]
        purchased_series = (getattr(tile, 'food_purchased_log', []) or [])[-30:]
        rent_series = [round(float(r), 1) for r in (getattr(tile, 'rent_collected_log', []) or [])][-30:]
        arrears_series = [round(float(a), 1) for a in (getattr(tile, 'rent_arrears_log', []) or [])][-30:]

        return {
            'name': tile.name,
            'display_name': getattr(tile, 'display_name', getattr(tile, 'city_name', tile.name)),
            'row': grid_r if grid_r is not None else 0,
            'col': grid_c if grid_c is not None else 0,
            'q': q,
            'r': r,
            'nation': tile.owner_nation.name if getattr(tile, 'owner_nation', None) else None,
            'elevation': float(getattr(tile, 'elevation', 0.0)),
            'elevation_meters': float(getattr(tile, 'elevation_meters', 0.0)),
            'biome': getattr(tile, 'biome', 'plains'),
            'is_ocean': getattr(tile, 'is_ocean', False),
            'wilderness': getattr(tile, 'wilderness', False),
            'cost_of_living': float(getattr(tile, 'cost_of_living', 1.0)),
            'gdp': round(gdp_val, 1),
            'protest_energy': round(unrest_val, 2),
            'market_prices': market_prices,
            'stockpiles': stockpiles,
            'buildings': buildings_list,
            'construction_projects': projects_list,
            'garrison': int(getattr(tile, 'garrison', 0)),
            'ecology': eco,
            'citizens': citizens,
            'charts': {
                'economic': {
                    'prices': {'food': g_price(Goods.food), 'wood': g_price(Goods.wood), 'furniture': g_price(Goods.furniture)},
                    'pop_hunger': {'pop': pop_series, 'hungry': hungry_series},
                    'production': {'food': g_prod(Goods.food), 'wood': g_prod(Goods.wood), 'furniture': g_prod(Goods.furniture)},
                    'trade_flow': {'export': tot_exp, 'import': tot_imp},
                    'gov_income': {'tax': tax_series, 'tariff': tariff_series, 'inheritance': inherit_series},
                    'gini_migration': {'gini': gini_series, 'migration': migr_series},
                    'inventories': {'food': g_inv(Goods.food), 'wood': g_inv(Goods.wood), 'furniture': g_inv(Goods.furniture)},
                    'protest_commons': {'protest': protest_series, 'commons': commons_series},
                    'gdp': gdp_series,
                    'demand_ratio': {'food': g_dem(Goods.food), 'wood': g_dem(Goods.wood), 'furniture': g_dem(Goods.furniture)},
                },
                'ecological': {
                    'soil_nutrition': {'soil': fert_series, 'nutrition': nutr_series},
                    'pollution': {'smog': smog_series, 'water': water_series, 'soil': soil_series},
                    'epidemics': {'malnutrition': malnutr_series, 'cholera': cholera_series, 'bronchitis': respir_series, 'toxic': chem_series},
                    'healthcare_outlay': {'private': priv_spend, 'public': pub_spend},
                    'untreated_fatalities': {'untreated': untreated_series, 'fatalities': fatalities_series},
                    'health_attrition': health_attr_series,
                },
                'labor': {
                    'shifts_exploitation': {'shifts': shifts_series, 'caps': legal_caps, 'sv_rate': sv_rates_series},
                    'alienation_health': {'alienation': alienation_series, 'health': health_series, 'vice': vice_series},
                    'consciousness_pacification': {'consciousness': consc_series, 'entertainment': entertain_series, 'protest': protest_series},
                    'workplace_resistance': {'strikers': strikers_series, 'sabotage': broken_series, 'machines': machines_series},
                },
                'citizens': {
                    'classes': {'serf': serfs_series, 'tenant': tenants_series, 'worker': proles_series, 'dispossessed': disposs_series, 'gentry': gentry_series, 'artisan': bourg_series},
                    'food_source': {'foraged': foraged_series, 'market': purchased_series, 'hungry': hungry_series},
                    'commons_rent': {'commons': commons_series, 'rent': rent_series, 'arrears': arrears_series},
                    'disparity_unrest': {'gini': gini_series, 'protest': protest_series},
                }
            },
            'tenure': {
                'commons_access': float(getattr(tenure, 'commons_access', 1.0)) if tenure else 1.0,
                'feudal_fraction': float(getattr(tenure, 'feudal_fraction', 0.0)) if tenure else 0.0,
                'enclosed_fraction': float(getattr(tenure, 'enclosed_fraction', 0.0)) if tenure else 0.0,
                'pasture_fraction': float(getattr(tenure, 'pasture_fraction', 0.0)) if tenure else 0.0,
                'arable_fraction': float(getattr(tenure, 'arable_fraction', 0.0)) if tenure else 0.0,
                'plots': plots_data,
                'survey_debts': survey_debts,
            },
            'workhouse': {
                'active': wh_active,
                'inmate_count': len(wh_inmates),
                'inmate_ids': wh_inmates,
                'census': wh_census,
            },
            'labor': {
                'shift_hours': shift_h,
                'max_workday_hours': max_workday,
                'ten_hour_act': bool(getattr(tile, 'ten_hour_act', max_workday <= 10.0)),
                'surplus_value': sv,
                'rate_of_exploitation': roe,
            },
            'population': len(getattr(tile, 'agents', [])),
        }

    def serialize_world(self) -> Dict[str, Any]:
        """Produce a complete JSON-serializable snapshot of the simulation world."""
        with self._lock:
            tiles_data = [self.serialize_tile(t, layout=self.layout, turn=self.turn) for t in self.tiles]
            player_nation = next((n for n in self.nations if n.name == self.player_nation_name), self.nations[0] if self.nations else None)
            player_nat_name = player_nation.name if player_nation else None

            # All nations macro stats for comparison modal & dropdown
            nations_summary = [self._calc_nation_macro(n) for n in self.nations]
            active_macro = next((m for m in nations_summary if m['name'] == player_nat_name), (nations_summary[0] if nations_summary else {}))

            # History series for charting
            history_data = self._nation_history.get(player_nat_name, {
                'turns': [], 'treasury': [], 'gdp': [], 'pop': [], 'food_price': [], 'unrest': []
            })

            # Build Recipes (Categorized)
            build_recipes = {}
            for k, r in BUILDING_RECIPES.items():
                req_g = {}
                if getattr(r, 'required_goods', None):
                    for g, cnt in r.required_goods.items():
                        req_g[g.name if hasattr(g, 'name') else str(g)] = cnt
                cat = 'industry'
                if k in ('night_soil_depot', 'sewer_system', 'infirmary', 'water_filtration', 'sanitarium', 'waste_incinerator'):
                    cat = 'ecology'
                elif k in ('fortress', 'naval_dockyard'):
                    cat = 'defense'
                elif k in ('paved_road', 'canal', 'railroad', 'telegraph'):
                    cat = 'roads'
                build_recipes[k] = {
                    'name': r.name,
                    'display_name': r.display_name,
                    'cost': float(r.cost),
                    'base_turns': int(r.base_turns),
                    'tier': r.tier,
                    'category': cat,
                    'description': r.description,
                    'required_goods': req_g
                }

            # Diplomacy state
            diplo_list = []
            try:
                dip = get_diplomacy()
                for other_n in self.nations:
                    if other_n.name == player_nat_name:
                        continue
                    rel = dip.get_relation(player_nat_name, other_n.name)
                    treaties = dip.get_active_treaties(player_nat_name, other_n.name)
                    status_str = "Neutral"
                    if rel >= 0.6: status_str = "Allied"
                    elif rel >= 0.2: status_str = "Cordial"
                    elif rel <= -0.6: status_str = "Hostile / War"
                    elif rel <= -0.2: status_str = "Strained"

                    diplo_list.append({
                        'nation': other_n.name,
                        'relation': round(float(rel), 2),
                        'status': status_str,
                        'treaties': [t.treaty_type for t in treaties if getattr(t, 'status', 'active') == 'active'],
                        'flag_color': next((m['flag_color'] for m in nations_summary if m['name'] == other_n.name), '#38bdf8'),
                        'gdp': next((m['gdp'] for m in nations_summary if m['name'] == other_n.name), 0.0),
                        'pop': next((m['population'] for m in nations_summary if m['name'] == other_n.name), 0)
                    })
            except Exception as e:
                print(f"[SimServer] Diplo serialize note: {e}")

            # Science Tech Tree & National Resources
            science_tree = []
            resources_list = []
            try:
                innov = get_innovation_system()
                bounties = {b.tech_id: b.bounty_amount for b in innov.active_bounties if b.nation_name == player_nat_name}
                for tid, tech in TECH_CATALOG.items():
                    is_mastered = innov.has_tech(player_nat_name, tid)
                    has_bounty = tid in bounties
                    prereqs = getattr(tech, 'required_techs', [])
                    can_research = all(innov.has_tech(player_nat_name, req) for req in prereqs)

                    st = "locked"
                    if is_mastered: st = "mastered"
                    elif has_bounty: st = "bounty_active"
                    elif can_research: st = "unlocked"

                    science_tree.append({
                        'id': tech.tech_id,
                        'name': tech.name,
                        'domain': tech.domain.value if hasattr(tech.domain, 'value') else str(tech.domain),
                        'era': getattr(tech, 'era', 1),
                        'description': tech.description,
                        'base_xp': float(tech.base_xp_required),
                        'status': st,
                        'prerequisites': list(prereqs),
                        'unlocked_buildings': list(getattr(tech, 'unlocked_buildings', [])),
                        'bounty_amount': bounties.get(tid, 300.0)
                    })

                # Extract regional resources for nation
                if player_nation:
                    res_set = set()
                    for t in player_nation.tiles:
                        for res in getattr(t, 'natural_resources', []):
                            res_set.add(res if isinstance(res, str) else getattr(res, 'name', str(res)))
                    resources_list = sorted(list(res_set))
            except Exception as e:
                print(f"[SimServer] Science serialize note: {e}")

            # Sovereign Debt State (Domestic + Foreign Portfolio)
            sovereign_debt_data = {
                'rating': active_macro.get('credit_rating', 'BBB'),
                'yield_rate': active_macro.get('bond_yield', 0.18),
                'public_debt': active_macro.get('public_debt', 0.0),
                'offerings': [],
                'foreign_portfolio': [],
                'available_foreign_bonds': []
            }
            try:
                market = get_bond_market()
                for off in getattr(market, 'offerings', []):
                    if off.issuer_nation == player_nat_name and off.status in ('announced', 'live'):
                        sovereign_debt_data['offerings'].append({
                            'id': off.offering_id,
                            'principal': float(off.principal),
                            'duration': int(off.duration_turns),
                            'coupon_rate': round(float(off.coupon_rate)*100, 2),
                            'status': off.status
                        })
                    elif off.issuer_nation != player_nat_name and off.status in ('announced', 'live'):
                        sovereign_debt_data['available_foreign_bonds'].append({
                            'id': off.offering_id,
                            'issuer': off.issuer_nation,
                            'principal': float(off.principal),
                            'duration': int(off.duration_turns),
                            'coupon_rate': round(float(off.coupon_rate)*100, 2)
                        })
                for b in getattr(market, 'active_bonds', []):
                    if getattr(b, 'holder_nation', None) == player_nat_name and b.issuer_nation != player_nat_name:
                        sovereign_debt_data['foreign_portfolio'].append({
                            'id': b.bond_id,
                            'issuer': b.issuer_nation,
                            'principal': float(b.principal),
                            'duration': int(b.duration),
                            'coupon_rate': round(float(b.coupon_rate)*100, 2),
                            'turns_remaining': max(0, int(b.maturity_turn - self.turn))
                        })
            except Exception:
                pass

            # Military Suite
            armies_data = []
            if player_nation:
                for a in getattr(player_nation, 'armies', []):
                    armies_data.append({
                        'id': getattr(a, 'unit_id', 'Army'),
                        'soldiers': int(getattr(a, 'soldiers', 0)),
                        'strength': round(float(getattr(a, 'strength', 1.0)), 1),
                        'morale': round(float(getattr(a, 'morale', 1.0)), 2),
                        'xp': round(float(getattr(a, 'veteran_xp', 0.0)), 1)
                    })

            # 6-Tab Comparison Accounts Suite
            comparison_suite = {
                'tab1_macro': nations_summary,
                'tab2_goods': [],
                'tab3_forex': {'banking': [], 'fx_matrix': {}},
                'tab4_extraction': {'by_country': [], 'by_province': [], 'by_tile': []},
                'tab5_protest': {'by_country': [], 'by_province': [], 'by_tile': []},
                'tab6_ecology': {'by_country': [], 'by_province': [], 'by_tile': []}
            }
            try:
                # Tab 2: Goods & Provinces
                for n in self.nations:
                    for prov in getattr(n, 'provinces', []):
                        p_tiles = getattr(prov, 'tiles', [])
                        if not p_tiles: continue
                        p_info = {'province': prov.name, 'nation': n.name, 'goods': {}}
                        for gd in (Goods.food, Goods.wood, Goods.furniture):
                            gd_name = gd.name
                            prices = [t.price_log.get(gd, [1.0])[-1] for t in p_tiles if t.price_log.get(gd)]
                            avg_p = round(sum(prices)/max(1, len(prices)), 2)
                            prods = [t.production_log.get(gd, [0.0])[-1] for t in p_tiles if t.production_log.get(gd)]
                            tot_prod = round(sum(prods), 1)
                            invs = [t.inventory_log.get(gd, [0.0])[-1] for t in p_tiles if t.inventory_log.get(gd)]
                            tot_inv = round(sum(invs), 1)
                            exps = [t.export_val.get(gd, [0.0])[-1] for t in p_tiles if t.export_val.get(gd)]
                            tot_exp = round(sum(exps), 1)
                            imps = [t.import_val.get(gd, [0.0])[-1] for t in p_tiles if t.import_val.get(gd)]
                            tot_imp = round(sum(imps), 1)
                            p_info['goods'][gd_name] = {
                                'price': avg_p, 'production': tot_prod, 'inventory': tot_inv, 'export': tot_exp, 'import': tot_imp
                            }
                        comparison_suite['tab2_goods'].append(p_info)

                # Tab 3: Forex & Banking
                for n in self.nations:
                    bank_dep = sum(sum(b.deposits.values()) for t in n.tiles if hasattr(t, 'bank') for b in [t.bank])
                    comparison_suite['tab3_forex']['banking'].append({
                        'nation': n.name,
                        'currency': getattr(n, 'currency', 'USD'),
                        'neer': round(float(getattr(n, 'neer', 1.0)), 2),
                        'reserves': round(float(getattr(n, 'central_bank_reserves', 1000.0)), 0),
                        'deposits': round(float(bank_dep), 0)
                    })
                fx_m = {}
                for n1 in self.nations:
                    c1 = getattr(n1, 'currency', n1.name[:3].upper())
                    fx_m[c1] = {}
                    for n2 in self.nations:
                        c2 = getattr(n2, 'currency', n2.name[:3].upper())
                        rate = round((len(n1.tiles) / max(1, len(n2.tiles))), 2) if n1 != n2 else 1.0
                        fx_m[c1][c2] = rate
                comparison_suite['tab3_forex']['fx_matrix'] = fx_m

                # Tab 4: Extraction
                for n in self.nations:
                    c_trib = sum(t.tribute_collected_log[-1] if getattr(t, 'tribute_collected_log', None) else 0.0 for t in n.tiles)
                    c_rent = sum(t.rent_collected_log[-1] if getattr(t, 'rent_collected_log', None) else 0.0 for t in n.tiles)
                    c_sv = sum(t.surplus_value_log[-1] if getattr(t, 'surplus_value_log', None) else 0.0 for t in n.tiles)
                    c_sv_rate = (sum(t.rate_of_exploitation_log[-1] if getattr(t, 'rate_of_exploitation_log', None) else 0.0 for t in n.tiles) / max(1, len(n.tiles))) * 100.0
                    c_tax = sum(sum(t.gov.tax_collected_history[-1:]) if hasattr(t, 'gov') and hasattr(t.gov, 'tax_collected_history') and t.gov.tax_collected_history else 0.0 for t in n.tiles)
                    c_alien = (sum(t.alienation_log[-1] if getattr(t, 'alienation_log', None) else 0.0 for t in n.tiles) / max(1, len(n.tiles))) * 100.0
                    c_health = (sum(t.health_attrition_log[-1] if getattr(t, 'health_attrition_log', None) else 0.0 for t in n.tiles) / max(1, len(n.tiles))) * 1000.0
                    comparison_suite['tab4_extraction']['by_country'].append({
                        'name': n.name, 'tribute': round(c_trib, 1), 'rent': round(c_rent, 1), 'surplus_value': round(c_sv, 1),
                        'sv_rate': round(c_sv_rate, 1), 'tax': round(c_tax, 1), 'alienation': round(c_alien, 1), 'health_attrition': round(c_health, 1)
                    })

                # Tab 5: Protest Energy & Grievances
                for n in self.nations:
                    tot_p = sum(t.protest_energy_log[-1] if getattr(t, 'protest_energy_log', None) else 0.0 for t in n.tiles)
                    shifts = sum(t.avg_shift_hours_log[-1] if getattr(t, 'avg_shift_hours_log', None) else 8.0 for t in n.tiles) / max(1, len(n.tiles))
                    hungry = sum(sum(1 for a in t.agents if getattr(a, 'hungry_steps', 0) > 0) for t in n.tiles)
                    strikers = sum(t.strikes_log[-1] if getattr(t, 'strikes_log', None) else 0 for t in n.tiles)
                    w_over = max(0.0, shifts - 8.0) * 10.0
                    w_enc = (1.0 - (sum(t.tenure.commons_access for t in n.tiles if hasattr(t, 'tenure')) / max(1, len(n.tiles)))) * 30.0
                    w_hung = hungry * 5.0
                    w_str = strikers * 8.0
                    w_st = (sum(getattr(t, 'repression_level', 0.0) for t in n.tiles)) * 15.0
                    w_in = (sum(t.gini_log.get(Goods.food, [0.3])[-1] for t in n.tiles if t.gini_log.get(Goods.food)) / max(1, len(n.tiles))) * 25.0
                    w_t = max(1.0, w_over + w_enc + w_hung + w_str + w_st + w_in)
                    comparison_suite['tab5_protest']['by_country'].append({
                        'name': n.name, 'total_protest': round(tot_p, 2),
                        'overwork': round(w_over / w_t * 100, 1),
                        'enclosure': round(w_enc / w_t * 100, 1),
                        'hunger': round(w_hung / w_t * 100, 1),
                        'strikes': round(w_str / w_t * 100, 1),
                        'state': round(w_st / w_t * 100, 1),
                        'inequality': round(w_in / w_t * 100, 1)
                    })

                # Tab 6: Ecology & Health
                for n in self.nations:
                    avg_f = sum(t.soil_fertility for t in n.tiles) / max(1, len(n.tiles)) * 100.0
                    avg_nu = sum(t.nutrition_density for t in n.tiles) / max(1, len(n.tiles)) * 100.0
                    avg_sm = sum(getattr(t, 'pollution_air', 0.0) for t in n.tiles) / max(1, len(n.tiles))
                    avg_wt = sum(getattr(t, 'pollution_water', 0.0) for t in n.tiles) / max(1, len(n.tiles))
                    avg_sl = sum(getattr(t, 'pollution_soil', 0.0) for t in n.tiles) / max(1, len(n.tiles))
                    tot_m = sum(sum(c.get('malnutrition', 0) for c in getattr(t, 'disease_cases_log', [{}])[-1:]) for t in n.tiles)
                    tot_ch = sum(sum(c.get('waterborne', 0) for c in getattr(t, 'disease_cases_log', [{}])[-1:]) for t in n.tiles)
                    tot_br = sum(sum(c.get('respiratory', 0) for c in getattr(t, 'disease_cases_log', [{}])[-1:]) for t in n.tiles)
                    tot_tx = sum(sum(c.get('chemical', 0) for c in getattr(t, 'disease_cases_log', [{}])[-1:]) for t in n.tiles)
                    comparison_suite['tab6_ecology']['by_country'].append({
                        'name': n.name, 'soil_fertility': round(avg_f, 1), 'nutrition_density': round(avg_nu, 1),
                        'smog': round(avg_sm, 1), 'water': round(avg_wt, 1), 'soil': round(avg_sl, 1),
                        'malnutrition': tot_m, 'cholera': tot_ch, 'bronchitis': tot_br, 'chemical': tot_tx
                    })
            except Exception as e:
                print(f"[SimServer] Comparison suite serialize note: {e}")

            x0, y0, x1, y1 = self.bbox
            from render_engine.camera import MAP_PAD_RATIO
            pad_x = (x1 - x0) * MAP_PAD_RATIO
            pad_y = (y1 - y0) * MAP_PAD_RATIO
            terrain_bounds = {
                'min_x': float(x0 - pad_x),
                'min_y': float(y0 - pad_y),
                'width': float((x1 - x0) + 2.0 * pad_x),
                'height': float((y1 - y0) + 2.0 * pad_y),
                'hex_size': float(getattr(self, 'hex_size', 50.0)),
            }

            return {
                'turn': self.turn,
                'playing': self.playing,
                'seed': self.seed,
                'terrain_seed': self.terrain_seed,
                'nation_seed': self.nation_seed,
                'hex_size': float(getattr(self, 'hex_size', 50.0)),
                'bbox': [float(v) for v in self.bbox],
                'terrain_bounds': terrain_bounds,
                'player_nation': player_nat_name,
                'macro': active_macro,
                'history': history_data,
                'nations': nations_summary,
                'tiles': tiles_data,
                'build_recipes': build_recipes,
                'diplomacy': diplo_list,
                'science_tree': science_tree,
                'resources': resources_list,
                'sovereign_debt': sovereign_debt_data,
                'armies': armies_data,
                'comparison_suite': comparison_suite,
                'ticker_events': list(self._ticker_events[-35:]),
            }
