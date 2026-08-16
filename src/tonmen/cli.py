from __future__ import annotations

from .core.runtime import TonmenRuntime

BANNER = """\
╔══════════════════════════════════════════════╗
║              雲 頂 天 宮                    ║
║               TONMEN Forge                 ║
║              by Top-Men AI                 ║
╚══════════════════════════════════════════════╝
"""


def main() -> int:
    runtime = TonmenRuntime.forge()
    print(BANNER)
    print(runtime.status_text())
    print("\n人予其意，宮成其事。")
    return 0
