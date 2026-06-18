from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class Target(BaseModel):
    name: str = Field(min_length=1)


class AppConfig(BaseModel):
    targets: list[Target] = Field(min_length=1)
    messages_file: Path = Path("messages.txt")
    profile_dir: Path = Path("data/browser-profile")
    state_file: Path = Path("data/state.json")
    lock_file: Path = Path("data/autody.lock")
    artifact_dir: Path = Path("data/artifacts")
    retry_count: int = Field(default=3, ge=1, le=5)
    timeout_ms: int = Field(default=30_000, ge=5_000, le=120_000)
    headless: bool = True

    @model_validator(mode="after")
    def unique_targets(self):
        names = [target.name.strip() for target in self.targets]
        if len(names) != len(set(names)):
            raise ValueError("target names must be unique")
        for target, name in zip(self.targets, names, strict=True):
            target.name = name
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
