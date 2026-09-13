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
            'cost_of_living': round(float(col_cur), 2),
            'exports': round(float(exports_cur), 1),
            'imports': round(float(imports_cur), 1),
            'trade_balance': round(float(trade_net), 1),
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

            # Build Recipes
            build_recipes = {}
            for k, r in BUILDING_RECIPES.items():
                req_g = {}
                if getattr(r, 'required_goods', None):
                    for g, cnt in r.required_goods.items():
                        req_g[g.name if hasattr(g, 'name') else str(g)] = cnt
                build_recipes[k] = {
                    'name': r.name,
                    'display_name': r.display_name,
                    'cost': float(r.cost),
                    'base_turns': int(r.base_turns),
                    'tier': r.tier,
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

            # Science Tech Tree
            science_tree = []
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
            except Exception as e:
                print(f"[SimServer] Science serialize note: {e}")

            # Sovereign Debt State
            sovereign_debt_data = {
                'rating': active_macro.get('credit_rating', 'BBB'),
                'yield_rate': active_macro.get('bond_yield', 0.18),
                'public_debt': active_macro.get('public_debt', 0.0),
                'offerings': []
            }
            try:
                market = get_bond_market()
                for off in getattr(market, 'offerings', []):
                    if off.issuer_nation == player_nat_name and off.status in ('announced', 'live'):
                        sovereign_debt_data['offerings'].append({
                            'id': off.offering_id,
                            'principal': float(off.principal),
                            'duration': int(off.duration_turns),
                            'coupon_rate': float(off.coupon_rate),
                            'status': off.status
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
                'sovereign_debt': sovereign_debt_data,
                'armies': armies_data,
                'ticker_events': list(self._ticker_events[-35:]),
            }
