from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from .inspector import ArtifactInspector


def _private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _atomic_private_write(path: Path, payload: bytes) -> None:
    _private_dir(path.parent)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sha256(value: str) -> str:
    candidate = value.strip().lower()
    if len(candidate) != 64 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise ValueError("artifact id must be a SHA-256 hex digest")
    return candidate


class ArtifactStore:
    """Workspace-local, content-addressed store for non-executed artifact evidence."""

    def __init__(self, workspace: str | Path, *, inspector: ArtifactInspector | None = None) -> None:
        self.workspace = Path(workspace)
        self.root = self.workspace / "artifacts"
        self.blobs = self.root / "blobs"
        self.reports = self.root / "reports"
        self.inspector = inspector or ArtifactInspector()
        _private_dir(self.root)
        _private_dir(self.blobs)
        _private_dir(self.reports)

    def ingest(self, source: str | Path) -> dict:
        report, data = self.inspector.read(source)
        blob = self.blobs / report.sha256
        if blob.exists():
            if not blob.is_file() or _sha256_file(blob) != report.sha256:
                raise ValueError("stored artifact blob failed its content-addressed integrity check")
        else:
            _atomic_private_write(blob, data)

        report_path = self.reports / f"{report.sha256}.json"
        payload = report.as_dict()
        payload.update(
            {
                "artifact_id": report.sha256,
                "stored_blob": str(blob.relative_to(self.workspace)),
                "report_path": str(report_path.relative_to(self.workspace)),
                "content_addressed": True,
                "execution_performed": False,
            }
        )
        encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        _atomic_private_write(report_path, encoded)
        return payload

    def load(self, artifact_id: str) -> dict:
        digest = _validate_sha256(artifact_id)
        path = self.reports / f"{digest}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("sha256") != digest:
            raise ValueError("artifact report identity mismatch")
        blob = self.blobs / digest
        if not blob.is_file() or _sha256_file(blob) != digest:
            raise ValueError("artifact blob integrity check failed")
        return payload

    def list(self) -> list[dict]:
        entries: list[dict] = []
        for path in self.reports.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            digest = str(payload.get("sha256") or "")
            try:
                _validate_sha256(digest)
            except ValueError:
                continue
            entries.append(
                {
                    "artifact_id": digest,
                    "source_name": payload.get("source_name"),
                    "format": payload.get("format"),
                    "architecture": payload.get("architecture"),
                    "bitness": payload.get("bitness"),
                    "size": payload.get("size"),
                    "inspected_at": payload.get("inspected_at"),
                    "execution_performed": False,
                }
            )
        return sorted(entries, key=lambda item: str(item.get("inspected_at") or ""), reverse=True)

    def delete(self, artifact_id: str) -> bool:
        digest = _validate_sha256(artifact_id)
        removed = False
        for path in (self.reports / f"{digest}.json", self.blobs / digest):
            try:
                path.unlink()
                removed = True
            except FileNotFoundError:
                pass
        return removed
