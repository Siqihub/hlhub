from __future__ import annotations

from datetime import datetime, time

from autody.config import AppConfig
from autody.state import AppState


def target_completed(daily: dict, target_name: str) -> bool:
    succeeded = set(daily.get("succeeded", []))
    return target_name in succeeded


def recovery_due(config: AppConfig, state: AppState, now: datetime) -> bool:
    if not config.targets:
        return False
    send_at = time.fromisoformat(config.daily_send_time)
    deadline = time.fromisoformat(config.recovery_deadline)
    if now.time() < send_at or now.time() > deadline:
        return False
    daily = state.daily.get(now.date().isoformat(), {})
    return any(not target_completed(daily, target.name) for target in config.targets)
