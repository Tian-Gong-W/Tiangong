from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urldefrag, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

_USER_AGENT = "TONMEN/0.4 governed-api-intel"
_MAX_ENTRY_BYTES = 524_288
_MAX_ENDPOINTS = 128
_STATIC_SUFFIXES = (
    ".css", ".gif", ".ico", ".jpeg", ".jpg", ".map", ".png", ".svg", ".webp", ".woff", ".woff2",
)
_QUOTED_ENDPOINT = re.compile(
    r"(?P<quote>['\"])(?P<value>(?:https?://[^'\"\\\s]+|/(?:api|graphql|rest|rpc|v[0-9]+)(?:/[^'\"\\\s]*)?))(?P=quote)",
    re.IGNORECASE,
)
_HINTS = ("graphql", "openapi", "swagger")


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.script_sources: list[str] = []
        self.inline_scripts: list[str] = []
        self._in_script = False
        self._script_has_src = False
        self._inline_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "script":
            return
        self._in_script = True
        self._script_has_src = False
        self._inline_parts = []
        for key, value in attrs:
            if key.lower() == "src" and value:
                self.script_sources.append(str(value))
                self._script_has_src = True
                break

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "script" or not self._in_script:
            return
        if not self._script_has_src and self._inline_parts:
            text = "".join(self._inline_parts).strip()
            if text:
                self.inline_scripts.append(text)
        self._in_script = False
        self._script_has_src = False
        self._inline_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_script and not self._script_has_src:
            self._inline_parts.append(data)


def _origin_key(parsed: ParseResult) -> tuple[str, str, int]:
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        raise ValueError("URL must use HTTP(S) and contain a hostname")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL contains an invalid port") from exc
    if port is None:
        port = 443 if scheme == "https" else 80
    return scheme, host, int(port)


class _SameOriginRedirects(HTTPRedirectHandler):
    def __init__(self, origin: tuple[str, str, int]) -> None:
        super().__init__()
        self.origin = origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        resolved = urljoin(req.full_url, newurl)
        parsed = urlparse(resolved)
        try:
            same_origin = _origin_key(parsed) == self.origin
        except ValueError:
            same_origin = False
        if not same_origin or parsed.username or parsed.password:
            raise HTTPError(req.full_url, 470, "cross-origin redirect blocked by TONMEN api-intel", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, resolved)


def _normalize_same_origin(url: str, origin: tuple[str, str, int]) -> str | None:
    value, _ = urldefrag(url)
    parsed = urlparse(value)
    if parsed.username or parsed.password:
        return None
    try:
        if _origin_key(parsed) != origin:
            return None
    except ValueError:
        return None
    return parsed.geturl()


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()


def _extract(text: str, *, source_url: str, origin: tuple[str, str, int]) -> tuple[list[dict[str, str]], set[str]]:
    endpoints: list[dict[str, str]] = []
    hints: set[str] = set()
    lowered = text.lower()
    for hint in _HINTS:
        if hint in lowered:
            hints.add(hint)

    seen: set[str] = set()
    for match in _QUOTED_ENDPOINT.finditer(text):
        raw = match.group("value").strip()
        if not raw:
            continue
        absolute = urljoin(source_url, raw)
        normalized = _normalize_same_origin(absolute, origin)
        if normalized is None:
            continue
        path = urlparse(normalized).path.lower()
        if any(path.endswith(suffix) for suffix in _STATIC_SUFFIXES):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        endpoints.append({"endpoint": raw[:1024], "absolute_url": normalized[:2048]})
        if len(endpoints) >= _MAX_ENDPOINTS:
            break
    return endpoints, hints


def inspect_api(start_url: str, *, max_scripts: int, max_bytes: int, timeout: int) -> int:
    parsed_start = urlparse(start_url if "://" in start_url else f"https://{start_url}")
    if parsed_start.username or parsed_start.password:
        raise ValueError("api-intel target must not contain credentials")
    origin = _origin_key(parsed_start)
    normalized_start = parsed_start.geturl()
    opener = build_opener(_SameOriginRedirects(origin))

    endpoint_rows: list[dict[str, str]] = []
    endpoint_seen: set[str] = set()
    hints: set[str] = set()
    scripts_seen: set[str] = set()
    scripts_fetched = 0
    entry_reachable = False
    parser = _ScriptParser()

    request = Request(
        normalized_start,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.1"},
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = _normalize_same_origin(response.geturl(), origin)
            if final_url is None:
                raise ValueError("entry response left the authorized origin")
            raw = response.read(_MAX_ENTRY_BYTES + 1)
            if len(raw) > _MAX_ENTRY_BYTES:
                raw = raw[:_MAX_ENTRY_BYTES]
            charset = response.headers.get_content_charset() or "utf-8"
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            text = raw.decode(charset, errors="replace") if content_type in {"text/html", "application/xhtml+xml"} else ""
            entry_reachable = True
            if text:
                parser.feed(text)
                for inline_index, inline in enumerate(parser.inline_scripts[:32]):
                    rows, found_hints = _extract(inline[:max_bytes], source_url=final_url, origin=origin)
                    hints.update(found_hints)
                    for row in rows:
                        absolute = row["absolute_url"]
                        if absolute in endpoint_seen:
                            continue
                        endpoint_seen.add(absolute)
                        endpoint_rows.append({**row, "source": "inline", "source_url": final_url, "inline_index": str(inline_index)})
                        if len(endpoint_rows) >= _MAX_ENDPOINTS:
                            break
                    if len(endpoint_rows) >= _MAX_ENDPOINTS:
                        break
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        _emit({"type": "api_error", "url": normalized_start, "error": str(exc)[:512]})

    for src in parser.script_sources:
        if scripts_fetched >= max_scripts or len(endpoint_rows) >= _MAX_ENDPOINTS:
            break
        candidate = _normalize_same_origin(urljoin(normalized_start, src), origin)
        if candidate is None or candidate in scripts_seen:
            continue
        scripts_seen.add(candidate)
        request = Request(candidate, headers={"User-Agent": _USER_AGENT, "Accept": "application/javascript,text/javascript,*/*;q=0.1"})
        try:
            with opener.open(request, timeout=timeout) as response:
                final_url = _normalize_same_origin(response.geturl(), origin)
                if final_url is None:
                    continue
                raw = response.read(max_bytes + 1)
                truncated = len(raw) > max_bytes
                if truncated:
                    raw = raw[:max_bytes]
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                scripts_fetched += 1
                _emit({"type": "script", "url": final_url, "bytes": len(raw), "truncated": truncated})
                rows, found_hints = _extract(text, source_url=final_url, origin=origin)
                hints.update(found_hints)
                for row in rows:
                    absolute = row["absolute_url"]
                    if absolute in endpoint_seen:
                        continue
                    endpoint_seen.add(absolute)
                    endpoint_rows.append({**row, "source": "script", "source_url": final_url})
                    if len(endpoint_rows) >= _MAX_ENDPOINTS:
                        break
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            _emit({"type": "script_error", "url": candidate, "error": str(exc)[:512]})

    for row in endpoint_rows[:_MAX_ENDPOINTS]:
        _emit({"type": "api", "kind": "endpoint", **row})
    for hint in sorted(hints):
        _emit({"type": "api", "kind": "hint", "hint": hint, "url": normalized_start})
    _emit(
        {
            "type": "api_summary",
            "url": normalized_start,
            "entry_reachable": entry_reachable,
            "scripts_discovered": len(parser.script_sources),
            "scripts_fetched": scripts_fetched,
            "endpoint_count": len(endpoint_rows),
            "hints": sorted(hints),
            "javascript_executed": False,
            "forms_submitted": False,
            "cross_origin_fetches": False,
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tonmen-api-intel")
    parser.add_argument("--url", required=True)
    parser.add_argument("--max-scripts", type=int, default=12)
    parser.add_argument("--max-bytes", type=int, default=262_144)
    parser.add_argument("--timeout", type=int, default=8)
    args = parser.parse_args(argv)
    if not 1 <= args.max_scripts <= 16:
        parser.error("--max-scripts must be between 1 and 16")
    if not 32_768 <= args.max_bytes <= 524_288:
        parser.error("--max-bytes must be between 32768 and 524288")
    if not 1 <= args.timeout <= 20:
        parser.error("--timeout must be between 1 and 20")
    try:
        return inspect_api(args.url, max_scripts=args.max_scripts, max_bytes=args.max_bytes, timeout=args.timeout)
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
