import random
from pathlib import Path

import pytest

from autody.messages import MessageRotation, read_messages
from autody.state import RotationState


def test_read_messages_ignores_blank_lines(tmp_path: Path):
    path = tmp_path / "messages.txt"
    path.write_text("早安\n\n今天也要开心\n", encoding="utf-8")
    assert read_messages(path) == ["早安", "今天也要开心"]


def test_empty_library_is_rejected(tmp_path: Path):
    path = tmp_path / "messages.txt"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        read_messages(path)


def test_rotation_uses_every_message_before_repeating():
    rotation = MessageRotation(random.Random(7))
    state = RotationState()
    values = []
    for _ in range(3):
        value = rotation.peek(["a", "b", "c"], state)
        values.append(value)
        rotation.consume(value, state)
    assert set(values) == {"a", "b", "c"}
    assert rotation.peek(["a", "b", "c"], state) in {"a", "b", "c"}


def test_rotation_recovers_when_library_changes():
    rotation = MessageRotation(random.Random(1))
    state = RotationState(order=["removed", "keep"], consumed=["done"])
    assert rotation.peek(["keep", "new"], state) in {"keep", "new"}
    assert "removed" not in state.order
    assert "done" not in state.consumed
