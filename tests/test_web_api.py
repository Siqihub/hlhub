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
    packs = tmp_path / "message-packs"
    packs.mkdir()
    (packs / "daily.txt").write_text("早安呀\n今天顺利\n", encoding="utf-8")
    (packs / "index.json").write_text(
        json.dumps(
            {
                "packs": [
                    {
                        "id": "daily",
                        "name": "日常",
                        "description": "日常测试包",
                        "version": "1.0.0",
                        "file": "daily.txt",
                        "relative_url": "daily.txt",
                        "raw_url": None,
                        "count": 2,
                        "category": "daily",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
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
            "message_suffix": {
                "enabled": True,
                "text": "每日问候",
                "style": "bracket",
            },
            "message_pack_index_url": "https://example.com/index.json",
        },
    )
    assert response.status_code == 200
    assert response.json()["targets"] == ["小明", "小蓝"]
    assert response.json()["message_suffix"]["text"] == "每日问候"

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


def test_message_pack_list_preview_and_merge_import(tmp_path: Path):
    client = TestClient(create_app(make_project(tmp_path)))

    catalog = client.get("/api/message-packs")
    assert catalog.status_code == 200
    assert catalog.json()["packs"][0]["id"] == "daily"
    assert catalog.json()["source"] == "local"

    preview = client.get("/api/message-packs/daily")
    assert preview.status_code == 200
    assert preview.json()["messages"] == ["早安呀", "今天顺利"]

    imported = client.post(
        "/api/message-packs/daily/import", json={"mode": "merge"}
    )
    assert imported.status_code == 200
    assert imported.json()["added_count"] == 2
    assert imported.json()["total_count"] == 4
    assert imported.json()["backup_path"].endswith(".txt")
    assert "早安呀" in (tmp_path / "messages.txt").read_text(encoding="utf-8")


def test_scan_friends_endpoint_starts_action_and_lists_candidates(tmp_path: Path):
    calls = []

    def runner(action: str):
        calls.append(action)
        return {"id": "scan-1", "action": action, "status": "running"}

    config = make_project(tmp_path)
    discovered = tmp_path / "data" / "discovered_friends.json"
    discovered.write_text(
        json.dumps(
            {
                "scanned_at": "2026-07-04T12:30:00",
                "candidates": [
                    {"name": "小明", "already_configured": True},
                    {"name": "新朋友", "already_configured": False},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(config, action_runner=runner))

    response = client.post("/api/friends/scan")
    candidates = client.get("/api/friends/discovered")

    assert response.status_code == 202
    assert calls == ["scan-friends"]
    assert candidates.json()["candidates"][1]["name"] == "新朋友"


def test_status_returns_actionable_issues_without_friends_or_messages(
    tmp_path: Path, monkeypatch
):
    config = make_project(tmp_path)
    config.write_text(
        "targets: []\nmessages_file: messages.txt\nstate_file: data/state.json\n",
        encoding="utf-8",
    )
    (tmp_path / "messages.txt").write_text("\n", encoding="utf-8")
    monkeypatch.setattr("autody.web_api._task_rows", lambda: [])
    client = TestClient(create_app(config))

    response = client.get("/api/status?today=2026-07-04")

    assert response.status_code == 200
    issue_ids = {issue["id"] for issue in response.json()["issues"]}
    assert {"no_friends", "no_messages", "scheduler_missing", "runtime_missing"} <= issue_ids
    assert "remote_library" in issue_ids
