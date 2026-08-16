from __future__ import annotations

from .core.runtime import TonmenRuntime

BANNER = """\
╔══════════════════════════════════════════════╗
║              雲 頂 天 宮                    ║
║             TONMEN Sentinel                ║
║              by Top-Men AI                 ║
╚══════════════════════════════════════════════╝
"""


def main() -> int:
    runtime = TonmenRuntime.sentinel()
    print(BANNER)
    print(runtime.status_text())
    print("\n人予其意，宮成其事。")
    return 0
