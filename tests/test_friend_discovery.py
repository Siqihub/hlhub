from datetime import datetime
import json
from pathlib import Path

from autody.chat import ChatSelectors
from autody.config import AppConfig, Target
from autody.friend_discovery import (
    discover_friends,
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
