from __future__ import annotations

from typing import Any

_MAX_LIBRARIES = 128
_MAX_SYMBOLS = 2048
_MAX_SECTION_HEADERS = 256
_MAX_MACH_COMMANDS = 4096
_MAX_NAME_BYTES = 256


def _u(data: bytes, offset: int, size: int, endian: str) -> int | None:
    end = offset + size
    if offset < 0 or end > len(data):
        return None
    return int.from_bytes(data[offset:end], byteorder=endian, signed=False)


def _cstring(data: bytes, offset: int | None, *, end: int | None = None) -> str:
    if offset is None or offset < 0 or offset >= len(data):
        return ""
    bound = min(len(data), end if end is not None else len(data), offset + _MAX_NAME_BYTES)
    raw = data[offset:bound]
    stop = raw.find(b"\x00")
    if stop >= 0:
        raw = raw[:stop]
    value = raw.decode("utf-8", errors="replace")
    return "".join(ch if ch.isprintable() and ch not in "\r\n\t" else "?" for ch in value)[:_MAX_NAME_BYTES]


def _elf_section_headers(data: bytes, bitness: int, endian: str) -> tuple[list[dict[str, int | None]], list[str]]:
    warnings: list[str] = []
    if bitness == 32:
        shoff = _u(data, 32, 4, endian)
        shentsize = _u(data, 46, 2, endian)
        shnum = _u(data, 48, 2, endian)
        minimum = 40
        fields = {
            "type": (4, 4), "offset": (16, 4), "size": (20, 4),
            "link": (24, 4), "entsize": (36, 4),
        }
    else:
        shoff = _u(data, 40, 8, endian)
        shentsize = _u(data, 58, 2, endian)
        shnum = _u(data, 60, 2, endian)
        minimum = 64
        fields = {
            "type": (4, 4), "offset": (24, 8), "size": (32, 8),
            "link": (40, 4), "entsize": (56, 8),
        }
    if shoff in {None, 0} or not shentsize or not shnum or shentsize < minimum:
        return [], warnings
    bounded = min(int(shnum), _MAX_SECTION_HEADERS)
    if shnum > bounded:
        warnings.append(f"ELF linkage section scan bounded to {_MAX_SECTION_HEADERS} entries")
    headers: list[dict[str, int | None]] = []
    for index in range(bounded):
        base = int(shoff) + index * int(shentsize)
        if base + minimum > len(data):
            warnings.append("ELF section table truncated during linkage analysis")
            break
        header = {key: _u(data, base + offset, size, endian) for key, (offset, size) in fields.items()}
        headers.append(header)
    return headers, warnings


def _elf_linkage(data: bytes, bitness: int | None, endian: str | None) -> dict[str, Any]:
    if bitness not in {32, 64} or endian not in {"little", "big"}:
        return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": ["ELF linkage unavailable without class and byte order"]}
    headers, warnings = _elf_section_headers(data, bitness, endian)
    dependencies: list[str] = []
    imports: list[str] = []
    exports: list[str] = []

    def string_table(index: int | None) -> tuple[int, int] | None:
        if index is None or index < 0 or index >= len(headers):
            return None
        header = headers[int(index)]
        offset, size = header.get("offset"), header.get("size")
        if offset is None or size is None or offset < 0 or size < 0 or offset + size > len(data):
            return None
        return int(offset), int(size)

    for header in headers:
        section_type = header.get("type")
        offset, size = header.get("offset"), header.get("size")
        if offset is None or size is None or offset < 0 or size < 0 or offset + size > len(data):
            continue
        linked = string_table(header.get("link"))
        if linked is None:
            continue
        str_offset, str_size = linked

        if section_type == 6:  # SHT_DYNAMIC
            entry_size = int(header.get("entsize") or (8 if bitness == 32 else 16))
            minimum = 8 if bitness == 32 else 16
            if entry_size < minimum:
                warnings.append("ELF dynamic entry size is invalid")
                continue
            count = min(int(size) // entry_size, _MAX_SYMBOLS)
            for index in range(count):
                base = int(offset) + index * entry_size
                tag_size = 4 if bitness == 32 else 8
                tag = _u(data, base, tag_size, endian)
                value = _u(data, base + tag_size, tag_size, endian)
                if tag == 0:
                    break
                if tag != 1 or value is None:  # DT_NEEDED
                    continue
                name = _cstring(data, str_offset + int(value), end=str_offset + str_size)
                if name and name not in dependencies:
                    dependencies.append(name)
                    if len(dependencies) >= _MAX_LIBRARIES:
                        warnings.append(f"ELF dependency inventory bounded to {_MAX_LIBRARIES} libraries")
                        break

        elif section_type == 11:  # SHT_DYNSYM
            entry_size = int(header.get("entsize") or (16 if bitness == 32 else 24))
            minimum = 16 if bitness == 32 else 24
            if entry_size < minimum:
                warnings.append("ELF dynamic-symbol entry size is invalid")
                continue
            declared = int(size) // entry_size
            count = min(declared, _MAX_SYMBOLS)
            if declared > count:
                warnings.append(f"ELF dynamic-symbol inventory bounded to {_MAX_SYMBOLS} symbols")
            for index in range(count):
                base = int(offset) + index * entry_size
                name_offset = _u(data, base, 4, endian)
                if bitness == 32:
                    info = data[base + 12] if base + 13 <= len(data) else None
                    shndx = _u(data, base + 14, 2, endian)
                else:
                    info = data[base + 4] if base + 5 <= len(data) else None
                    shndx = _u(data, base + 6, 2, endian)
                if not name_offset:
                    continue
                name = _cstring(data, str_offset + int(name_offset), end=str_offset + str_size)
                if not name:
                    continue
                symbol_type = (info & 0xF) if info is not None else None
                # Record externally relevant function/object/unknown dynamic symbols only.
                if symbol_type not in {None, 0, 1, 2, 10}:
                    continue
                destination = imports if shndx == 0 else exports
                if name not in destination:
                    destination.append(name)

    return {
        "dependencies": dependencies[:_MAX_LIBRARIES],
        "imports": imports[:_MAX_SYMBOLS],
        "exports": exports[:_MAX_SYMBOLS],
        "linkage_warnings": list(dict.fromkeys(warnings)),
    }


def _pe_sections(data: bytes, pe_offset: int, count: int, optional_size: int) -> list[dict[str, int]]:
    table = pe_offset + 24 + optional_size
    sections: list[dict[str, int]] = []
    for index in range(min(count, _MAX_SECTION_HEADERS)):
        base = table + index * 40
        if base + 40 > len(data):
            break
        virtual_size = _u(data, base + 8, 4, "little") or 0
        virtual_address = _u(data, base + 12, 4, "little") or 0
        raw_size = _u(data, base + 16, 4, "little") or 0
        raw_offset = _u(data, base + 20, 4, "little") or 0
        sections.append(
            {
                "virtual_size": int(virtual_size),
                "virtual_address": int(virtual_address),
                "raw_size": int(raw_size),
                "raw_offset": int(raw_offset),
            }
        )
    return sections


def _pe_rva_to_offset(rva: int, sections: list[dict[str, int]], data_size: int) -> int | None:
    for section in sections:
        start = section["virtual_address"]
        span = max(section["virtual_size"], section["raw_size"])
        if span and start <= rva < start + span:
            value = section["raw_offset"] + (rva - start)
            return value if 0 <= value < data_size else None
    return rva if 0 <= rva < data_size else None


def _pe_linkage(data: bytes, bitness: int | None) -> dict[str, Any]:
    warnings: list[str] = []
    pe_offset = _u(data, 0x3C, 4, "little")
    if pe_offset is None or pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
        return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": ["PE import directory unavailable"]}
    section_count = int(_u(data, pe_offset + 6, 2, "little") or 0)
    optional_size = int(_u(data, pe_offset + 20, 2, "little") or 0)
    optional = pe_offset + 24
    magic = _u(data, optional, 2, "little")
    resolved_bits = 32 if magic == 0x10B else 64 if magic == 0x20B else bitness
    if resolved_bits not in {32, 64}:
        return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": ["PE optional header does not expose import directory layout"]}

    data_directory = optional + (96 if resolved_bits == 32 else 112)
    import_entry = data_directory + 8  # IMAGE_DIRECTORY_ENTRY_IMPORT = 1
    if import_entry + 8 > optional + optional_size or import_entry + 8 > len(data):
        return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": []}
    import_rva = _u(data, import_entry, 4, "little") or 0
    import_size = _u(data, import_entry + 4, 4, "little") or 0
    if not import_rva or not import_size:
        return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": []}

    sections = _pe_sections(data, int(pe_offset), section_count, optional_size)
    descriptor_offset = _pe_rva_to_offset(int(import_rva), sections, len(data))
    if descriptor_offset is None:
        return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": ["PE import directory RVA is not file-backed"]}

    dependencies: list[str] = []
    imports: list[dict[str, Any]] = []
    thunk_size = 8 if resolved_bits == 64 else 4
    ordinal_mask = 1 << (63 if resolved_bits == 64 else 31)
    total_symbols = 0

    for descriptor_index in range(_MAX_LIBRARIES):
        base = descriptor_offset + descriptor_index * 20
        if base + 20 > len(data):
            warnings.append("PE import descriptor table is truncated")
            break
        original_thunk = _u(data, base, 4, "little") or 0
        name_rva = _u(data, base + 12, 4, "little") or 0
        first_thunk = _u(data, base + 16, 4, "little") or 0
        if not any(data[base:base + 20]):
            break
        library_offset = _pe_rva_to_offset(int(name_rva), sections, len(data)) if name_rva else None
        library = _cstring(data, library_offset) or f"library_{descriptor_index}"
        if library not in dependencies:
            dependencies.append(library)

        thunk_rva = int(original_thunk or first_thunk)
        thunk_offset = _pe_rva_to_offset(thunk_rva, sections, len(data)) if thunk_rva else None
        library_imports: list[str] = []
        if thunk_offset is not None:
            for thunk_index in range(_MAX_SYMBOLS - total_symbols):
                entry = _u(data, thunk_offset + thunk_index * thunk_size, thunk_size, "little")
                if not entry:
                    break
                total_symbols += 1
                if entry & ordinal_mask:
                    name = f"ordinal-{entry & 0xFFFF}"
                else:
                    hint_name = _pe_rva_to_offset(int(entry), sections, len(data))
                    name = _cstring(data, None if hint_name is None else hint_name + 2) or "unnamed-import"
                library_imports.append(name)
                if total_symbols >= _MAX_SYMBOLS:
                    warnings.append(f"PE import inventory bounded to {_MAX_SYMBOLS} symbols")
                    break
        imports.append({"library": library, "symbols": library_imports})
        if total_symbols >= _MAX_SYMBOLS:
            break
    else:
        warnings.append(f"PE dependency inventory bounded to {_MAX_LIBRARIES} libraries")

    return {
        "dependencies": dependencies,
        "imports": imports,
        "exports": [],
        "linkage_warnings": list(dict.fromkeys(warnings)),
    }


def _macho_linkage(data: bytes, bitness: int | None, endian: str | None) -> dict[str, Any]:
    if bitness not in {32, 64} or endian not in {"little", "big"}:
        return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": ["Mach-O linkage unavailable"]}
    header_size = 32 if bitness == 64 else 28
    ncmds = _u(data, 16, 4, endian)
    sizeofcmds = _u(data, 20, 4, endian)
    if ncmds is None or sizeofcmds is None:
        return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": ["Mach-O load commands unavailable"]}
    warnings: list[str] = []
    dependencies: list[str] = []
    cursor = header_size
    command_end = min(len(data), header_size + int(sizeofcmds))
    dylib_commands = {0xC, 0x80000018, 0x8000001F, 0x80000023}
    for index in range(min(int(ncmds), _MAX_MACH_COMMANDS)):
        if cursor + 8 > command_end:
            warnings.append("Mach-O load-command table is truncated during linkage analysis")
            break
        command = _u(data, cursor, 4, endian)
        command_size = _u(data, cursor + 4, 4, endian)
        if command_size is None or command_size < 8 or cursor + command_size > command_end:
            warnings.append("Mach-O load command has an invalid size during linkage analysis")
            break
        if command in dylib_commands and command_size >= 24:
            name_offset = _u(data, cursor + 8, 4, endian)
            absolute = cursor + int(name_offset) if name_offset is not None else None
            library = _cstring(data, absolute, end=cursor + int(command_size))
            if library and library not in dependencies:
                dependencies.append(library)
                if len(dependencies) >= _MAX_LIBRARIES:
                    warnings.append(f"Mach-O dependency inventory bounded to {_MAX_LIBRARIES} libraries")
                    break
        cursor += int(command_size)
    if ncmds > _MAX_MACH_COMMANDS:
        warnings.append(f"Mach-O linkage load-command scan bounded to {_MAX_MACH_COMMANDS} entries")
    return {
        "dependencies": dependencies,
        "imports": [],
        "exports": [],
        "linkage_warnings": list(dict.fromkeys(warnings)),
    }


def inspect_linkage(
    data: bytes,
    *,
    format: str,
    bitness: int | None,
    endianness: str | None,
) -> dict[str, Any]:
    """Return bounded dependency/import metadata without disassembling or executing code."""
    if format == "elf":
        return _elf_linkage(data, bitness, endianness)
    if format == "pe":
        return _pe_linkage(data, bitness)
    if format == "macho":
        return _macho_linkage(data, bitness, endianness)
    return {"dependencies": [], "imports": [], "exports": [], "linkage_warnings": []}
