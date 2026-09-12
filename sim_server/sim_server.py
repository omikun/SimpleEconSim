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
                return {'success': False, 'error': 'Nation not found'}

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
