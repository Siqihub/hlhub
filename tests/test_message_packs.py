from datetime import datetime
import json
from pathlib import Path

from autody.message_packs import ImportMode, MessagePackService


def make_pack_root(tmp_path: Path) -> Path:
    packs = tmp_path / "message-packs"
    packs.mkdir()
    (packs / "sample.txt").write_text("早安呀\n今天顺利\n早安呀\n", encoding="utf-8")
    (packs / "index.json").write_text(
        json.dumps(
            {
                "packs": [
                    {
                        "id": "sample",
                        "name": "示例文案",
                        "description": "测试",
                        "version": "1.0.0",
                        "file": "sample.txt",
                        "relative_url": "sample.txt",
                        "raw_url": None,
                        "count": 3,
                        "category": "daily",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_repository_index_contains_five_fifty_message_packs():
    service = MessagePackService(Path.cwd())

    catalog = service.list_packs()

    assert catalog.source == "local"
    assert len(catalog.packs) == 5
    assert {pack.count for pack in catalog.packs} == {50}
    for pack in catalog.packs:
        preview = service.preview(pack.id)
        assert len(preview.messages) == 50
        assert len(set(preview.messages)) == 50


def test_preview_deduplicates_pack_lines(tmp_path: Path):
    service = MessagePackService(make_pack_root(tmp_path))

    preview = service.preview("sample")

    assert preview.messages == ["早安呀", "今天顺利"]
    assert preview.duplicate_count == 1
    assert preview.source == "local"


def test_merge_import_deduplicates_and_creates_backup(tmp_path: Path):
    service = MessagePackService(
        make_pack_root(tmp_path),
        now=lambda: datetime(2026, 7, 4, 8, 30, 15),
    )
    messages = tmp_path / "messages.txt"
    messages.write_text("已有文案\n早安呀\n", encoding="utf-8")

    result = service.import_pack("sample", messages, ImportMode.MERGE)

    assert result.added_count == 1
    assert result.duplicate_count == 2
    assert result.total_count == 3
    assert result.mode is ImportMode.MERGE
    assert result.backup_path == tmp_path / "data/backups/messages-20260704-083015.txt"
    assert result.backup_path.read_text(encoding="utf-8") == "已有文案\n早安呀\n"
    assert messages.read_text(encoding="utf-8") == "已有文案\n早安呀\n今天顺利\n"


def test_replace_import_backs_up_and_replaces(tmp_path: Path):
    service = MessagePackService(
        make_pack_root(tmp_path),
        now=lambda: datetime(2026, 7, 4, 9, 0, 0),
    )
    messages = tmp_path / "messages.txt"
    messages.write_text("旧文案\n", encoding="utf-8")

    result = service.import_pack("sample", messages, ImportMode.REPLACE)

    assert result.added_count == 2
    assert result.duplicate_count == 1
    assert result.total_count == 2
    assert result.backup_path is not None and result.backup_path.exists()
    assert messages.read_text(encoding="utf-8") == "早安呀\n今天顺利\n"


def test_remote_network_failure_falls_back_to_local_with_clear_warning(tmp_path: Path):
    def unavailable(_url: str) -> str:
        raise OSError("network offline")

    service = MessagePackService(
        make_pack_root(tmp_path),
        remote_index_url="https://example.invalid/index.json",
        fetch_text=unavailable,
    )

    catalog = service.list_packs()

    assert catalog.source == "local"
    assert catalog.warning is not None
    assert "远程文案库不可用" in catalog.warning
    assert catalog.packs[0].id == "sample"


def test_preview_only_never_writes_or_backs_up(tmp_path: Path):
    service = MessagePackService(make_pack_root(tmp_path))
    messages = tmp_path / "messages.txt"
    messages.write_text("原文案\n", encoding="utf-8")

    result = service.import_pack("sample", messages, ImportMode.PREVIEW_ONLY)

    assert result.backup_path is None
    assert messages.read_text(encoding="utf-8") == "原文案\n"
    assert not (tmp_path / "data/backups").exists()
