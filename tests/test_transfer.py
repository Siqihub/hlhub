from io import BytesIO
from pathlib import Path
import zipfile

import pytest

from autody.config import AppConfig, Target
from autody.transfer import (
    ExportCategory,
    ImportMode,
    TransferError,
    apply_backup,
    create_backup,
    parse_friend_import,
    parse_message_import,
    preview_backup,
)


def _config(root: Path) -> AppConfig:
    return AppConfig(
        targets=[Target(name="小明")],
        messages_file=root / "messages.txt",
        state_file=root / "data/state.json",
        profile_dir=root / "data/browser-profile",
        lock_file=root / "data/locks/autody.lock",
        artifact_dir=root / "data/artifacts",
    )


def test_selective_backup_has_manifest_checksums_and_no_sensitive_files(tmp_path: Path):
    config = _config(tmp_path)
    config.messages_file.write_text("早安\n", encoding="utf-8")
    package = create_backup(config, {ExportCategory.FRIENDS, ExportCategory.MESSAGES})

    with zipfile.ZipFile(BytesIO(package)) as archive:
        names = set(archive.namelist())
        manifest = archive.read("manifest.json").decode("utf-8")
    assert names == {"manifest.json", "friends.json", "messages.txt"}
    assert "checksums" in manifest
    assert "browser-profile" not in manifest


def test_backup_rejects_unsafe_path_before_mutating_files(tmp_path: Path):
    config = _config(tmp_path)
    config.messages_file.write_text("原文案\n", encoding="utf-8")
    raw = BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("../evil.exe", "bad")
        archive.writestr("manifest.json", '{"format":"autody-backup","version":2,"files":{}}')

    with pytest.raises(TransferError, match="不安全"):
        preview_backup(raw.getvalue(), config)
    assert config.messages_file.read_text(encoding="utf-8") == "原文案\n"


def test_backup_merge_keeps_ambiguous_friend_and_creates_local_backup(tmp_path: Path):
    config = _config(tmp_path)
    config.messages_file.write_text("原文案\n", encoding="utf-8")
    incoming_messages = tmp_path / "incoming.txt"
    incoming = AppConfig(targets=[Target(name="小明"), Target(name="小红")], messages_file=incoming_messages)
    incoming.messages_file.write_text("原文案\n新文案\n", encoding="utf-8")
    package = create_backup(incoming, {ExportCategory.FRIENDS, ExportCategory.MESSAGES})

    result = apply_backup(package, tmp_path / "config.yaml", config, mode=ImportMode.MERGE)

    assert result["friends"]["conflicted"] == 1
    assert result["friends"]["imported"] == 1
    assert (tmp_path / "data/backups").exists()
    assert "新文案" in config.messages_file.read_text(encoding="utf-8")


def test_friend_csv_json_and_message_txt_csv_json_preview_and_exact_dedupe():
    friends = parse_friend_import("display name,enabled,note\n小明,true,同学\n小红,false,\n".encode(), "friends.csv")
    assert friends.valid_count == 2
    assert friends.duplicates == []
    friend_json = parse_friend_import('{"friends":[{"name":"小蓝","enabled":false}]}'.encode(), "friends.json")
    assert friend_json.targets[0].enabled is False

    messages = parse_message_import("早安\n早安\n\nhttps://example.com\n".encode(), "messages.txt")
    assert messages.total_count == 4
    assert messages.exact_duplicates == 1
    assert messages.empty_count == 1
    assert messages.link_count == 1
    assert messages.messages == ["早安", "https://example.com"]
    assert parse_message_import("message\n午安\n".encode(), "messages.csv").messages == ["午安"]
    assert parse_message_import('{"messages":["晚安"]}'.encode(), "messages.json").messages == ["晚安"]


def test_import_rollback_restores_messages_when_write_fails(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    config.messages_file.write_text("保留\n", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("targets: []\n", encoding="utf-8")
    incoming = tmp_path / "incoming.txt"
    incoming.write_text("新文案\n", encoding="utf-8")
    package = create_backup(AppConfig(messages_file=incoming), {ExportCategory.MESSAGES})
    monkeypatch.setattr("autody.transfer._write_messages", lambda *_args: (_ for _ in ()).throw(OSError("disk error")))

    with pytest.raises(TransferError, match="已回滚"):
        apply_backup(package, config_path, config, mode=ImportMode.REPLACE)
    assert config.messages_file.read_text(encoding="utf-8") == "保留\n"
