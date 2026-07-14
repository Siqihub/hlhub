from datetime import datetime
import json
from pathlib import Path

from autody.chat import ChatSelectors
from autody.config import AppConfig, Target
from autody.friend_discovery import (
    discover_friends,
    is_discovery_stale,
    load_discovered_friends,
    record_discovery_failure,
    refresh_configured_avatars,
    scan_friend_names,
)


class FakeNamesLocator:
    def __init__(self, page):
        self.page = page

    def all_inner_texts(self):
        pages = [
            ["测试好友甲", "测试好友乙", "  测试好友甲  "],
            ["测试好友丙", "测试好友乙"],
            ["测试好友丁", ""],
        ]
        return pages[min(self.page.position, len(pages) - 1)]


class FakeScrollLocator:
    def __init__(self, page):
        self.page = page

    def count(self):
        return 1

    @property
    def first(self):
        return self

    def evaluate(self, expression, *_args):
        if "before" in expression:
            return {
                "before": self.page.position,
                "maximum": 2,
                "step": 1,
            }
        self.page.position += 1


class FakeTextLocator:
    def __init__(self, value: str):
        self.value = value

    def inner_text(self):
        return self.value


class FakeAvatarLocator:
    def __init__(self, content: bytes | None):
        self.content = content

    @property
    def first(self):
        return self

    def screenshot(self, path: str):
        if self.content is None:
            raise RuntimeError("avatar unavailable")
        Path(path).write_bytes(self.content)


class FakeConversationItem:
    def __init__(self, selectors: ChatSelectors, name: str, avatar: bytes | None):
        self.selectors = selectors
        self.name = name
        self.avatar = avatar

    def locator(self, selector: str):
        if selector == self.selectors.conversation_name:
            return FakeTextLocator(self.name)
        if selector == "img":
            return FakeAvatarLocator(self.avatar)
        raise AssertionError(f"unexpected item selector: {selector}")


class FakeConversationLocator:
    def __init__(self, page):
        self.page = page

    def count(self):
        return len(self.page.rows[min(self.page.position, len(self.page.rows) - 1)])

    def nth(self, index: int):
        return self.page.rows[min(self.page.position, len(self.page.rows) - 1)][index]


class FakePage:
    def __init__(self, selectors: ChatSelectors, rows: list[list[FakeConversationItem]] | None = None):
        self.position = 0
        self.selectors = selectors
        self.waits = []
        self.rows = rows or [
            [
                FakeConversationItem(selectors, "测试好友甲", b"avatar-jiang"),
                FakeConversationItem(selectors, "测试好友乙", b"avatar-gege"),
            ],
            [
                FakeConversationItem(selectors, "测试好友丙", b"avatar-ning"),
                FakeConversationItem(selectors, "测试好友乙", b"avatar-gege"),
            ],
            [FakeConversationItem(selectors, "测试好友丁", b"avatar-chen")],
        ]

    def locator(self, selector):
        if selector == self.selectors.conversation:
            return FakeConversationLocator(self)
        if selector == self.selectors.conversation_name:
            return FakeNamesLocator(self)
        if selector == self.selectors.conversation_list:
            return FakeScrollLocator(self)
        raise AssertionError(f"unexpected selector: {selector}")

    def wait_for_timeout(self, delay):
        self.waits.append(delay)


def test_scan_friend_names_scrolls_and_deduplicates():
    selectors = ChatSelectors.test_defaults()
    page = FakePage(selectors)

    names = scan_friend_names(page, selectors, max_scrolls=5)

    assert names == ["测试好友甲", "测试好友乙", "测试好友丙", "测试好友丁"]
    assert page.position == 2
    assert len(page.waits) == 2


def test_discovery_persists_candidates_without_overwriting_config(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    config = AppConfig(targets=[Target(name="测试好友乙")])
    output = tmp_path / "data" / "discovered_friends.json"

    result = discover_friends(
        config,
        FakePage(selectors),
        selectors,
        output,
        now=lambda: datetime(2026, 7, 4, 12, 30, 0),
    )

    assert [target.name for target in config.targets] == ["测试好友乙"]
    assert result.candidates[1].name == "测试好友乙"
    assert result.candidates[1].already_configured is True
    assert result.candidates[0].already_configured is False
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["scanned_at"] == "2026-07-04T12:30:00"
    assert len(saved["candidates"]) == 4


def test_discovery_captures_avatar_and_matches_existing_target(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    config = AppConfig(targets=[Target(name="测试好友乙", enabled=False, stable_id="friend-gege")])
    output = tmp_path / "data" / "discovered_friends.json"
    cache = tmp_path / "data" / "avatar-cache"

    result = discover_friends(
        config,
        FakePage(selectors),
        selectors,
        output,
        avatar_cache_dir=cache,
        now=lambda: datetime(2026, 7, 4, 12, 30, 0),
    )

    candidate = next(item for item in result.candidates if item.display_name == "测试好友乙")
    assert candidate.match_status == "configured"
    assert candidate.configured_target_id == "friend-gege"
    assert candidate.configured_enabled is False
    assert candidate.avatar_status == "cached"
    assert candidate.avatar_cache_path == "friend-gege.png"
    assert (cache / "friend-gege.png").read_bytes() == b"avatar-gege"
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert "avatar_cache_path" in saved["candidates"][1]
    assert "http" not in json.dumps(saved, ensure_ascii=False)


def test_avatar_capture_failure_does_not_fail_discovery(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    page = FakePage(
        selectors,
        [[FakeConversationItem(selectors, "无头像", None)]],
    )

    result = discover_friends(
        AppConfig(),
        page,
        selectors,
        tmp_path / "data" / "discovered_friends.json",
        avatar_cache_dir=tmp_path / "data" / "avatar-cache",
    )

    assert result.candidates[0].avatar_status == "missing"
    assert result.candidates[0].avatar_cache_path is None


def test_duplicate_nickname_does_not_overwrite_configured_avatar(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    config = AppConfig(targets=[Target(name="测试好友乙", stable_id="friend-gege")])
    cache = tmp_path / "data" / "avatar-cache"
    cache.mkdir(parents=True)
    avatar_path = cache / "friend-gege.png"
    avatar_path.write_bytes(b"original")
    page = FakePage(
        selectors,
        [[
            FakeConversationItem(selectors, "测试好友乙", b"first-avatar"),
            FakeConversationItem(selectors, "测试好友乙", b"second-avatar"),
        ]],
    )

    result = refresh_configured_avatars(config, page, selectors, cache)

    assert result.updated == 0
    assert result.ambiguous == 1
    assert config.targets[0].name == "测试好友乙"
    assert config.targets[0].stable_id == "friend-gege"
    assert avatar_path.read_bytes() == b"original"


def test_discovery_preserves_candidate_identity_and_marks_missed_rows_stale(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    output = tmp_path / "data" / "discovered_friends.json"

    first = discover_friends(
        AppConfig(),
        FakePage(selectors, [[FakeConversationItem(selectors, "旧候选", b"old")]]),
        selectors,
        output,
        now=lambda: datetime(2026, 7, 4, 8, 0, 0),
    )
    second = discover_friends(
        AppConfig(),
        FakePage(selectors, [[FakeConversationItem(selectors, "新候选", b"new")]]),
        selectors,
        output,
        now=lambda: datetime(2026, 7, 5, 8, 0, 0),
    )

    previous = next(item for item in second.candidates if item.display_name == "旧候选")
    current = next(item for item in second.candidates if item.display_name == "新候选")
    assert previous.candidate_id == first.candidates[0].candidate_id
    assert previous.presence_status == "stale"
    assert previous.first_discovered_at == "2026-07-04T08:00:00"
    assert current.presence_status == "current"
    assert second.last_result["status"] == "completed"
    assert second.last_result["candidates_found"] == 1


def test_failed_scan_records_failure_without_erasing_previous_candidates(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    output = tmp_path / "data" / "discovered_friends.json"
    discover_friends(
        AppConfig(),
        FakePage(selectors, [[FakeConversationItem(selectors, "保留候选", b"keep")]]),
        selectors,
        output,
        now=lambda: datetime(2026, 7, 4, 8, 0, 0),
    )

    record_discovery_failure(
        output,
        "chat list unavailable",
        now=lambda: datetime(2026, 7, 5, 8, 0, 0),
    )

    cached = load_discovered_friends(output)
    assert cached is not None
    assert [item.display_name for item in cached.candidates] == ["保留候选"]
    assert cached.scanned_at == "2026-07-04T08:00:00"
    assert cached.last_result == {
        "status": "failed",
        "finished_at": "2026-07-05T08:00:00",
        "error": "chat list unavailable",
    }


def test_discovery_cache_freshness_uses_a_24_hour_window():
    now = datetime(2026, 7, 5, 8, 0, 0)

    assert is_discovery_stale("2026-07-04T08:00:00", now) is False
    assert is_discovery_stale("2026-07-04T07:59:59", now) is True
    assert is_discovery_stale("not-a-date", now) is True


def test_fresh_cached_avatar_is_reused_without_overwriting_it(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    output = tmp_path / "data" / "discovered_friends.json"
    cache = tmp_path / "data" / "avatar-cache"
    current = datetime.now()
    first = discover_friends(
        AppConfig(),
        FakePage(selectors, [[FakeConversationItem(selectors, "缓存头像", b"first-avatar")]]),
        selectors,
        output,
        avatar_cache_dir=cache,
        now=lambda: current,
    )
    avatar = cache / f"{first.candidates[0].candidate_id}.png"
    second = discover_friends(
        AppConfig(),
        FakePage(selectors, [[FakeConversationItem(selectors, "缓存头像", b"new-avatar")]]),
        selectors,
        output,
        avatar_cache_dir=cache,
        now=lambda: current,
    )

    assert avatar.read_bytes() == b"first-avatar"
    assert second.last_result["avatars_updated"] == 0
    assert second.last_result["avatars_reused"] == 1


def test_automatic_scan_does_not_recapture_a_fresh_cached_avatar(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    output = tmp_path / "data" / "discovered_friends.json"
    cache = tmp_path / "data" / "avatar-cache"
    current = datetime.now()
    discover_friends(
        AppConfig(),
        FakePage(selectors, [[FakeConversationItem(selectors, "免重抓", b"avatar")]]),
        selectors,
        output,
        avatar_cache_dir=cache,
        now=lambda: current,
    )
    screenshot_calls = []

    class CountingAvatar:
        @property
        def first(self):
            return self

        def screenshot(self, path: str):
            screenshot_calls.append(path)
            Path(path).write_bytes(b"unexpected")

    class CachedItem(FakeConversationItem):
        def locator(self, selector: str):
            if selector == "img":
                return CountingAvatar()
            return super().locator(selector)

    discover_friends(
        AppConfig(),
        FakePage(selectors, [[CachedItem(selectors, "免重抓", b"unused")]]),
        selectors,
        output,
        avatar_cache_dir=cache,
        now=lambda: current,
    )

    assert screenshot_calls == []


def test_configured_target_is_kept_when_a_later_scan_does_not_find_it(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    config = AppConfig(targets=[Target(name="已配置目标")])
    output = tmp_path / "data" / "discovered_friends.json"
    discover_friends(
        config,
        FakePage(selectors, [[FakeConversationItem(selectors, "已配置目标", b"avatar")]]),
        selectors,
        output,
        now=lambda: datetime(2026, 7, 4, 8, 0, 0),
    )
    result = discover_friends(
        config,
        FakePage(selectors, [[]]),
        selectors,
        output,
        now=lambda: datetime(2026, 7, 5, 8, 0, 0),
    )

    candidate = next(item for item in result.candidates if item.display_name == "已配置目标")
    assert [target.name for target in config.targets] == ["已配置目标"]
    assert candidate.match_status == "configured"
    assert candidate.presence_status == "stale"
