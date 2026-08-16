from pathlib import Path

from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime


def test_runtime_rejects_arbitrary_shell():
    cfg = TonmenConfig(workspace=Path("."), allow_arbitrary_shell=True)
    try:
        TonmenRuntime.genesis(cfg)
    except ValueError as exc:
        assert "forbids arbitrary shell" in str(exc)
    else:
        raise AssertionError("arbitrary shell must never be enabled in Genesis")
