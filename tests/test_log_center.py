from datetime import date
from pathlib import Path

from autody.config import AppConfig, Target
from autody.log_center import archive_logs, query_logs


def test_logs_default_to_three_days_filter_and_mask_names(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    for day, level in [("2026-07-09", "ERROR"), ("2026-07-11", "INFO"), ("2026-07-12", "WARNING"), ("2026-07-13", "ERROR")]:
        (log_dir / f"autody-{day}.log").write_text(
            f"{day} 08:00:00,000 {level} 发送失败：小明\nTraceback line\n",
            encoding="utf-8",
        )
    config = AppConfig(targets=[Target(name="小明")], mask_log_friend_names=True)

    page = query_logs(log_dir, config, today=date(2026, 7, 13), level="ERROR")

    assert page.start_date == "2026-07-11"
    assert page.total == 1
    assert "小明" not in page.items[0].summary
    assert "好友#" in page.items[0].summary
    assert page.items[0].detail == "Traceback line"


def test_archive_moves_old_logs_without_deleting(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    old = log_dir / "autody-2026-07-01.log"
    recent = log_dir / "autody-2026-07-13.log"
    old.write_text("old", encoding="utf-8")
    recent.write_text("recent", encoding="utf-8")

    moved = archive_logs(log_dir, date(2026, 7, 10))

    assert len(moved) == 1
    assert moved[0].read_text(encoding="utf-8") == "old"
    assert not old.exists()
    assert recent.exists()


def test_legacy_rotated_traceback_is_filterable_and_collapsed(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "autody.log.2026-07-01").write_text(
        "2026-07-01 08:00:00,000 ERROR 发送任务异常：小明\n"
        "Traceback (most recent call last):\n"
        "  File 'runner.py', line 1\n"
        "RuntimeError: failed\n",
        encoding="utf-8",
    )
    config = AppConfig(targets=[Target(name="小明")])

    page = query_logs(
        log_dir,
        config,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 1),
        level="ERROR",
    )

    assert page.total == 1
    assert "好友#" in page.items[0].summary
    assert page.items[0].detail.startswith("Traceback")
