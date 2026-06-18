from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import re
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


CHAT_URL = "https://www.douyin.com/chat"


class FatalChatError(RuntimeError):
    """A failure for which sending to further targets is unsafe."""


class AuthenticationError(FatalChatError):
    pass


class PageChangedError(FatalChatError):
    pass


@dataclass(frozen=True)
class ChatSelectors:
    conversation: str
    conversation_name: str
    conversation_list: str
    header_name: str
    input: str
    message_text: str
    login_marker: str
    verification_marker: str

    @classmethod
    def test_defaults(cls):
        return cls(
            '[data-e2e="conversation-item"]',
            '[data-e2e="conversation-name"]',
            '[data-e2e="chat-app"]',
            '[data-e2e="chat-header-name"]',
            '[data-e2e="chat-input"]',
            '[data-e2e="message-text"]',
            '[data-e2e="conversation-item"]',
            "text=安全验证",
        )


# Centralized selectors based on the current douyin.com/chat page and the upstream
# DouYinSparkFlow dev branch. Adjust only this object when the page changes.
DOUYIN_SELECTORS = ChatSelectors(
    conversation=".conversationConversationItemwrapper",
    conversation_name=".conversationConversationItemtitle",
    conversation_list=".conversationConversationListwrapper",
    header_name=".RightPanelHeadertitle",
    input=".messageEditorimChatEditorContainer",
    message_text=".componentsRightPanelwrapper .MessageBoxContentactiveClickArea .MessageItemTextisFromMe .TextMessageTextpureText",
    login_marker=".conversationConversationListwrapper",
    verification_marker="text=/安全验证|扫码登录|登录后即可聊天/",
)


class DouyinChat:
    def __init__(
        self,
        page: Page,
        selectors: ChatSelectors,
        artifact_dir: Path,
        confirmation_delay_ms: int = 2_000,
    ):
        self.page = page
        self.selectors = selectors
        self.artifact_dir = artifact_dir
        self.confirmation_delay_ms = confirmation_delay_ms

    def _message_locator(self, message: str):
        return self.page.locator(self.selectors.message_text).filter(
            has_text=re.compile(rf"^{re.escape(message)}$")
        )

    def _message_exists(self, message: str) -> bool:
        return self._message_locator(message).count() > 0

    def send(self, target: str, message: str) -> None:
        try:
            matches = self.page.locator(self.selectors.conversation).filter(
                has=self.page.locator(
                    self.selectors.conversation_name,
                    has_text=re.compile(rf"^{re.escape(target)}$"),
                )
            )
            count = matches.count()
            if count == 0:
                raise RuntimeError(f"target not found: {target}")
            if count > 1:
                raise RuntimeError(f"ambiguous target: {target}")
            matches.first.click()
            header = self.page.locator(self.selectors.header_name).filter(
                has_text=re.compile(rf"^{re.escape(target)}$")
            )
            header.first.wait_for(state="visible")
            if self._message_exists(message):
                return
            editor_container = self.page.locator(self.selectors.input)
            editor_container.wait_for(state="visible")
            editable_child = editor_container.locator(
                "[contenteditable], textarea, input"
            )
            editor = editable_child.last if editable_child.count() else editor_container
            editor.fill(message)
            editor.press("Enter")
            self._message_locator(message).last.wait_for()
            self.page.wait_for_timeout(self.confirmation_delay_ms)
            if not self._message_exists(message):
                raise RuntimeError("sent message did not persist")
        except RuntimeError:
            self.screenshot("send-error")
            raise
        except PlaywrightTimeoutError as exc:
            self.screenshot("page-changed")
            raise PageChangedError("Douyin chat page structure changed or timed out") from exc

    def screenshot(self, label: str) -> Path:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        safe_label = re.sub(r"[^a-zA-Z0-9_-]", "-", label)
        path = self.artifact_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{safe_label}.png"
        self.page.screenshot(path=path, full_page=True)
        return path


def login(profile_dir: Path, timeout_ms: int = 300_000) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), headless=False
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(CHAT_URL)
            page.locator(DOUYIN_SELECTORS.login_marker).wait_for(timeout=timeout_ms)
        finally:
            context.close()


@contextmanager
def open_chat(
    profile_dir: Path,
    timeout_ms: int = 30_000,
    headless: bool = True,
    artifact_dir: Path | None = None,
):
    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        str(profile_dir), headless=headless
    )
    context.set_default_timeout(timeout_ms)
    page = context.pages[0] if context.pages else context.new_page()
    try:
        page.goto(CHAT_URL)
        if page.locator(DOUYIN_SELECTORS.verification_marker).count():
            if artifact_dir:
                DouyinChat(page, DOUYIN_SELECTORS, artifact_dir).screenshot("authentication")
            raise AuthenticationError("login expired or security verification required")
        try:
            page.locator(DOUYIN_SELECTORS.login_marker).wait_for()
        except PlaywrightTimeoutError as exc:
            if artifact_dir:
                DouyinChat(page, DOUYIN_SELECTORS, artifact_dir).screenshot("authentication")
            raise AuthenticationError("Douyin login is unavailable; run autody login") from exc
        yield page
    finally:
        context.close()
        playwright.stop()
