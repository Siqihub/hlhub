from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Callable
import uuid

from autody.chat import ChatSelectors
from autody.config import AppConfig, Target


_SAFE_LOCAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


@dataclass(frozen=True)
class FriendCandidate:
    candidate_id: str
    display_name: str
    avatar_cache_path: str | None
    avatar_status: str
    discovered_at: str
    match_status: str
    configured_target_id: str | None = None
    configured_enabled: bool | None = None

    @property
    def name(self) -> str:
        """Compatibility alias for the original discovery payload."""
        return self.display_name

    @property
    def already_configured(self) -> bool:
        return self.match_status == "configured"


@dataclass(frozen=True)
class FriendDiscoveryResult:
    scanned_at: str
    candidates: list[FriendCandidate]
    output_path: Path
    config_changed: bool = False


@dataclass(frozen=True)
class AvatarRefreshResult:
    updated: int
    missing: int
    ambiguous: int
    config_changed: bool


@dataclass(frozen=True)
class _ScannedItem:
    name: str
    temporary_avatar: Path | None
    avatar_hash: str | None


def _new_local_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _ensure_target_id(target: Target) -> bool:
    if target.stable_id and _SAFE_LOCAL_ID.fullmatch(target.stable_id):
        return False
    target.stable_id = _new_local_id("friend")
    return True


def _avatar_path(cache_dir: Path, identifier: str) -> Path:
    return cache_dir / f"{identifier}.png"


def _capture_temporary_avatar(item, cache_dir: Path) -> tuple[Path | None, str | None]:
    """Capture the rendered in-list avatar without storing its remote URL."""
    temporary = cache_dir / f".scan-{uuid.uuid4().hex}.png"
    try:
        item.locator("img").first.screenshot(path=str(temporary))
        content = temporary.read_bytes()
        if not content:
            raise OSError("captured avatar was empty")
        return temporary, hashlib.sha256(content).hexdigest()
    except Exception:
        temporary.unlink(missing_ok=True)
        return None, None


def _scan_items(
    page,
    selectors: ChatSelectors,
    cache_dir: Path,
    max_scrolls: int = 20,
) -> list[_ScannedItem]:
    """Read visible conversation rows while keeping avatar failures non-fatal."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    conversations = page.locator(selectors.conversation)
    scrollable = page.locator(selectors.conversation_list)
    items: list[_ScannedItem] = []
    seen: set[tuple[str, str | None]] = set()
    missing_counts: Counter[str] = Counter()

    for _ in range(max_scrolls + 1):
        for index in range(conversations.count()):
            item = conversations.nth(index)
            try:
                name = item.locator(selectors.conversation_name).inner_text().strip()
            except Exception:
                continue
            if not name:
                continue
            temporary, avatar_hash = _capture_temporary_avatar(item, cache_dir)
            # A rendered avatar distinguishes same-named rows without persisting a
            # remote URL. If capture fails, retain occurrences so they can be shown
            # as ambiguous instead of silently choosing a nickname match.
            signature = (name, avatar_hash)
            if avatar_hash is not None and signature in seen:
                if temporary:
                    temporary.unlink(missing_ok=True)
                continue
            if avatar_hash is None:
                missing_counts[name] += 1
                signature = (name, f"missing-{missing_counts[name]}")
            seen.add(signature)
            items.append(_ScannedItem(name, temporary, avatar_hash))

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
    return items


def _publish_avatar(
    temporary: Path | None,
    cache_dir: Path,
    identifier: str,
) -> tuple[str | None, str]:
    destination = _avatar_path(cache_dir, identifier)
    if temporary is not None:
        try:
            os.replace(temporary, destination)
            return destination.name, "cached"
        except OSError:
            temporary.unlink(missing_ok=True)
    if destination.is_file():
        return destination.name, "cached"
    return None, "missing"


def _discard_temporary(items: list[_ScannedItem]) -> None:
    for item in items:
        if item.temporary_avatar is not None:
            item.temporary_avatar.unlink(missing_ok=True)


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
    avatar_cache_dir: Path | None = None,
) -> FriendDiscoveryResult:
    cache_dir = avatar_cache_dir or output_path.parent / "avatar-cache"
    scanned = _scan_items(page, selectors, cache_dir)
    scanned_at = (now or datetime.now)().isoformat(timespec="seconds")
    by_name: dict[str, list[_ScannedItem]] = defaultdict(list)
    for item in scanned:
        by_name[item.name].append(item)
    targets = {target.name: target for target in config.targets}
    config_changed = False
    candidates: list[FriendCandidate] = []

    try:
        for item in scanned:
            target = targets.get(item.name)
            duplicate = len(by_name[item.name]) > 1
            candidate_id = _new_local_id("candidate")
            configured_target_id = None
            configured_enabled = None
            if target is not None:
                config_changed = _ensure_target_id(target) or config_changed
                configured_target_id = target.stable_id
                configured_enabled = target.enabled
            if target is not None and not duplicate:
                cache_id = configured_target_id or candidate_id
                match_status = "configured"
            elif duplicate:
                cache_id = candidate_id
                match_status = "ambiguous"
            else:
                cache_id = candidate_id
                match_status = "unconfigured"
            avatar_cache_path, avatar_status = _publish_avatar(
                item.temporary_avatar, cache_dir, cache_id
            )
            candidates.append(
                FriendCandidate(
                    candidate_id=candidate_id,
                    display_name=item.name,
                    avatar_cache_path=avatar_cache_path,
                    avatar_status=avatar_status,
                    discovered_at=scanned_at,
                    match_status=match_status,
                    configured_target_id=configured_target_id,
                    configured_enabled=configured_enabled,
                )
            )
    finally:
        _discard_temporary(scanned)

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
    return FriendDiscoveryResult(scanned_at, candidates, output_path, config_changed)


def refresh_configured_avatars(
    config: AppConfig,
    page,
    selectors: ChatSelectors,
    avatar_cache_dir: Path,
) -> AvatarRefreshResult:
    """Refresh only unambiguous configured-avatar associations; never edit names."""
    scanned = _scan_items(page, selectors, avatar_cache_dir)
    by_name: dict[str, list[_ScannedItem]] = defaultdict(list)
    for item in scanned:
        by_name[item.name].append(item)
    updated = missing = ambiguous = 0
    config_changed = False
    try:
        for target in config.targets:
            matches = by_name.get(target.name, [])
            if len(matches) > 1:
                ambiguous += 1
                continue
            if not matches:
                missing += 1
                continue
            config_changed = _ensure_target_id(target) or config_changed
            avatar_cache_path, avatar_status = _publish_avatar(
                matches[0].temporary_avatar,
                avatar_cache_dir,
                target.stable_id or _new_local_id("friend"),
            )
            if avatar_status == "cached" and matches[0].temporary_avatar is not None:
                updated += 1
            elif avatar_cache_path is None:
                missing += 1
    finally:
        _discard_temporary(scanned)
    return AvatarRefreshResult(updated, missing, ambiguous, config_changed)


def _candidate_from_payload(item: object, scanned_at: str) -> FriendCandidate:
    if not isinstance(item, dict):
        raise ValueError("candidate must be an object")
    display_name = str(item.get("display_name", item.get("name", ""))).strip()
    if not display_name:
        raise ValueError("candidate name is required")
    match_status = str(item.get("match_status", ""))
    if not match_status:
        match_status = "configured" if item.get("already_configured") else "unconfigured"
    return FriendCandidate(
        candidate_id=str(item.get("candidate_id") or _new_local_id("legacy-candidate")),
        display_name=display_name,
        avatar_cache_path=(str(item["avatar_cache_path"]) if item.get("avatar_cache_path") else None),
        avatar_status=str(item.get("avatar_status", "missing")),
        discovered_at=str(item.get("discovered_at", scanned_at)),
        match_status=match_status,
        configured_target_id=(str(item["configured_target_id"]) if item.get("configured_target_id") else None),
        configured_enabled=(bool(item["configured_enabled"]) if item.get("configured_enabled") is not None else None),
    )


def load_discovered_friends(path: Path) -> FriendDiscoveryResult | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        scanned_at = str(payload["scanned_at"])
        candidates = [_candidate_from_payload(item, scanned_at) for item in payload["candidates"]]
        return FriendDiscoveryResult(scanned_at, candidates, path)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
