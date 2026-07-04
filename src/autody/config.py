from pathlib import Path
import os
from enum import Enum

import yaml
from pydantic import BaseModel, Field, model_validator


class Target(BaseModel):
    name: str = Field(min_length=1)


class MessageSuffixStyle(str, Enum):
    DASH = "dash"
    BRACKET = "bracket"
    NEWLINE = "newline"
    NONE = "none"


class MessageSuffixConfig(BaseModel):
    enabled: bool = True
    text: str = "gpt小助手"
    style: MessageSuffixStyle = MessageSuffixStyle.DASH


class AppConfig(BaseModel):
    targets: list[Target] = Field(default_factory=list)
    messages_file: Path = Path("messages.txt")
    profile_dir: Path = Path("data/browser-profile")
    state_file: Path = Path("data/state.json")
    lock_file: Path = Path("data/locks/autody.lock")
    artifact_dir: Path = Path("data/artifacts")
    retry_count: int = Field(default=3, ge=1, le=5)
    timeout_ms: int = Field(default=30_000, ge=5_000, le=120_000)
    headless: bool = True
    message_suffix: MessageSuffixConfig = Field(default_factory=MessageSuffixConfig)
    message_pack_index_url: str | None = None

    @model_validator(mode="after")
    def unique_targets(self):
        names = [target.name.strip() for target in self.targets]
        if len(names) != len(set(names)):
            raise ValueError("target names must be unique")
        for target, name in zip(self.targets, names, strict=True):
            target.name = name
        if self.message_pack_index_url is not None:
            self.message_pack_index_url = self.message_pack_index_url.strip() or None
        return self


def load_config(path: Path) -> AppConfig:
    path = path.resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = AppConfig.model_validate(data)
    for field_name in ("messages_file", "profile_dir", "state_file", "lock_file", "artifact_dir"):
        value = getattr(config, field_name)
        if not value.is_absolute():
            setattr(config, field_name, path.parent / value)
    return config


def save_config(path: Path, config: AppConfig) -> None:
    path = path.resolve()
    root = path.parent

    def portable(value: Path) -> str:
        try:
            return str(value.resolve().relative_to(root))
        except ValueError:
            return str(value)

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
        "message_suffix": config.message_suffix.model_dump(mode="json"),
        "message_pack_index_url": config.message_pack_index_url,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)
