from pathlib import Path

from typer.testing import CliRunner

from autody.cli import app


runner = CliRunner()


def test_check_config_reports_success(tmp_path: Path):
    (tmp_path / "messages.txt").write_text("早安\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["check-config", "--config", str(tmp_path / "config.yaml")]
    )
    assert result.exit_code == 0
    assert "配置有效" in result.stdout


def test_check_config_rejects_missing_message_library(tmp_path: Path):
    (tmp_path / "config.yaml").write_text(
        "targets:\n  - name: 小明\nmessages_file: missing.txt\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["check-config", "--config", str(tmp_path / "config.yaml")]
    )
    assert result.exit_code != 0
    assert "文案库不存在" in result.output


def test_health_check_reports_success(tmp_path: Path, monkeypatch):
    (tmp_path / "messages.txt").write_text("早安\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n",
        encoding="utf-8",
    )

    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("autody.cli.open_chat", lambda *args, **kwargs: Context())
    result = runner.invoke(
        app, ["health-check", "--config", str(tmp_path / "config.yaml")]
    )
    assert result.exit_code == 0
    assert "登录状态正常" in result.stdout
