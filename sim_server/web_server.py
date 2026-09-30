"""
sim_server/web_server.py — Pure-Python HTTP & REST Server for REGNUM Web Client.

Facade module re-exporting from client.web.
"""

from client.web.server import (
    RegnumHTTPRequestHandler,
    RegnumWebServer,
    run_web_server,
    get_local_ip,
    WEB_ASSETS_DIR,
)

if __name__ == '__main__':
    run_web_server()
