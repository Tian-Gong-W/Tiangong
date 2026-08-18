from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import ssl
import tempfile


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _flatten_name(value) -> str:
    parts: list[str] = []
    if not isinstance(value, (list, tuple)):
        return ""
    for rdn in value:
        if not isinstance(rdn, (list, tuple)):
            continue
        for item in rdn:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                parts.append(f"{item[0]}={item[1]}")
    return ", ".join(parts)


def _decode_der(der: bytes) -> dict:
    decoder = getattr(getattr(ssl, "_ssl", None), "_test_decode_cert", None)
    if decoder is None:
        return {}
    path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="ascii", suffix=".pem", delete=False) as handle:
            handle.write(ssl.DER_cert_to_PEM_cert(der))
            path = handle.name
        decoded = decoder(path)
        return decoded if isinstance(decoded, dict) else {}
    except (OSError, ssl.SSLError, ValueError):
        return {}
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def inspect_tls(host: str, port: int, timeout: int) -> int:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls_sock:
                der = tls_sock.getpeercert(binary_form=True) or b""
                decoded = _decode_der(der) if der else {}
                cipher = tls_sock.cipher()
                sans: list[str] = []
                raw_sans = decoded.get("subjectAltName", ())
                if isinstance(raw_sans, (list, tuple)):
                    for item in raw_sans[:128]:
                        if isinstance(item, (list, tuple)) and len(item) == 2:
                            kind, value = str(item[0]), str(item[1])
                            if kind in {"DNS", "IP Address"}:
                                sans.append(value[:255])
                _emit(
                    {
                        "type": "tls",
                        "host": host,
                        "port": port,
                        "version": tls_sock.version(),
                        "cipher": cipher[0] if cipher else None,
                        "cipher_bits": cipher[2] if cipher else None,
                        "fingerprint_sha256": hashlib.sha256(der).hexdigest() if der else None,
                        "subject": _flatten_name(decoded.get("subject")),
                        "issuer": _flatten_name(decoded.get("issuer")),
                        "serial_number": decoded.get("serialNumber"),
                        "not_before": decoded.get("notBefore"),
                        "not_after": decoded.get("notAfter"),
                        "sans": sorted(set(sans)),
                    }
                )
        return 0
    except (OSError, ssl.SSLError, TimeoutError) as exc:
        _emit({"type": "tls_error", "host": host, "port": port, "error": str(exc)[:400]})
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TONMEN bounded TLS certificate intelligence")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--timeout", type=int, default=8)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if not 1 <= args.timeout <= 20:
        parser.error("timeout must be between 1 and 20 seconds")
    return inspect_tls(args.host, args.port, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
