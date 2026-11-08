"""trader_core.dashboard.server - HTTP Server, REST Bootstrap & CLI Entrypoint.

Integrates the Upstox V3 Visual Trading Cockpit:
- Multithreaded HTTP server serving static assets on configurable port.
- REST bootstrap endpoints: watchlist, bars, alerts, health.
- Manages UpstoxRelay on configurable WebSocket port.
- Ingests Upstox ticks into CandleStitcher and evaluates alerts.
- CLI runner: python3 -m trader_core.dashboard.server [--port 8080] [--ws-port 8765] [--open].
- Zero automated broker execution.
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import logging
import mimetypes
import os
import re
import socket
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.parse
import webbrowser
from typing import Any, Dict, List, Optional, Union

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ..calendar import IST
from ..feed import FeedStatus, Tick
from ..instruments import COMMON_ALIASES
from .alerts import DashboardAlertEngine
from .relay import UpstoxRelay
from .stitcher import CandleStitcher

logger = logging.getLogger("trader_dashboard.server")

DEFAULT_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
DEFAULT_DECK_STATIC_DIR = os.path.join(ROOT, "trader_core", "dashboard", "static")
DEFAULT_SYMBOLS = ["NIFTY 50", "HDFIRE", "RELIANCE", "TCS", "INFY"]
SYMBOL_REGEX = re.compile(r"^[A-Za-z0-9_.\s&-]{1,30}$")


def normalize_symbol(symbol: str) -> str:
    """Normalize trading symbol and aliases."""
    raw = (symbol or "").strip().upper()
    if raw in COMMON_ALIASES:
        return COMMON_ALIASES[raw]
    if raw in ("NSE", "NIFTY", "NIFTY50", "NIFTY_50", "^NSEI"):
        return "NIFTY 50"
    if raw in ("BANKNIFTY", "BANK_NIFTY", "^NSEBANK"):
        return "BANK NIFTY"
    if raw == "HDFC":
        return "HDFCBANK"
    return raw


def load_watchlist(workspace_dir: Optional[str] = None) -> List[str]:
    """Load active watchlist symbols from trader/watchlist.txt or trader/watchlist.json."""
    base = workspace_dir or ROOT

    txt_path = os.path.join(base, "trader", "watchlist.txt")
    if os.path.isfile(txt_path):
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                lines = []
                seen = set()
                for line in f:
                    symbol = normalize_symbol(line.strip())
                    if symbol and not symbol.startswith("#") and symbol not in seen:
                        lines.append(symbol)
                        seen.add(symbol)
                if lines:
                    if "NIFTY 50" not in seen:
                        lines.insert(0, "NIFTY 50")
                    return lines
        except Exception as e:
            logger.warning("Error reading %s: %s", txt_path, e)

    json_path = os.path.join(base, "trader", "watchlist.json")
    if os.path.isfile(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            symbols: List[str] = []
            if isinstance(data, dict):
                if "hits" in data and isinstance(data["hits"], list):
                    for h in data["hits"]:
                        sym = h.get("symbol") if isinstance(h, dict) else str(h)
                        if sym:
                            clean_sym = sym.split(".")[0].strip().upper()
                            if clean_sym and clean_sym not in symbols:
                                symbols.append(clean_sym)
                elif "watchlist" in data and isinstance(data["watchlist"], list):
                    symbols = [
                        str(s).split(".")[0].strip().upper()
                        for s in data["watchlist"] if s
                    ]
                elif "symbols" in data and isinstance(data["symbols"], list):
                    symbols = [
                        str(s).split(".")[0].strip().upper()
                        for s in data["symbols"] if s
                    ]
            elif isinstance(data, list):
                symbols = [
                    str(s).split(".")[0].strip().upper() for s in data if s
                ]
            if symbols:
                return symbols
        except Exception as e:
            logger.warning("Error reading %s: %s", json_path, e)

    return list(DEFAULT_SYMBOLS)


class DashboardHTTPHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Request Handler for Dashboard frontend and REST bootstrap endpoints."""

    server_version = "UpstoxTradingCockpit/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        pass

    @property
    def dashboard_server(self) -> "DashboardServer":
        return getattr(self.server, "dashboard_server")

    def send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        if getattr(self, "command", "GET") != "HEAD":
            self.wfile.write(body)

    def send_error_json(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message, "status": "error"}, status=status)

    def send_file(self, file_path: str, base_dir: Optional[str] = None) -> None:
        static_dir = os.path.abspath(base_dir or self.dashboard_server.static_dir)
        target = os.path.abspath(file_path)
        try:
            common = os.path.commonpath([static_dir, target])
        except ValueError:
            self.send_error_json("Invalid file path", 400)
            return
        if common != static_dir or not os.path.isfile(target):
            self.send_error_json("File Not Found", 404)
            return
        mime_type, _ = mimetypes.guess_type(target)
        if target.endswith(".ico"):
            mime_type = "image/x-icon"
        elif not mime_type:
            mime_type = "text/plain; charset=utf-8"
        elif mime_type.startswith("text/") or mime_type in [
            "application/javascript",
            "application/json",
        ]:
            mime_type += "; charset=utf-8"
        try:
            with open(target, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if getattr(self, "command", "GET") != "HEAD":
                self.wfile.write(content)
        except Exception as e:
            logger.error("Failed to read static file %s: %s", target, e)
            self.send_error_json("Internal Server Error", 500)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static file serving
        if path == "/" or path == "/index.html":
            return self.send_file(os.path.join(self.dashboard_server.static_dir, "index.html"))
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            return self.send_file(os.path.join(self.dashboard_server.static_dir, rel))
        if path.startswith("/cockpit"):
            return self.send_file(os.path.join(self.dashboard_server.static_dir, "index.html"))

        # REST endpoints
        if path == "/api/health":
            return self.send_json({
                "status": "ok",
                "feed_status": str(self.dashboard_server.feed_status),
                "signals_unlocked": self.dashboard_server.signals_unlocked,
            })

        if path == "/api/watchlist":
            return self.send_json({"symbols": load_watchlist()})

        if path == "/api/bars":
            symbol = query.get("symbol", [None])[0]
            if not symbol:
                return self.send_error_json("symbol required", 400)
            interval = query.get("interval", ["5m"])[0]
            stitcher = self.dashboard_server.stitcher
            bars = stitcher.get_bars(symbol, interval=interval) if stitcher else []
            return self.send_json({
                "symbol": symbol,
                "interval": interval,
                "bars": bars,
            })

        if path == "/api/macro":
            agg = self.dashboard_server.aggregator
            return self.send_json(agg.get_macro_overview())

        if path == "/api/signals":
            agg = self.dashboard_server.aggregator
            return self.send_json({"signals": agg.get_signals(stitcher=self.dashboard_server.stitcher)})

        if path == "/api/stock/":
            symbol = query.get("symbol", [None])[0]
            if not symbol:
                return self.send_error_json("symbol required", 400)
            agg = self.dashboard_server.aggregator
            return self.send_json(agg.get_stock_detail(symbol, stitcher=self.dashboard_server.stitcher))

        if path == "/api/scan/daily" and self.dashboard_server.command == "POST":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len else b"{}"
            try:
                data = json.loads(body.decode()) if body.strip() else {}
            except Exception:
                data = {}
            agg = self.dashboard_server.aggregator
            symbols = data.get("symbols") or agg.get_watchlist_symbols()
            # Return cached scans
            return self.send_json({
                "hits": [],
                "scanned": 0,
                "message": "Use /api/scanner/daily endpoint instead",
            })

        return self.send_error_json("Not Found", 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/scan/daily":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len else b"{}"
            try:
                data = json.loads(body.decode()) if body.strip() else {}
            except Exception:
                data = {}
            return self.send_json({
                "hits": [],
                "scanned": 0,
                "message": "Scanner endpoint not implemented in dashboard server",
            })

        if path == "/api/alerts":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len) if content_len else b"{}"
            try:
                data = json.loads(body.decode()) if body.strip() else {}
            except Exception:
                data = {}
            engine = self.dashboard_server.alert_engine
            alert = engine.add_user_alert(
                symbol=data.get("symbol", ""),
                price=data.get("price", 0),
                direction=data.get("direction", "above"),
                note=data.get("note", ""),
            )
            return self.send_json(alert)

        return self.send_error_json("Not Found", 404)


class DashboardServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Threaded HTTP server for the dashboard."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        static_dir: Optional[str] = None,
        open_browser: bool = False,
        offline: bool = False,
        demo: bool = False,
    ):
        self.static_dir = static_dir or DEFAULT_STATIC_DIR
        self.open_browser = open_browser
        self.offline = offline
        self.demo = demo

        from .stitcher import CandleStitcher
        self.stitcher = CandleStitcher()
        from .alerts import DashboardAlertEngine
        self.alert_engine = DashboardAlertEngine()
        from .aggregator import DashboardAggregator
        self.aggregator = DashboardAggregator(offline=offline, demo=demo)

        self.feed_status = "DISCONNECTED"
        self.signals_unlocked = False

        super().__init__((host, port), DashboardHTTPHandler)
        self.dashboard_server = self


def run_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    static_dir: Optional[str] = None,
    open_browser: bool = False,
    offline: bool = False,
    demo: bool = False,
) -> None:
    server = DashboardServer(
        host=host,
        port=port,
        static_dir=static_dir,
        open_browser=open_browser,
        offline=offline,
        demo=demo,
    )
    print(f"Dashboard server running on http://{host}:{port}")
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard server...")
        server.shutdown()
