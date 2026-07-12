from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from pathlib import Path
import shutil

from pydantic import BaseModel

from autody.config import AppConfig
from autody.history import stable_target_id


LOG_LINE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)\s+"
    r"(?P<level>INFO|WARNING|ERROR|CRITICAL)\s+(?P<message>.*)$"
)
CURRENT_LOG_NAME = re.compile(r"^autody-(\d{4}-\d{2}-\d{2})\.log$")
LEGACY_LOG_NAME = re.compile(r"^autody\.log\.(\d{4}-\d{2}-\d{2})$")


class LogEntry(BaseModel):
    timestamp: str
    date: str
    level: str
    task_type: str
    summary: str
    detail: str = ""
    source: str


class LogPage(BaseModel):
    items: list[LogEntry]
    total: int
    page: int
    page_size: int
    start_date: str
    end_date: str


def _task_type(message: str) -> str:
    lowered = message.lower()
    if "好友识别" in message or "scan" in lowered:
        return "friend_scan"
    if "扫码" in message or "login" in lowered:
        return "login"
    if "登录" in message or "health" in lowered:
        return "health_check"
    if "发送" in message or "续火" in message:
        return "daily_send"
    return "system"


def _mask(text: str, config: AppConfig) -> str:
    if not config.mask_log_friend_names:
        return text
    result = text
    for target in sorted(config.targets, key=lambda item: len(item.name), reverse=True):
        suffix = stable_target_id(target.name)[-4:]
        result = result.replace(target.name, f"好友#{suffix}")
    return result


def parse_log_file(path: Path, config: AppConfig) -> list[LogEntry]:
    entries: list[LogEntry] = []
    current: LogEntry | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LOG_LINE.match(line)
        if match:
            if current:
                entries.append(current)
            message = _mask(match.group("message"), config)
            current = LogEntry(
                timestamp=match.group("timestamp"),
                date=match.group("timestamp")[:10],
                level="ERROR" if match.group("level") == "CRITICAL" else match.group("level"),
                task_type=_task_type(message),
                summary=message[:240],
                source=path.name,
            )
        elif current:
            detail_line = _mask(line, config)
            current.detail = f"{current.detail}\n{detail_line}".strip()
        elif line.strip():
            stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            message = _mask(line.strip(), config)
            current = LogEntry(
                timestamp=stamp,
                date=stamp[:10],
                level="INFO",
                task_type=_task_type(message),
                summary=message[:240],
                source=path.name,
            )
    if current:
        entries.append(current)
    return entries


def _named_log_date(path: Path) -> date | None:
    match = CURRENT_LOG_NAME.match(path.name) or LEGACY_LOG_NAME.match(path.name)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _log_files(log_dir: Path) -> list[Path]:
    files = {
        *log_dir.glob("autody-????-??-??.log"),
        *log_dir.glob("autody.log.????-??-??"),
    }
    legacy = log_dir / "autody.log"
    if legacy.exists():
        files.add(legacy)
    return sorted(files, key=lambda path: path.name)


def query_logs(
    log_dir: Path,
    config: AppConfig,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    level: str | None = None,
    task_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    today: date | None = None,
) -> LogPage:
    today = today or date.today()
    end_date = end_date or today
    start_date = start_date or (end_date - timedelta(days=2))
    entries: list[LogEntry] = []
    for path in _log_files(log_dir):
        file_day = _named_log_date(path)
        if file_day is None:
            entries.extend(
                item for item in parse_log_file(path, config)
                if start_date.isoformat() <= item.date <= end_date.isoformat()
            )
            continue
        if start_date <= file_day <= end_date:
            entries.extend(parse_log_file(path, config))
    entries = [
        item
        for item in entries
        if (level is None or item.level == level)
        and (task_type is None or item.task_type == task_type)
    ]
    entries.reverse()
    page = max(1, page)
    page_size = min(200, max(1, page_size))
    offset = (page - 1) * page_size
    return LogPage(
        items=entries[offset : offset + page_size],
        total=len(entries),
        page=page,
        page_size=page_size,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )


def archive_logs(log_dir: Path, before: date) -> list[Path]:
    archive_dir = log_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for path in _log_files(log_dir):
        file_date = _named_log_date(path) or datetime.fromtimestamp(path.stat().st_mtime).date()
        if file_date >= before:
            continue
        destination = archive_dir / path.name
        if destination.exists():
            destination = archive_dir / f"{path.stem}-{datetime.now():%H%M%S}{path.suffix}"
        shutil.move(str(path), destination)
        moved.append(destination)
    return moved
