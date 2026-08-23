from __future__ import annotations

import json
import os
import stat
import struct

import pytest

from tonmen.artifacts import ArtifactInspector, ArtifactStore


def _elf64() -> bytes:
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        ident,
        3,       # ET_DYN / PIE candidate
        62,      # EM_X86_64
        1,
        0,
        64,      # e_phoff
        0,
        0,
        64,
        56,
        2,
        0,
        0,
        0,
    )
    gnu_stack = struct.pack("<IIQQQQQQ", 0x6474E551, 0x6, 0, 0, 0, 0, 0, 0)  # RW, not executable
    gnu_relro = struct.pack("<IIQQQQQQ", 0x6474E552, 0x4, 0, 0, 0, 0, 0, 0)
    return header + gnu_stack + gnu_relro


def _pe64() -> bytes:
    dos = bytearray(0x80)
    dos[:2] = b"MZ"
    dos[0x3C:0x40] = (0x80).to_bytes(4, "little")
    coff = struct.pack("<HHIIIHH", 0x8664, 3, 0, 0, 0, 0xF0, 0x0022)
    optional = bytearray(0xF0)
    optional[:2] = (0x20B).to_bytes(2, "little")
    optional[0x46:0x48] = (0x0040 | 0x0100 | 0x4000).to_bytes(2, "little")
    return bytes(dos) + b"PE\x00\x00" + coff + bytes(optional)


def test_inspector_identifies_elf_architecture_and_basic_mitigations():
    report = ArtifactInspector().inspect_bytes(_elf64(), source_name="demo.elf")

    assert report.format == "elf"
    assert report.architecture == "x86_64"
    assert report.bitness == 64
    assert report.endianness == "little"
    assert report.mitigations == {
        "pie_candidate": True,
        "nx_stack": True,
        "gnu_relro": True,
    }
    assert report.metadata["program_headers_declared"] == 2
    assert report.metadata["program_headers_parsed"] == 2


def test_inspector_identifies_pe_mitigation_flags_without_loading_binary():
    report = ArtifactInspector().inspect_bytes(_pe64(), source_name="demo.exe")

    assert report.format == "pe"
    assert report.architecture == "x86_64"
    assert report.bitness == 64
    assert report.mitigations["aslr"] is True
    assert report.mitigations["nx_compat"] is True
    assert report.mitigations["control_flow_guard"] is True
    assert report.mitigations["high_entropy_va"] is False
    assert report.as_dict()["execution_performed"] is False


def test_artifact_store_is_content_addressed_private_and_integrity_checked(tmp_path):
    source = tmp_path / "sample.elf"
    source.write_bytes(_elf64())
    workspace = tmp_path / "workspace"
    store = ArtifactStore(workspace)

    payload = store.ingest(source)

    artifact_id = payload["artifact_id"]
    assert artifact_id == payload["sha256"]
    assert payload["execution_performed"] is False
    assert payload["content_addressed"] is True
    assert payload["source_name"] == "sample.elf"
    assert str(source.resolve()) not in json.dumps(payload)

    blob = workspace / payload["stored_blob"]
    report_path = workspace / payload["report_path"]
    assert blob.read_bytes() == _elf64()
    assert report_path.is_file()
    if os.name == "posix":
        assert stat.S_IMODE(blob.stat().st_mode) == 0o600
        assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
        assert stat.S_IMODE((workspace / "artifacts").stat().st_mode) == 0o700

    loaded = store.load(artifact_id)
    assert loaded["sha256"] == artifact_id
    assert store.list()[0]["artifact_id"] == artifact_id

    blob.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        store.load(artifact_id)


def test_artifact_intake_has_hard_size_and_regular_file_boundaries(tmp_path):
    inspector = ArtifactInspector(max_bytes=8)
    with pytest.raises(ValueError, match="intake limit"):
        inspector.inspect_bytes(b"123456789")

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(ValueError, match="regular file|cannot be read"):
        inspector.inspect(directory)


def test_artifact_store_delete_removes_blob_and_report(tmp_path):
    source = tmp_path / "sample.exe"
    source.write_bytes(_pe64())
    store = ArtifactStore(tmp_path / "workspace")
    payload = store.ingest(source)

    assert store.delete(payload["artifact_id"]) is True
    assert store.list() == []
    assert store.delete(payload["artifact_id"]) is False
