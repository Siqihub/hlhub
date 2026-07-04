from datetime import datetime
import json
from pathlib import Path

from autody.chat import ChatSelectors
from autody.config import AppConfig, Target
from autody.friend_discovery import discover_friends, scan_friend_names


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


class FakePage:
    def __init__(self, selectors: ChatSelectors):
        self.position = 0
        self.selectors = selectors
        self.waits = []

    def locator(self, selector):
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
