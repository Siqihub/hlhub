from pathlib import Path

from typer.testing import CliRunner

from autody.cli import app
from autody.locking import SingleInstanceLock
from autody.runner import RunResult, RunStatus


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


def test_health_check_skips_when_another_browser_task_holds_lock(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "messages.txt").write_text("早安\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n"
        "lock_file: data/locks/autody.lock\n",
        encoding="utf-8",
    )
    called = False

    def should_not_open(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("browser must not open while lock is held")

    monkeypatch.setattr("autody.cli.open_chat", should_not_open)
    lock_path = tmp_path / "data" / "locks" / "autody.lock"
    with SingleInstanceLock(lock_path):
        result = runner.invoke(
            app, ["health-check", "--config", str(tmp_path / "config.yaml")]
        )

    assert result.exit_code == 0
    assert "已有 AutoDy 任务正在运行，本次跳过。" in result.stdout
    assert called is False


def test_scan_friends_uses_same_global_lock(tmp_path: Path, monkeypatch):
    (tmp_path / "messages.txt").write_text("早安\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        "targets: []\nmessages_file: messages.txt\n"
        "lock_file: data/locks/autody.lock\n",
        encoding="utf-8",
    )
    called = False

    def should_not_open(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("browser must not open while lock is held")

    monkeypatch.setattr("autody.cli.open_chat", should_not_open)
    with SingleInstanceLock(tmp_path / "data" / "locks" / "autody.lock"):
        result = runner.invoke(app, ["scan-friends", "--config", str(config)])

    assert result.exit_code == 0
    assert "已有 AutoDy 任务正在运行，本次跳过。" in result.stdout
    assert called is False


def test_run_reports_already_done_without_claiming_new_send(tmp_path: Path, monkeypatch):
    (tmp_path / "messages.txt").write_text("早安\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n",
        encoding="utf-8",
    )

    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("autody.cli.open_chat", lambda *_args, **_kwargs: Context())
    monkeypatch.setattr("autody.cli.DouyinChat", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "autody.cli.run_daily",
        lambda *_args, **_kwargs: RunResult(
            status=RunStatus.ALREADY_DONE,
            total_targets=1,
            sent_count=0,
            skipped_count=1,
            failed_count=0,
        ),
    )

    result = runner.invoke(app, ["run", "--config", str(config)])

    assert result.exit_code == 0
    assert "当天所有目标此前已完成。" in result.stdout
    assert "当天所有目标已完成。" not in result.stdout


def test_run_reports_completed_counts(tmp_path: Path, monkeypatch):
    (tmp_path / "messages.txt").write_text("早安\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n",
        encoding="utf-8",
    )

    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("autody.cli.open_chat", lambda *_args, **_kwargs: Context())
    monkeypatch.setattr("autody.cli.DouyinChat", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "autody.cli.run_daily",
        lambda *_args, **_kwargs: RunResult(
            status=RunStatus.COMPLETED,
            total_targets=2,
            sent_count=2,
            skipped_count=0,
            failed_count=0,
        ),
    )

    result = runner.invoke(app, ["run", "--config", str(config)])

    assert result.exit_code == 0
    assert "本次发送完成：成功 2 个，失败 0 个。" in result.stdout


def test_run_reports_partial_failure_and_exit_code(tmp_path: Path, monkeypatch):
    (tmp_path / "messages.txt").write_text("早安\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n",
        encoding="utf-8",
    )

    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("autody.cli.open_chat", lambda *_args, **_kwargs: Context())
    monkeypatch.setattr("autody.cli.DouyinChat", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "autody.cli.run_daily",
        lambda *_args, **_kwargs: RunResult(
            status=RunStatus.PARTIAL_FAILED,
            total_targets=2,
            sent_count=1,
            skipped_count=0,
            failed_count=1,
        ),
    )

    result = runner.invoke(app, ["run", "--config", str(config)])

    assert result.exit_code == 2
    assert "本次发送完成：成功 1 个，失败 1 个。" in result.stdout
    assert "本次部分失败，再次运行将只补发失败目标。" in result.output


def test_ui_starts_local_server(tmp_path: Path, monkeypatch):
    (tmp_path / "messages.txt").write_text("早安\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n",
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr("autody.cli.uvicorn.run", lambda app, **kwargs: calls.append(kwargs))
    result = runner.invoke(
        app,
        [
            "ui",
            "--config",
            str(tmp_path / "config.yaml"),
            "--no-open",
            "--port",
            "9876",
        ],
    )
    assert result.exit_code == 0
    assert calls == [{"host": "127.0.0.1", "port": 9876, "log_level": "warning"}]
