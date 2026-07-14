from datetime import date, datetime
from io import BytesIO, StringIO
import csv
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import zipfile

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import yaml

from autody.config import (
    AppConfig,
    MessageSuffixConfig,
    Target,
    load_config,
    save_config,
)
from autody.friend_discovery import load_discovered_friends
from autody.history import TaskHistoryStore, bootstrap_legacy_daily_history, dashboard_statistics
from autody.log_center import archive_historical_logs, archive_logs, log_summary, query_logs
from autody.message_packs import ImportMode, MessagePackError, MessagePackService
from autody.messages import read_messages
from autody.recovery import recovery_due
from autody.state import StateStore
from autody.scheduler import ScheduleSettings, SchedulerService
from autody.transfer import (
    DEFAULT_CATEGORIES,
    ExportCategory,
    ImportMode as BackupImportMode,
    TransferError,
    apply_backup,
    apply_friend_import,
    apply_message_import,
    create_backup,
    parse_friend_import,
    parse_message_import,
    preview_backup,
)
from autody.web_actions import ActionAlreadyRunning, ActionManager


class ConfigUpdate(BaseModel):
    targets: list[str] = Field(default_factory=list)
    retry_count: int = Field(ge=1, le=5)
    timeout_ms: int = Field(ge=5_000, le=120_000)
    headless: bool
    message_suffix: MessageSuffixConfig = Field(default_factory=MessageSuffixConfig)
    message_pack_index_url: str | None = None
    daily_send_time: str = Field(default="07:30", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    daily_health_check_time: str = Field(default="07:20", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    weekly_health_check_enabled: bool = True
    weekly_health_check_weekday: str = Field(default="Sunday", pattern=r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$")
    weekly_health_check_time: str = Field(default="20:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    startup_recovery_enabled: bool = True
    recovery_deadline: str = Field(default="23:59", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    min_delay_seconds: float = Field(default=1.0, ge=0, le=60)
    max_delay_seconds: float = Field(default=3.0, ge=0, le=60)
    page_load_timeout_ms: int = Field(default=30_000, ge=5_000, le=120_000)
    friend_search_timeout_ms: int = Field(default=30_000, ge=5_000, le=120_000)
    confirmation_timeout_ms: int = Field(default=12_000, ge=2_000, le=60_000)
    friend_order: str = Field(default="configured", pattern=r"^(configured|randomized)$")
    message_selection: str = Field(default="one_for_all", pattern=r"^(one_for_all|per_friend)$")
    completion_notifications_enabled: bool = True
    log_retention_days: int = Field(default=30, ge=7, le=3650)
    mask_log_friend_names: bool = True


class MessagesUpdate(BaseModel):
    messages: list[str]


class MessagePackImportRequest(BaseModel):
    mode: ImportMode


class ScheduleUpdate(ScheduleSettings):
    pass


class BackupExportRequest(BaseModel):
    categories: list[ExportCategory] = Field(default_factory=lambda: list(DEFAULT_CATEGORIES))


class FriendBatchUpdate(BaseModel):
    names: list[str] = Field(default_factory=list)
    action: str = Field(pattern=r"^(enable|disable|delete)$")


def _tail(path: Path, limit: int = 400) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - 131_072))
        text = handle.read().decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-limit:])


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def _login_status(path: Path, log_dir: Path | None = None) -> str:
    if not path.exists():
        if log_dir is None:
            return "unknown"
        dated = sorted(log_dir.glob("autody-????-??-??.log"))
        fallback = dated[-1] if dated else log_dir / "autody.log"
        if not fallback.exists():
            return "unknown"
        text = _tail(fallback, 200)
        successful = text.rfind("登录状态和抖音聊天页正常")
        failed = max(text.rfind("登录健康检查失败"), text.rfind("浏览器任务已安全停止"))
        if successful < 0 and failed < 0:
            return "unknown"
        return "failed" if failed > successful else "success"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("status", "unknown"))
    except (json.JSONDecodeError, OSError, TypeError):
        return "unknown"


def _message_count(path: Path) -> int:
    try:
        return len(read_messages(path))
    except (FileNotFoundError, ValueError):
        return 0


def _runtime_available(root: Path) -> bool:
    browsers = root / "data" / "ms-playwright"
    return any(browsers.glob("chromium-*/chrome-win*/chrome.exe"))


def _config_payload(config: AppConfig) -> dict:
    return {
        "targets": [target.name for target in config.targets],
        "retry_count": config.retry_count,
        "timeout_ms": config.timeout_ms,
        "headless": config.headless,
        "message_suffix": config.message_suffix.model_dump(mode="json"),
        "message_pack_index_url": config.message_pack_index_url,
        "daily_send_time": config.daily_send_time,
        "daily_health_check_time": config.daily_health_check_time,
        "weekly_health_check_enabled": config.weekly_health_check_enabled,
        "weekly_health_check_weekday": config.weekly_health_check_weekday,
        "weekly_health_check_time": config.weekly_health_check_time,
        "startup_recovery_enabled": config.startup_recovery_enabled,
        "recovery_deadline": config.recovery_deadline,
        "min_delay_seconds": config.min_delay_seconds,
        "max_delay_seconds": config.max_delay_seconds,
        "page_load_timeout_ms": config.page_load_timeout_ms,
        "friend_search_timeout_ms": config.friend_search_timeout_ms,
        "confirmation_timeout_ms": config.confirmation_timeout_ms,
        "friend_order": config.friend_order,
        "message_selection": config.message_selection,
        "completion_notifications_enabled": config.completion_notifications_enabled,
        "log_retention_days": config.log_retention_days,
        "mask_log_friend_names": config.mask_log_friend_names,
    }


def _task_rows() -> list[dict]:
    if platform.system() != "Windows":
        return []
    script = """
$rows=@()
foreach($name in @('AutoDy-Health-Daily','AutoDy-DailySpark','AutoDy-Health-Weekly')){
  $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  if($task){
    $info=Get-ScheduledTaskInfo -TaskName $name
    $rows += [pscustomobject]@{
      name=$name; state=[string]$task.State; next_run=$info.NextRunTime.ToString('s');
      last_run=$info.LastRunTime.ToString('s'); last_result=$info.LastTaskResult
    }
  }
}
$rows | ConvertTo-Json -Compress
"""
    try:
        output = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=8,
            check=False,
        ).stdout.strip()
        if not output:
            return []
        data = json.loads(output)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def _portable_config(config_path: Path, config: AppConfig) -> bytes:
    root = config_path.parent

    def portable(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(root))
        except ValueError:
            return str(path)

    data = {
        "targets": [target.model_dump(mode="json", exclude_none=True) for target in config.targets],
        "messages_file": portable(config.messages_file),
        "profile_dir": portable(config.profile_dir),
        "state_file": portable(config.state_file),
        "lock_file": portable(config.lock_file),
        "artifact_dir": portable(config.artifact_dir),
        "retry_count": config.retry_count,
        "timeout_ms": config.timeout_ms,
        "headless": config.headless,
        "message_suffix": config.message_suffix.model_dump(mode="json"),
        "message_pack_index_url": config.message_pack_index_url,
        "daily_send_time": config.daily_send_time,
        "daily_health_check_time": config.daily_health_check_time,
        "weekly_health_check_enabled": config.weekly_health_check_enabled,
        "weekly_health_check_weekday": config.weekly_health_check_weekday,
        "weekly_health_check_time": config.weekly_health_check_time,
        "startup_recovery_enabled": config.startup_recovery_enabled,
        "recovery_deadline": config.recovery_deadline,
        "min_delay_seconds": config.min_delay_seconds,
        "max_delay_seconds": config.max_delay_seconds,
        "page_load_timeout_ms": config.page_load_timeout_ms,
        "friend_search_timeout_ms": config.friend_search_timeout_ms,
        "confirmation_timeout_ms": config.confirmation_timeout_ms,
        "friend_order": config.friend_order,
        "message_selection": config.message_selection,
        "completion_notifications_enabled": config.completion_notifications_enabled,
        "log_retention_days": config.log_retention_days,
        "mask_log_friend_names": config.mask_log_friend_names,
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).encode("utf-8")


def create_app(config_path: Path, action_runner=None, now_provider=None) -> FastAPI:
    config_path = config_path.resolve()
    root = config_path.parent
    manager = ActionManager(root, config_path)
    run_action = action_runner or manager.start
    current_time = now_provider or datetime.now
    app = FastAPI(title="AutoDy", docs_url=None, redoc_url=None)
    task_cache: dict[str, object] = {"expires": 0.0, "rows": []}
    recovery_attempted: set[str] = set()

    def cached_task_rows() -> list[dict]:
        if time.monotonic() >= float(task_cache["expires"]):
            task_cache["rows"] = _task_rows()
            task_cache["expires"] = time.monotonic() + 10
        return list(task_cache["rows"])  # type: ignore[arg-type]

    @app.get("/api/status")
    def status(today: str | None = None):
        config = load_config(config_path)
        state = StateStore(config.state_file).load()
        key = today or date.today().isoformat()
        daily = state.daily.get(
            key, {"message": "", "succeeded": [], "failures": {}, "consumed": False}
        )
        succeeded = set(daily.get("succeeded", []))
        failures = daily.get("failures", {})
        friends = []
        for target in config.targets:
            friend_status = (
                "success"
                if target.name in succeeded
                else "failed"
                if target.name in failures
                else "pending"
            )
            friends.append(
                {
                    "name": target.name,
                    "status": friend_status,
                    "error": failures.get(target.name),
                }
            )
        history_store = TaskHistoryStore(config.state_file.parent / "history" / "task-runs.jsonl")
        bootstrap_legacy_daily_history(history_store, state.daily, len(config.targets))
        history_page = history_store.query(page_size=30)
        records = list(reversed(history_page.items))
        history = [
            {
                "run_id": item.run_id,
                "date": item.date,
                "task_type": item.task_type,
                "trigger_source": item.trigger_source,
                "success_count": item.success_count,
                "failed_count": item.failed_count,
                "skipped_count": item.skipped_count,
                "total_targets": item.total_targets,
                "retry_count": item.retry_count,
                "final_status": item.final_status,
                "end_time": item.end_time,
            }
            for item in history_page.items
        ]
        tasks = cached_task_rows()
        message_count = _message_count(config.messages_file)
        next_run = next(
            (
                task.get("next_run")
                for task in tasks
                if task.get("name") == "AutoDy-DailySpark"
            ),
            None,
        )
        next_health = next(
            (task.get("next_run") for task in tasks if task.get("name") == "AutoDy-Health-Daily"),
            None,
        )
        login_status = _login_status(
            config.state_file.parent / "health.json",
            config.state_file.parent / "logs",
        )
        issues = []
        if login_status == "failed":
            issues.append({
                "id": "login_expired", "status": "error",
                "explanation": "抖音登录已失效或需要安全验证。",
                "action": "login", "action_label": "扫码登录",
            })
        if not _runtime_available(root):
            issues.append({
                "id": "runtime_missing", "status": "error",
                "explanation": "项目内 Chromium 缺失或不可用。",
                "action": "repair-playwright", "action_label": "修复运行时",
            })
        if not config.targets:
            issues.append({
                "id": "no_friends", "status": "warning",
                "explanation": "尚未配置续火好友。",
                "action": "friends", "action_label": "管理好友",
            })
        if message_count == 0:
            issues.append({
                "id": "no_messages", "status": "warning",
                "explanation": "本地文案库为空。",
                "action": "packs", "action_label": "导入文案",
            })
        if not any(task.get("name") == "AutoDy-DailySpark" for task in tasks):
            issues.append({
                "id": "scheduler_missing", "status": "warning",
                "explanation": "每日定时任务尚未安装。",
                "action": "scheduler", "action_label": "安装任务",
            })
        if daily.get("message") and not daily.get("consumed"):
            issues.append({
                "id": "last_run_partial", "status": "warning",
                "explanation": "最近一次发送未全部完成，再次运行只补发失败目标。",
                "action": "run", "action_label": "继续补发",
            })
        latest_run = history_page.items[0] if history_page.items else None
        if latest_run and "confirmation_failed" in latest_run.confirmation_results.values():
            issues.append({
                "id": "message_confirmation_failure", "status": "error",
                "explanation": "最近一次发送存在未确认消息，再次运行只处理未完成目标。",
                "action": "run", "action_label": "继续补发",
            })
        if not config.message_pack_index_url:
            issues.append({
                "id": "remote_library", "status": "warning",
                "explanation": "未配置 GitHub 远程文案索引，当前使用内置文案包。",
                "action": "packs", "action_label": "查看文案包",
            })
        notice = config.state_file.parent / "notifications" / "need-attention.txt"
        if notice.exists():
            issues.append({
                "id": "notification", "status": "error",
                "explanation": _tail(notice, 8),
                "action": "logs", "action_label": "查看日志",
            })
        statistics = dashboard_statistics(records, date.fromisoformat(key))
        try:
            pack_count = len(json.loads((root / "message-packs" / "index.json").read_text(encoding="utf-8")).get("packs", []))
        except (OSError, json.JSONDecodeError, TypeError):
            pack_count = 0
        statistics.update({
            "successful_today": len(succeeded),
            "failed_today": len(failures),
            "configured_friend_count": len(config.targets),
            "enabled_friend_count": len(config.targets),
            "local_message_count": message_count,
            "active_message_pack_count": pack_count,
            "next_health_check": next_health,
            "next_daily_send": next_run,
            "most_recent_issue": issues[0]["explanation"] if issues else None,
            "log_summary": log_summary(config.state_file.parent / "logs", config),
        })
        return {
            "today": {
                "date": key,
                "message": daily.get("message", ""),
                "succeeded": len(succeeded),
                "failed": len(failures),
                "total": len(config.targets),
                "complete": bool(daily.get("consumed")),
            },
            "friends": friends,
            "history": history[:30],
            "scheduler": tasks,
            "next_run": next_run,
            "login": {"status": login_status},
            "message_count": message_count,
            "issues": issues,
            "statistics": statistics,
        }

    @app.get("/api/config")
    def get_config():
        return _config_payload(load_config(config_path))

    @app.put("/api/config")
    def update_config(payload: ConfigUpdate):
        config = load_config(config_path)
        existing = {target.name: target for target in config.targets}
        config.targets = [existing.get(name, Target(name=name)) for name in payload.targets]
        for field_name, value in payload.model_dump().items():
            if field_name != "targets":
                if field_name == "message_suffix":
                    value = MessageSuffixConfig.model_validate(value)
                setattr(config, field_name, value)
        config = AppConfig.model_validate(config.model_dump())
        save_config(config_path, config)
        return _config_payload(config)

    @app.post("/api/scheduler/preview")
    def scheduler_preview(payload: ScheduleUpdate):
        current = load_config(config_path)
        candidate = current.model_copy(update=payload.model_dump())
        candidate = AppConfig.model_validate(candidate.model_dump())
        return SchedulerService(root).preview(current, candidate)

    @app.post("/api/scheduler/apply")
    def scheduler_apply(payload: ScheduleUpdate):
        current = load_config(config_path)
        candidate = AppConfig.model_validate(current.model_copy(update=payload.model_dump()).model_dump())
        try:
            SchedulerService(root).apply(config_path, current, candidate)
        except RuntimeError as exc:
            raise HTTPException(409, f"定时任务未更新：{exc}") from exc
        return {"config": _config_payload(candidate), "tasks": _task_rows(), "message": "定时任务已更新"}

    @app.post("/api/scheduler/{operation}")
    def scheduler_operation(operation: str):
        service = SchedulerService(root)
        config = load_config(config_path)
        try:
            if operation in {"install", "update", "repair"}:
                getattr(service, "repair" if operation == "repair" else "install")(config)
            elif operation == "remove":
                service.remove()
            else:
                raise HTTPException(404, "未知定时任务操作")
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"tasks": _task_rows(), "message": "定时任务操作完成"}

    @app.post("/api/recovery/check")
    def check_startup_recovery():
        config = load_config(config_path)
        now = current_time()
        key = now.date().isoformat()
        due = config.startup_recovery_enabled and recovery_due(config, StateStore(config.state_file).load(), now)
        if not due or key in recovery_attempted:
            return {"due": due, "started": False, "already_checked": key in recovery_attempted}
        recovery_attempted.add(key)
        try:
            job = run_action("startup-recovery")
        except ActionAlreadyRunning:
            return {"due": True, "started": False, "already_checked": False}
        return {"due": True, "started": True, "job": job}

    @app.get("/api/history")
    def task_history(
        start_date: date | None = None,
        end_date: date | None = None,
        status_filter: str | None = None,
        task_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        config = load_config(config_path)
        return TaskHistoryStore(
            config.state_file.parent / "history" / "task-runs.jsonl"
        ).query(
            start_date=start_date,
            end_date=end_date,
            status=status_filter,
            task_type=task_type,
            page=page,
            page_size=page_size,
        )

    @app.get("/api/messages")
    def get_messages():
        config = load_config(config_path)
        return {"messages": read_messages(config.messages_file)}

    @app.put("/api/messages")
    def update_messages(payload: MessagesUpdate):
        config = load_config(config_path)
        messages = list(dict.fromkeys(item.strip() for item in payload.messages if item.strip()))
        if not messages:
            raise HTTPException(422, "文案库不能为空")
        temporary = config.messages_file.with_suffix(".tmp")
        temporary.write_text("\n".join(messages) + "\n", encoding="utf-8")
        os.replace(temporary, config.messages_file)
        return {"messages": messages}

    @app.post("/api/messages/import/preview")
    async def preview_message_import(file: UploadFile = File(...)):
        try:
            result = parse_message_import(await file.read(), file.filename or "messages.txt")
        except TransferError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "total_entries": result.total_count, "valid_entries": result.valid_count,
            "exact_duplicates": result.exact_duplicates, "empty_entries": result.empty_count,
            "overly_long_entries": result.long_count, "entries_with_links": result.link_count,
        }

    @app.post("/api/messages/import")
    async def import_messages(file: UploadFile = File(...), mode: BackupImportMode = BackupImportMode.MERGE):
        config = load_config(config_path)
        try:
            result = apply_message_import(config, parse_message_import(await file.read(), file.filename or "messages.txt"), mode=mode)
        except TransferError as exc:
            raise HTTPException(422, str(exc)) from exc
        return result

    @app.post("/api/messages/deduplicate")
    def deduplicate_messages():
        config = load_config(config_path)
        try:
            messages = read_messages(config.messages_file)
            before = len([line for line in config.messages_file.read_text(encoding="utf-8").splitlines() if line.strip()])
            parsed = parse_message_import("\n".join(messages).encode("utf-8"), "messages.txt")
            result = apply_message_import(config, parsed, mode=BackupImportMode.REPLACE)
        except (FileNotFoundError, ValueError, TransferError) as exc:
            raise HTTPException(422, str(exc)) from exc
        result["removed"] = max(0, before - len(messages))
        return result

    @app.get("/api/messages/export")
    def export_messages(format: str = "txt", source: str = "local", category: str | None = None, pack_id: str | None = None):
        config = load_config(config_path)
        try:
            if source == "local":
                messages = read_messages(config.messages_file)
            else:
                service = MessagePackService(root, config.message_pack_index_url)
                packs = service.list_packs().packs
                selected = [item for item in packs if (pack_id and item.id == pack_id) or (category and item.category == category)]
                if not selected:
                    raise MessagePackError("未找到指定文案包或类别")
                messages = []
                for pack in selected:
                    messages.extend(service.preview(pack.id).messages)
                messages = list(dict.fromkeys(messages))
        except (FileNotFoundError, ValueError, MessagePackError) as exc:
            raise HTTPException(422, str(exc)) from exc
        if format == "json":
            return Response(_json_bytes({"messages": messages}), media_type="application/json", headers={"Content-Disposition": "attachment; filename=autody-messages.json"})
        if format == "csv":
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(["message"])
            writer.writerows([[item] for item in messages])
            return PlainTextResponse(output.getvalue(), headers={"Content-Disposition": "attachment; filename=autody-messages.csv"})
        return PlainTextResponse("\n".join(messages) + "\n", headers={"Content-Disposition": "attachment; filename=autody-messages.txt"})

    @app.get("/api/message-packs")
    def message_packs():
        config = load_config(config_path)
        try:
            return MessagePackService(
                root, config.message_pack_index_url
            ).list_packs()
        except MessagePackError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/api/message-packs/{pack_id}")
    def preview_message_pack(pack_id: str):
        config = load_config(config_path)
        try:
            return MessagePackService(
                root, config.message_pack_index_url
            ).preview(pack_id)
        except MessagePackError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/message-packs/{pack_id}/import")
    def import_message_pack(pack_id: str, payload: MessagePackImportRequest):
        config = load_config(config_path)
        try:
            return MessagePackService(
                root, config.message_pack_index_url
            ).import_pack(pack_id, config.messages_file, payload.mode)
        except MessagePackError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/friends/scan", status_code=202)
    def scan_friends():
        try:
            return run_action("scan-friends")
        except ActionAlreadyRunning as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/friends/discovered")
    def discovered_friends():
        config = load_config(config_path)
        result = load_discovered_friends(
            config.state_file.parent / "discovered_friends.json"
        )
        if result is None:
            return {"scanned_at": None, "candidates": []}
        configured = {target.name for target in config.targets}
        return {
            "scanned_at": result.scanned_at,
            "candidates": [
                {
                    "name": candidate.name,
                    "already_configured": candidate.name in configured,
                }
                for candidate in result.candidates
            ],
        }

    @app.get("/api/friends")
    def get_friends():
        return {"friends": [target.model_dump(mode="json", exclude_none=True) for target in load_config(config_path).targets]}

    @app.post("/api/friends/import/preview")
    async def preview_friend_import(file: UploadFile = File(...)):
        try:
            result = parse_friend_import(await file.read(), file.filename or "friends.csv")
        except TransferError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"total_entries": result.total_count, "valid_entries": result.valid_count, "duplicates": result.duplicates, "invalid_entries": result.invalid_count}

    @app.post("/api/friends/import")
    async def import_friends(file: UploadFile = File(...), mode: BackupImportMode = BackupImportMode.MERGE):
        config = load_config(config_path)
        try:
            result = apply_friend_import(config_path, config, parse_friend_import(await file.read(), file.filename or "friends.csv"), mode=mode)
        except TransferError as exc:
            raise HTTPException(422, str(exc)) from exc
        return result

    @app.patch("/api/friends/batch")
    def update_friends_batch(payload: FriendBatchUpdate):
        config = load_config(config_path)
        names = set(payload.names)
        affected = 0
        if payload.action == "delete":
            before = len(config.targets)
            config.targets = [target for target in config.targets if target.name not in names]
            affected = before - len(config.targets)
        else:
            enabled = payload.action == "enable"
            for target in config.targets:
                if target.name in names:
                    target.enabled = enabled
                    affected += 1
        save_config(config_path, config)
        return {"affected": affected, "friends": [target.model_dump(mode="json", exclude_none=True) for target in config.targets]}

    @app.get("/api/friends/export")
    def export_friends(format: str = "json"):
        targets = [target.model_dump(mode="json", exclude_none=True) for target in load_config(config_path).targets]
        if format == "csv":
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=["display name", "enabled", "note", "stable_id", "message_pack", "suffix_override"])
            writer.writeheader()
            for target in targets:
                writer.writerow({"display name": target.pop("name"), **target})
            return PlainTextResponse(output.getvalue(), headers={"Content-Disposition": "attachment; filename=autody-friends.csv"})
        return Response(_json_bytes({"friends": targets}), media_type="application/json", headers={"Content-Disposition": "attachment; filename=autody-friends.json"})

    @app.get("/api/logs")
    def logs(
        start_date: date | None = None,
        end_date: date | None = None,
        level: str | None = None,
        task_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ):
        config = load_config(config_path)
        log_dir = config.state_file.parent / "logs"
        page_result = query_logs(
            log_dir,
            config,
            start_date=start_date,
            end_date=end_date,
            level=level,
            task_type=task_type,
            status=status,
            page=page,
            page_size=page_size,
        )
        payload = page_result.model_dump(mode="json")
        payload["application"] = "\n".join(
            f"{item.timestamp} {item.level} {item.summary}\n{item.detail}".strip()
            for item in reversed(page_result.items)
        )
        payload["scheduler"] = _tail(log_dir / "scheduler.log")
        return payload

    @app.post("/api/logs/archive")
    def archive_application_logs(before: date):
        config = load_config(config_path)
        moved = archive_logs(config.state_file.parent / "logs", before)
        return {"archived_count": len(moved), "archive_dir": str(config.state_file.parent / "logs" / "archive")}

    @app.post("/api/logs/archive-historical")
    def archive_historical_application_logs():
        config = load_config(config_path)
        moved = archive_historical_logs(config.state_file.parent / "logs", config)
        return {"archived_count": len(moved), "archive_dir": str(config.state_file.parent / "logs" / "archive")}

    @app.get("/api/logs/diagnostic-export")
    def export_masked_diagnostics():
        config = load_config(config_path)
        page = query_logs(config.state_file.parent / "logs", config, page_size=200)
        lines = [f"{item.timestamp} {item.level} {item.task_type} [{item.status}] {item.summary}" for item in page.items]
        manifest = {"format": "autody-diagnostics", "version": 1, "masked": True, "includes": ["recent-log-summary"], "excludes": ["sent-message-content", "cookies", "browser-profile"]}
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", _json_bytes(manifest))
            archive.writestr("recent-log-summary.txt", "\n".join(lines) + "\n")
        return Response(buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": "attachment; filename=autody-diagnostics-masked.zip"})

    @app.post("/api/logs/open-folder")
    def open_log_folder():
        log_dir = load_config(config_path).state_file.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        if platform.system() != "Windows":
            raise HTTPException(409, "仅支持在 Windows 本地打开日志目录")
        try:
            os.startfile(str(log_dir))  # type: ignore[attr-defined]
        except OSError as exc:
            raise HTTPException(409, f"无法打开日志目录：{exc}") from exc
        return {"opened": True}

    @app.get("/api/backup")
    def backup():
        # Retained for old desktop launchers. The selectable export center uses
        # POST /api/backup/export and the checksummed v2 package below.
        config = load_config(config_path)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("config.yaml", _portable_config(config_path, config))
            archive.writestr("messages.txt", config.messages_file.read_bytes())
            archive.writestr("manifest.json", _json_bytes({"format": "autody-backup", "version": 1, "created_at": datetime.now().isoformat(timespec="seconds"), "browser_profile_included": False}))
            if config.state_file.exists():
                archive.writestr("state.json", config.state_file.read_bytes())
        return Response(
            buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=autody-backup.zip"},
        )

    @app.post("/api/backup/export")
    def export_backup(payload: BackupExportRequest):
        try:
            package = create_backup(load_config(config_path), set(payload.categories))
        except TransferError as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(package, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=autody-backup.zip"})

    @app.post("/api/backup/preview")
    async def preview_backup_upload(file: UploadFile = File(...)):
        try:
            return preview_backup(await file.read(), load_config(config_path))
        except TransferError as exc:
            raise HTTPException(422, f"备份无效：{exc}") from exc

    @app.post("/api/backup/import")
    async def import_backup(file: UploadFile = File(...), mode: BackupImportMode = BackupImportMode.MERGE):
        raw = await file.read()
        try:
            result = apply_backup(raw, config_path, load_config(config_path), mode=mode)
        except TransferError as exc:
            # v1 was the previous built-in local backup. It contained no
            # browser profile and remains importable, but all new exports are
            # validated v2 packages with checksums.
            try:
                with zipfile.ZipFile(BytesIO(raw)) as archive:
                    names = set(archive.namelist())
                    manifest = json.loads(archive.read("manifest.json"))
                    if manifest.get("format") != "autody-backup" or manifest.get("version") != 1 or not {"config.yaml", "messages.txt"} <= names:
                        raise ValueError("not a legacy backup")
                    current = load_config(config_path)
                    candidate_path = root / ".autody-legacy-import.yaml"
                    candidate_path.write_bytes(archive.read("config.yaml"))
                    candidate = load_config(candidate_path)
                    candidate_path.unlink(missing_ok=True)
                    candidate.messages_file = current.messages_file
                    candidate.profile_dir = current.profile_dir
                    candidate.state_file = current.state_file
                    candidate.lock_file = current.lock_file
                    candidate.artifact_dir = current.artifact_dir
                    messages = archive.read("messages.txt").decode("utf-8")
                    if not [line for line in messages.splitlines() if line.strip()]:
                        raise ValueError("empty message library")
                    backup_dir = current.state_file.parent / "backups"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    (backup_dir / f"before-legacy-import-{datetime.now():%Y%m%d-%H%M%S}.zip").write_bytes(create_backup(current, DEFAULT_CATEGORIES))
                    original_config = config_path.read_bytes() if config_path.exists() else None
                    original_messages = current.messages_file.read_bytes() if current.messages_file.exists() else None
                    try:
                        save_config(config_path, candidate)
                        current.messages_file.write_text(messages, encoding="utf-8")
                    except Exception:
                        if original_config is not None: config_path.write_bytes(original_config)
                        if original_messages is not None: current.messages_file.write_bytes(original_messages)
                        raise
                    result = {"legacy": True, "friends": {"imported": len(candidate.targets)}, "messages": {"imported": len(read_messages(current.messages_file))}}
            except (zipfile.BadZipFile, ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as legacy_exc:
                raise HTTPException(422, f"备份无效：{exc}") from legacy_exc
        restored = load_config(config_path)
        return {**result, "targets": [target.name for target in restored.targets], "messages": _message_count(restored.messages_file)}

    @app.post("/api/actions/{action}", status_code=202)
    def action(action: str):
        if action not in {
            "run",
            "login",
            "health-check",
            "scan-friends",
            "repair-playwright",
            "install-scheduler",
            "remove-scheduler",
        }:
            raise HTTPException(404, "未知操作")
        try:
            return run_action(action)
        except ActionAlreadyRunning as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/actions/{job_id}")
    def action_status(job_id: str):
        job = manager.get(job_id)
        if not job:
            raise HTTPException(404, "任务不存在")
        return job

    static_dir = Path(__file__).parent / "web" / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            file = (static_dir / path).resolve()
            if path and static_dir.resolve() in file.parents and file.is_file():
                return FileResponse(file)
            return FileResponse(static_dir / "index.html")

    return app
