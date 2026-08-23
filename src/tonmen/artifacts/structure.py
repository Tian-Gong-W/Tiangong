from __future__ import annotations

from typing import Any

_MAX_SECTIONS = 256
_MAX_MACH_COMMANDS = 4096

_ELF_SECTION_TYPES = {
    0: "null",
    1: "progbits",
    2: "symtab",
    3: "strtab",
    4: "rela",
    5: "hash",
    6: "dynamic",
    7: "note",
    8: "nobits",
    9: "rel",
    11: "dynsym",
    14: "init_array",
    15: "fini_array",
    16: "preinit_array",
    18: "symtab_shndx",
}


def _u(data: bytes, offset: int, size: int, endian: str) -> int | None:
    end = offset + size
    if offset < 0 or end > len(data):
        return None
    return int.from_bytes(data[offset:end], byteorder=endian, signed=False)


def _fixed_name(data: bytes) -> str:
    value = data.split(b"\x00", 1)[0].decode("ascii", errors="replace")
    return "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in value)[:128]


def _string_at(table: bytes, offset: int | None) -> str:
    if offset is None or offset < 0 or offset >= len(table):
        return ""
    end = table.find(b"\x00", offset)
    if end < 0:
        end = len(table)
    raw = table[offset:min(end, offset + 128)]
    return _fixed_name(raw)


def _elf_permissions(flags: int | None) -> str:
    if flags is None:
        return ""
    # SHF_WRITE=1, SHF_ALLOC=2, SHF_EXECINSTR=4. Allocation is represented as R.
    return ("R" if flags & 0x2 else "") + ("W" if flags & 0x1 else "") + ("X" if flags & 0x4 else "")


def _elf_sections(data: bytes, bitness: int | None, endian: str | None) -> dict[str, Any]:
    if bitness not in {32, 64} or endian not in {"little", "big"}:
        return {"sections": [], "structure_warnings": ["ELF section table cannot be parsed without class and byte order"]}

    if bitness == 32:
        shoff = _u(data, 32, 4, endian)
        shentsize = _u(data, 46, 2, endian)
        shnum = _u(data, 48, 2, endian)
        shstrndx = _u(data, 50, 2, endian)
        minimum = 40
        fields = {"name": (0, 4), "type": (4, 4), "flags": (8, 4), "addr": (12, 4), "offset": (16, 4), "size": (20, 4)}
    else:
        shoff = _u(data, 40, 8, endian)
        shentsize = _u(data, 58, 2, endian)
        shnum = _u(data, 60, 2, endian)
        shstrndx = _u(data, 62, 2, endian)
        minimum = 64
        fields = {"name": (0, 4), "type": (4, 4), "flags": (8, 8), "addr": (16, 8), "offset": (24, 8), "size": (32, 8)}

    warnings: list[str] = []
    if shoff in {None, 0} or shnum is None or shentsize is None:
        return {"sections": [], "sections_declared": shnum, "structure_warnings": []}
    if shnum == 0:
        return {"sections": [], "sections_declared": 0, "structure_warnings": ["extended ELF section count is not expanded"]}
    if shentsize < minimum:
        return {"sections": [], "sections_declared": shnum, "structure_warnings": ["ELF section-header entry is smaller than expected"]}
    if shstrndx == 0xFFFF:
        warnings.append("extended ELF section-name index is not expanded")

    bounded = min(int(shnum), _MAX_SECTIONS)
    if shnum > bounded:
        warnings.append(f"ELF section inventory bounded to {_MAX_SECTIONS} entries")

    headers: list[dict[str, int | None]] = []
    for index in range(bounded):
        base = int(shoff) + index * int(shentsize)
        if base < 0 or base + minimum > len(data):
            warnings.append("ELF section-header table is truncated")
            break
        header = {key: _u(data, base + offset, size, endian) for key, (offset, size) in fields.items()}
        headers.append(header)

    string_table = b""
    if shstrndx is not None and shstrndx < len(headers):
        string_header = headers[int(shstrndx)]
        table_offset = string_header.get("offset")
        table_size = string_header.get("size")
        if table_offset is not None and table_size is not None and table_offset <= len(data):
            end = int(table_offset) + int(table_size)
            if end <= len(data):
                string_table = data[int(table_offset):end]
            else:
                warnings.append("ELF section-name string table is truncated")

    sections: list[dict[str, Any]] = []
    for index, header in enumerate(headers):
        section_type = header.get("type")
        flags = header.get("flags")
        sections.append(
            {
                "index": index,
                "name": _string_at(string_table, header.get("name")) or f"section_{index}",
                "type": _ELF_SECTION_TYPES.get(section_type, f"type-{section_type}" if section_type is not None else "unknown"),
                "permissions": _elf_permissions(flags),
                "file_offset": header.get("offset"),
                "size": header.get("size"),
                "virtual_address": header.get("addr"),
            }
        )

    return {
        "sections_declared": shnum,
        "sections_parsed": len(sections),
        "sections": sections,
        "structure_warnings": list(dict.fromkeys(warnings)),
    }


def _pe_permissions(characteristics: int | None) -> str:
    if characteristics is None:
        return ""
    return (
        ("R" if characteristics & 0x40000000 else "")
        + ("W" if characteristics & 0x80000000 else "")
        + ("X" if characteristics & 0x20000000 else "")
    )


def _pe_sections(data: bytes) -> dict[str, Any]:
    warnings: list[str] = []
    pe_offset = _u(data, 0x3C, 4, "little")
    if pe_offset is None or pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
        return {"sections": [], "structure_warnings": ["PE section table unavailable"]}
    declared = _u(data, pe_offset + 6, 2, "little") or 0
    optional_size = _u(data, pe_offset + 20, 2, "little") or 0
    table = int(pe_offset) + 24 + int(optional_size)
    bounded = min(int(declared), _MAX_SECTIONS)
    if declared > bounded:
        warnings.append(f"PE section inventory bounded to {_MAX_SECTIONS} entries")

    sections: list[dict[str, Any]] = []
    for index in range(bounded):
        base = table + index * 40
        if base < 0 or base + 40 > len(data):
            warnings.append("PE section table is truncated")
            break
        characteristics = _u(data, base + 36, 4, "little")
        sections.append(
            {
                "index": index,
                "name": _fixed_name(data[base:base + 8]) or f"section_{index}",
                "permissions": _pe_permissions(characteristics),
                "virtual_size": _u(data, base + 8, 4, "little"),
                "virtual_address": _u(data, base + 12, 4, "little"),
                "raw_size": _u(data, base + 16, 4, "little"),
                "file_offset": _u(data, base + 20, 4, "little"),
                "contains_code": bool(characteristics & 0x20) if characteristics is not None else None,
            }
        )
    return {
        "sections_declared": declared,
        "sections_parsed": len(sections),
        "sections": sections,
        "structure_warnings": list(dict.fromkeys(warnings)),
    }


def _mach_permissions(protection: int | None) -> str:
    if protection is None:
        return ""
    return ("R" if protection & 0x1 else "") + ("W" if protection & 0x2 else "") + ("X" if protection & 0x4 else "")


def _macho_sections(data: bytes, bitness: int | None, endian: str | None) -> dict[str, Any]:
    if bitness not in {32, 64} or endian not in {"little", "big"}:
        return {"segments": [], "sections": [], "structure_warnings": ["Mach-O load commands cannot be parsed"]}
    header_size = 32 if bitness == 64 else 28
    ncmds = _u(data, 16, 4, endian)
    sizeofcmds = _u(data, 20, 4, endian)
    if ncmds is None or sizeofcmds is None or len(data) < header_size:
        return {"segments": [], "sections": [], "structure_warnings": ["Mach-O header is truncated"]}

    warnings: list[str] = []
    bounded_commands = min(int(ncmds), _MAX_MACH_COMMANDS)
    if ncmds > bounded_commands:
        warnings.append(f"Mach-O load-command inventory bounded to {_MAX_MACH_COMMANDS} entries")

    cursor = header_size
    command_end = min(len(data), header_size + int(sizeofcmds))
    segments: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    for _ in range(bounded_commands):
        if cursor + 8 > command_end:
            warnings.append("Mach-O load-command table is truncated")
            break
        command = _u(data, cursor, 4, endian)
        command_size = _u(data, cursor + 4, 4, endian)
        if command_size is None or command_size < 8 or cursor + command_size > command_end:
            warnings.append("Mach-O load command has an invalid size")
            break

        is_segment = (bitness == 32 and command == 0x1) or (bitness == 64 and command == 0x19)
        if is_segment:
            minimum = 56 if bitness == 32 else 72
            section_size = 68 if bitness == 32 else 80
            if command_size < minimum:
                warnings.append("Mach-O segment command is truncated")
            else:
                segment_name = _fixed_name(data[cursor + 8:cursor + 24]) or "segment"
                if bitness == 32:
                    file_offset = _u(data, cursor + 32, 4, endian)
                    file_size = _u(data, cursor + 36, 4, endian)
                    init_prot = _u(data, cursor + 44, 4, endian)
                    section_count = _u(data, cursor + 48, 4, endian) or 0
                else:
                    file_offset = _u(data, cursor + 40, 8, endian)
                    file_size = _u(data, cursor + 48, 8, endian)
                    init_prot = _u(data, cursor + 60, 4, endian)
                    section_count = _u(data, cursor + 64, 4, endian) or 0
                permissions = _mach_permissions(init_prot)
                segments.append(
                    {
                        "name": segment_name,
                        "permissions": permissions,
                        "file_offset": file_offset,
                        "size": file_size,
                        "sections_declared": section_count,
                    }
                )
                remaining_slots = max(0, _MAX_SECTIONS - len(sections))
                bounded_sections = min(int(section_count), remaining_slots)
                if section_count > bounded_sections:
                    warnings.append(f"Mach-O section inventory bounded to {_MAX_SECTIONS} entries")
                section_base = cursor + minimum
                for index in range(bounded_sections):
                    base = section_base + index * section_size
                    if base + section_size > cursor + int(command_size):
                        warnings.append("Mach-O section table is truncated")
                        break
                    section_name = _fixed_name(data[base:base + 16]) or f"section_{len(sections)}"
                    owning_segment = _fixed_name(data[base + 16:base + 32]) or segment_name
                    if bitness == 32:
                        address = _u(data, base + 32, 4, endian)
                        size = _u(data, base + 36, 4, endian)
                        offset = _u(data, base + 40, 4, endian)
                    else:
                        address = _u(data, base + 32, 8, endian)
                        size = _u(data, base + 40, 8, endian)
                        offset = _u(data, base + 48, 4, endian)
                    sections.append(
                        {
                            "index": len(sections),
                            "name": section_name,
                            "segment": owning_segment,
                            "permissions": permissions,
                            "file_offset": offset,
                            "size": size,
                            "virtual_address": address,
                        }
                    )
        cursor += int(command_size)

    return {
        "load_commands_declared": ncmds,
        "load_commands_size": sizeofcmds,
        "segments_parsed": len(segments),
        "segments": segments,
        "sections_parsed": len(sections),
        "sections": sections,
        "structure_warnings": list(dict.fromkeys(warnings)),
    }


def inspect_structure(
    data: bytes,
    *,
    format: str,
    bitness: int | None,
    endianness: str | None,
) -> dict[str, Any]:
    """Return bounded container structure metadata; raw section contents are excluded."""
    if format == "elf":
        return _elf_sections(data, bitness, endianness)
    if format == "pe":
        return _pe_sections(data)
    if format == "macho":
        return _macho_sections(data, bitness, endianness)
    if format == "macho-fat":
        return {"segments": [], "sections": [], "structure_warnings": ["fat Mach-O slice inventories are not expanded"]}
    return {"sections": [], "structure_warnings": []}
