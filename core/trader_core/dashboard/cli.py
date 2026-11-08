"""CLI Launcher for Dalal Street Decision Deck Dashboard.

Usage:
    python3 -m trader_core.dashboard [--port PORT] [--host HOST] [--no-open] [--offline]
    python3 trader/dashboard.py [--port PORT] [--host HOST] [--no-open] [--offline]
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .server import run_server


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments for the dashboard server."""
    parser = argparse.ArgumentParser(
        description="Dalal Street Pro: Decision-First Trading Dashboard"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="HTTP server port to bind (default: 8050)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not automatically open the browser on launch",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run in offline research mode using local cached files",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in sandbox demo mode with sample technical and fundamental data",
    )
    return parser.parse_args(args)


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    args = parse_args(argv)
    run_server(
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
        offline=args.offline,
        demo=args.demo,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
