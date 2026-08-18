from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urldefrag, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

_MAX_RESPONSE_BYTES = 1_048_576
_USER_AGENT = "TONMEN/0.4 governed-crawler"


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._in_title = False
        self._title_parts: list[str] = []

    @property
    def title(self) -> str | None:
        value = " ".join("".join(self._title_parts).split())
        return value[:240] or None

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = True
        if lowered != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(str(value))
                break

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)


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
            raise HTTPError(req.full_url, 470, "cross-origin redirect blocked by TONMEN crawler", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, resolved)


def _normalize(url: str, origin: tuple[str, str, int]) -> str | None:
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


def crawl(start_url: str, *, max_pages: int, max_depth: int, timeout: int) -> int:
    parsed_start = urlparse(start_url if "://" in start_url else f"https://{start_url}")
    if parsed_start.username or parsed_start.password:
        raise ValueError("crawler target must not contain credentials")
    try:
        origin = _origin_key(parsed_start)
    except ValueError as exc:
        raise ValueError("crawler target must be an HTTP(S) URL or hostname") from exc

    normalized_start = parsed_start.geturl()
    opener = build_opener(_SameOriginRedirects(origin))
    queue = deque([(normalized_start, 0)])
    queued = {normalized_start}
    visited: set[str] = set()
    successful = 0

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        request = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.2"})
        try:
            with opener.open(request, timeout=timeout) as response:
                final_url = _normalize(response.geturl(), origin)
                if final_url is None:
                    _emit({"type": "blocked", "url": url, "reason": "cross_origin_response"})
                    continue
                status = int(getattr(response, "status", 200) or 200)
                content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                truncated = len(raw) > _MAX_RESPONSE_BYTES
                if truncated:
                    raw = raw[:_MAX_RESPONSE_BYTES]
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace") if content_type in {"text/html", "application/xhtml+xml"} else ""
                parser = _LinkParser()
                if text:
                    parser.feed(text)
                _emit(
                    {
                        "type": "page",
                        "url": final_url,
                        "status": status,
                        "title": parser.title,
                        "content_type": content_type or None,
                        "depth": depth,
                        "bytes": len(raw),
                        "truncated": truncated,
                    }
                )
                successful += 1
                if depth >= max_depth or not text:
                    continue
                for href in parser.links:
                    candidate = _normalize(urljoin(final_url, href), origin)
                    if candidate is None or candidate in visited or candidate in queued:
                        continue
                    queued.add(candidate)
                    queue.append((candidate, depth + 1))
                    if len(queued) >= max_pages * 8:
                        break
        except HTTPError as exc:
            _emit({"type": "error", "url": url, "depth": depth, "status": int(exc.code), "error": str(exc.reason)})
        except (URLError, TimeoutError, OSError) as exc:
            _emit({"type": "error", "url": url, "depth": depth, "error": str(exc)})

    _emit({"type": "summary", "start_url": normalized_start, "visited": len(visited), "successful": successful, "max_pages": max_pages, "max_depth": max_depth})
    return 0 if successful else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tonmen-crawler")
    parser.add_argument("--url", required=True)
    parser.add_argument("--max-pages", type=int, default=25)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args(argv)
    if not 1 <= args.max_pages <= 100:
        parser.error("--max-pages must be between 1 and 100")
    if not 0 <= args.max_depth <= 4:
        parser.error("--max-depth must be between 0 and 4")
    if not 1 <= args.timeout <= 30:
        parser.error("--timeout must be between 1 and 30")
    try:
        return crawl(args.url, max_pages=args.max_pages, max_depth=args.max_depth, timeout=args.timeout)
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
