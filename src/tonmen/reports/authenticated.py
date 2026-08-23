from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from pathlib import Path
from typing import Any

from .store import ReportStore as LegacyReportStore

_KEY_BYTES = 32
_ALGORITHM = "hmac-sha256"
_MANIFEST_SCHEMA = 1


def _canonical(payload: dict[str, Any]) -> bytes:
    body = {key: value for key, value in payload.items() if key != "digest"}
    return json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class AuthenticatedReportStore(LegacyReportStore):
    """ReportStore wrapper with an authenticated JSON/Markdown bundle manifest.

    Existing report pairs without a manifest remain readable for migration. New saves
    create a separate 0600 HMAC key and a per-run integrity manifest covering the exact
    JSON and Markdown bytes. If an authenticated bundle is modified or the key is lost,
    reads fail closed instead of serving an unverifiable report.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)
        super().__init__(workspace)
        self.key_path = self.workspace / ".reports.key"
        self._integrity_lock = threading.RLock()

    def _integrity_path(self, run_id: str) -> Path:
        return self.root / f"{self._validate_run_id(run_id)}.integrity.json"

    def _load_key(self, *, create: bool) -> bytes:
        if self.key_path.exists():
            key = self.key_path.read_bytes()
            if len(key) != _KEY_BYTES:
                raise RuntimeError("Report HMAC key has invalid length")
            return key
        if not create:
            raise RuntimeError("Report HMAC key is missing")

        self.workspace.mkdir(parents=True, exist_ok=True)
        key = os.urandom(_KEY_BYTES)
        try:
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = self.key_path.read_bytes()
            if len(existing) != _KEY_BYTES:
                raise RuntimeError("Report HMAC key has invalid length")
            return existing
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(key)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
        except Exception:
            try:
                self.key_path.unlink()
            except OSError:
                pass
            raise
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return key

    @staticmethod
    def _digest(payload: dict[str, Any], key: bytes) -> str:
        return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()

    def _build_manifest(self, run_id: str, key: bytes) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "schema": _MANIFEST_SCHEMA,
            "algorithm": _ALGORITHM,
            "run_id": self._validate_run_id(run_id),
            "json_sha256": _file_sha256(self._path(run_id, "json")),
            "markdown_sha256": _file_sha256(self._path(run_id, "md")),
        }
        manifest["digest"] = self._digest(manifest, key)
        return manifest

    def save(self, plan, run) -> dict:
        with self._integrity_lock:
            report = super().save(plan, run)
            key = self._load_key(create=True)
            manifest = self._build_manifest(run.id, key)
            self._atomic_write(
                self._integrity_path(run.id),
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            )
            return report

    def verify(self, run_id: str) -> bool | None:
        """Return True for authenticated valid, False for invalid, None for legacy."""
        with self._integrity_lock:
            manifest_path = self._integrity_path(run_id)
            if not manifest_path.exists():
                return None
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    return False
                if manifest.get("schema") != _MANIFEST_SCHEMA or manifest.get("algorithm") != _ALGORITHM:
                    return False
                if manifest.get("run_id") != self._validate_run_id(run_id):
                    return False
                digest = str(manifest.get("digest") or "")
                if len(digest) != 64:
                    return False
                key = self._load_key(create=False)
                expected = self._digest(manifest, key)
                if not hmac.compare_digest(digest, expected):
                    return False
                json_path = self._path(run_id, "json")
                markdown_path = self._path(run_id, "md")
                if not json_path.is_file() or not markdown_path.is_file():
                    return False
                if not hmac.compare_digest(str(manifest.get("json_sha256") or ""), _file_sha256(json_path)):
                    return False
                if not hmac.compare_digest(str(manifest.get("markdown_sha256") or ""), _file_sha256(markdown_path)):
                    return False
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
                return False
            return True

    def _require_integrity(self, run_id: str) -> None:
        verified = self.verify(run_id)
        if verified is False:
            raise RuntimeError("report integrity verification failed")

    def load_json(self, run_id: str) -> dict:
        self._require_integrity(run_id)
        return super().load_json(run_id)

    def load_markdown(self, run_id: str) -> str:
        self._require_integrity(run_id)
        return super().load_markdown(run_id)

    def delete(self, run_id: str) -> bool:
        with self._integrity_lock:
            removed = super().delete(run_id)
            try:
                self._integrity_path(run_id).unlink()
                removed = True
            except FileNotFoundError:
                pass
            return removed
