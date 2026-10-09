#!/usr/bin/env python3
"""
manager_server.py — Independent Web Control Panel for CoC Game Server & Mapgen2 Web Server.

Provides a standalone web dashboard on port 8000 allowing users to:
  • Monitor live status (Running/Stopped, PID, port, uptime, memory)
  • Start / Stop / Restart the Call of Capital Game Web Server (:8081)
  • Start / Stop / Restart the Mapgen2 Explorer Web Server (:8080)
  • Inspect live log tails in real time
  • Quick-launch each service into a browser tab
"""

import os
import sys
import json
import time
import signal
import socket
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

PYTHON_BIN = os.path.join(PROJECT_ROOT, "venv", "bin", "python")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = sys.executable

SERVICES = {
    "game": {
        "name": "Call of Capital (CoC)",
        "subtitle": "Macroeconomic Simulation & 3D Voronoi Client",
        "default_port": 8081,
        "cmd": [PYTHON_BIN, "client/web/server.py", "--port", "8081"],
        "log_file": os.path.join(LOGS_DIR, "game_server.log"),
        "icon": "👑",
        "accent": "#f59e0b",
    },
    "mapgen": {
        "name": "Mapgen2 Terrain Explorer",
        "subtitle": "3D Micropoly Mesh & Geopolitical Map Viewer",
        "default_port": 8080,
        "cmd": [PYTHON_BIN, "mapgen_web.py", "--port", "8080", "--host", "0.0.0.0"],
        "log_file": os.path.join(LOGS_DIR, "mapgen_server.log"),
        "icon": "🗺️",
        "accent": "#3b82f6",
    },
}

# In-memory process tracking: service_key -> subprocess.Popen or external PID
PROCESSES = {}
PROCESS_LOCK = threading.Lock()
START_TIMES = {}


def find_pids_for_port(port: int) -> list[int]:
    """Find process IDs currently bound to the specified TCP port."""
    pids = []
    try:
        out = subprocess.check_output(["lsof", "-ti", f":{port}"], stderr=subprocess.DEVNULL).decode().strip()
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.append(int(line))
    except Exception:
        pass
    return pids


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Check if the given port is actively listening for TCP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def kill_pids(pids: list[int], force_after: float = 1.5):
    """Terminate given PIDs gracefully with SIGTERM, then SIGKILL if still running."""
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    t0 = time.time()
    while time.time() - t0 < force_after:
        alive = []
        for pid in pids:
            try:
                os.kill(pid, 0)
                alive.append(pid)
            except OSError:
                pass
        if not alive:
            return
        time.sleep(0.1)

    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def start_service(key: str) -> dict:
    with PROCESS_LOCK:
        spec = SERVICES.get(key)
        if not spec:
            return {"status": "error", "message": f"Unknown service '{key}'"}

        port = spec["default_port"]
        existing_pids = find_pids_for_port(port)
        if existing_pids:
            return {
                "status": "warning",
                "message": f"Service '{key}' is already running on port {port} (PID: {existing_pids})",
            }

        # Clear old log file
        log_path = spec["log_file"]
        log_file = open(log_path, "a", encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = PROJECT_ROOT
        env["MPLCONFIGDIR"] = "/tmp"
        env["SDL_AUDIODRIVER"] = "dummy"
        env["SDL_VIDEODRIVER"] = "dummy"

        try:
            proc = subprocess.Popen(
                spec["cmd"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )
            PROCESSES[key] = proc
            START_TIMES[key] = time.time()
        except Exception as e:
            return {"status": "error", "message": f"Failed to start service: {e}"}

        # Wait up to 1 second for early crashes
        time.sleep(0.5)
        if proc.poll() is not None:
            return {"status": "error", "message": f"Process exited immediately with code {proc.returncode}"}

        return {"status": "ok", "message": f"{spec['name']} started successfully", "pid": proc.pid, "port": port}


def stop_service(key: str) -> dict:
    with PROCESS_LOCK:
        spec = SERVICES.get(key)
        if not spec:
            return {"status": "error", "message": f"Unknown service '{key}'"}

        port = spec["default_port"]
        pids_on_port = find_pids_for_port(port)
        proc = PROCESSES.get(key)

        all_pids = set(pids_on_port)
        if proc and proc.pid:
            all_pids.add(proc.pid)

        if not all_pids:
            return {"status": "ok", "message": f"{spec['name']} is not running"}

        kill_pids(list(all_pids))
        PROCESSES.pop(key, None)
        START_TIMES.pop(key, None)

        return {"status": "ok", "message": f"{spec['name']} stopped"}


def restart_service(key: str) -> dict:
    stop_res = stop_service(key)
    time.sleep(0.5)
    start_res = start_service(key)
    return {
        "status": start_res.get("status", "ok"),
        "message": f"{SERVICES[key]['name']} restarted",
        "details": {"stop": stop_res, "start": start_res},
    }


def get_service_status(key: str) -> dict:
    spec = SERVICES.get(key)
    if not spec:
        return {}

    port = spec["default_port"]
    pids = find_pids_for_port(port)
    port_open = is_port_open(port)

    proc = PROCESSES.get(key)
    running = False
    active_pid = None

    if proc:
        poll_res = proc.poll()
        if poll_res is None:
            running = True
            active_pid = proc.pid
        else:
            PROCESSES.pop(key, None)

    if not running and pids:
        running = True
        active_pid = pids[0]

    uptime_sec = 0
    if running and key in START_TIMES:
        uptime_sec = int(time.time() - START_TIMES[key])

    return {
        "key": key,
        "name": spec["name"],
        "subtitle": spec["subtitle"],
        "port": port,
        "running": running,
        "port_listening": port_open,
        "pid": active_pid,
        "uptime": uptime_sec,
        "url": f"http://localhost:{port}",
        "icon": spec["icon"],
        "accent": spec["accent"],
    }


def get_logs(key: str, lines: int = 120) -> str:
    spec = SERVICES.get(key)
    if not spec:
        return ""
    log_file = spec["log_file"]
    if not os.path.exists(log_file):
        return f"(No log file generated yet at {log_file})"
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading logs: {e}"


# ---------------------------------------------------------------------------
# HTML Dashboard UI
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>CoC & Mapgen Server Manager</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #131c2e;
      --card-border: #1e293b;
      --accent: #3b82f6;
      --accent-glow: rgba(59, 130, 246, 0.25);
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      padding: 24px 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .container {
      width: 100%;
      max-width: 940px;
    }
    header {
      margin-bottom: 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 20px;
    }
    .title-group h1 {
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .title-group p {
      color: var(--text-muted);
      font-size: 14px;
      margin-top: 4px;
    }
    .global-actions {
      display: flex;
      gap: 8px;
    }
    button {
      cursor: pointer;
      border: none;
      font-weight: 600;
      font-size: 13px;
      border-radius: 8px;
      padding: 8px 14px;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .btn-primary { background: #2563eb; color: #fff; }
    .btn-primary:hover:not(:disabled) { background: #1d4ed8; }
    .btn-danger { background: #dc2626; color: #fff; }
    .btn-danger:hover:not(:disabled) { background: #b91c1c; }
    .btn-warning { background: #d97706; color: #fff; }
    .btn-warning:hover:not(:disabled) { background: #b45309; }
    .btn-secondary { background: #1e293b; color: #cbd5e1; }
    .btn-secondary:hover:not(:disabled) { background: #334155; }
    .btn-launch {
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: #fff;
      font-size: 14px;
      padding: 10px 18px;
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
      text-decoration: none;
      border-radius: 8px;
      font-weight: 700;
    }
    .btn-launch:hover {
      filter: brightness(1.1);
    }
    .cards-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 20px;
    }
    @media (min-width: 768px) {
      .cards-grid { grid-template-columns: 1fr 1fr; }
    }
    .server-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
      position: relative;
      overflow: hidden;
    }
    .server-card::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 4px;
      background: var(--server-accent, #3b82f6);
    }
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }
    .server-identity h2 {
      font-size: 19px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .server-identity p {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 3px;
    }
    .status-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .status-badge.online {
      background: rgba(16, 185, 129, 0.15);
      color: #10b981;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-badge.offline {
      background: rgba(239, 68, 68, 0.15);
      color: #ef4444;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
    }
    .status-badge.online .status-dot {
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
      animation: pulse 2s infinite;
    }
    .status-badge.offline .status-dot { background: #ef4444; }
    @keyframes pulse {
      0% { transform: scale(0.95); opacity: 0.8; }
      50% { transform: scale(1.2); opacity: 1; }
      100% { transform: scale(0.95); opacity: 0.8; }
    }
    .meta-row {
      display: flex;
      justify-content: space-between;
      background: rgba(0, 0, 0, 0.25);
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 12px;
      color: var(--text-muted);
    }
    .meta-row strong { color: var(--text); }
    .card-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .card-actions .btn-launch-container {
      width: 100%;
      margin-top: 4px;
    }
    .card-actions .btn-launch-container a {
      display: block;
      text-align: center;
    }
    .logs-panel {
      margin-top: 6px;
      border-top: 1px solid var(--card-border);
      padding-top: 14px;
    }
    .logs-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
    }
    .log-box {
      background: #060910;
      border: 1px solid #1e293b;
      border-radius: 6px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 11px;
      color: #94a3b8;
      padding: 10px;
      height: 140px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
      line-height: 1.45;
    }
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      color: #fff;
      padding: 12px 20px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      border: 1px solid #334155;
      display: none;
      z-index: 100;
    }
    footer {
      margin-top: 32px;
      color: var(--text-muted);
      font-size: 12px;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>⚙️ Server Control Center</h1>
        <p>Monitor, restart, and launch Call of Capital & Mapgen2 web servers</p>
      </div>
      <div class="global-actions">
        <button class="btn-primary" onclick="restartAll()">🔄 Restart Both</button>
        <button class="btn-danger" onclick="stopAll()">🛑 Stop Both</button>
      </div>
    </header>

    <div class="cards-grid" id="cardsGrid">
      <!-- Injected by JavaScript -->
    </div>

    <footer>
      Manager listening on port 8000 &bull; Auto-refreshing every 2s
    </footer>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    /*__INITIAL_DATA__*/
    let statusData = (typeof INITIAL_STATUS !== 'undefined') ? INITIAL_STATUS : {};
    let isActionInProgress = false;

    // Synchronously render initial status without waiting for network fetch
    if (Object.keys(statusData).length > 0) {
      renderCards();
      if (typeof INITIAL_LOGS !== 'undefined') {
        for (const [k, text] of Object.entries(INITIAL_LOGS)) {
          const el = document.getElementById(`log-${k}`);
          if (el) { el.innerText = text; el.scrollTop = el.scrollHeight; }
        }
      }
    }

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      toast.innerText = msg;
      toast.style.borderColor = isError ? '#ef4444' : '#10b981';
      toast.style.display = 'block';
      setTimeout(() => { toast.style.display = 'none'; }, 2800);
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        statusData = data;
        renderCards();
      } catch (e) {
        console.error('Fetch status error', e);
      }
    }

    async function executeAction(action, service) {
      if (isActionInProgress) return;
      isActionInProgress = true;
      document.querySelectorAll('button').forEach(b => b.disabled = true);
      showToast(`${action.toUpperCase()} requested for ${service}...`);

      try {
        const res = await fetch(`/api/${action}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ service })
        });
        const out = await res.json();
        showToast(out.message || 'Action executed successfully', out.status === 'error');
      } catch (err) {
        showToast('Action failed: ' + err, true);
      } finally {
        setTimeout(async () => {
          await fetchStatus();
          isActionInProgress = false;
          document.querySelectorAll('button').forEach(b => b.disabled = false);
        }, 600);
      }
    }

    async function restartAll() {
      await executeAction('restart', 'game');
      await executeAction('restart', 'mapgen');
    }

    async function stopAll() {
      await executeAction('stop', 'game');
      await executeAction('stop', 'mapgen');
    }

    function formatUptime(seconds) {
      if (!seconds) return '—';
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      if (m < 60) return `${m}m ${s}s`;
      const h = Math.floor(m / 60);
      return `${h}h ${m % 60}m`;
    }

    function renderCards() {
      const container = document.getElementById('cardsGrid');
      const services = Object.values(statusData);

      container.innerHTML = services.map(svc => {
        const isOnline = svc.running;
        const statusBadge = isOnline
          ? `<div class="status-badge online"><div class="status-dot"></div> Online</div>`
          : `<div class="status-badge offline"><div class="status-dot"></div> Stopped</div>`;

        return `
          <div class="server-card" style="--server-accent: ${svc.accent};">
            <div class="card-top">
              <div class="server-identity">
                <h2>${svc.icon} ${svc.name}</h2>
                <p>${svc.subtitle}</p>
              </div>
              ${statusBadge}
            </div>

            <div class="meta-row">
              <div>Port: <strong>:${svc.port}</strong></div>
              <div>PID: <strong>${svc.pid || '—'}</strong></div>
              <div>Uptime: <strong>${formatUptime(svc.uptime)}</strong></div>
            </div>

            <div class="card-actions">
              ${isOnline
                ? `<button class="btn-warning" onclick="executeAction('restart', '${svc.key}')">🔄 Restart</button>
                   <button class="btn-danger" onclick="executeAction('stop', '${svc.key}')">🛑 Stop</button>`
                : `<button class="btn-primary" onclick="executeAction('start', '${svc.key}')">🚀 Launch</button>`
              }
              <button class="btn-secondary" onclick="refreshLog('${svc.key}')">📄 Reload Log</button>
              
              <div class="btn-launch-container">
                <a href="${svc.url}" target="_blank" class="btn-launch" style="background: ${isOnline ? '' : '#475569; pointer-events: none; opacity: 0.6;'}">
                  👉 Open in Browser (${svc.url})
                </a>
              </div>
            </div>

            <div class="logs-panel">
              <div class="logs-header">
                <span>Recent Console Output</span>
              </div>
              <div class="log-box" id="log-${svc.key}">Loading console log...</div>
            </div>
          </div>
        `;
      }).join('');

      services.forEach(svc => refreshLog(svc.key));
    }

    async function refreshLog(key) {
      try {
        const res = await fetch(`/api/logs?service=${key}&lines=100`);
        if (res.ok) {
          const text = await res.text();
          const el = document.getElementById(`log-${key}`);
          if (el) {
            el.innerText = text || '(No log entries yet)';
            el.scrollTop = el.scrollHeight;
          }
        }
      } catch (e) {}
    }

    // Initial load & periodic polling
    fetchStatus();
    setInterval(fetchStatus, 2500);
  </script>
</body>
</html>
"""


class ManagerHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default access logging to avoid spamming
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            status = {k: get_service_status(k) for k in SERVICES}
            logs = {k: get_logs(k, lines=30) for k in SERVICES}
            data_injection = (
                f"const INITIAL_STATUS = {json.dumps(status)};\n"
                f"    const INITIAL_LOGS = {json.dumps(logs)};"
            )
            html = DASHBOARD_HTML.replace("/*__INITIAL_DATA__*/", data_injection)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/status":
            res = {}
            for k in SERVICES:
                res[k] = get_service_status(k)
            body = json.dumps(res).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/logs":
            service = query.get("service", ["game"])[0]
            lines = int(query.get("lines", [100])[0])
            content = get_logs(service, lines=lines).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}

        service = data.get("service")

        if path == "/api/start":
            res = start_service(service)
        elif path == "/api/stop":
            res = stop_service(service)
        elif path == "/api/restart":
            res = restart_service(service)
        else:
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps(res).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_manager(host: str = "0.0.0.0", port: int = 8000):
    server = HTTPServer((host, port), ManagerHTTPRequestHandler)
    print("\n" + "=" * 62)
    print("  👑 CALL OF CAPITAL & MAPGEN2 CONTROL MANAGER ONLINE")
    print("=" * 62)
    print(f"  👉 Visit Dashboard: http://localhost:{port}")
    print(f"  👉 On your iPhone : http://127.0.0.1:{port}")
    print("=" * 62)
    print("  Manage both servers interactively (Start / Stop / Restart)\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Manager...")
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CoC & Mapgen Web Manager")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind (default 0.0.0.0)")
    args = parser.parse_args()

    run_manager(host=args.host, port=args.port)
