from datetime import date
from pathlib import Path

from autody.config import AppConfig, Target
from autody.runner import run_daily


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
    assert run_daily(config, chat, date(2026, 6, 18)) is True
    assert run_daily(config, chat, date(2026, 6, 18)) is True
    assert len(chat.sent) == 2
    assert len({message for _, message in chat.sent}) == 1


def test_retry_only_processes_failed_target_with_same_message(tmp_path: Path):
    config, first = make_config(tmp_path), FakeChat({"小红"})
    assert run_daily(config, first, date(2026, 6, 18)) is False
    second = FakeChat()
    assert run_daily(config, second, date(2026, 6, 18)) is True
    assert [target for target, _ in second.sent] == ["小红"]
    assert second.sent[0][1] == first.sent[0][1]
