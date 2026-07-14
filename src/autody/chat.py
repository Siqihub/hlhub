from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from autody.runtime import configure_runtime


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
            '[data-e2e="conversation-item"]',
            "text=安全验证",
        )


@dataclass(frozen=True)
class ConfirmationSelectors:
    outgoing_message_text: str

    @classmethod
    def test_defaults(cls):
        return cls('[data-e2e="message-text"]')


class DeliveryStatus(str, Enum):
    CONFIRMED = "confirmed"
    RETRY_CONFIRMED = "retry_confirmed"
    SEND_FAILED = "send_failed"
    CONFIRMATION_FAILED = "confirmation_failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class DeliveryResult:
    status: DeliveryStatus
    send_attempts: int = 0
    confirmation_attempts: int = 0
    screenshot_path: Path | None = None
    error: str | None = None

    @property
    def successful(self) -> bool:
        return self.status in {DeliveryStatus.CONFIRMED, DeliveryStatus.RETRY_CONFIRMED}


# Centralized selectors based on the current douyin.com/chat page and the upstream
# DouYinSparkFlow dev branch. Adjust only this object when the page changes.
DOUYIN_SELECTORS = ChatSelectors(
    conversation=".conversationConversationItemwrapper",
    conversation_name=".conversationConversationItemtitle",
    conversation_list=".conversationConversationListwrapper",
    header_name=".RightPanelHeadertitle",
    input=".messageEditorimChatEditorContainer",
    login_marker=".conversationConversationListwrapper",
    verification_marker="text=/安全验证|扫码登录|登录后即可聊天/",
)

# Delivery confirmation selectors are deliberately isolated from navigation and
# editor selectors. A Douyin page change here must not alter friend search/send.
DOUYIN_CONFIRMATION_SELECTORS = ConfirmationSelectors(
    outgoing_message_text=".componentsRightPanelwrapper .MessageBoxContentactiveClickArea .MessageItemTextisFromMe .TextMessageTextpureText"
)


def normalize_message_text(value: str) -> str:
    return " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split())


class DouyinChat:
    def __init__(
        self,
        page: Page,
        selectors: ChatSelectors,
        artifact_dir: Path,
        confirmation_selectors: ConfirmationSelectors | None = None,
        confirmation_delay_ms: int = 2_000,
        confirmation_retries: int = 2,
        friend_search_timeout_ms: int = 30_000,
    ):
        self.page = page
        self.selectors = selectors
        self.artifact_dir = artifact_dir
        self.confirmation_selectors = confirmation_selectors or (
            ConfirmationSelectors.test_defaults()
            if selectors.login_marker.startswith('[data-e2e=')
            else DOUYIN_CONFIRMATION_SELECTORS
        )
        self.confirmation_delay_ms = confirmation_delay_ms
        self.confirmation_retries = confirmation_retries
        self.friend_search_timeout_ms = friend_search_timeout_ms

    def _latest_outgoing_text(self) -> str | None:
        messages = self.page.locator(self.confirmation_selectors.outgoing_message_text)
        if messages.count() == 0:
            return None
        # Douyin renders the message list in reverse DOM order. Selecting by the
        # largest visual bottom coordinate works for both normal and reversed
        # lists and therefore reflects the latest visible outgoing bubble.
        return messages.evaluate_all(
            """elements => elements
                .map(element => ({
                    text: element.innerText || element.textContent || '',
                    bottom: element.getBoundingClientRect().bottom
                }))
                .sort((left, right) => right.bottom - left.bottom)[0]?.text || null"""
        )

    def _latest_matches(self, message: str) -> bool:
        latest = self._latest_outgoing_text()
        return latest is not None and normalize_message_text(latest) == normalize_message_text(message)

    def _confirm_delivery(self, message: str) -> tuple[DeliveryStatus | None, int]:
        for attempt in range(1, self.confirmation_retries + 2):
            if self.confirmation_delay_ms:
                self.page.wait_for_timeout(self.confirmation_delay_ms)
            if self._latest_matches(message):
                status = DeliveryStatus.CONFIRMED if attempt == 1 else DeliveryStatus.RETRY_CONFIRMED
                return status, attempt
        return None, self.confirmation_retries + 1

    def _find_conversation(self, target: str):
        conversations = self.page.locator(self.selectors.conversation)
        names = self.page.locator(
            self.selectors.conversation_name,
            has_text=re.compile(rf"^{re.escape(target)}$"),
        )
        matches = conversations.filter(has=names)
        scrollable = self.page.locator(self.selectors.conversation_list)
        if scrollable.count():
            scrollable.first.evaluate("el => el.scrollTop = 0")
        deadline = time.monotonic() + self.friend_search_timeout_ms / 1000
        for _ in range(50):
            count = matches.count()
            if count:
                return matches, count
            if not scrollable.count():
                break
            position = scrollable.first.evaluate(
                """el => ({
                    before: el.scrollTop,
                    maximum: Math.max(0, el.scrollHeight - el.clientHeight),
                    step: Math.max(200, Math.floor(el.clientHeight * 0.7))
                })"""
            )
            if position["before"] >= position["maximum"]:
                break
            if time.monotonic() >= deadline:
                break
            scrollable.first.evaluate(
                "(el, step) => { el.scrollTop += step; el.dispatchEvent(new Event('scroll')); }",
                position["step"],
            )
            self.page.wait_for_timeout(250)
        return matches, matches.count()

    def send(self, target: str, message: str) -> DeliveryResult:
        try:
            matches, count = self._find_conversation(target)
            if count == 0:
                raise RuntimeError(f"target not found: {target}")
            if count > 1:
                raise RuntimeError(f"ambiguous target: {target}")
            matches.first.click()
            header = self.page.locator(self.selectors.header_name).filter(
                has_text=re.compile(rf"^{re.escape(target)}$")
            )
            header.first.wait_for(state="visible")
            if self._latest_matches(message):
                return DeliveryResult(
                    DeliveryStatus.CONFIRMED,
                    send_attempts=0,
                    confirmation_attempts=1,
                )
            editor_container = self.page.locator(self.selectors.input)
            editor_container.wait_for(state="visible")
            editable_child = editor_container.locator(
                "[contenteditable], textarea, input"
            )
            editor = editable_child.last if editable_child.count() else editor_container
            editor.fill(message)
            editor.press("Enter")
            status, attempts = self._confirm_delivery(message)
            if status:
                return DeliveryResult(status, send_attempts=1, confirmation_attempts=attempts)
            screenshot = self.screenshot("confirmation-failed")
            return DeliveryResult(
                DeliveryStatus.CONFIRMATION_FAILED,
                send_attempts=1,
                confirmation_attempts=attempts,
                screenshot_path=screenshot,
                error="latest outgoing message did not match the final sent message",
            )
        except RuntimeError as exc:
            screenshot = self.screenshot("send-error")
            return DeliveryResult(
                DeliveryStatus.SEND_FAILED,
                send_attempts=1,
                screenshot_path=screenshot,
                error=str(exc),
            )
        except PlaywrightTimeoutError as exc:
            screenshot = self.screenshot("page-changed")
            return DeliveryResult(
                DeliveryStatus.BLOCKED,
                screenshot_path=screenshot,
                error="Douyin chat page structure changed or timed out",
            )

    def screenshot(self, label: str) -> Path:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        safe_label = re.sub(r"[^a-zA-Z0-9_-]", "-", label)
        path = self.artifact_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{safe_label}.png"
        self.page.screenshot(path=path, full_page=True)
        return path


def _runtime_home(profile_dir: Path, home: Path | None) -> Path:
    if home is not None:
        return home
    resolved = profile_dir.resolve()
    return resolved.parent.parent if resolved.parent.name == "data" else resolved.parent


def login(
    profile_dir: Path,
    timeout_ms: int = 300_000,
    home: Path | None = None,
) -> None:
    configure_runtime(_runtime_home(profile_dir, home))
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
    home: Path | None = None,
):
    configure_runtime(_runtime_home(profile_dir, home))
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
                DouyinChat(page, DOUYIN_SELECTORS, artifact_dir, DOUYIN_CONFIRMATION_SELECTORS).screenshot("authentication")
            raise AuthenticationError("login expired or security verification required")
        try:
            page.locator(DOUYIN_SELECTORS.login_marker).wait_for()
        except PlaywrightTimeoutError as exc:
            if artifact_dir:
                DouyinChat(page, DOUYIN_SELECTORS, artifact_dir, DOUYIN_CONFIRMATION_SELECTORS).screenshot("authentication")
            raise AuthenticationError("Douyin login is unavailable; run autody login") from exc
        yield page
    finally:
        context.close()
        playwright.stop()
