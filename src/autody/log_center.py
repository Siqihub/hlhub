from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
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
SEND_RECIPIENT = re.compile(
    r"(?P<prefix>发送(?:已确认|未确认|成功|失败)?：)(?P<name>(?!好友#)[^（(\n]{1,80}?)(?P<tail>[（(]|$)"
)


class LogEntry(BaseModel):
    timestamp: str
    date: str
    level: str
    task_type: str
    summary: str
    detail: str = ""
    source: str
    status: str = "resolved"
    fingerprint: str = ""
    occurrences: int = 1


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

    def replace_recipient(match: re.Match[str]) -> str:
        name = match.group("name").strip()
        if not name:
            return match.group(0)
        suffix = stable_target_id(name)[-4:]
        return f"{match.group('prefix')}好友#{suffix}{match.group('tail')}"

    return SEND_RECIPIENT.sub(replace_recipient, result)


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


def _fingerprint(entry: LogEntry) -> str:
    evidence = "\n".join([entry.summary, *entry.detail.splitlines()[:3]])
    return hashlib.sha256(evidence.encode("utf-8", errors="replace")).hexdigest()[:16]


def _classify(entries: list[LogEntry]) -> list[LogEntry]:
    health_success = max((item.timestamp for item in entries if "登录状态和抖音聊天页正常" in item.summary), default="")
    send_success = max((item.timestamp for item in entries if "本次发送完成" in item.summary and "失败 0 个" in item.summary), default="")
    for item in entries:
        text = f"{item.summary}\n{item.detail}"
        item.fingerprint = _fingerprint(item)
        if LEGACY_LOG_NAME.match(item.source) or item.source == "autody.log" or "TimedRotatingFileHandler" in text:
            item.status = "historical"
        elif item.level != "ERROR":
            item.status = "resolved"
        elif "autody.diagnostics" in text and health_success > item.timestamp:
            item.status = "resolved"
        elif item.task_type == "health_check" and health_success > item.timestamp:
            item.status = "resolved"
        elif (
            item.task_type == "daily_send"
            or "浏览器任务已安全停止" in item.summary
            or "本次部分失败" in item.summary
        ) and send_success > item.timestamp:
            item.status = "resolved"
        else:
            item.status = "active"
    return entries


def _group(entries: list[LogEntry]) -> list[LogEntry]:
    grouped: dict[tuple[str, str, str], LogEntry] = {}
    for item in entries:
        key = (item.fingerprint, item.status, item.level)
        previous = grouped.get(key)
        if previous is None:
            grouped[key] = item
        else:
            previous.occurrences += 1
            if item.timestamp > previous.timestamp:
                item.occurrences = previous.occurrences
                grouped[key] = item
    return list(grouped.values())


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
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    today: date | None = None,
) -> LogPage:
    today = today or date.today()
    end_date = end_date or today
    start_date = start_date or (end_date - timedelta(days=2))
    all_entries: list[LogEntry] = []
    for path in _log_files(log_dir):
        file_day = _named_log_date(path)
        if file_day is not None and not (start_date <= file_day <= end_date):
            continue
        if file_day is None and not (start_date <= datetime.fromtimestamp(path.stat().st_mtime).date() <= end_date):
            continue
        all_entries.extend(parse_log_file(path, config))
    all_entries = _classify(all_entries)
    entries = [item for item in all_entries if start_date.isoformat() <= item.date <= end_date.isoformat()]
    entries = [
        item
        for item in entries
        if (level is None or item.level == level)
        and (task_type is None or item.task_type == task_type)
        and (status is None or item.status == status)
    ]
    entries = _group(entries)
    entries.sort(key=lambda item: item.timestamp, reverse=True)
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


def log_summary(log_dir: Path, config: AppConfig, *, today: date | None = None) -> dict:
    today = today or date.today()
    page = query_logs(log_dir, config, start_date=today - timedelta(days=6), end_date=today, page_size=200, today=today)
    entries = page.items
    errors = [item for item in entries if item.level == "ERROR"]
    latest = lambda task: next((item for item in entries if item.task_type == task), None)
    return {
        "active_errors": sum(item.occurrences for item in errors if item.status == "active"),
        "warnings_24h": sum(item.occurrences for item in entries if item.level == "WARNING" and item.date == today.isoformat()),
        "successful_tasks_7d": sum(1 for item in entries if item.level == "INFO" and ("正常" in item.summary or "本次发送完成" in item.summary)),
        "last_health_check": latest("health_check").summary if latest("health_check") else None,
        "last_send": latest("daily_send").summary if latest("daily_send") else None,
        "last_error_time": max((item.timestamp for item in errors if item.status == "active"), default=None),
    }


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


def archive_historical_logs(log_dir: Path, config: AppConfig) -> list[Path]:
    archive_dir = log_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for path in _log_files(log_dir):
        entries = _classify(parse_log_file(path, config))
        if not entries or not all(item.status == "historical" for item in entries):
            continue
        destination = archive_dir / path.name
        if destination.exists():
            destination = archive_dir / f"{path.stem}-{datetime.now():%H%M%S}{path.suffix}"
        shutil.move(str(path), destination)
        moved.append(destination)
    return moved
