from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
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
DISCOVERY_CACHE_TTL = timedelta(hours=24)
AVATAR_CACHE_TTL = timedelta(days=7)


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
    avatar_cache_key: str | None = None
    avatar_updated_at: str | None = None
    first_discovered_at: str | None = None
    last_seen_at: str | None = None
    last_scan_id: str | None = None
    presence_status: str = "current"

    @property
    def name(self) -> str:
        """Compatibility alias for the original discovery payload."""
        return self.display_name

    @property
    def already_configured(self) -> bool:
        return self.match_status == "configured"


@dataclass(frozen=True)
class FriendDiscoveryResult:
    scanned_at: str | None
    candidates: list[FriendCandidate]
    output_path: Path
    config_changed: bool = False
    scan_id: str | None = None
    last_result: dict[str, object] = field(default_factory=dict)


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
    capture_attempted: bool = True


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
    capture_avatar: Callable[[str], bool] | None = None,
) -> list[_ScannedItem]:
    """Read visible conversation rows while keeping avatar failures non-fatal."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    conversations = page.locator(selectors.conversation)
    scrollable = page.locator(selectors.conversation_list)
    items: list[_ScannedItem] = []
    seen: set[tuple[str, str | None]] = set()
    missing_counts: Counter[str] = Counter()

    for _ in range(max_scrolls + 1):
        visible: list[tuple[object, str]] = []
        for index in range(conversations.count()):
            item = conversations.nth(index)
            try:
                name = item.locator(selectors.conversation_name).inner_text().strip()
            except Exception:
                continue
            if not name:
                continue
            visible.append((item, name))
        visible_counts = Counter(name for _, name in visible)
        for item, name in visible:
            should_capture = (
                capture_avatar is None
                or capture_avatar(name)
                or visible_counts[name] > 1
            )
            if should_capture:
                temporary, avatar_hash = _capture_temporary_avatar(item, cache_dir)
            else:
                temporary, avatar_hash = None, None
            # A rendered avatar distinguishes same-named rows without persisting a
            # remote URL. If capture fails, retain occurrences so they can be shown
            # as ambiguous instead of silently choosing a nickname match.
            signature = (name, avatar_hash)
            if avatar_hash is not None and signature in seen:
                if temporary:
                    temporary.unlink(missing_ok=True)
                continue
            if avatar_hash is None and should_capture:
                missing_counts[name] += 1
                signature = (name, f"missing-{missing_counts[name]}")
            elif avatar_hash is None:
                signature = (name, "cached-without-capture")
                if signature in seen:
                    continue
            seen.add(signature)
            items.append(_ScannedItem(name, temporary, avatar_hash, should_capture))

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


def _avatar_needs_refresh(path: Path, now: datetime) -> bool:
    if not path.is_file():
        return True
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return True
    return now - modified >= AVATAR_CACHE_TTL


def _publish_avatar(
    temporary: Path | None,
    cache_dir: Path,
    identifier: str,
    now: datetime,
) -> tuple[str | None, str, bool]:
    destination = _avatar_path(cache_dir, identifier)
    refresh_needed = _avatar_needs_refresh(destination, now)
    if temporary is not None and refresh_needed:
        try:
            os.replace(temporary, destination)
            return destination.name, "cached", True
        except OSError:
            temporary.unlink(missing_ok=True)
    elif temporary is not None:
        temporary.unlink(missing_ok=True)
    if destination.is_file():
        return destination.name, "cached", False
    return None, "missing", False


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


def _fresh_avatar_names(
    config: AppConfig,
    previous: FriendDiscoveryResult | None,
    cache_dir: Path,
    now: datetime,
) -> set[str]:
    fresh: set[str] = set()
    for target in config.targets:
        if target.stable_id and _SAFE_LOCAL_ID.fullmatch(target.stable_id):
            if not _avatar_needs_refresh(_avatar_path(cache_dir, target.stable_id), now):
                fresh.add(target.name)
    for candidate in previous.candidates if previous else []:
        if candidate.match_status == "ambiguous":
            continue
        cache_key = (
            candidate.configured_target_id
            if candidate.match_status == "configured"
            else candidate.avatar_cache_key or candidate.candidate_id
        )
        if cache_key and _SAFE_LOCAL_ID.fullmatch(cache_key):
            if not _avatar_needs_refresh(_avatar_path(cache_dir, cache_key), now):
                fresh.add(candidate.display_name)
    return fresh


def discover_friends(
    config: AppConfig,
    page,
    selectors: ChatSelectors,
    output_path: Path,
    now: Callable[[], datetime] | None = None,
    avatar_cache_dir: Path | None = None,
    force_avatar_refresh: bool = False,
) -> FriendDiscoveryResult:
    cache_dir = avatar_cache_dir or output_path.parent / "avatar-cache"
    previous = load_discovered_friends(output_path)
    scanned_now = (now or datetime.now)()
    fresh_avatar_names = (
        set()
        if force_avatar_refresh
        else _fresh_avatar_names(config, previous, cache_dir, scanned_now)
    )
    scanned = _scan_items(
        page,
        selectors,
        cache_dir,
        capture_avatar=lambda name: name not in fresh_avatar_names,
    )
    scanned_at = scanned_now.isoformat(timespec="seconds")
    scan_id = _new_local_id("scan")
    by_name: dict[str, list[_ScannedItem]] = defaultdict(list)
    for item in scanned:
        by_name[item.name].append(item)
    targets = {target.name: target for target in config.targets}
    previous_by_name: dict[str, list[FriendCandidate]] = defaultdict(list)
    for candidate in previous.candidates if previous else []:
        previous_by_name[candidate.display_name].append(candidate)
    config_changed = False
    candidates: list[FriendCandidate] = []
    seen_previous_ids: set[str] = set()
    avatars_updated = avatars_reused = avatars_failed = configured_matched = new_candidates = 0

    try:
        for item in scanned:
            target = targets.get(item.name)
            duplicate = len(by_name[item.name]) > 1
            matching_previous = [
                candidate
                for candidate in previous_by_name[item.name]
                if candidate.candidate_id not in seen_previous_ids
            ]
            prior = matching_previous[0] if not duplicate and len(matching_previous) == 1 else None
            candidate_id = (
                prior.candidate_id
                if prior and _SAFE_LOCAL_ID.fullmatch(prior.candidate_id)
                else _new_local_id("candidate")
            )
            configured_target_id = None
            configured_enabled = None
            if target is not None:
                config_changed = _ensure_target_id(target) or config_changed
                configured_target_id = target.stable_id
                configured_enabled = target.enabled
            if target is not None and not duplicate:
                candidate_id = candidate_id if prior else configured_target_id or candidate_id
                cache_id = configured_target_id or candidate_id
                match_status = "configured"
                configured_matched += 1
            elif duplicate:
                cache_id = candidate_id
                match_status = "ambiguous"
            else:
                cache_id = (
                    prior.avatar_cache_key
                    if prior and prior.avatar_cache_key and _SAFE_LOCAL_ID.fullmatch(prior.avatar_cache_key)
                    else candidate_id
                )
                match_status = "unconfigured"
            avatar_cache_path, avatar_status, avatar_updated = _publish_avatar(
                item.temporary_avatar,
                cache_dir,
                cache_id,
                scanned_now,
            )
            if avatar_updated:
                avatars_updated += 1
            elif avatar_status == "cached":
                avatars_reused += 1
            else:
                avatars_failed += 1
            if prior is None:
                new_candidates += 1
            else:
                seen_previous_ids.add(prior.candidate_id)
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
                    avatar_cache_key=cache_id,
                    avatar_updated_at=scanned_at if avatar_updated else (prior.avatar_updated_at if prior else None),
                    first_discovered_at=prior.first_discovered_at if prior else scanned_at,
                    last_seen_at=scanned_at,
                    last_scan_id=scan_id,
                    presence_status="current",
                )
            )

        for candidate in previous.candidates if previous else []:
            if candidate.candidate_id in seen_previous_ids:
                continue
            target = targets.get(candidate.display_name)
            configured_target_id = candidate.configured_target_id
            configured_enabled = candidate.configured_enabled
            match_status = candidate.match_status
            if target is not None:
                config_changed = _ensure_target_id(target) or config_changed
                configured_target_id = target.stable_id
                configured_enabled = target.enabled
                match_status = "configured"
            candidates.append(
                replace(
                    candidate,
                    match_status=match_status,
                    configured_target_id=configured_target_id,
                    configured_enabled=configured_enabled,
                    last_scan_id=scan_id,
                    presence_status="stale",
                )
            )
    finally:
        _discard_temporary(scanned)

    last_result: dict[str, object] = {
        "status": "completed",
        "finished_at": scanned_at,
        "scan_id": scan_id,
        "candidates_found": len(scanned),
        "new_candidates": new_candidates,
        "configured_matched": configured_matched,
        "avatars_updated": avatars_updated,
        "avatars_reused": avatars_reused,
        "avatars_failed": avatars_failed,
        "stale_candidates": sum(item.presence_status == "stale" for item in candidates),
    }
    _write_discovery_payload(
        output_path,
        {
            "version": 2,
            "scanned_at": scanned_at,
            "scan_id": scan_id,
            "last_result": last_result,
            "candidates": [asdict(candidate) for candidate in candidates],
        },
    )
    return FriendDiscoveryResult(
        scanned_at, candidates, output_path, config_changed, scan_id, last_result
    )


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
            avatar_cache_path, avatar_status, avatar_updated = _publish_avatar(
                matches[0].temporary_avatar,
                avatar_cache_dir,
                target.stable_id or _new_local_id("friend"),
                datetime.now(),
            )
            if avatar_status == "cached" and avatar_updated:
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
    first_discovered_at = str(item.get("first_discovered_at", item.get("discovered_at", scanned_at)))
    return FriendCandidate(
        candidate_id=str(item.get("candidate_id") or _new_local_id("legacy-candidate")),
        display_name=display_name,
        avatar_cache_path=(str(item["avatar_cache_path"]) if item.get("avatar_cache_path") else None),
        avatar_status=str(item.get("avatar_status", "missing")),
        discovered_at=str(item.get("discovered_at", scanned_at)),
        match_status=match_status,
        configured_target_id=(str(item["configured_target_id"]) if item.get("configured_target_id") else None),
        configured_enabled=(bool(item["configured_enabled"]) if item.get("configured_enabled") is not None else None),
        avatar_cache_key=(str(item["avatar_cache_key"]) if item.get("avatar_cache_key") else None),
        avatar_updated_at=(str(item["avatar_updated_at"]) if item.get("avatar_updated_at") else None),
        first_discovered_at=first_discovered_at,
        last_seen_at=str(item.get("last_seen_at", scanned_at)),
        last_scan_id=(str(item["last_scan_id"]) if item.get("last_scan_id") else None),
        presence_status=str(item.get("presence_status", "current")),
    )


def load_discovered_friends(path: Path) -> FriendDiscoveryResult | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_scanned_at = payload.get("scanned_at")
        scanned_at = str(raw_scanned_at) if raw_scanned_at else None
        candidates = [_candidate_from_payload(item, scanned_at or "") for item in payload["candidates"]]
        last_result = payload.get("last_result", {})
        return FriendDiscoveryResult(
            scanned_at,
            candidates,
            path,
            scan_id=str(payload["scan_id"]) if payload.get("scan_id") else None,
            last_result=last_result if isinstance(last_result, dict) else {},
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def is_discovery_stale(scanned_at: str | None, now: datetime | None = None) -> bool:
    if not scanned_at:
        return True
    try:
        scanned = datetime.fromisoformat(scanned_at)
    except ValueError:
        return True
    current = now or datetime.now()
    if scanned.tzinfo is not None and current.tzinfo is None:
        current = current.replace(tzinfo=scanned.tzinfo)
    return current - scanned > DISCOVERY_CACHE_TTL


def _write_discovery_payload(path: Path, payload: dict[str, object]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    json.loads(serialized)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}-{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(serialized, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def record_discovery_failure(
    path: Path,
    error: str,
    now: Callable[[], datetime] | None = None,
) -> FriendDiscoveryResult:
    previous = load_discovered_friends(path)
    finished_at = (now or datetime.now)().isoformat(timespec="seconds")
    candidates = previous.candidates if previous else []
    scanned_at = previous.scanned_at if previous else None
    scan_id = previous.scan_id if previous else None
    last_result: dict[str, object] = {
        "status": "failed",
        "finished_at": finished_at,
        "error": error,
    }
    _write_discovery_payload(
        path,
        {
            "version": 2,
            "scanned_at": scanned_at,
            "scan_id": scan_id,
            "last_result": last_result,
            "candidates": [asdict(candidate) for candidate in candidates],
        },
    )
    return FriendDiscoveryResult(scanned_at, candidates, path, scan_id=scan_id, last_result=last_result)
