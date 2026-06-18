from pathlib import Path
from dataclasses import replace

import pytest

from autody.chat import ChatSelectors, DouyinChat


@pytest.fixture
def fake_chat(page, tmp_path: Path):
    page.goto((Path("tests/fixtures/chat.html").resolve()).as_uri())
    return DouyinChat(page, ChatSelectors.test_defaults(), tmp_path)


def test_send_confirms_exact_target_and_message(page, fake_chat):
    fake_chat.send("小明", "早安")
    assert page.locator('[data-e2e="message-text"]', has_text="早安").count() == 1


def test_existing_message_is_not_sent_twice(page, fake_chat):
    page.locator('[data-e2e="message-list"]').evaluate(
        "(el) => { const p=document.createElement('p'); p.dataset.e2e='message-text'; p.textContent='早安'; el.append(p); }"
    )
    fake_chat.send("小明", "早安")
    assert page.locator('[data-e2e="message-text"]', has_text="早安").count() == 1


def test_duplicate_names_are_rejected(page, fake_chat):
    page.locator('[data-e2e="conversation-item"]').evaluate(
        "el => el.parentNode.appendChild(el.cloneNode(true))"
    )
    with pytest.raises(RuntimeError, match="ambiguous"):
        fake_chat.send("小明", "早安")


def test_header_mismatch_is_rejected(page, fake_chat):
    page.locator('[data-e2e="chat-header-name"]').evaluate("el => el.textContent='小红'")
    with pytest.raises(RuntimeError, match="header mismatch"):
        fake_chat.send("小明", "早安")


def test_semantic_text_fallback_handles_unknown_header_and_message_classes(page, tmp_path):
    page.goto((Path("tests/fixtures/chat.html").resolve()).as_uri())
    selectors = replace(
        ChatSelectors.test_defaults(),
        header_name=".unknown-header-class",
        message_text=".unknown-message-class",
    )
    chat = DouyinChat(page, selectors, tmp_path)
    chat.send("小明", "早安")
    assert page.get_by_text("早安", exact=True).count() == 1
