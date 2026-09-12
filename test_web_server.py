"""
test_web_server.py — Comprehensive Unit & Integration Tests for REGNUM Web Client & REST API.
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
        self.assertIn('REGNUM Mobile', body)
        self.assertIn('map-canvas', body)
        self.assertIn('drawer', body)

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
                                         headers={'Content-Length': len(body)}, body=body)
        self.assertEqual(handler.response_status, 200)
        data = json.loads(handler.get_body().decode('utf-8'))
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('turn'), initial_turn + 1)
        self.assertEqual(self.sim.turn, initial_turn + 1)

    def test_api_command_play_pause(self):
        body = json.dumps({'cmd_type': 'PLAY'}).encode('utf-8')
        handler = MockHttpRequestHandler(self.mock_server, 'POST', '/api/command',
                                         headers={'Content-Length': len(body)}, body=body)
        self.assertEqual(handler.response_status, 200)
        data = json.loads(handler.get_body().decode('utf-8'))
        self.assertTrue(data.get('playing'))
        self.assertTrue(self.sim.playing)

        body = json.dumps({'cmd_type': 'PAUSE'}).encode('utf-8')
        handler = MockHttpRequestHandler(self.mock_server, 'POST', '/api/command',
                                         headers={'Content-Length': len(body)}, body=body)
        self.assertEqual(handler.response_status, 200)
        data = json.loads(handler.get_body().decode('utf-8'))
        self.assertFalse(data.get('playing'))
        self.assertFalse(self.sim.playing)

    def test_api_command_invalid(self):
        body = json.dumps({'cmd_type': 'INVALID_CMD'}).encode('utf-8')
        handler = MockHttpRequestHandler(self.mock_server, 'POST', '/api/command',
                                         headers={'Content-Length': len(body)}, body=body)
        self.assertEqual(handler.response_status, 400)


if __name__ == '__main__':
    unittest.main()
