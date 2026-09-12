"""
game_client/game_client.py — Game Client implementation.

Bridges user interaction and UI layers with the authoritative SimServer,
and presents the visual game state using RenderEngine.
"""

from typing import Any, Dict, Optional
import pygame

from sim_server import SimServer, CommandType
from sim_server.protocol import CommandMessage, ServerEvent
from render_engine import RenderEngine, Camera
from worldview_camera import (
    WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H, HEX_SIZE,
    reset_cam, clamp_cam, zoom_cam_at, tile_at
)
from worldview_left_dock import open_left_panel, close_left_panels, is_any_left_panel_open


class GameClient:
    """Client controller managing user input, local UI state, and rendering."""

    def __init__(self, server: Optional[SimServer] = None, seed: Optional[int] = None,
                 terrain_seed: Optional[int] = None, nation_seed: Optional[int] = None):
        if server is None:
            self.server = SimServer(seed=seed, terrain_seed=terrain_seed, nation_seed=nation_seed)
        else:
            self.server = server

        self.render_engine = RenderEngine(width=WIDTH, height=HEIGHT, map_right=MAP_RIGHT,
                                          top_bar_h=TOP_BAR_H, ticker_h=TICKER_H)

        # Build client-side world representation
        self.world = self.server.get_world_dict()
        self._init_client_ui_state()

        # Connect camera
        reset_cam(self.world)
        self.render_engine.set_bbox(self.world['bbox'])
        self.render_engine.camera.sync_from_dict(self.world['cam'])

        # Subscribe to server events
        self.server.subscribe(self._on_server_event)

    def _init_client_ui_state(self):
        """Initialize client-specific UI session flags and drawer state."""
        self.world.update({
            'cam': {'ox': 0.0, 'oy': 0.0, 'zoom': 1.0},
            'selected_region': None,
            'selected_nation': None,
            'player_nation_name': self.world['nations'][0].name if self.world['nations'] else None,
            'hover_region': None,
            'frame': 0,
            'view': 0,
            'window': 100,
            'scope': 'tile',
            'help_open': False,
            'help_scroll': 0,
            'map_layer': 'overview',
            'layers_collapsed': True,
            'panel_tab': 'charts',
            'left_panel': None,
            'last_left_panel': 'build',
            'policy_scope': 'tile',
            'policy_feedback': None,
            'needs_redraw': True,
            'loading_modal': None,
            '_cached_topo_surface': None,
            '_map_generation_done': False,
            '_cached_from_disk': False,
        })

    def _on_server_event(self, event_type: ServerEvent, data: Dict[str, Any]):
        """Handle real-time updates from SimServer."""
        if event_type == ServerEvent.TURN_ADVANCED:
            self.world['turn'] = data.get('turn', self.world['turn'])
            self.world['needs_redraw'] = True
        elif event_type == ServerEvent.TICKER_MESSAGE:
            self.world['ticker_events'] = list(self.server._ticker_events)
            self.world['needs_redraw'] = True

    def send_command(self, cmd_type: CommandType, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch a command to the authoritative simulation server."""
        cmd = CommandMessage(cmd_type=cmd_type, payload=payload or {})
        res = self.server.execute_command(cmd)
        self.world['needs_redraw'] = True
        return res

    def step(self) -> int:
        """Request one simulation turn step."""
        res = self.send_command(CommandType.STEP)
        return res.get('turn', self.world['turn'])

    def toggle_play(self) -> bool:
        """Toggle simulation autoplay."""
        if self.server.playing:
            self.send_command(CommandType.PAUSE)
        else:
            self.send_command(CommandType.PLAY)
        self.world['playing'] = self.server.playing
        return self.world['playing']

    def reload_world(self, seed: Optional[int] = None, terrain_seed: Optional[int] = None,
                     nation_seed: Optional[int] = None):
        """Request full regeneration of the simulation world."""
        self.render_engine.invalidate_cache()
        self.send_command(CommandType.RELOAD_WORLD, {
            'seed': seed, 'terrain_seed': terrain_seed, 'nation_seed': nation_seed
        })
        self.world = self.server.get_world_dict()
        self._init_client_ui_state()
        reset_cam(self.world)
        self.render_engine.camera.sync_from_dict(self.world['cam'])

    def select_tile(self, tile):
        """Select a hex tile, update active nation, and open the build/governance drawer."""
        self.world['selected_region'] = tile
        if getattr(tile, 'owner_nation', None) is not None:
            self.world['selected_nation'] = tile.owner_nation
            self.world['player_nation_name'] = tile.owner_nation.name

        target_panel = self.world.get('last_left_panel', 'build')
        open_left_panel(self.world, target_panel)
        self.world['needs_redraw'] = True

    def render(self, surface: pygame.Surface, mouse_pos=None):
        """Render complete client frame: map viewport + UI panels."""
        from worldview import render_frame
        render_frame(surface, self.world, mouse_pos=mouse_pos)
        self.world['needs_redraw'] = False
