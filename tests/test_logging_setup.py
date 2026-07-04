from datetime import date
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from autody.config import AppConfig, Target
from autody.logging_setup import read_daily_logs, setup_logging


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        targets=[Target(name="小明")],
        state_file=tmp_path / "data" / "state.json",
    )


def test_logging_writes_directly_to_date_named_file_without_rotation(tmp_path: Path):
    logger = logging.getLogger(f"autody-test-{tmp_path.name}")
    logger.handlers.clear()

    path = setup_logging(make_config(tmp_path), today=date(2026, 7, 4), logger=logger)

    assert path == tmp_path / "data" / "logs" / "autody-2026-07-04.log"
    assert any(isinstance(handler, logging.FileHandler) for handler in logger.handlers)
    assert not any(
        isinstance(handler, TimedRotatingFileHandler) for handler in logger.handlers
    )
    logger.info("测试日志")
    for handler in logger.handlers:
        handler.flush()
    assert "测试日志" in path.read_text(encoding="utf-8")


def test_read_daily_logs_merges_recent_files_in_time_order(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "autody-2026-07-03.log").write_text("旧记录\n", encoding="utf-8")
    (log_dir / "autody-2026-07-04.log").write_text("新记录\n", encoding="utf-8")
    (log_dir / "autody.log").write_text("旧轮转格式\n", encoding="utf-8")

    text = read_daily_logs(log_dir, line_limit=20)

    assert text.splitlines() == ["旧记录", "新记录"]

