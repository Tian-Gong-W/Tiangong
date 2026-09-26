from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import cli as legacy_cli
from .core.config import TonmenConfig
from .dashboard import serve_dashboard
from .workers import serve_worker


def _is_named_invocation(argv: list[str], name: str) -> bool:
    if not argv:
        return False
    if argv[0] == name:
        return True
    return len(argv) >= 3 and argv[0] == "--config" and argv[2] == name


def _is_console_invocation(argv: list[str]) -> bool:
    return _is_named_invocation(argv, "console")


def _is_worker_invocation(argv: list[str]) -> bool:
    return _is_named_invocation(argv, "worker")


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


def _worker_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="tonmen")
    parser.add_argument("--config", type=Path, help="worker project config path (scope is enforced locally)")
    sub = parser.add_subparsers(dest="command", required=True)
    worker = sub.add_parser("worker", help="launch a governed TONMEN execution worker")
    worker.add_argument("--id", required=True, help="stable worker id, e.g. uae-1")
    worker.add_argument("--host", default="127.0.0.1", help="bind host; remote bind requires --allow-remote-bind")
    worker.add_argument("--port", type=int, default=8890)
    worker.add_argument("--region", default="default")
    worker.add_argument("--tags", default="", help="comma-separated routing tags")
    worker.add_argument("--max-concurrency", type=int, default=int(os.getenv("TONMEN_WORKER_MAX_CONCURRENCY", "4") or "4"), help="hard worker execution concurrency limit (1-64)")
    worker.add_argument("--secret-env", default="TONMEN_WORKER_SECRET", help="environment variable holding >=32-byte shared secret")
    worker.add_argument("--allow-remote-bind", action="store_true", help="allow a specific non-loopback bind address; never allows 0.0.0.0/::")
    args = parser.parse_args(argv)

    try:
        config = TonmenConfig.default(args.config)
        secret = os.getenv(args.secret_env, "")
        tags = tuple(item.strip().lower() for item in args.tags.split(",") if item.strip())
        return serve_worker(
            config,
            worker_id=args.id,
            secret=secret,
            host=args.host,
            port=args.port,
            region=args.region,
            tags=tags,
            max_concurrency=args.max_concurrency,
            allow_remote_bind=args.allow_remote_bind,
        )
    except (OSError, ValueError) as exc:
        print(f"TONMEN Worker 拒絕: {exc}")
        return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if _is_console_invocation(args):
        return _console_main(args)
    if _is_worker_invocation(args):
        return _worker_main(args)
    return legacy_cli.main(args)
