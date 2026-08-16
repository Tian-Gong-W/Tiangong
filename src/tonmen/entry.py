from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import cli as legacy_cli
from .core.config import TonmenConfig
from .dashboard import serve_dashboard


def _is_console_invocation(argv: list[str]) -> bool:
    if not argv:
        return False
    if argv[0] == "console":
        return True
    return len(argv) >= 3 and argv[0] == "--config" and argv[2] == "console"


def _console_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="tonmen")
    parser.add_argument("--config", type=Path, help="project config path (default: ./tonmen.toml)")
    sub = parser.add_subparsers(dest="command", required=True)
    console = sub.add_parser("console", help="launch the local TONMEN web control panel")
    console.add_argument("--port", type=int, help="local loopback port (default: config bind_port / 8888)")
    console.add_argument("--no-open", action="store_true", help="do not open a browser automatically")
    args = parser.parse_args(argv)

    try:
        config = TonmenConfig.default(args.config)
        return serve_dashboard(config, host="127.0.0.1", port=args.port, open_browser=not args.no_open)
    except (OSError, ValueError) as exc:
        print(f"天宮 Console 拒絕: {exc}")
        return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if _is_console_invocation(args):
        return _console_main(args)
    return legacy_cli.main(args)
