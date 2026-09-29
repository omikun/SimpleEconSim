"""
test_web_server.py — Comprehensive Unit & Integration Tests for Call of Capital Web Client & REST API.
"""

import sys
import os
import json
from io import BytesIO
import urllib.parse
import unittest

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sim_server.qr_code import QRCode, generate_terminal_qr, generate_svg_qr
from sim_server.sim_server import SimServer
from sim_server.web_server import RegnumHTTPRequestHandler, RegnumWebServer, get_local_ip


class MockRegnumServer:
    """Mock HTTP server context for dispatching requests without opening external sockets."""

    def __init__(self, sim_server: SimServer, base_url: str = "http://192.168.1.100:8080"):
        self.sim_server = sim_server
        self.base_url = base_url
        self.api_token = 'test-token'


class MockHttpRequestHandler(RegnumHTTPRequestHandler):
    """Executes RegnumHTTPRequestHandler methods in-memory using BytesIO streams."""

    def __init__(self, mock_server: MockRegnumServer, method: str, path: str,
                 headers: dict = None, body: bytes = b''):
        self.server = mock_server
        self.command = method
        self.path = path
        self.request_version = 'HTTP/1.1'
        self.requestline = f"{method} {path} HTTP/1.1"
        self.headers = headers or {}
        self.rfile = BytesIO(body)
        self.wfile = BytesIO()
        self._headers_buffer = []
        self.response_status = None
        self.response_headers = {}

        if method == 'GET':
            self.do_GET()
        elif method == 'POST':
            self.do_POST()
        elif method == 'OPTIONS':
            self.do_OPTIONS()

    def send_response(self, code, message=None):
        self.response_status = code
        super().send_response(code, message)

    def send_header(self, keyword, value):
        self.response_headers[keyword.lower()] = value
        super().send_header(keyword, value)

    def get_body(self) -> bytes:
        raw = self.wfile.getvalue()
        # Find header / body boundary
        boundary = b'\r\n\r\n'
        idx = raw.find(boundary)
        if idx != -1:
            return raw[idx + len(boundary):]
        return raw


class TestQRCodeGenerator(unittest.TestCase):
    """Test pure-Python dependency-free QR code generation."""

    def test_qr_matrix_dimensions(self):
        qr = QRCode("http://192.168.1.100:8080")
        self.assertIn(qr.version, [1, 2, 3, 4, 5, 6])
        self.assertEqual(len(qr.matrix), qr.size)
        self.assertEqual(len(qr.matrix[0]), qr.size)

    def test_qr_ansi_terminal_output(self):
        ansi_full = generate_terminal_qr("http://10.0.0.1:8080", style='full')
        self.assertIsInstance(ansi_full, str)
        self.assertIn("\033[47m", ansi_full)  # White background ANSI
        self.assertIn("\033[40m", ansi_full)  # Black background ANSI

        ansi_half = generate_terminal_qr("http://10.0.0.1:8080", style='half')
        self.assertIsInstance(ansi_half, str)
        self.assertIn("\033[47m", ansi_half)
        self.assertTrue(any(ch in ansi_half for ch in ("█", "▀", "▄")))

    def test_qr_svg_output(self):
        svg = generate_svg_qr("http://10.0.0.1:8080", size=240)
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn('<rect', svg)
        self.assertIn('viewBox="0 0 240 240"', svg)


class TestWebServerEndpoints(unittest.TestCase):
    """Test HTTP static file serving, REST API endpoints, and simulation state commands."""

    def setUp(self):
        self.sim = SimServer(seed=4242)
        self.mock_server = MockRegnumServer(self.sim)

    def test_local_ip_resolution(self):
        ip = get_local_ip()
        self.assertIsInstance(ip, str)
        parts = ip.split('.')
        self.assertEqual(len(parts), 4)

    def test_serve_index_html(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/')
        self.assertEqual(handler.response_status, 200)
        self.assertIn('text/html', handler.response_headers.get('content-type', ''))
        body = handler.get_body().decode('utf-8')
        self.assertIn('Call of Capital', body)
        self.assertIn('map-canvas', body)
        self.assertIn('drawer', body)
        self.assertIn('window.REGNUM_API_TOKEN="test-token"', body)

    def test_serve_css(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/style.css')
        self.assertEqual(handler.response_status, 200)
        self.assertIn('text/css', handler.response_headers.get('content-type', ''))
        body = handler.get_body().decode('utf-8')
        self.assertIn('--gold', body)
        self.assertIn('safe-area-inset-bottom', body)

    def test_serve_javascript(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/client.js')
        self.assertEqual(handler.response_status, 200)
        self.assertIn('javascript', handler.response_headers.get('content-type', ''))
        body = handler.get_body().decode('utf-8')
        self.assertIn('axialToPixel', body)
        self.assertIn('pixelToAxial', body)

    def test_serve_web_ui_utilities(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/ui_utils.js')
        self.assertEqual(handler.response_status, 200)
        self.assertIn('javascript', handler.response_headers.get('content-type', ''))
        body = handler.get_body().decode('utf-8')
        self.assertIn('RegnumUIUtils', body)
        self.assertIn('escapeHtml', body)

    def test_serve_state_sync_module(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/state_sync.js')
        self.assertEqual(handler.response_status, 200)
        self.assertIn('javascript', handler.response_headers.get('content-type', ''))
        body = handler.get_body().decode('utf-8')
        self.assertIn('RegnumStateSync', body)

    def test_serve_hex_geometry_module(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/hex_geometry.js')
        self.assertEqual(handler.response_status, 200)
        self.assertIn('javascript', handler.response_headers.get('content-type', ''))
        self.assertIn('RegnumHexGeometry', handler.get_body().decode('utf-8'))

    def test_get_qr_svg_endpoint(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/api/qr.svg')
        self.assertEqual(handler.response_status, 200)
        self.assertIn('image/svg+xml', handler.response_headers.get('content-type', ''))
        body = handler.get_body()
        self.assertTrue(body.startswith(b'<svg'))

    def test_api_world_state(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/api/state')
        self.assertEqual(handler.response_status, 200)
        self.assertIn('application/json', handler.response_headers.get('content-type', ''))
        data = json.loads(handler.get_body().decode('utf-8'))
        self.assertIn('turn', data)
        self.assertIn('playing', data)
        self.assertIn('tiles', data)
        self.assertIn('nations', data)
        self.assertEqual(data.get('lan_url'), "http://192.168.1.100:8080")
        self.assertGreater(len(data['tiles']), 0)
        self.assertGreater(len(data['nations']), 0)

        sample_tile = data['tiles'][0]
        self.assertIn('name', sample_tile)
        self.assertIn('q', sample_tile)
        self.assertIn('r', sample_tile)
        self.assertIn('biome', sample_tile)
        self.assertIn('elevation_meters', sample_tile)
        self.assertIn('tenure', sample_tile)
        self.assertIn('labor', sample_tile)

        # Verify all tiles have distinct (q, r) hex coordinates (not collapsed to 0, 0)
        coords = [(t['q'], t['r']) for t in data['tiles']]
        self.assertEqual(len(coords), len(set(coords)), "Every tile must have unique (q, r) coordinates!")
        self.assertGreater(len(set(coords)), 1)

        # Verify terrain bounds & coordinate layout for Approach A rendering
        self.assertIn('hex_size', data)
        self.assertEqual(data['hex_size'], 50.0)
        self.assertIn('bbox', data)
        self.assertEqual(len(data['bbox']), 4)
        self.assertIn('terrain_bounds', data)
        bounds = data['terrain_bounds']
        self.assertIn('min_x', bounds)
        self.assertIn('min_y', bounds)
        self.assertIn('width', bounds)
        self.assertIn('height', bounds)
        self.assertGreater(bounds['width'], 0)
        self.assertGreater(bounds['height'], 0)

    def test_compact_state_and_versioned_refresh(self):
        first = MockHttpRequestHandler(self.mock_server, 'GET', '/api/state?compact=1')
        self.assertEqual(first.response_status, 200)
        state = json.loads(first.get_body())
        self.assertIn('version', state)
        self.assertIn('population', state['tiles'][0])
        self.assertNotIn('citizens', state['tiles'][0])
        self.assertNotIn('charts', state['tiles'][0])

        unchanged = MockHttpRequestHandler(
            self.mock_server, 'GET', f"/api/state?compact=1&since={state['version']}"
        )
        self.assertEqual(unchanged.response_status, 304)
        self.assertEqual(unchanged.get_body(), b'')

        tile_name = urllib.parse.quote(state['tiles'][0]['name'])
        detail = MockHttpRequestHandler(self.mock_server, 'GET', f'/api/tile?name={tile_name}')
        self.assertEqual(detail.response_status, 200)
        self.assertIn('charts', json.loads(detail.get_body()))

        command_body = json.dumps({'cmd_type': 'PAUSE', 'payload': {}}).encode()
        command = MockHttpRequestHandler(
            self.mock_server, 'POST', '/api/command',
            headers={'Content-Length': str(len(command_body)), 'X-REGNUM-Token': 'test-token'}, body=command_body
        )
        self.assertEqual(command.response_status, 200)
        after_command = MockHttpRequestHandler(
            self.mock_server, 'GET', f"/api/state?compact=1&since={state['version']}"
        )
        self.assertEqual(after_command.response_status, 200)
        command_version = json.loads(after_command.get_body())['version']
        self.assertNotEqual(command_version, state['version'])

        self.sim.step()
        changed = MockHttpRequestHandler(
            self.mock_server, 'GET', f'/api/state?compact=1&since={command_version}'
        )
        self.assertEqual(changed.response_status, 200)
        self.assertNotEqual(json.loads(changed.get_body())['version'], command_version)

    def test_api_terrain_png(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/api/terrain.png')
        self.assertEqual(handler.response_status, 200)
        self.assertEqual(handler.response_headers.get('content-type'), 'image/png')
        body = handler.get_body()
        self.assertTrue(body.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertGreater(len(body), 1000)

    def test_api_terrain_jpg(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/api/terrain.jpg')
        self.assertEqual(handler.response_status, 200)
        self.assertEqual(handler.response_headers.get('content-type'), 'image/jpeg')
        body = handler.get_body()
        self.assertTrue(body.startswith(b'\xff\xd8'))
        self.assertGreater(len(body), 1000)

    def test_qr_pygame_surface(self):
        from sim_server.qr_code import generate_pygame_qr
        surf = generate_pygame_qr("http://10.0.0.1:8080", module_px=4)
        self.assertIsNotNone(surf)
        self.assertGreater(surf.get_width(), 100)
        self.assertEqual(surf.get_width(), surf.get_height())

    def test_api_single_tile_detail(self):
        tile_name = self.sim.tiles[0].name
        quoted = urllib.parse.quote(tile_name)
        handler = MockHttpRequestHandler(self.mock_server, 'GET', f'/api/tile?name={quoted}')
        self.assertEqual(handler.response_status, 200)
        data = json.loads(handler.get_body().decode('utf-8'))
        self.assertEqual(data['name'], tile_name)
        self.assertIn('tenure', data)
        self.assertIn('workhouse', data)
        self.assertIn('labor', data)

    def test_api_tile_missing_param(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/api/tile')
        self.assertEqual(handler.response_status, 400)

    def test_api_tile_not_found(self):
        handler = MockHttpRequestHandler(self.mock_server, 'GET', '/api/tile?name=NonExistentTile')
        self.assertEqual(handler.response_status, 404)

    def test_api_command_step(self):
        initial_turn = self.sim.turn
        body = json.dumps({'cmd_type': 'STEP'}).encode('utf-8')
        handler = MockHttpRequestHandler(self.mock_server, 'POST', '/api/command',
                                         headers={'Content-Length': len(body), 'X-REGNUM-Token': 'test-token'}, body=body)
        self.assertEqual(handler.response_status, 200)
        data = json.loads(handler.get_body().decode('utf-8'))
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('turn'), initial_turn + 1)
        self.assertEqual(self.sim.turn, initial_turn + 1)

    def test_api_command_play_pause(self):
        body = json.dumps({'cmd_type': 'PLAY'}).encode('utf-8')
        handler = MockHttpRequestHandler(self.mock_server, 'POST', '/api/command',
                                         headers={'Content-Length': len(body), 'X-REGNUM-Token': 'test-token'}, body=body)
        self.assertEqual(handler.response_status, 200)
        data = json.loads(handler.get_body().decode('utf-8'))
        self.assertTrue(data.get('playing'))
        self.assertTrue(self.sim.playing)

        body = json.dumps({'cmd_type': 'PAUSE'}).encode('utf-8')
        handler = MockHttpRequestHandler(self.mock_server, 'POST', '/api/command',
                                         headers={'Content-Length': len(body), 'X-REGNUM-Token': 'test-token'}, body=body)
        self.assertEqual(handler.response_status, 200)
        data = json.loads(handler.get_body().decode('utf-8'))
        self.assertFalse(data.get('playing'))
        self.assertFalse(self.sim.playing)

    def test_api_command_invalid(self):
        body = json.dumps({'cmd_type': 'INVALID_CMD'}).encode('utf-8')
        handler = MockHttpRequestHandler(self.mock_server, 'POST', '/api/command',
                                         headers={'Content-Length': len(body), 'X-REGNUM-Token': 'test-token'}, body=body)
        self.assertEqual(handler.response_status, 400)

    def test_api_command_requires_token(self):
        body = json.dumps({'cmd_type': 'STEP'}).encode('utf-8')
        handler = MockHttpRequestHandler(
            self.mock_server, 'POST', '/api/command',
            headers={'Content-Length': len(body)}, body=body,
        )
        self.assertEqual(handler.response_status, 403)
        self.assertEqual(self.sim.turn, 0)

    def test_api_command_rejects_non_object_payload(self):
        body = json.dumps({'cmd_type': 'STEP', 'payload': []}).encode('utf-8')
        handler = MockHttpRequestHandler(
            self.mock_server, 'POST', '/api/command',
            headers={'Content-Length': len(body), 'X-REGNUM-Token': 'test-token'}, body=body,
        )
        self.assertEqual(handler.response_status, 400)
        self.assertEqual(self.sim.turn, 0)

    def test_api_command_rejects_oversized_body(self):
        handler = MockHttpRequestHandler(
            self.mock_server, 'POST', '/api/command',
            headers={'Content-Length': str(1024 * 1024 + 1), 'X-REGNUM-Token': 'test-token'},
        )
        self.assertEqual(handler.response_status, 413)

    def test_api_command_reports_malformed_request_body(self):
        malformed_json = MockHttpRequestHandler(
            self.mock_server, 'POST', '/api/command',
            headers={'Content-Length': '1', 'X-REGNUM-Token': 'test-token'}, body=b'{',
        )
        self.assertEqual(malformed_json.response_status, 400)

        malformed_length = MockHttpRequestHandler(
            self.mock_server, 'POST', '/api/command',
            headers={'Content-Length': 'one', 'X-REGNUM-Token': 'test-token'}, body=b'',
        )
        self.assertEqual(malformed_length.response_status, 400)

    def test_api_does_not_enable_cross_origin_access(self):
        options = MockHttpRequestHandler(self.mock_server, 'OPTIONS', '/api/state')
        self.assertEqual(options.response_status, 405)
        self.assertNotIn('access-control-allow-origin', options.response_headers)

    def test_shutdown_get_is_disabled_and_post_requires_token(self):
        get_handler = MockHttpRequestHandler(self.mock_server, 'GET', '/api/shutdown')
        self.assertEqual(get_handler.response_status, 405)

        post_handler = MockHttpRequestHandler(self.mock_server, 'POST', '/api/shutdown')
        self.assertEqual(post_handler.response_status, 403)


if __name__ == '__main__':
    unittest.main()
