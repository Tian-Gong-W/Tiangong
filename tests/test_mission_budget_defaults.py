from __future__ import annotations

from importlib import resources

from tonmen.cli import _parser
from tonmen.loop import MissionLoopPolicy


def test_mission_budget_defaults_are_consistent_across_policy_cli_and_console():
    policy = MissionLoopPolicy()
    assert policy.max_executions == 6
    assert policy.max_duration_seconds == 900

    args = _parser().parse_args(["loop", "localhost"])
    assert args.max_executions == 6
    assert args.max_duration_seconds == 900

    # Server source is checked because the HTTP handler's fallback is the third
    # independent constructor path used when a Console client omits budget fields.
    server_source = resources.files("tonmen.dashboard").joinpath("server.py").read_text(encoding="utf-8")
    assert 'data.get("max_executions", 6)' in server_source
    assert 'data.get("max_duration_seconds", 900)' in server_source
    assert 'data.get("max_executions", 3)' not in server_source
    assert 'data.get("max_duration_seconds", 300)' not in server_source
