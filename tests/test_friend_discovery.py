from datetime import datetime
import json
from pathlib import Path

from autody.chat import ChatSelectors
from autody.config import AppConfig, Target
from autody.friend_discovery import (
    ScanProgress,
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
    def __init__(self, content: bytes | None, source: str | None = None):
        self.content = content
        self.source = source

    @property
    def first(self):
        return self

    def screenshot(self, path: str):
        if self.content is None:
            raise RuntimeError("avatar unavailable")
        Path(path).write_bytes(self.content)

    def get_attribute(self, attribute: str):
        return self.source if attribute == "src" else None


class FakeConversationItem:
    def __init__(
        self,
        selectors: ChatSelectors,
        name: str,
        avatar: bytes | None,
        row_id: str | None = None,
        avatar_source: str | None = None,
    ):
        self.selectors = selectors
        self.name = name
        self.avatar = avatar
        self.row_id = row_id
        self.avatar_source = avatar_source

    def get_attribute(self, attribute: str):
        if attribute in {"data-conversation-id", "data-id", "data-key"}:
            return self.row_id
        return None

    def inner_text(self):
        return self.name

    def locator(self, selector: str):
        if selector == self.selectors.conversation_name:
            return FakeTextLocator(self.name)
        if selector == "img":
            return FakeAvatarLocator(self.avatar, self.avatar_source)
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


def test_duplicate_nickname_rows_keep_stable_ids_and_avatars_after_reorder(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    output = tmp_path / "data" / "discovered_friends.json"
    cache = tmp_path / "data" / "avatar-cache"
    first = discover_friends(
        AppConfig(),
        FakePage(
            selectors,
            [[
                FakeConversationItem(selectors, "同名", b"avatar-a", "conversation-a"),
                FakeConversationItem(selectors, "同名", b"avatar-b", "conversation-b"),
            ]],
        ),
        selectors,
        output,
        avatar_cache_dir=cache,
        now=lambda: datetime(2026, 7, 4, 8, 0, 0),
    )
    first_ids = [item.candidate_id for item in first.candidates]

    second = discover_friends(
        AppConfig(),
        FakePage(
            selectors,
            [[
                FakeConversationItem(selectors, "同名", b"avatar-b-new", "conversation-b"),
                FakeConversationItem(selectors, "同名", b"avatar-a-new", "conversation-a"),
            ]],
        ),
        selectors,
        output,
        avatar_cache_dir=cache,
        force_avatar_refresh=True,
        now=lambda: datetime(2026, 7, 5, 8, 0, 0),
    )
    assert len(set(first_ids)) == 2
    assert [item.candidate_id for item in second.candidates] == list(reversed(first_ids))
    assert (cache / f"{second.candidates[0].avatar_cache_key}.png").read_bytes() == b"avatar-b-new"
    assert (cache / f"{second.candidates[1].avatar_cache_key}.png").read_bytes() == b"avatar-a-new"


def test_avatar_source_identity_is_preferred_when_rows_lack_conversation_ids(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    output = tmp_path / "data" / "discovered_friends.json"
    first = discover_friends(
        AppConfig(),
        FakePage(
            selectors,
            [[
                FakeConversationItem(selectors, "同名", b"avatar-a", avatar_source="https://avatar/a"),
                FakeConversationItem(selectors, "同名", b"avatar-b", avatar_source="https://avatar/b"),
            ]],
        ),
        selectors,
        output,
    )
    second = discover_friends(
        AppConfig(),
        FakePage(
            selectors,
            [[
                FakeConversationItem(selectors, "同名", b"avatar-b-new", avatar_source="https://avatar/b"),
                FakeConversationItem(selectors, "同名", b"avatar-a-new", avatar_source="https://avatar/a"),
            ]],
        ),
        selectors,
        output,
        force_avatar_refresh=True,
    )

    assert [candidate.candidate_id for candidate in second.candidates] == list(
        reversed([candidate.candidate_id for candidate in first.candidates])
    )
    assert {candidate.identity_source for candidate in second.candidates} == {"avatar_source"}


def test_avatar_url_query_changes_keep_candidate_and_target_ids_stable(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    output = tmp_path / "data" / "discovered_friends.json"
    config = AppConfig(targets=[Target(name="小明", stable_id="target-permanent")])
    first = discover_friends(
        config,
        FakePage(selectors, [[FakeConversationItem(selectors, "小明", b"old", avatar_source="https://cdn/avatar/a.png?x-expires=1&x-signature=old")]]),
        selectors,
        output,
    )
    original_candidate = first.candidates[0].candidate_id
    original_target = config.targets[0].stable_id
    second = discover_friends(
        config,
        FakePage(selectors, [[FakeConversationItem(selectors, "小明", b"new", avatar_source="https://cdn/avatar/a.png?x-expires=2&x-signature=new")]]),
        selectors,
        output,
        force_avatar_refresh=True,
    )

    assert second.candidates[0].candidate_id == original_candidate
    assert second.candidates[0].configured_target_id == original_target
    assert config.targets[0].stable_id == original_target
    assert config.targets[0].candidate_id == original_candidate


def test_deadline_saves_partial_scan_with_a_clear_status(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    output = tmp_path / "data" / "discovered_friends.json"
    ticks = iter([0.0, 0.0, 0.0, 2.0])

    result = discover_friends(
        AppConfig(),
        FakePage(selectors, [[FakeConversationItem(selectors, "小明", b"avatar")]]),
        selectors,
        output,
        overall_timeout_ms=1,
        monotonic=lambda: next(ticks),
    )

    assert result.last_result["status"] == "partial_timeout"
    assert result.last_result["partial"] is True
    assert load_discovered_friends(output) is not None


def test_avatar_capture_failure_does_not_block_later_rows(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()

    class SlowAvatar(FakeAvatarLocator):
        def screenshot(self, path: str, timeout=None):
            raise TimeoutError(f"timed out after {timeout}")

    class SlowItem(FakeConversationItem):
        def locator(self, selector: str):
            if selector == "img":
                return SlowAvatar(self.avatar, self.avatar_source)
            return super().locator(selector)

    result = discover_friends(
        AppConfig(),
        FakePage(selectors, [[
            SlowItem(selectors, "慢头像", b"slow", "slow-row"),
            FakeConversationItem(selectors, "正常头像", b"fast", "fast-row"),
        ]]),
        selectors,
        tmp_path / "data" / "discovered_friends.json",
        avatar_timeout_ms=500,
    )

    assert result.last_result["status"] == "completed_with_avatar_failures"
    assert result.last_result["avatars_failed"] == 1
    assert next(item for item in result.candidates if item.display_name == "正常头像").avatar_status == "cached"


def test_virtual_scan_honors_the_maximum_round_count(tmp_path: Path):
    selectors = ChatSelectors.test_defaults()
    result = discover_friends(
        AppConfig(),
        FakePage(selectors, [
            [FakeConversationItem(selectors, "第一行", b"first", "first-row")],
            [FakeConversationItem(selectors, "第二行", b"second", "second-row")],
        ]),
        selectors,
        tmp_path / "data" / "discovered_friends.json",
        max_scrolls=0,
    )

    assert [candidate.display_name for candidate in result.candidates] == ["第一行"]


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
        FakePage(selectors, [[FakeConversationItem(selectors, "缓存头像", b"first-avatar", "cached-row")]]),
        selectors,
        output,
        avatar_cache_dir=cache,
        now=lambda: current,
    )
    avatar = cache / f"{first.candidates[0].candidate_id}.png"
    second = discover_friends(
        AppConfig(),
        FakePage(selectors, [[FakeConversationItem(selectors, "缓存头像", b"new-avatar", "cached-row")]]),
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
        FakePage(selectors, [[FakeConversationItem(selectors, "免重抓", b"avatar", "fresh-row")]]),
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
        FakePage(selectors, [[CachedItem(selectors, "免重抓", b"unused", "fresh-row")]]),
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


def test_scan_progress_records_the_browser_lock_release_stage(tmp_path: Path):
    ticks = iter([0.0, 1.0, 1.5])
    progress = ScanProgress(
        tmp_path / "data" / "discovered_friends.json",
        monotonic=lambda: next(ticks),
    )

    progress.update("releasing_browser_lock")
    payload = progress.finish("completed")

    assert payload["timings"] == {
        "waiting_browser": 1.0,
        "releasing_browser_lock": 0.5,
    }
