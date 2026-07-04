from datetime import date, datetime
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import subprocess
import zipfile

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import yaml

from autody.config import AppConfig, Target, load_config, save_config
from autody.messages import read_messages
from autody.logging_setup import read_daily_logs
from autody.state import StateStore
from autody.web_actions import ActionAlreadyRunning, ActionManager


class ConfigUpdate(BaseModel):
    targets: list[str] = Field(min_length=1)
    retry_count: int = Field(ge=1, le=5)
    timeout_ms: int = Field(ge=5_000, le=120_000)
    headless: bool


class MessagesUpdate(BaseModel):
    messages: list[str]


def _tail(path: Path, limit: int = 400) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:])


def _login_status(log_text: str) -> str:
    successful = log_text.rfind("登录状态和抖音聊天页正常")
    failed = max(
        log_text.rfind("登录健康检查失败"),
        log_text.rfind("浏览器任务已安全停止"),
    )
    if successful < 0 and failed < 0:
        return "unknown"
    return "failed" if failed > successful else "success"


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
        "targets": [{"name": target.name} for target in config.targets],
        "messages_file": portable(config.messages_file),
        "profile_dir": portable(config.profile_dir),
        "state_file": portable(config.state_file),
        "lock_file": portable(config.lock_file),
        "artifact_dir": portable(config.artifact_dir),
        "retry_count": config.retry_count,
        "timeout_ms": config.timeout_ms,
        "headless": config.headless,
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).encode("utf-8")


def create_app(config_path: Path, action_runner=None) -> FastAPI:
    config_path = config_path.resolve()
    root = config_path.parent
    manager = ActionManager(root, config_path)
    run_action = action_runner or manager.start
    app = FastAPI(title="AutoDy", docs_url=None, redoc_url=None)

    @app.get("/api/status")
    def status(today: str | None = None):
        config = load_config(config_path)
        state = StateStore(config.state_file).load()
        application_log = read_daily_logs(config.state_file.parent / "logs")
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
        history = [
            {
                "date": day,
                "message": value.get("message", ""),
                "succeeded": len(value.get("succeeded", [])),
                "total": len(config.targets),
                "failed": len(value.get("failures", {})),
                "complete": bool(value.get("consumed")),
            }
            for day, value in sorted(state.daily.items(), reverse=True)
        ]
        tasks = _task_rows()
        next_run = next(
            (
                task.get("next_run")
                for task in tasks
                if task.get("name") == "AutoDy-DailySpark"
            ),
            None,
        )
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
            "login": {"status": _login_status(application_log)},
            "message_count": len(read_messages(config.messages_file)),
        }

    @app.get("/api/config")
    def get_config():
        config = load_config(config_path)
        return {
            "targets": [target.name for target in config.targets],
            "retry_count": config.retry_count,
            "timeout_ms": config.timeout_ms,
            "headless": config.headless,
        }

    @app.put("/api/config")
    def update_config(payload: ConfigUpdate):
        config = load_config(config_path)
        config.targets = [Target(name=name) for name in payload.targets]
        config.retry_count = payload.retry_count
        config.timeout_ms = payload.timeout_ms
        config.headless = payload.headless
        config = AppConfig.model_validate(config.model_dump())
        save_config(config_path, config)
        return {
            "targets": [target.name for target in config.targets],
            "retry_count": config.retry_count,
            "timeout_ms": config.timeout_ms,
            "headless": config.headless,
        }

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

    @app.get("/api/logs")
    def logs():
        config = load_config(config_path)
        log_dir = config.state_file.parent / "logs"
        return {
            "application": read_daily_logs(log_dir),
            "scheduler": _tail(log_dir / "scheduler.log"),
        }

    @app.get("/api/backup")
    def backup():
        config = load_config(config_path)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("config.yaml", _portable_config(config_path, config))
            archive.writestr("messages.txt", config.messages_file.read_bytes())
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "format": "autody-backup",
                        "version": 1,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "browser_profile_included": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            if config.state_file.exists():
                archive.writestr("state.json", config.state_file.read_bytes())
        return Response(
            buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=autody-backup.zip"},
        )

    @app.post("/api/backup/import")
    async def import_backup(file: UploadFile = File(...)):
        raw = await file.read()
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                names = set(archive.namelist())
                if not {"manifest.json", "config.yaml", "messages.txt"} <= names:
                    raise ValueError("backup files missing")
                manifest = json.loads(archive.read("manifest.json"))
                if manifest.get("format") != "autody-backup":
                    raise ValueError("invalid backup format")
                candidate = root / ".autody-import.yaml"
                candidate.write_bytes(archive.read("config.yaml"))
                restored = load_config(candidate)
                candidate.unlink(missing_ok=True)
                restored.messages_file = root / "messages.txt"
                restored.profile_dir = root / "data/browser-profile"
                restored.state_file = root / "data/state.json"
                restored.lock_file = root / "data/locks/autody.lock"
                restored.artifact_dir = root / "data/artifacts"
                messages = archive.read("messages.txt").decode("utf-8")
                if not [line for line in messages.splitlines() if line.strip()]:
                    raise ValueError("message library empty")
                save_config(config_path, restored)
                restored.messages_file.write_text(messages, encoding="utf-8")
                if "state.json" in names:
                    restored.state_file.parent.mkdir(parents=True, exist_ok=True)
                    restored.state_file.write_bytes(archive.read("state.json"))
        except (zipfile.BadZipFile, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise HTTPException(422, f"备份无效：{exc}") from exc
        return {
            "targets": [target.name for target in restored.targets],
            "messages": len(read_messages(restored.messages_file)),
        }

    @app.post("/api/actions/{action}", status_code=202)
    def action(action: str):
        if action not in {
            "run",
            "login",
            "health-check",
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
