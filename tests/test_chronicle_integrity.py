from __future__ import annotations

import json

import pytest

from tonmen.chronicle import ChronicleStore
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, MissionStep
from tonmen.tools import RiskLevel


def _mission():
    step = MissionStep.create(
        tool="nmap",
        target="localhost",
        parameters={"ports": "80,443", "service_detection": False},
        risk=int(RiskLevel.DISCOVERY),
        requires_approval=False,
        rationale="bounded discovery",
    )
    plan = MissionPlan.create("localhost", [step])
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    return plan, run


def test_chronicle_snapshot_is_hmac_authenticated_and_private(tmp_path):
    store = ChronicleStore(tmp_path)
    plan, run = _mission()

    path = store.save(plan, run)

    assert store.verify(run.id) is True
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["integrity"]["algorithm"] == "hmac-sha256"
    assert len(payload["integrity"]["digest"]) == 64
    assert path.stat().st_mode & 0o077 == 0
    assert store.key_path.exists()
    assert store.key_path.stat().st_mode & 0o077 == 0
    assert len(store.key_path.read_bytes()) == 32

    loaded_plan, loaded_run = store.load(run.id)
    assert loaded_plan.id == plan.id
    assert loaded_run.id == run.id


def test_chronicle_tampering_is_rejected_on_load_and_listing(tmp_path):
    store = ChronicleStore(tmp_path)
    plan, run = _mission()
    path = store.save(plan, run)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["run"]["target"] = "tampered.example"
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    assert store.verify(run.id) is False
    with pytest.raises(ValueError, match="integrity verification failed"):
        store.load(run.id)
    assert all(entry.run_id != run.id for entry in store.list())


def test_schema1_legacy_snapshot_loads_and_is_upgraded_on_next_save(tmp_path):
    store = ChronicleStore(tmp_path)
    plan, run = _mission()
    path = store.save(plan, run)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("integrity")
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    assert store.verify(run.id) is False
    loaded_plan, loaded_run = store.load(run.id)
    upgraded = store.save(loaded_plan, loaded_run)

    assert store.verify(run.id) is True
    upgraded_payload = json.loads(upgraded.read_text(encoding="utf-8"))
    assert upgraded_payload["integrity"]["algorithm"] == "hmac-sha256"


def test_missing_chronicle_key_rejects_authenticated_snapshot(tmp_path):
    store = ChronicleStore(tmp_path)
    plan, run = _mission()
    store.save(plan, run)
    store.key_path.unlink()

    assert store.verify(run.id) is False
    with pytest.raises(ValueError, match="integrity verification failed"):
        store.load(run.id)
