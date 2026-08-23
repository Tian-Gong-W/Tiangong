from __future__ import annotations

import struct

from tonmen.artifacts import ArtifactStore
from tonmen.artifacts.linkage import inspect_linkage


def _elf64_linked() -> bytes:
    shoff = 64
    dynstr = b"\x00libc.so.6\x00puts\x00exported\x00"
    libc_offset = dynstr.index(b"libc.so.6")
    puts_offset = dynstr.index(b"puts")
    exported_offset = dynstr.index(b"exported")

    headers_size = 4 * 64
    dynstr_offset = shoff + headers_size
    dynsym_offset = dynstr_offset + len(dynstr)
    dynsym = b"".join(
        (
            bytes(24),
            struct.pack("<IBBHQQ", puts_offset, 0x12, 0, 0, 0, 0),
            struct.pack("<IBBHQQ", exported_offset, 0x12, 0, 1, 0x401000, 8),
        )
    )
    dynamic_offset = dynsym_offset + len(dynsym)
    dynamic = struct.pack("<QQ", 1, libc_offset) + struct.pack("<QQ", 0, 0)

    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        ident,
        3,
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
        4,
        0,
    )
    null = bytes(64)
    dynstr_header = struct.pack(
        "<IIQQQQIIQQ",
        0,
        3,
        0,
        0,
        dynstr_offset,
        len(dynstr),
        0,
        0,
        1,
        0,
    )
    dynsym_header = struct.pack(
        "<IIQQQQIIQQ",
        0,
        11,
        0,
        0,
        dynsym_offset,
        len(dynsym),
        1,
        0,
        8,
        24,
    )
    dynamic_header = struct.pack(
        "<IIQQQQIIQQ",
        0,
        6,
        0,
        0,
        dynamic_offset,
        len(dynamic),
        1,
        0,
        8,
        16,
    )
    return header + null + dynstr_header + dynsym_header + dynamic_header + dynstr + dynsym + dynamic


def _pe64_linked() -> bytes:
    pe_offset = 0x80
    optional_size = 0xF0
    raw_offset = 0x200
    section_rva = 0x1000

    dos = bytearray(pe_offset)
    dos[:2] = b"MZ"
    dos[0x3C:0x40] = pe_offset.to_bytes(4, "little")
    coff = struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, optional_size, 0x0022)
    optional = bytearray(optional_size)
    optional[:2] = (0x20B).to_bytes(2, "little")
    # PE32+ data directory begins at optional+112; import directory is entry 1.
    optional[120:124] = section_rva.to_bytes(4, "little")
    optional[124:128] = (40).to_bytes(4, "little")
    section = struct.pack(
        "<8sIIIIIIHHI",
        b".rdata\x00\x00",
        0x200,
        section_rva,
        0x200,
        raw_offset,
        0,
        0,
        0,
        0,
        0x40000040,
    )

    image = bytearray(bytes(dos) + b"PE\x00\x00" + coff + bytes(optional) + section)
    if len(image) < raw_offset + 0x200:
        image.extend(b"\x00" * (raw_offset + 0x200 - len(image)))

    descriptor = raw_offset
    name_rva = section_rva + 0x30
    thunk_rva = section_rva + 0x40
    hint_name_rva = section_rva + 0x50
    image[descriptor:descriptor + 20] = struct.pack(
        "<IIIII",
        thunk_rva,
        0,
        0,
        name_rva,
        thunk_rva,
    )
    image[raw_offset + 0x30:raw_offset + 0x30 + len(b"KERNEL32.dll\x00")] = b"KERNEL32.dll\x00"
    image[raw_offset + 0x40:raw_offset + 0x48] = hint_name_rva.to_bytes(8, "little")
    image[raw_offset + 0x48:raw_offset + 0x50] = (0).to_bytes(8, "little")
    image[raw_offset + 0x50:raw_offset + 0x52] = (0).to_bytes(2, "little")
    image[raw_offset + 0x52:raw_offset + 0x52 + len(b"ExitProcess\x00")] = b"ExitProcess\x00"
    return bytes(image)


def _macho64_linked() -> bytes:
    dependency = b"/usr/lib/libSystem.B.dylib\x00"
    command_size = 24 + len(dependency)
    command_size = (command_size + 7) & ~7
    header = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,
        0x01000007,
        3,
        2,
        1,
        command_size,
        0x00200000,
        0,
    )
    command = struct.pack("<IIIIII", 0xC, command_size, 24, 0, 0, 0)
    command += dependency
    command += b"\x00" * (command_size - len(command))
    return header + command


def test_elf_linkage_extracts_needed_library_and_dynamic_symbols_only():
    linkage = inspect_linkage(_elf64_linked(), format="elf", bitness=64, endianness="little")

    assert linkage["dependencies"] == ["libc.so.6"]
    assert linkage["imports"] == ["puts"]
    assert linkage["exports"] == ["exported"]
    assert linkage["linkage_warnings"] == []


def test_pe_linkage_resolves_import_directory_through_section_rva():
    linkage = inspect_linkage(_pe64_linked(), format="pe", bitness=64, endianness="little")

    assert linkage["dependencies"] == ["KERNEL32.dll"]
    assert linkage["imports"] == [{"library": "KERNEL32.dll", "symbols": ["ExitProcess"]}]
    assert linkage["exports"] == []


def test_macho_linkage_extracts_linked_dylib_without_loading_image():
    linkage = inspect_linkage(_macho64_linked(), format="macho", bitness=64, endianness="little")

    assert linkage["dependencies"] == ["/usr/lib/libSystem.B.dylib"]
    assert linkage["imports"] == []
    assert linkage["exports"] == []


def test_artifact_store_persists_linkage_as_static_report_metadata(tmp_path):
    store = ArtifactStore(tmp_path)
    payload = store.ingest_bytes(_elf64_linked(), source_name="linked.elf")

    assert payload["execution_performed"] is False
    assert payload["linkage"]["dependencies"] == ["libc.so.6"]
    assert payload["linkage"]["imports"] == ["puts"]
    assert payload["linkage"]["exports"] == ["exported"]

    listed = store.list()[0]
    assert listed["dependencies"] == 1
    assert listed["imports"] == 1
