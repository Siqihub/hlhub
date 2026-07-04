from io import BytesIO
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient

from autody.web_api import create_app


def make_project(tmp_path: Path) -> Path:
    (tmp_path / "messages.txt").write_text("早安\n晚安\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        """
targets:
  - name: 小明
  - name: 小红
messages_file: messages.txt
profile_dir: data/browser-profile
state_file: data/state.json
lock_file: data/autody.lock
artifact_dir: data/artifacts
retry_count: 3
timeout_ms: 30000
headless: true
""".strip(),
        encoding="utf-8",
    )
    state = {
        "rotation": {"order": ["晚安"], "consumed": ["早安"]},
        "daily": {
            "2026-06-24": {
                "message": "早安",
                "succeeded": ["小明"],
                "failures": {"小红": "target not found"},
                "consumed": False,
            }
        },
    }
    path = tmp_path / "data" / "state.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    logs = tmp_path / "data" / "logs"
    logs.mkdir()
    (logs / "autody.log").write_text("发送成功：小明\n", encoding="utf-8")
    return tmp_path / "config.yaml"


def test_status_returns_dashboard_summary(tmp_path: Path):
    client = TestClient(create_app(make_project(tmp_path)))
    response = client.get("/api/status?today=2026-06-24")
    assert response.status_code == 200
    data = response.json()
    assert data["today"]["succeeded"] == 1
    assert data["today"]["total"] == 2
    assert data["today"]["message"] == "早安"
    assert data["friends"][1]["status"] == "failed"
    assert data["login"]["status"] == "unknown"


def test_status_reports_latest_login_health_result(tmp_path: Path):
    config = make_project(tmp_path)
    log = tmp_path / "data" / "logs" / "autody.log"
    log.write_text(
        "2026-06-24 INFO 登录状态和抖音聊天页正常。\n"
        "2026-06-25 ERROR 登录健康检查失败：需要重新登录\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(config))
    assert client.get("/api/status").json()["login"]["status"] == "failed"

    log.write_text(
        log.read_text(encoding="utf-8")
        + "2026-06-25 INFO 登录状态和抖音聊天页正常。\n",
        encoding="utf-8",
    )
    assert client.get("/api/status").json()["login"]["status"] == "success"


def test_config_and_messages_can_be_updated(tmp_path: Path):
    config = make_project(tmp_path)
    client = TestClient(create_app(config))
    response = client.put(
        "/api/config",
        json={
            "targets": ["小明", "小蓝"],
            "retry_count": 2,
            "timeout_ms": 45000,
            "headless": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["targets"] == ["小明", "小蓝"]

    response = client.put("/api/messages", json={"messages": ["甲", "乙", "甲"]})
    assert response.status_code == 200
    assert response.json()["messages"] == ["甲", "乙"]
    assert (tmp_path / "messages.txt").read_text(encoding="utf-8") == "甲\n乙\n"


def test_logs_and_backup_exclude_browser_profile(tmp_path: Path):
    config = make_project(tmp_path)
    profile = tmp_path / "data" / "browser-profile"
    profile.mkdir(parents=True)
    (profile / "secret.cookie").write_text("secret", encoding="utf-8")
    client = TestClient(create_app(config))

    logs = client.get("/api/logs").json()
    assert "发送成功" in logs["application"]

    response = client.get("/api/backup")
    assert response.status_code == 200
    archive = zipfile.ZipFile(BytesIO(response.content))
    assert set(archive.namelist()) == {
        "config.yaml",
        "messages.txt",
        "manifest.json",
        "state.json",
    }
    assert "secret.cookie" not in "\n".join(archive.namelist())


def test_backup_import_validates_and_restores(tmp_path: Path):
    config = make_project(tmp_path)
    client = TestClient(create_app(config))
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "config.yaml",
            "targets:\n  - name: 恢复好友\nmessages_file: messages.txt\n",
        )
        archive.writestr("messages.txt", "恢复文案\n")
        archive.writestr("manifest.json", '{"format":"autody-backup","version":1}')
    response = client.post(
        "/api/backup/import",
        files={"file": ("backup.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 200
    assert response.json()["targets"] == ["恢复好友"]
    assert (tmp_path / "messages.txt").read_text(encoding="utf-8") == "恢复文案\n"


def test_actions_are_started_and_reported(tmp_path: Path):
    calls = []

    def runner(action: str):
        calls.append(action)
        return {"id": "job-1", "action": action, "status": "running"}

    client = TestClient(create_app(make_project(tmp_path), action_runner=runner))
    response = client.post("/api/actions/run")
    assert response.status_code == 202
    assert response.json()["id"] == "job-1"
    assert calls == ["run"]
