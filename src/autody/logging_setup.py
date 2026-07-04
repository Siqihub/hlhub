from datetime import date
import logging
from pathlib import Path

from autody.config import AppConfig


def setup_logging(
    config: AppConfig,
    today: date | None = None,
    logger: logging.Logger | None = None,
) -> Path:
    active_logger = logger or logging.getLogger()
    log_dir = config.state_file.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"autody-{today or date.today():%Y-%m-%d}.log"

    for handler in list(active_logger.handlers):
        if getattr(handler, "_autody_daily_handler", False):
            active_logger.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler._autody_daily_handler = True
    active_logger.setLevel(logging.INFO)
    active_logger.addHandler(file_handler)
    return log_path


def read_daily_logs(log_dir: Path, line_limit: int = 400) -> str:
    files = sorted(log_dir.glob("autody-????-??-??.log"))
    if not files:
        legacy = log_dir / "autody.log"
        files = [legacy] if legacy.exists() else []
    lines: list[str] = []
    for path in files[-14:]:
        lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return "\n".join(lines[-line_limit:])

