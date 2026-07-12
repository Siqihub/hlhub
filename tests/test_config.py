from pathlib import Path

import pytest
from pydantic import ValidationError

from autody.config import MessageSuffixStyle, load_config, save_config


def test_loads_valid_config(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert [target.name for target in config.targets] == ["小明"]
    assert config.messages_file == tmp_path / "messages.txt"
    assert config.retry_count == 3
    assert config.message_suffix.enabled is True
    assert config.message_suffix.text == "gpt小助手"
    assert config.message_suffix.style is MessageSuffixStyle.DASH


def test_allows_empty_targets_for_first_run_and_discovery(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("targets: []\n", encoding="utf-8")

    assert load_config(path).targets == []


def test_rejects_duplicate_targets(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("targets:\n  - name: 小明\n  - name: 小明\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(path)


def test_save_config_persists_suffix_and_remote_pack_url(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("targets: []\n", encoding="utf-8")
    config = load_config(path)
    config.message_suffix.text = "每日问候"
    config.message_suffix.style = MessageSuffixStyle.BRACKET
    config.message_pack_index_url = "https://example.com/index.json"

    save_config(path, config)
    restored = load_config(path)

    assert restored.message_suffix.text == "每日问候"
    assert restored.message_suffix.style is MessageSuffixStyle.BRACKET
    assert restored.message_pack_index_url == "https://example.com/index.json"


def test_new_recovery_and_log_defaults_keep_old_config_compatible(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("targets:\n  - name: 小明\n", encoding="utf-8")

    config = load_config(path)

    assert config.daily_send_time == "07:30"
    assert config.recovery_deadline == "23:59"
    assert config.mask_log_friend_names is True
