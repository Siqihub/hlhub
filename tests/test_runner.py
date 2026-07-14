from datetime import date
import json
from pathlib import Path

from autody.config import AppConfig, Target
from autody.chat import DeliveryResult, DeliveryStatus, FatalChatError
from autody.runner import RunStatus, run_daily


class FakeChat:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.sent = []

    def send(self, target, message):
        if target in self.failures:
            raise RuntimeError("network timeout")
        self.sent.append((target, message))


def make_config(tmp_path: Path):
    messages = tmp_path / "messages.txt"
    messages.write_text("早安\n晚安\n", encoding="utf-8")
    return AppConfig(
        targets=[Target(name="小明"), Target(name="小红")],
        messages_file=messages,
        state_file=tmp_path / "state.json",
        lock_file=tmp_path / "run.lock",
        artifact_dir=tmp_path / "artifacts",
        retry_count=1,
    )


def test_second_run_same_day_sends_nothing(tmp_path: Path):
    config, chat = make_config(tmp_path), FakeChat()
    first = run_daily(config, chat, date(2026, 6, 18))
    second = run_daily(config, chat, date(2026, 6, 18))
    assert first.status is RunStatus.COMPLETED
    assert first.sent_count == 2
    assert first.skipped_count == 0
    assert second.status is RunStatus.ALREADY_DONE
    assert second.sent_count == 0
    assert second.skipped_count == 2
    assert len(chat.sent) == 2
    assert len({message for _, message in chat.sent}) == 1
    assert chat.sent[0][1].endswith(" —— gpt小助手")


def test_retry_only_processes_failed_target_with_same_message(tmp_path: Path):
    config, first = make_config(tmp_path), FakeChat({"小红"})
    first_result = run_daily(config, first, date(2026, 6, 18))
    assert first_result.status is RunStatus.PARTIAL_FAILED
    assert first_result.sent_count == 1
    assert first_result.failed_count == 1
    second = FakeChat()
    second_result = run_daily(config, second, date(2026, 6, 18))
    assert second_result.status is RunStatus.COMPLETED
    assert second_result.sent_count == 1
    assert second_result.skipped_count == 1
    assert [target for target, _ in second.sent] == ["小红"]
    assert second.sent[0][1] == first.sent[0][1]


def test_fatal_chat_error_returns_blocked_result(tmp_path: Path):
    config = make_config(tmp_path)

    class BlockedChat:
        def send(self, _target, _message):
            raise FatalChatError("需要安全验证")

    result = run_daily(config, BlockedChat(), date(2026, 6, 18))

    assert result.status is RunStatus.BLOCKED
    assert result.sent_count == 0
    assert result.error == "需要安全验证"


def test_duplicate_enabled_names_are_blocked_without_sending_ambiguous_targets(tmp_path: Path):
    config = make_config(tmp_path)
    config.targets = [Target(name="同名"), Target(name="同名"), Target(name="唯一")]
    chat = FakeChat()

    result = run_daily(config, chat, date(2026, 7, 14))

    assert result.status is RunStatus.BLOCKED_AMBIGUOUS_TARGET
    assert [target for target, _ in chat.sent] == ["唯一"]
    state = json.loads(config.state_file.read_text(encoding="utf-8"))
    assert state["daily"]["2026-07-14"]["failures"]["同名"] == "blocked_ambiguous_target"


def test_unique_names_continue_to_send_normally(tmp_path: Path):
    config, chat = make_config(tmp_path), FakeChat()

    result = run_daily(config, chat, date(2026, 7, 14))

    assert result.status is RunStatus.COMPLETED
    assert [target for target, _ in chat.sent] == ["小明", "小红"]


def test_suffix_is_send_only_and_state_tracks_base_message(tmp_path: Path):
    config, chat = make_config(tmp_path), FakeChat()
    original = config.messages_file.read_text(encoding="utf-8")

    run_daily(config, chat, date(2026, 7, 4))

    state = json.loads(config.state_file.read_text(encoding="utf-8"))
    base = state["daily"]["2026-07-04"]["message"]
    assert base in {"早安", "晚安"}
    assert chat.sent[0][1] == f"{base} —— gpt小助手"
    assert config.messages_file.read_text(encoding="utf-8") == original


def test_confirmation_failure_is_not_recorded_as_success_and_retry_does_not_duplicate(tmp_path: Path):
    config = make_config(tmp_path)
    config.retry_count = 2
    config.targets = [Target(name="小明")]

    class UnconfirmedChat:
        def __init__(self):
            self.calls = 0

        def send(self, _target, _message):
            self.calls += 1
            return DeliveryResult(DeliveryStatus.CONFIRMATION_FAILED, confirmation_attempts=3, error="not visible")

    first_chat = UnconfirmedChat()
    first = run_daily(config, first_chat, date(2026, 7, 13))

    class ExistingBubbleChat:
        def __init__(self):
            self.calls = 0

        def send(self, _target, _message):
            self.calls += 1
            return DeliveryResult(DeliveryStatus.CONFIRMED, send_attempts=0)

    second_chat = ExistingBubbleChat()
    second = run_daily(config, second_chat, date(2026, 7, 13))

    assert first.status is RunStatus.PARTIAL_FAILED
    assert first_chat.calls == 1
    assert second.status is RunStatus.COMPLETED
    assert second_chat.calls == 1


def test_structured_history_contains_ids_not_friend_names(tmp_path: Path):
    config, chat = make_config(tmp_path), FakeChat()

    result = run_daily(config, chat, date(2026, 7, 13), trigger_source="scheduled")

    lines = (config.state_file.parent / "history" / "task-runs.jsonl").read_text(encoding="utf-8")
    assert result.run_id in lines
    assert '"trigger_source": "scheduled"' in lines
    assert "小明" not in lines
    assert "小红" not in lines
