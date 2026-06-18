from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path


@dataclass
class RotationState:
    order: list[str] = field(default_factory=list)
    consumed: list[str] = field(default_factory=list)


@dataclass
class AppState:
    rotation: RotationState = field(default_factory=RotationState)
    daily: dict[str, dict] = field(default_factory=dict)


class StateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> AppState:
        if not self.path.exists():
            return AppState()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return AppState(
                rotation=RotationState(**raw.get("rotation", {})),
                daily=raw.get("daily", {}),
            )
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            raise ValueError(f"state file is corrupt: {self.path}") from exc

    def save(self, state: AppState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
