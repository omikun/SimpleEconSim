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

            self._broadcast(ServerEvent.TURN_ADVANCED, {'turn': t})
            return t

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

            elif c_type == CommandType.SET_POLICY:
                target_nation = next((n for n in self.nations if n.name == p.get('nation')), None)
                if target_nation:
                    policy_key = p.get('key')
                    policy_val = p.get('val')
                    if hasattr(target_nation, 'policies') and isinstance(target_nation.policies, dict):
                        target_nation.policies[policy_key] = policy_val
                    else:
                        setattr(target_nation, policy_key, policy_val)
                    return {'success': True, 'nation': target_nation.name, 'key': policy_key, 'val': policy_val}
            elif c_type == CommandType.GET_STATE:
                target_tile = p.get('tile')
                if target_tile:
                    tile_obj = self.by_name.get(target_tile)
                    if tile_obj:
                        return {'success': True, 'tile': self.serialize_tile(tile_obj, layout=self.layout)}
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
    def serialize_tile(cls, tile, layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Serialize a Region / Tile into a JSON-compatible dictionary."""
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
            tiles_data = [self.serialize_tile(t, layout=self.layout) for t in self.tiles]
            nations_data = [
                {
                    'name': n.name,
                    'currency': getattr(n, 'currency', ''),
                    'regime_type': getattr(n, 'regime_type', 'Monarchy'),
                    'max_workday_hours': float(getattr(n, 'max_workday_hours', 12.0)),
                    'ten_hour_act': bool(getattr(n, 'ten_hour_act', False)),
                    'tiles': [t.name for t in getattr(n, 'tiles', [])],
                    'treasury': float(n.government.agent.cash) if getattr(n, 'government', None) and hasattr(n.government, 'agent') else 0.0,
                }
                for n in self.nations
            ]
            return {
                'turn': self.turn,
                'playing': self.playing,
                'seed': self.seed,
                'terrain_seed': self.terrain_seed,
                'nation_seed': self.nation_seed,
                'nations': nations_data,
                'tiles': tiles_data,
                'ticker_events': list(self._ticker_events[-30:]),
            }
