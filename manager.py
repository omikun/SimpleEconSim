#!/usr/bin/env python3
"""
manager.py — Root facade for Independent Web Control Panel.
"""
from client.web.manager_server import run_manager

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CoC & Mapgen Web Manager")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind (default 0.0.0.0)")
    args = parser.parse_args()
    run_manager(host=args.host, port=args.port)
