from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from .model import ArtifactReport

_DEFAULT_MAX_BYTES = 32 * 1024 * 1024
_HARD_MAX_BYTES = 128 * 1024 * 1024

_ELF_ARCH = {
    3: "x86",
    8: "mips",
    20: "powerpc",
    40: "arm",
    62: "x86_64",
    183: "aarch64",
    243: "riscv",
}
_PE_ARCH = {
    0x014C: "x86",
    0x01C0: "arm",
    0x01C4: "armv7",
    0x8664: "x86_64",
    0xAA64: "aarch64",
}
_MACH_ARCH = {
    7: "x86",
    12: "arm",
    0x01000007: "x86_64",
    0x0100000C: "aarch64",
}


def _u(data: bytes, offset: int, size: int, endian: str) -> int | None:
    end = offset + size
    if offset < 0 or end > len(data):
        return None
    return int.from_bytes(data[offset:end], byteorder=endian, signed=False)


def _elf(data: bytes) -> tuple[str, str | None, int | None, str | None, dict[str, bool | None], dict[str, Any], tuple[str, ...]] | None:
    if not data.startswith(b"\x7fELF"):
        return None
    warnings: list[str] = []
    if len(data) < 20:
        return "elf", None, None, None, {}, {}, ("ELF header is truncated",)

    elf_class = data[4]
    data_encoding = data[5]
    bitness = 32 if elf_class == 1 else 64 if elf_class == 2 else None
    endian = "little" if data_encoding == 1 else "big" if data_encoding == 2 else None
    if bitness is None:
        warnings.append("unknown ELF class")
    if endian is None:
        warnings.append("unknown ELF byte order")
        return "elf", None, bitness, None, {}, {}, tuple(warnings)

    e_type = _u(data, 16, 2, endian)
    machine = _u(data, 18, 2, endian)
    arch = _ELF_ARCH.get(machine, f"machine-{machine}" if machine is not None else None)
    type_name = {1: "relocatable", 2: "executable", 3: "shared-or-pie", 4: "core"}.get(e_type, "unknown")

    phoff_offset, phentsize_offset, phnum_offset = ((28, 42, 44) if bitness == 32 else (32, 54, 56))
    phoff_size = 4 if bitness == 32 else 8
    phoff = _u(data, phoff_offset, phoff_size, endian) if bitness else None
    phentsize = _u(data, phentsize_offset, 2, endian) if bitness else None
    phnum = _u(data, phnum_offset, 2, endian) if bitness else None

    gnu_stack_seen = False
    nx_stack: bool | None = None
    gnu_relro = False
    parsed_headers = 0
    if phoff is not None and phentsize and phnum is not None:
        bounded_phnum = min(int(phnum), 4096)
        if phnum > bounded_phnum:
            warnings.append("ELF program-header count was bounded")
        for index in range(bounded_phnum):
            offset = int(phoff) + index * int(phentsize)
            if offset < 0 or offset + min(int(phentsize), 8) > len(data):
                warnings.append("ELF program-header table is truncated")
                break
            p_type = _u(data, offset, 4, endian)
            if bitness == 64:
                p_flags = _u(data, offset + 4, 4, endian)
            else:
                p_flags = _u(data, offset + 24, 4, endian) if int(phentsize) >= 28 else None
            parsed_headers += 1
            if p_type == 0x6474E551:  # PT_GNU_STACK
                gnu_stack_seen = True
                nx_stack = None if p_flags is None else not bool(p_flags & 0x1)
            elif p_type == 0x6474E552:  # PT_GNU_RELRO
                gnu_relro = True

    mitigations = {
        "pie_candidate": e_type == 3 if e_type is not None else None,
        "nx_stack": nx_stack if gnu_stack_seen else None,
        "gnu_relro": gnu_relro,
    }
    metadata = {
        "elf_type": type_name,
        "machine_id": machine,
        "program_headers_declared": phnum,
        "program_headers_parsed": parsed_headers,
    }
    return "elf", arch, bitness, endian, mitigations, metadata, tuple(dict.fromkeys(warnings))


def _pe(data: bytes) -> tuple[str, str | None, int | None, str | None, dict[str, bool | None], dict[str, Any], tuple[str, ...]] | None:
    if not data.startswith(b"MZ"):
        return None
    warnings: list[str] = []
    pe_offset = _u(data, 0x3C, 4, "little")
    if pe_offset is None or pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
        return "pe-like", None, None, "little", {}, {}, ("MZ header has no complete PE signature",)

    machine = _u(data, pe_offset + 4, 2, "little")
    sections = _u(data, pe_offset + 6, 2, "little")
    optional_size = _u(data, pe_offset + 20, 2, "little") or 0
    optional = pe_offset + 24
    magic = _u(data, optional, 2, "little") if optional_size >= 2 else None
    bitness = 32 if magic == 0x10B else 64 if magic == 0x20B else None
    if bitness is None:
        warnings.append("unknown or absent PE optional-header magic")
    arch = _PE_ARCH.get(machine, f"machine-{machine:#x}" if machine is not None else None)

    dll_characteristics = None
    if optional_size >= 0x48 and optional + 0x48 <= len(data):
        dll_characteristics = _u(data, optional + 0x46, 2, "little")
    elif optional_size:
        warnings.append("PE optional header is truncated before DLL characteristics")

    mitigations = {
        "aslr": None if dll_characteristics is None else bool(dll_characteristics & 0x0040),
        "high_entropy_va": None if dll_characteristics is None else bool(dll_characteristics & 0x0020),
        "nx_compat": None if dll_characteristics is None else bool(dll_characteristics & 0x0100),
        "control_flow_guard": None if dll_characteristics is None else bool(dll_characteristics & 0x4000),
    }
    metadata = {
        "machine_id": machine,
        "sections": sections,
        "optional_header_magic": magic,
    }
    return "pe", arch, bitness, "little", mitigations, metadata, tuple(dict.fromkeys(warnings))


def _macho(data: bytes) -> tuple[str, str | None, int | None, str | None, dict[str, bool | None], dict[str, Any], tuple[str, ...]] | None:
    if len(data) < 4:
        return None
    magic = data[:4]
    thin = {
        b"\xce\xfa\xed\xfe": (32, "little"),
        b"\xfe\xed\xfa\xce": (32, "big"),
        b"\xcf\xfa\xed\xfe": (64, "little"),
        b"\xfe\xed\xfa\xcf": (64, "big"),
    }
    fat = {
        b"\xca\xfe\xba\xbe": (32, "big"),
        b"\xbe\xba\xfe\xca": (32, "little"),
        b"\xca\xfe\xba\xbf": (64, "big"),
        b"\xbf\xba\xfe\xca": (64, "little"),
    }
    if magic in fat:
        fat_bitness, endian = fat[magic]
        count = _u(data, 4, 4, endian)
        return (
            "macho-fat",
            "multi-arch",
            fat_bitness,
            endian,
            {},
            {"architectures_declared": count},
            (),
        )
    if magic not in thin:
        return None

    bitness, endian = thin[magic]
    cputype = _u(data, 4, 4, endian)
    filetype = _u(data, 12, 4, endian)
    commands = _u(data, 16, 4, endian)
    flags = _u(data, 24, 4, endian)
    arch = _MACH_ARCH.get(cputype, f"cpu-{cputype:#x}" if cputype is not None else None)
    mitigations = {"pie": None if flags is None else bool(flags & 0x00200000)}
    metadata = {"cpu_type": cputype, "file_type": filetype, "load_commands": commands}
    warnings = () if len(data) >= (32 if bitness == 64 else 28) else ("Mach-O header is truncated",)
    return "macho", arch, bitness, endian, mitigations, metadata, warnings


def _classify(data: bytes):
    for parser in (_elf, _pe, _macho):
        result = parser(data)
        if result is not None:
            return result
    if data.startswith(b"#!"):
        return "script", "text", None, None, {}, {}, ()
    return "unknown", None, None, None, {}, {}, ()


class ArtifactInspector:
    """Bounded static inspector. It never loads or executes the supplied artifact."""

    def __init__(self, *, max_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        value = int(max_bytes)
        if not 1 <= value <= _HARD_MAX_BYTES:
            raise ValueError(f"max_bytes must be between 1 and {_HARD_MAX_BYTES}")
        self.max_bytes = value

    def read(self, path: str | Path) -> tuple[ArtifactReport, bytes]:
        source = Path(path).expanduser()
        if source.is_symlink():
            raise ValueError("artifact source must not be a symbolic link")
        try:
            with source.open("rb") as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("artifact source must be a regular file")
                if info.st_size > self.max_bytes:
                    raise ValueError(f"artifact exceeds the {self.max_bytes}-byte intake limit")
                data = handle.read(self.max_bytes + 1)
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise ValueError(f"artifact cannot be read: {exc}") from exc
        if len(data) > self.max_bytes:
            raise ValueError(f"artifact exceeds the {self.max_bytes}-byte intake limit")

        report = self.inspect_bytes(data, source_name=source.name or "artifact")
        return report, data

    def inspect(self, path: str | Path) -> ArtifactReport:
        report, _ = self.read(path)
        return report

    def inspect_bytes(self, data: bytes, *, source_name: str = "artifact") -> ArtifactReport:
        if not isinstance(data, bytes):
            raise TypeError("artifact data must be bytes")
        if len(data) > self.max_bytes:
            raise ValueError(f"artifact exceeds the {self.max_bytes}-byte intake limit")
        fmt, arch, bitness, endian, mitigations, metadata, warnings = _classify(data)
        return ArtifactReport(
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            source_name=Path(source_name).name[:255] or "artifact",
            format=fmt,
            architecture=arch,
            bitness=bitness,
            endianness=endian,
            mitigations=mitigations,
            metadata=metadata,
            warnings=warnings,
        )
