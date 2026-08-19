from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .pool import WorkerSpec
from .protocol import DispatchEnvelope


class WorkerTransportError(RuntimeError):
    """Remote worker transport failure. The caller should fail closed on ambiguous dispatches."""


class WorkerHTTPTransport:
    def __init__(self, *, opener: Callable[..., Any] = urlopen, timeout_seconds: int = 150) -> None:
        self._opener = opener
        self.timeout_seconds = max(5, int(timeout_seconds))

    @staticmethod
    def _allow_url(spec: WorkerSpec) -> None:
        parsed = urlparse(spec.url)
        if parsed.scheme == "https":
            return
        host = (parsed.hostname or "").lower()
        if host in {"127.0.0.1", "::1", "localhost"}:
            return
        if os.getenv("TONMEN_WORKER_ALLOW_INSECURE_HTTP", "").strip() == "1":
            return
        raise ValueError(
            "remote worker HTTP requires TLS, or TONMEN_WORKER_ALLOW_INSECURE_HTTP=1 on a trusted encrypted private overlay"
        )

    @staticmethod
    def _decode_response(response, *, max_bytes: int = 32 * 1024 * 1024) -> Mapping[str, Any]:
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise WorkerTransportError("worker response exceeded 32 MiB")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkerTransportError("worker returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise WorkerTransportError("worker response must be a JSON object")
        return payload

    def health(self, spec: WorkerSpec, *, timeout: int = 5) -> Mapping[str, Any]:
        self._allow_url(spec)
        request = Request(f"{spec.base_url}/v1/health", method="GET", headers={"Accept": "application/json"})
        try:
            with self._opener(request, timeout=max(1, int(timeout))) as response:
                payload = self._decode_response(response, max_bytes=2 * 1024 * 1024)
        except HTTPError as exc:
            raise WorkerTransportError(f"worker health returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise WorkerTransportError(f"worker health unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise WorkerTransportError("worker health timed out") from exc
        return payload

    def dispatch(self, spec: WorkerSpec, envelope: DispatchEnvelope) -> Mapping[str, Any]:
        self._allow_url(spec)
        body = json.dumps(envelope.as_dict(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(
            f"{spec.base_url}/v1/execute",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                payload = self._decode_response(response)
        except HTTPError as exc:
            try:
                detail_raw = exc.read(8192)
                detail_payload = json.loads(detail_raw.decode("utf-8"))
                detail = str(detail_payload.get("error") or f"HTTP {exc.code}")[:500]
            except Exception:
                detail = f"HTTP {exc.code}"
            raise WorkerTransportError(f"worker rejected dispatch: {detail}") from exc
        except URLError as exc:
            raise WorkerTransportError(f"worker dispatch unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise WorkerTransportError("worker dispatch timed out; execution state is ambiguous and will not be retried elsewhere") from exc
        if payload.get("ok") is not True:
            raise WorkerTransportError(str(payload.get("error") or "worker dispatch failed")[:500])
        return payload
