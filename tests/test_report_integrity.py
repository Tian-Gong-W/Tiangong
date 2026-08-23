from __future__ import annotations

import json

import pytest

from tonmen.missions import MissionPlan, MissionRun, MissionRunState
from tonmen.reports import ReportStore
from tonmen.reports.store import ReportStore as LegacyReportStore


def _completed_run():
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.finish(MissionRunState.SUCCEEDED)
    return plan, run


def test_report_bundle_is_hmac_authenticated_and_private(tmp_path):
    plan, run = _completed_run()
    store = ReportStore(tmp_path)

    report = store.save(plan, run)

    manifest = tmp_path / "reports" / f"{run.id}.integrity.json"
    key = tmp_path / ".reports.key"
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert report["mission"]["run_id"] == run.id
    assert store.verify(run.id) is True
    assert payload["algorithm"] == "hmac-sha256"
    assert payload["run_id"] == run.id
    assert len(payload["json_sha256"]) == 64
    assert len(payload["markdown_sha256"]) == 64
    assert len(payload["digest"]) == 64
    assert key.stat().st_mode & 0o077 == 0
    assert manifest.stat().st_mode & 0o077 == 0


def test_report_json_or_markdown_tampering_fails_closed(tmp_path):
    plan, run = _completed_run()
    store = ReportStore(tmp_path)
    store.save(plan, run)

    json_path = tmp_path / "reports" / f"{run.id}.json"
    json_path.write_text(json_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert store.verify(run.id) is False
    with pytest.raises(RuntimeError, match="integrity verification failed"):
        store.load_json(run.id)

    store.save(plan, run)
    markdown_path = tmp_path / "reports" / f"{run.id}.md"
    markdown_path.write_text(markdown_path.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    assert store.verify(run.id) is False
    with pytest.raises(RuntimeError, match="integrity verification failed"):
        store.load_markdown(run.id)


def test_authenticated_report_key_loss_is_not_silently_treated_as_legacy(tmp_path):
    plan, run = _completed_run()
    store = ReportStore(tmp_path)
    store.save(plan, run)
    (tmp_path / ".reports.key").unlink()

    assert store.verify(run.id) is False
    with pytest.raises(RuntimeError, match="integrity verification failed"):
        store.load_json(run.id)


def test_legacy_report_pair_remains_readable_and_upgrades_on_save(tmp_path):
    plan, run = _completed_run()
    legacy = LegacyReportStore(tmp_path)
    legacy.save(plan, run)

    store = ReportStore(tmp_path)
    assert store.verify(run.id) is None
    assert store.load_json(run.id)["mission"]["run_id"] == run.id
    assert "TONMEN Mission Report" in store.load_markdown(run.id)

    store.save(plan, run)
    assert store.verify(run.id) is True
    assert (tmp_path / "reports" / f"{run.id}.integrity.json").is_file()


def test_report_delete_removes_integrity_sidecar_too(tmp_path):
    plan, run = _completed_run()
    store = ReportStore(tmp_path)
    store.save(plan, run)

    assert store.delete(run.id) is True
    assert not (tmp_path / "reports" / f"{run.id}.json").exists()
    assert not (tmp_path / "reports" / f"{run.id}.md").exists()
    assert not (tmp_path / "reports" / f"{run.id}.integrity.json").exists()
