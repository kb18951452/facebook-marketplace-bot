"""
map_server.py — Local HTTP server for the listings map dashboard.

Serves listings_map.html with live bot controls:
  GET  /              -> regenerate map and serve HTML
  GET  /api/status    -> JSON: next_run, last_run, running, last_log
  GET  /api/markers   -> regenerate + return markers/uncovered/stats JSON
  GET  /api/live      -> parse log: what's publishing right now + recent posts
  POST /api/run/agent -> trigger run_daily_agent.bat
  POST /api/run/stats -> trigger run_stats_tracker.bat

Usage:
    python map_server.py           # serves on http://localhost:8080
    python map_server.py --port 9000 --no-open
"""

import argparse
import json
import os
import re
import subprocess
import sys
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8080


# ── Task Scheduler helpers ────────────────────────────────────────────────────

def _schtasks_bot_tasks():
    """Return list of dicts for all FacebookMarketplaceBot_*_Run* tasks."""
    try:
        r = subprocess.run(
            ["schtasks", "/query", "/fo", "LIST", "/v"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace"
        )
        tasks, cur = [], {}
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("TaskName:"):
                if cur.get("name") and "FacebookMarketplaceBot" in cur["name"]:
                    tasks.append(cur)
                name = line.split(":", 1)[1].strip()
                cur = {"name": name} if "FacebookMarketplaceBot" in name else {}
            elif cur:
                if line.startswith("Next Run Time:"):
                    cur["next_run"] = line.split(":", 1)[1].strip()
                elif line.startswith("Last Run Time:"):
                    cur["last_run"] = line.split(":", 1)[1].strip()
                elif line.startswith("Status:"):
                    cur["status"] = line.split(":", 1)[1].strip()
        if cur.get("name") and "FacebookMarketplaceBot" in cur["name"]:
            tasks.append(cur)
        return tasks
    except Exception:
        return []


def _parse_ts(s):
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y %I:%M:%S %p")
    except Exception:
        return None


def _get_next_run(tasks):
    now = datetime.now()
    soonest = None
    for t in tasks:
        if "_Run" not in t.get("name", ""):
            continue
        nr = t.get("next_run", "")
        if not nr or "N/A" in nr:
            continue
        dt = _parse_ts(nr)
        if dt and dt > now and (soonest is None or dt < soonest):
            soonest = dt
    return soonest.strftime("%a %m/%d %I:%M %p") if soonest else None


def _get_last_run(tasks):
    latest = None
    for t in tasks:
        if "_Run" not in t.get("name", ""):
            continue
        lr = t.get("last_run", "")
        if not lr or "N/A" in lr:
            continue
        dt = _parse_ts(lr)
        if dt and (latest is None or dt > latest):
            latest = dt
    return latest.strftime("%a %m/%d %I:%M %p") if latest else None


def _is_agent_running():
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "CommandLine"],
            capture_output=True, text=True, timeout=8
        )
        return "daily_agent.py" in r.stdout or "stats_tracker.py" in r.stdout
    except Exception:
        return False


def _last_log_line():
    log_path = os.path.join(BASE_DIR, "listing_progress.log")
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [l.rstrip() for l in f if l.strip()]
        return lines[-1] if lines else None
    except Exception:
        return None


def _parse_live():
    """Parse the log for what the agent is currently posting and recent posts."""
    log_path = os.path.join(BASE_DIR, "listing_progress.log")
    publishing = None
    recent = []
    phase = None
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in lines[-150:]:
            line = line.strip()
            m = re.search(r"(\d{2}:\d{2}:\d{2}).*Publishing slot '([^']+)': (.+)$", line)
            if m:
                slot  = m.group(2)
                parts = slot.split("_")
                publishing = {
                    "slot":  slot,
                    "title": m.group(3),
                    "city":  parts[1] if len(parts) > 1 else "",
                    "equip": parts[0],
                    "ts":    m.group(1),
                }
                recent.append(publishing.copy())
            else:
                pm = re.search(r"Phase (\S+)", line)
                if pm:
                    phase = pm.group(1).rstrip(".")
                if "Agent run complete" in line or "Session window closing" in line:
                    phase = "done"
    except Exception:
        pass

    running = _is_agent_running()
    return {
        "running":    running,
        "publishing": publishing if running else None,
        "recent":     recent[-6:],
        "phase":      phase,
    }


def _regenerate_map():
    subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, "map_listings.py")],
        cwd=BASE_DIR, timeout=30, capture_output=True
    )


# ── HTTP handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default request logging

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body, status=200):
        enc = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(enc)))
        self.end_headers()
        self.wfile.write(enc)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path in ("/", "/index.html"):
            _regenerate_map()
            html_path = os.path.join(BASE_DIR, "listings_map.html")
            try:
                with open(html_path, "r", encoding="utf-8") as f:
                    self._send_html(f.read())
            except Exception as e:
                self._send_html(f"<h1>Error loading map: {e}</h1>", 500)

        elif path == "/api/status":
            tasks = _schtasks_bot_tasks()
            self._send_json({
                "running":  _is_agent_running(),
                "next_run": _get_next_run(tasks),
                "last_run": _get_last_run(tasks),
                "last_log": _last_log_line(),
            })

        elif path == "/api/live":
            self._send_json(_parse_live())

        elif path == "/api/markers":
            _regenerate_map()
            data_path = os.path.join(BASE_DIR, "listings_data.json")
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    self._send_json(json.load(f))
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/run/agent":
            bat = os.path.join(BASE_DIR, "run_daily_agent.bat")
            try:
                subprocess.Popen(
                    ["cmd", "/c", bat],
                    cwd=BASE_DIR,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                self._send_json({"ok": True, "message": "Agent started in new console window."})
            except Exception as e:
                self._send_json({"ok": False, "message": str(e)}, 500)

        elif path == "/api/run/competitors":
            script = os.path.join(BASE_DIR, "competitor_scraper.py")
            try:
                subprocess.Popen(
                    [sys.executable, script],
                    cwd=BASE_DIR,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                self._send_json({"ok": True, "message": "Competitor scraper started."})
            except Exception as e:
                self._send_json({"ok": False, "message": str(e)}, 500)

        elif path == "/api/run/stats":
            bat = os.path.join(BASE_DIR, "run_stats_tracker.bat")
            try:
                subprocess.Popen(
                    ["cmd", "/c", bat],
                    cwd=BASE_DIR,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                self._send_json({"ok": True, "message": "Stats tracker started in new console window."})
            except Exception as e:
                self._send_json({"ok": False, "message": str(e)}, 500)

        else:
            self.send_response(404)
            self.end_headers()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Listings map dashboard server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    server = HTTPServer(("localhost", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"Listings map server: {url}")
    print("Ctrl+C to stop.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
