from pathlib import Path
from dataclasses import replace

import pytest

from autody.chat import ChatSelectors, DOUYIN_SELECTORS, DouyinChat, PageChangedError


@pytest.fixture
def fake_chat(page, tmp_path: Path):
    page.goto((Path("tests/fixtures/chat.html").resolve()).as_uri())
    return DouyinChat(
        page, ChatSelectors.test_defaults(), tmp_path, confirmation_delay_ms=0
    )


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
    page.set_default_timeout(300)
    page.locator('[data-e2e="chat-header-name"]').evaluate("el => el.textContent='小红'")
    with pytest.raises(PageChangedError):
        fake_chat.send("小明", "早安")


def test_send_waits_for_header_to_switch_to_target(page, fake_chat):
    page.locator('[data-e2e="chat-header-name"]').evaluate(
        "el => { el.textContent='小红'; setTimeout(() => el.textContent='小明', 100); }"
    )
    fake_chat.send("小明", "早安")
    assert page.locator('[data-e2e="message-text"]', has_text="早安").count() == 1


def test_production_selectors_scope_current_right_panel():
    assert DOUYIN_SELECTORS.header_name == ".RightPanelHeadertitle"
    assert DOUYIN_SELECTORS.message_text.startswith(
        ".componentsRightPanelwrapper .MessageBoxContentactiveClickArea"
    )


def test_conversation_preview_is_not_accepted_as_sent_message(page, tmp_path):
    page.goto((Path("tests/fixtures/chat.html").resolve()).as_uri())
    page.set_default_timeout(300)
    page.locator("body").evaluate(
        "el => { const preview=document.createElement('pre'); preview.textContent='早安'; el.append(preview); }"
    )
    chat = DouyinChat(
        page, ChatSelectors.test_defaults(), tmp_path, confirmation_delay_ms=0
    )
    chat.send("小明", "早安")
    assert page.locator('[data-e2e="message-text"]', has_text="早安").count() == 1


def test_editor_container_uses_contenteditable_descendant(page, tmp_path):
    page.goto((Path("tests/fixtures/chat.html").resolve()).as_uri())
    page.locator('[data-e2e="chat-input"]').evaluate(
        "el => { const wrapper=document.createElement('div'); wrapper.className='editor-wrapper'; el.parentNode.insertBefore(wrapper, el); wrapper.append(el); }"
    )
    selectors = replace(ChatSelectors.test_defaults(), input=".editor-wrapper")
    chat = DouyinChat(page, selectors, tmp_path, confirmation_delay_ms=0)
    chat.send("小明", "早安")
    assert page.get_by_text("早安", exact=True).count() == 1


def test_send_rejects_optimistic_bubble_that_disappears(page, tmp_path):
    page.goto((Path("tests/fixtures/chat.html").resolve()).as_uri())
    page.locator('[data-e2e="chat-input"]').evaluate(
        "el => el.addEventListener('keydown', event => { if (event.key === 'Enter') setTimeout(() => document.querySelector('.MessageItemTextisFromMe')?.remove(), 50); })"
    )
    chat = DouyinChat(
        page, ChatSelectors.test_defaults(), tmp_path, confirmation_delay_ms=150
    )
    with pytest.raises(RuntimeError, match="did not persist"):
        chat.send("小明", "早安")


def test_find_target_scrolls_conversation_list(page, tmp_path):
    page.goto((Path("tests/fixtures/chat.html").resolve()).as_uri())
    page.locator('[data-e2e="conversation-item"]').evaluate("el => el.remove()")
    page.locator('[data-e2e="chat-app"]').evaluate(
        """el => {
          el.style.height='100px'; el.style.overflow='auto';
          const spacer=document.createElement('div'); spacer.style.height='500px'; el.prepend(spacer);
          el.addEventListener('scroll', () => {
            if (el.querySelector('[data-late-target]')) return;
            const button=document.createElement('button');
            button.dataset.e2e='conversation-item'; button.dataset.lateTarget='1';
            button.innerHTML='<span data-e2e="conversation-name">小明</span>';
            el.append(button);
          });
        }"""
    )
    chat = DouyinChat(
        page, ChatSelectors.test_defaults(), tmp_path, confirmation_delay_ms=0
    )
    chat.send("小明", "早安")
    assert page.locator('[data-e2e="message-text"]', has_text="早安").count() == 1
