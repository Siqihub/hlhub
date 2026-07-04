from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Callable

from autody.chat import ChatSelectors
from autody.config import AppConfig


@dataclass(frozen=True)
class FriendCandidate:
    name: str
    already_configured: bool


@dataclass(frozen=True)
class FriendDiscoveryResult:
    scanned_at: str
    candidates: list[FriendCandidate]
    output_path: Path


def scan_friend_names(
    page,
    selectors: ChatSelectors,
    max_scrolls: int = 20,
) -> list[str]:
    names_locator = page.locator(selectors.conversation_name)
    scrollable = page.locator(selectors.conversation_list)
    names: list[str] = []
    seen: set[str] = set()
    for _ in range(max_scrolls + 1):
        for raw_name in names_locator.all_inner_texts():
            name = raw_name.strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        if not scrollable.count():
            break
        metrics = scrollable.first.evaluate(
            """el => ({
                before: el.scrollTop,
                maximum: Math.max(0, el.scrollHeight - el.clientHeight),
                step: Math.max(200, Math.floor(el.clientHeight * 0.7))
            })"""
        )
        if metrics["before"] >= metrics["maximum"]:
            break
        scrollable.first.evaluate(
            "(el, step) => { el.scrollTop += step; el.dispatchEvent(new Event('scroll')); }",
            metrics["step"],
        )
        page.wait_for_timeout(250)
    return names


def discover_friends(
    config: AppConfig,
    page,
    selectors: ChatSelectors,
    output_path: Path,
    now: Callable[[], datetime] | None = None,
) -> FriendDiscoveryResult:
    configured = {target.name for target in config.targets}
    candidates = [
        FriendCandidate(name=name, already_configured=name in configured)
        for name in scan_friend_names(page, selectors)
    ]
    scanned_at = (now or datetime.now)().isoformat(timespec="seconds")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "scanned_at": scanned_at,
                "candidates": [asdict(candidate) for candidate in candidates],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    os.replace(temporary, output_path)
    return FriendDiscoveryResult(scanned_at, candidates, output_path)


def load_discovered_friends(path: Path) -> FriendDiscoveryResult | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        candidates = [FriendCandidate(**item) for item in payload["candidates"]]
        return FriendDiscoveryResult(payload["scanned_at"], candidates, path)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
