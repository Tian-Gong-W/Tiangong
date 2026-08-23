from __future__ import annotations

import argparse
import ipaddress
import json
import socket


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def resolve(host: str) -> int:
    addresses: set[tuple[str, str]] = set()
    try:
        rows = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        _emit(
            {
                "type": "dns",
                "host": host,
                "record_type": "STATUS",
                "resolved": False,
                "error": str(exc)[:400],
            }
        )
        _emit({"type": "summary", "host": host, "addresses": 0, "resolved": False})
        return 0

    for row in rows:
        address = row[4][0]
        try:
            version = ipaddress.ip_address(address).version
        except ValueError:
            continue
        record_type = "A" if version == 4 else "AAAA"
        addresses.add((record_type, address))

    canonical = socket.getfqdn(host)
    for record_type, address in sorted(addresses):
        reverse = None
        try:
            reverse = socket.gethostbyaddr(address)[0]
        except (socket.herror, socket.gaierror, OSError):
            pass
        _emit(
            {
                "type": "dns",
                "host": host,
                "record_type": record_type,
                "address": address,
                "canonical_name": canonical if canonical and canonical != host else None,
                "reverse_name": reverse,
                "resolved": True,
            }
        )

    _emit(
        {
            "type": "summary",
            "host": host,
            "addresses": len(addresses),
            "canonical_name": canonical if canonical and canonical != host else None,
            "resolved": bool(addresses),
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TONMEN bounded DNS identity resolver")
    parser.add_argument("--host", required=True)
    args = parser.parse_args(argv)
    return resolve(args.host)


if __name__ == "__main__":
    raise SystemExit(main())
