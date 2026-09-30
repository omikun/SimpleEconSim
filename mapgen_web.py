"""
mapgen_web.py — High-Performance Mobile-Ready Web Server for Mapgen2 Terrain Explorer.

Facade module re-exporting from client.web.mapgen_server.
"""

from client.web.mapgen_server import *

if __name__ == '__main__':
    from client.web.mapgen_server import main
    main()
