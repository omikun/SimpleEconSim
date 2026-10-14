"""
client/web — Web Client Services, Static Frontend Assets & HTTP/REST Server.
"""

from client.web.server import (
    CoCHTTPRequestHandler,
    CoCWebServer,
    run_web_server,
    get_local_ip,
    WEB_ASSETS_DIR,
)

__all__ = [
    'CoCHTTPRequestHandler',
    'CoCWebServer',
    'run_web_server',
    'get_local_ip',
    'WEB_ASSETS_DIR',
]
