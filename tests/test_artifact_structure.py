from __future__ import annotations

import struct

from tonmen.artifacts import ArtifactStore
from tonmen.artifacts.structure import inspect_structure


def _elf64_with_sections() -> bytes:
    names = b"\x00.text\x00.shstrtab\x00"
    shoff = 64
    names_offset = shoff + 3 * 64
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        ident,
        2,
        62,
        1,
        0,
        0,
        shoff,
        0,
        64,
        0,
        0,
        64,
        3,
        2,
    )
    null = bytes(64)
    text = struct.pack("<IIQQQQIIQQ", 1, 1, 0x6, 0x401000, 0x300, 0x20, 0, 0, 16, 0)
    shstr = struct.pack("<IIQQQQIIQQ", 7, 3, 0, 0, names_offset, len(names), 0, 0, 1, 0)
    return header + null + text + shstr + names


def _pe64_with_sections() -> bytes:
    dos = bytearray(0x80)
    dos[:2] = b"MZ"
    dos[0x3C:0x40] = (0x80).to_bytes(4, "little")
    coff = struct.pack("<HHIIIHH", 0x8664, 2, 0, 0, 0, 0xF0, 0x0022)
    optional = bytearray(0xF0)
    optional[:2] = (0x20B).to_bytes(2, "little")
    text = struct.pack("<8sIIIIIIHHI", b".text\x00\x00\x00", 0x120, 0x1000, 0x200, 0x400, 0, 0, 0, 0, 0x60000020)
    data = struct.pack("<8sIIIIIIHHI", b".data\x00\x00\x00", 0x80, 0x2000, 0x200, 0x600, 0, 0, 0, 0, 0xC0000040)
    return bytes(dos) + b"PE\x00\x00" + coff + bytes(optional) + text + data


def _macho64_with_section() -> bytes:
    header = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,
        0x01000007,
        3,
        2,
        1,
        152,
        0x00200000,
        0,
    )
    segment = struct.pack(
        "<II16sQQQQiiII",
        0x19,
        152,
        b"__TEXT\x00" + b"\x00" * 9,
        0x100000000,
        0x1000,
        0,
        0x1000,
        7,
        5,
        1,
        0,
    )
    section = struct.pack(
        "<16s16sQQIIIIIIII",
        b"__text\x00" + b"\x00" * 9,
        b"__TEXT\x00" + b"\x00" * 9,
        0x100000F00,
        0x80,
        0xF00,
        4,
        0,
        0,
        0x80000400,
        0,
        0,
        0,
    )
    return header + segment + section


def test_elf_structure_inventory_records_metadata_not_section_contents():
    data = _elf64_with_sections()
    structure = inspect_structure(data, format="elf", bitness=64, endianness="little")

    assert structure["sections_declared"] == 3
    assert structure["sections_parsed"] == 3
    text = structure["sections"][1]
    assert text == {
        "index": 1,
        "name": ".text",
        "type": "progbits",
        "permissions": "RX",
        "file_offset": 0x300,
        "size": 0x20,
        "virtual_address": 0x401000,
    }
    assert all("content" not in section for section in structure["sections"])


def test_pe_structure_inventory_records_section_permissions():
    structure = inspect_structure(_pe64_with_sections(), format="pe", bitness=64, endianness="little")

    assert structure["sections_declared"] == 2
    assert structure["sections_parsed"] == 2
    assert structure["sections"][0]["name"] == ".text"
    assert structure["sections"][0]["permissions"] == "RX"
    assert structure["sections"][0]["contains_code"] is True
    assert structure["sections"][1]["name"] == ".data"
    assert structure["sections"][1]["permissions"] == "RW"


def test_macho_structure_inventory_records_segment_and_section():
    structure = inspect_structure(_macho64_with_section(), format="macho", bitness=64, endianness="little")

    assert structure["load_commands_declared"] == 1
    assert structure["segments_parsed"] == 1
    assert structure["segments"][0]["name"] == "__TEXT"
    assert structure["segments"][0]["permissions"] == "RX"
    assert structure["sections_parsed"] == 1
    assert structure["sections"][0]["name"] == "__text"
    assert structure["sections"][0]["segment"] == "__TEXT"


def test_artifact_store_persists_structure_inventory_in_static_report(tmp_path):
    store = ArtifactStore(tmp_path)
    payload = store.ingest_bytes(_pe64_with_sections(), source_name="demo.exe")

    assert payload["execution_performed"] is False
    assert payload["structure"]["sections_parsed"] == 2
    assert [item["name"] for item in payload["structure"]["sections"]] == [".text", ".data"]
    listed = store.list()[0]
    assert listed["sections"] == 2
