from __future__ import annotations

from tonmen.cli import main


def test_artifact_cli_inspect_list_show_delete_without_executing(tmp_path, capsys):
    config = tmp_path / "tonmen.toml"
    source = tmp_path / "sample.bin"
    source.write_bytes(b"\x7fELF" + b"\x00" * 32)

    assert main(["--config", str(config), "artifact", "inspect", str(source)]) == 0
    inspect_output = capsys.readouterr().out
    assert '"execution_performed": false' in inspect_output
    assert '"sha256":' in inspect_output
    assert "未加载、未执行" in inspect_output

    report_files = list((tmp_path / ".tonmen" / "artifacts" / "reports").glob("*.json"))
    assert len(report_files) == 1
    artifact_id = report_files[0].stem

    assert main(["--config", str(config), "artifact", "list"]) == 0
    assert artifact_id in capsys.readouterr().out

    assert main(["--config", str(config), "artifact", "show", artifact_id]) == 0
    show_output = capsys.readouterr().out
    assert artifact_id in show_output
    assert '"execution_performed": false' in show_output

    assert main(["--config", str(config), "artifact", "delete", artifact_id]) == 0
    assert "Artifact 已删除" in capsys.readouterr().out
    assert not report_files[0].exists()
